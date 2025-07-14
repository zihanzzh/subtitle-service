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

# convert milliseconds back to SRT time string.
def ms_to_time(ms):
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

# Group subtitle blocks by time continuity and max lines.
# Return list of grouped blocks with updated time ranges.
# Group subtitle blocks by time continuity and max lines.
# Return list of grouped blocks with updated time ranges.
def group_subtitles(
    srt_path,
    time_tolerance_ms=50,
    max_lines_per_group=10,
    max_group_duration_sec=10
):
    # step 1: parse SRT into blocks
    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines() #read all the lines and store them into list lines

    raw_blocks = []
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
            raw_blocks.append({
                "index": index,
                "start": start,
                "end": end,
                "lines": text_lines
            })
        i += 1

    # Step 2: Grouping based on time continuity
    groups = []
    current_group = [raw_blocks[0]]
    for j in range(1, len(raw_blocks)):
        prev = current_group[-1]
        curr = raw_blocks[j]
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
    
    # Step 3: enforce max lines per group
    final_groups = []
    for group in groups:
        temp_group = []
        for block in group:
            temp_group.append(block)
            total_lines = sum(len(b["lines"]) for b in temp_group)
            duration_ms = (
                time_to_ms(temp_group[-1]["end"]) - time_to_ms(temp_group[0]["start"])
            )
            duration_sec = duration_ms / 1000.0
            if total_lines >= max_lines_per_group or duration_sec >= max_group_duration_sec:
                # Split out this chunk
                final_groups.append(temp_group)
                temp_group = []
        if temp_group:
            final_groups.append(temp_group)
       
    # Step 4: Recalculate start/end time for each final group
    grouped_results = []
    for subgroup in final_groups:
        merged_lines = []
        for block in subgroup:
            merged_lines.extend(block["lines"])

        start_time = subgroup[0]["start"]
        end_time = subgroup[-1]["end"]


        # skip groups with no actual lines
        if merged_lines:
            grouped_results.append({
                "start": start_time,
                "end": end_time,
                "lines": merged_lines
            })

    print(f"Grouping complete: {len(grouped_results)} groups created.")
    return grouped_results

# Setup Gemini
def load_gemini_api_key(path="gemini_key.txt"):
    with open(path, "r") as f:
        return f.read().strip()

def setup_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("models/gemini-2.0-flash-lite")

# Translates grouped subtitles in batches
# Each group keeps its time range and combined lines.
# Returns a list of translated batch strings.
def translate_groups(groups, model, target_lang="Chinese", batch_size=20):

    all_translated_batches = []
    for i in range(0, len(groups), batch_size):
        batch = groups[i : i + batch_size]

        # Build batch text: each block = time range + content
        batch_text = ""
        for group in batch:
            time_range = f"{group['start']} --> {group['end']}"
            content = " ".join(group["lines"]).strip()
            batch_text += f"{time_range}\n{content}\n\n"  # Double line break after each block

        # Build prompt
        prompt = f"""
Translate the following English subtitle blocks into natural, fluent spoken {target_lang}.

== INSTRUCTIONS ==
- For each block, keep the original time range exactly as given, at the top.
- Below the time range, provide the translated text for ONLY that block's text.
- DO NOT merge, combine, split, or reorder content between different blocks. The order of sentences must remain EXACTLY the same as given — do NOT reorder for storytelling or grammar reasons.
- If a block has no dialogue, return the time range as is and leave the text blank.
- Add natural Chinese punctuation marks where appropriate to ensure clear, fluent reading. You do NOT need to preserve the exact punctuation from the original — translate naturally.
- Use full-width Chinese commas （，） instead of English commas (,).
- Keep names, terms, and proper nouns consistent throughout.
- Remove any filler words like 'like', 'uh', 'you know' unless needed for natural flow.
- After each block, insert exactly one blank line to separate blocks.
- Do NOT add any extra comments or explanations — only the time range and translated text for each block.
== CONTENT ==
{batch_text}
""".strip()
        # send to Gemini
        try:
            response = model.generate_content(prompt)
            translated_text = response.text.strip()
            print(f"[Batch {i // batch_size + 1}] Translation complete. Returned {len(translated_text)} chars.")
        except Exception as e:
            print(f"[Batch {i // batch_size + 1}] Translation failed: {e}")
            translated_text = ""

        # Add raw translated text to final results
        all_translated_batches.append(translated_text)

        # Pause to respect rate limits
        time.sleep(random.uniform(5, 7))
    
    return all_translated_batches


# Split each translated block into smaller chunks by strong punctuation,
# calculate proportional time ranges, and return final subtitle blocks.
def split_and_assign_translation(translated_batches, max_chars_per_block=28):
    final_blocks = []

    for batch_text in translated_batches:
        # Split the batch into blocks by blank line
        blocks = re.split(r'\n\s*\n', batch_text.strip())

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 2:
                continue

            time_range = lines[0].strip()
            paragraph = "".join("".join(lines[1:]).split())  # Remove extra spaces/newlines

            # Parse time range
            start_str, end_str = [s.strip() for s in time_range.split("-->")]
            start_ms = time_to_ms(start_str)
            end_ms = time_to_ms(end_str)
            total_duration = end_ms - start_ms

            # Split paragraph by strong punctuation
            segments = re.split(r'(……|。|？|！|\!|\.{3}|…|”|，)', paragraph)
            segments = ["".join(pair) for pair in zip(segments[::2], segments[1::2])] + segments[len(segments)//2*2:]
            segments = [s.strip() for s in segments if s.strip()]

            # Accumulate segments into sub-blocks
            current_block = ""
            current_length = 0
            used_chars = 0
            sub_blocks = []

            seg_idx = 0
            while seg_idx < len(segments):
                seg = segments[seg_idx]
                seg_len = len(seg)
                if current_length + seg_len <= max_chars_per_block:
                    current_block += seg
                    current_length += seg_len
                    used_chars += seg_len
                    seg_idx += 1
                else:
                    if current_block:
                        sub_blocks.append(current_block)
                        current_block = ""
                        current_length = 0
                    else:
                        # Single segment longer than max, force split
                        sub_blocks.append(seg)
                        used_chars += seg_len
                        seg_idx += 1

            if current_block:
                sub_blocks.append(current_block)

            # Calculate new time ranges proportionally
            chunk_start = start_ms
            for sb in sub_blocks:
                chunk_chars = len(sb)
                proportion = chunk_chars / max(used_chars, 1)
                chunk_duration = int(proportion * total_duration)
                chunk_end = chunk_start + chunk_duration

                # prevent overlap or reverse
                if chunk_end > end_ms or sb == sub_blocks[-1]:
                    chunk_end = end_ms
                
                final_blocks.append({
                    "start": ms_to_time(chunk_start),
                    "end": ms_to_time(chunk_end),
                    "lines": [sb]
                })

                chunk_start = chunk_end  # next chunk starts where this ends

    print(f"Split and assign complete: {len(final_blocks)} blocks generated.")
    return final_blocks


def write_srt_file(blocks, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, block in enumerate(blocks, start=1):
            f.write(f"{i}\n")
            f.write(f"{block['start']} --> {block['end']}\n")
            for line in block["lines"]:
                f.write(line + "\n")
            f.write("\n")

