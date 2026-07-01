"""
批量将所有 SRT 字幕转换为纯文本
用法: uv run batch_srt_to_text.py
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SUBTITLE_DIRS = [
    PROJECT_ROOT / "raw" / "subtitles" / "all",
    PROJECT_ROOT / "raw" / "subtitles" / "zhuyi",
    PROJECT_ROOT / "raw" / "subtitles" / "merged",
]
TEXT_DIR = PROJECT_ROOT / "raw" / "texts"


def clean_srt(content: str) -> str:
    lines = content.strip().split('\n')
    texts = []
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+$', line):
            continue
        if re.match(r'\d{2}:\d{2}:\d{2}', line):
            continue
        if not line:
            continue
        line = re.sub(r'<[^>]+>', '', line)
        if line:
            texts.append(line)
    # 去重
    deduped = []
    for t in texts:
        if not deduped or t != deduped[-1]:
            deduped.append(t)
    # 合并段落
    result = []
    current = []
    for t in deduped:
        current.append(t)
        joined = ''.join(current)
        if len(joined) > 200 or re.search(r'[。！？.!?]$', t):
            result.append(joined)
            current = []
    if current:
        result.append(''.join(current))
    return '\n\n'.join(result)


def main():
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    converted = 0

    for sdir in SUBTITLE_DIRS:
        if not sdir.exists():
            continue
        for srt_file in sorted(sdir.glob("*.srt")):
            total += 1
            txt_name = srt_file.stem + ".txt"
            txt_path = TEXT_DIR / txt_name

            if txt_path.exists():
                continue  # 跳过已转换的

            try:
                content = srt_file.read_text(encoding='utf-8')
                transcript = clean_srt(content)
                txt_path.write_text(transcript, encoding='utf-8')
                converted += 1
            except Exception as e:
                print(f"  错误 {srt_file.name}: {e}")

    all_txt = list(TEXT_DIR.glob("*.txt"))
    total_chars = sum(f.stat().st_size for f in all_txt)

    print(f"SRT 总数: {total}")
    print(f"本次转换: {converted}")
    print(f"文本总数: {len(all_txt)}")
    print(f"总字数: {total_chars / 10000:.1f} 万字")


if __name__ == "__main__":
    main()
