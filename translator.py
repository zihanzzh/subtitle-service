import re
import google.generativeai as genai
import os
import time
import random


# time conversion
def time_to_ms(t):
    # Convert HH:MM:SS,mmm to milliseconds
    h, m, s_ms = t.split(":")
    s, ms = s_ms.split(",")
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

# group the subtitle blocks, if <= 50ms, put them into one sentence.
# return a list of sentence groups. Each group contains one or more subtitle blocks.
def group_subtitles(srt_path, time_tolerance_ms=50):
    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines() #read all the lines and store them into list lines

    blocks = []
    i = 0
    while i < len(lines):
        if lines[i].strip().isdigit():
            index = int(lines[i].strip())
            time_range = lines[i+1].strip()
            text_lines = []
            i += 2
            while i < len(lines) and lines[i].strip() != "":
                text_lines.append(lines[i].strip())
                i += 1
            start, end = time_range.split(" --> ")
            blocks.append({
                "index": index,
                "start": start,
                "end": end,
                "lines": text_lines
            })
        i += 1

    # Grouping based on time continuity
    groups = []
    current_group = [blocks[0]]
    for j in range(1, len(blocks)):
        prev = current_group[-1]
        curr = blocks[j]
        prev_end = time_to_ms(prev["end"])
        curr_start = time_to_ms(curr["start"])
        gap = curr_start - prev_end
        # check if they belong to one sentence
        if gap <= time_tolerance_ms:
            current_group.append(curr)
        else:
            groups.append(current_group)
            current_group = [curr]
    # add the last block
    if current_group:
        groups.append(current_group)
    
    return groups    

# Setup Gemini
def load_gemini_api_key(path="gemini_key.txt"):
    with open(path, "r") as f:
        return f.read().strip()

def setup_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("models/gemini-2.0-flash-lite")

# Translate in batches and split back
def translate_groups(groups, model, target_lang="Chinese", batch_size=20):
    # split the total groups into batches of batchsize
    for i in range(0, len(groups), batch_size):
        batch = groups[i : i + batch_size]

        # Combine all blocks in this batch into one big text
        source_texts = []
        for group in batch:
            for block in group:
                source_texts.append(" ".join(block["lines"]))

        full_text = " ".join(source_texts)

        # Send to Gemini
        prompt = (
            f"Translate the following English dialogue into natural, fluent spoken {target_lang}.\n"
            f"Keep the meaning clear, complete, and connected.\n"
            f"If you see a short phrase that starts with 'that', 'which', or 'who', do NOT attach it to the previous sentence — keep it as its own line.\n"
            f"Do not reorder phrases or clauses inside a sentence — each part must stay in its original place.\n"           
            f"Preserve all punctuation marks — including commas, periods, question marks, and exclamation marks — exactly as in the original; do not add, remove, or reorder them.\n"
            f"Always use full-width Chinese commas （，） instead of English commas (,) in the translation. Keep them in exactly the same position.\n"
            f"Use professional, context-appropriate wording for any official terms (for example, legal, sports, or technical jargon) so they match real-world usage in {target_lang}.\n"
            f"Keep names of people or places consistent throughout.\n"
            f"Remove any filler words like 'like', 'uh', 'you know', unless they are needed for natural spoken style.\n"
            f"Return only the final translation as one continuous text, with no added comments or extra formatting.\n\n"
            f"{full_text}"
        ) 
        response = model.generate_content(prompt)
        translated = response.text.strip()

        # Flatten blocks: we know exactly how many blocks there are
        flat_blocks = [block for group in batch for block in group]

        # Split the translated text into exact segment
        split_segments = split_and_assign_translation(flat_blocks, translated)
    
        print(f"Translated batch of {len(flat_blocks)} blocks.")        
        time.sleep(random.uniform(5, 7))

    return groups

# Combined function that splits translation and assigns to blocks with proper shifting when carryover occurs from comma-ending blocks
def split_and_assign_translation(flat_blocks, translated_text):
    # 1. Split only on sentence-ending punctuation
    segments = re.split(r'(……|。|？|！|\.{3}|…)', translated_text)
    segments = ["".join(pair) for pair in zip(segments[::2], segments[1::2])] + segments[len(segments)//2*2:]
    # Remove empty
    segments = [s.strip() for s in segments if s.strip()]

    # 2. Ensure we have enough segments for blocks
    num_blocks = len(flat_blocks)
    num_segments = len(segments)

    while num_segments < num_blocks:
        segments.append(segments[-1] if segments else "")
        num_segments += 1
    
    while num_segments > num_blocks:
        segments[-2] += segments[-1]
        segments.pop()
        num_segments -= 1

    # 3. Assign segments to blocks with carry-over handling
    carry_over = ""
    original_segments = segments[:]  # Keep a copy of original segments
    block_index = 0
    segment_index = 0

    while block_index < len(flat_blocks):
        block = flat_blocks[block_index]
        # Determine what segment to use for this block
        if carry_over:
            # Use carry-over from previous block
            current_segment = carry_over
            carry_over = ""
        else:
            # Use the next available segment
            if segment_index < len(original_segments):
                current_segment = original_segments[segment_index]
                segment_index += 1
            else:
                current_segment = ""

        # Check if this block originally ended with comma
        original_line = " ".join(block["lines"]).strip()
        original_punct = original_line[-1] if original_line else ""

        if original_punct == ",":
            # Handle comma-ending block
            expected_commas = original_line.count(",")
            translated_commas = current_segment.count("，")
            
            if translated_commas >= expected_commas and expected_commas > 0:
                # Split by Chinese commas
                parts = current_segment.split("，")
                # Keep the first 'expected_commas' parts with commas
                kept_parts = []
                for i in range(expected_commas):
                    if i < len(parts):
                        kept_parts.append(parts[i] + "，")
                
                # Join remaining parts as carry-over
                if len(parts) > expected_commas:
                    remaining_parts = parts[expected_commas:]
                    carry_over = "，".join(remaining_parts).strip()
                    # Remove leading comma if it exists
                    if carry_over.startswith("，"):
                        carry_over = carry_over[1:].strip()

                # Assign the kept parts to current block
                block["lines"] = ["".join(kept_parts).rstrip("，") + "，"]
            else:
                # Not enough commas, just assign the whole segment
                block["lines"] = [current_segment]
        else:
            # Normal block, assign the segment as is
            block["lines"] = [current_segment]

        block_index += 1

        
    return flat_blocks


# flattens grouped subtitle blocks into a single list of blocks. Keep their original order for writing to.srt
def flatten_groups(groups):
    return [block for group in groups for block in group]

def write_srt_file(blocks, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, block in enumerate(blocks, start=1):
            f.write(f"{i}\n")
            f.write(f"{block['start']} --> {block['end']}\n")
            for line in block["lines"]:
                f.write(line + "\n")
            f.write("\n")

