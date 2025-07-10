import re

def add_terminal_punctuation(srt_path, output_path):
    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    new_lines = []
    for line in lines:
        line_strip = line.strip()

        # === 跳过序号行 & 时间戳行 ===
        if (
            not line_strip
            or line_strip.isdigit()
            or re.match(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', line_strip)
        ):
            new_lines.append(line)
            continue

        # === STEP 0: 先执行补句号（保持原写法）===
        if line_strip.endswith('...') or line_strip.endswith('……') or line_strip[-1] in {'.', '?', '!', '…', ',', ';', ':'}:
            pass
        else:
            line_strip += '.'

        # === STEP 1: 查找所有强标点（优先长匹配）===
        strong_punct_pattern = r'(……|\.{3}|…|[.?!])'
        strong_puncts = list(re.finditer(strong_punct_pattern, line_strip))

        if len(strong_puncts) >= 2:
            working_line = line_strip

            # === STEP 1: 从后往前，每个都切后半句 + 降小写 + 删标点 ===
            for m in reversed(strong_puncts[:-1]):
                punct_pos = m.start()
                punct_end = m.end()  # 核心：要用 end() 保证多字符符号一次性删除

                after_part = working_line[punct_end:].strip()

                # 找首个大写词（含撇号）
                m_word = re.search(r"\b([A-Z][a-z']+)\b", after_part)
                if m_word:
                    word = m_word.group(1)
                    after_part = after_part.replace(word, word.lower(), 1)

                working_line = working_line[:punct_pos].rstrip() + ' ' + after_part

            line_strip = working_line.strip()

        # === STEP 2: 不再重复补句号 ===
        new_lines.append(line_strip)

    # === 写回文件 ===
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print(f"✅ Saved fixed SRT to {output_path}")