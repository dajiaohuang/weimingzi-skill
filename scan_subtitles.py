"""
全量扫描无字幕列表，用 yt-dlp 检查并下载所有可用的 CC 字幕
输出：精确的无字幕 BV 列表 + 新下载的字幕文件

用法: uv run scan_subtitles.py
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
BV_LIST_FILE = PROJECT_ROOT / "references" / "no_subtitle_bv_list.txt"
COOKIE_FILE = PROJECT_ROOT / "cookies.txt"
SUBS_ALL_DIR = PROJECT_ROOT / "raw" / "subtitles" / "all"  # 新下载的放这里

# 结果文件
NEW_SUBS_FILE = PROJECT_ROOT / "references" / "new_subs_found.txt"      # 新发现有字幕的
TRUE_NO_SUBS_FILE = PROJECT_ROOT / "references" / "true_no_subtitle.txt"  # 真正无字幕的


def check_and_download_subs(bv: str) -> str:
    """
    检查视频是否有 CC 字幕，有就下载。
    返回: 'cc_downloaded' | 'cc_failed' | 'no_subtitle' | 'error'
    """
    url = f"https://www.bilibili.com/video/{bv}"
    sub_dir = SUBS_ALL_DIR

    # 先用 --list-subs 检测，同时下载（yt-dlp 可以一次完成）
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--write-subs",
        "--sub-langs", "all,-live_chat",
        "--skip-download",  # 不下视频，只下字幕
        "--cookies", str(COOKIE_FILE),
        "--no-playlist",
        "--socket-timeout", "15",
        "-o", str(sub_dir / f"%(id)s_%(title)s.%(ext)s"),
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60, encoding='utf-8', errors='replace')
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 'error'
    except Exception:
        return 'error'

    # 判断是否下载了字幕
    # yt-dlp 下载字幕后会在输出里显示 subtitle 相关信息
    has_subtitle = False
    for line in output.split('\n'):
        if 'Writing subtitle' in line or 'Downloading subtitles' in line:
            has_subtitle = True
            break

    if has_subtitle:
        return 'cc_downloaded'
    elif 'has no subtitles' in output.lower():
        return 'no_subtitle'
    elif 'There are no subtitles' in output:
        return 'no_subtitle'
    else:
        return 'no_subtitle'  # 默认无字幕


def main():
    if not BV_LIST_FILE.exists():
        print(f"错误: {BV_LIST_FILE} 不存在")
        return

    bv_list = [l.strip() for l in BV_LIST_FILE.read_text().strip().split("\n") if l.strip()]
    total = len(bv_list)
    print(f"待检查: {total} 个视频\n")

    SUBS_ALL_DIR.mkdir(parents=True, exist_ok=True)

    new_subs = []   # 新发现有字幕的
    no_subs = []    # 真正无字幕的
    errors = []     # 出错的

    start_time = time.time()

    for i, bv in enumerate(bv_list):
        status = check_and_download_subs(bv)

        if status == 'cc_downloaded':
            new_subs.append(bv)
            no_subs.append(None)  # placeholder
        elif status == 'no_subtitle':
            no_subs.append(bv)
        else:
            errors.append(bv)

        # 进度
        pct = (i + 1) / total * 100
        elapsed = time.time() - start_time
        done = i + 1
        rate = done / elapsed * 60 if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0

        bar = '#' * int(pct / 2) + '-' * (50 - int(pct / 2))
        print(f"\r[{bar}] {pct:.1f}% | {done}/{total} | "
              f"有CC:{len(new_subs)} 无字幕:{len([x for x in no_subs if x])} 错:{len(errors)} | "
              f"{rate:.0f}个/分 | 剩余{eta:.0f}分",
              end='', flush=True)

        # 控制频率
        time.sleep(0.3)

    print()  # newline after progress

    # 保存结果
    true_no_subs = [x for x in no_subs if x]
    NEW_SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(NEW_SUBS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_subs) + "\n")
    with open(TRUE_NO_SUBS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(true_no_subs) + "\n")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"扫描完成! 耗时: {elapsed/60:.1f} 分钟")
    print(f"  新发现有 CC 字幕: {len(new_subs)}")
    print(f"  真正无字幕:       {len(true_no_subs)}")
    print(f"  出错:             {len(errors)}")
    print(f"  字幕文件目录:     {SUBS_ALL_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
