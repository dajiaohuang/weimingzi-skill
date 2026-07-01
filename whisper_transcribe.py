"""
Whisper 语音转文字 — 未明子无字幕视频批处理
================================================
适配设备: GTX 1050 Ti (4GB VRAM)
模型方案: faster-whisper medium + INT8 量化 (~2.5GB VRAM)

用法:
  # 1. 先获取 BV 列表（如果还没有）
  uv run fetch_bilibili_videos.py 23191782 未明子

  # 2. 生成无字幕 BV 列表
  uv run whisper_transcribe.py --gen-bv-list

  # 3. 下载音频（yt-dlp 批量）
  uv run whisper_transcribe.py --download-audio

  # 4. 开始转写
  uv run whisper_transcribe.py --transcribe

  # 5. 或者一键全流程
  uv run whisper_transcribe.py --all

  # 单个文件测试
  uv run whisper_transcribe.py --transcribe --bv BVxxxxxx
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import timedelta

# Windows terminal UTF-8 encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).parent
AUDIO_DIR = PROJECT_ROOT / "audio"
OUTPUT_SRT_DIR = PROJECT_ROOT / "output" / "whisper_srt"
SUBTITLE_DIR = PROJECT_ROOT / "raw" / "subtitles" / "whisper"
TEXT_DIR = PROJECT_ROOT / "raw" / "texts" / "whisper"
BV_LIST_FILE = PROJECT_ROOT / "references" / "no_subtitle_bv_list.txt"
COOKIE_FILE = PROJECT_ROOT / "cookies.txt"

# ============================================================
# 设备配置 — GTX 1050 Ti (4GB VRAM, Pascal CC 6.1)
# ============================================================
MODEL_PATH = str(PROJECT_ROOT / "models" / "faster-whisper-medium")  # 本地模型
COMPUTE_TYPE = "int8"            # Pascal CC 6.1 只支持 int8
DEVICE = "cuda"                  # GPU 加速
BEAM_SIZE = 5                    # beam search
VAD_FILTER = True                # 过滤静音段
LANGUAGE = "zh"                  # 中文

# cuBLAS DLL 路径（GPU 推理必需）
_CUBLAS_PATH = PROJECT_ROOT / ".venv" / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin"
if _CUBLAS_PATH.exists():
    os.add_dll_directory(str(_CUBLAS_PATH))


def get_audio_path(bv: str) -> Path:
    """获取 BV 号对应的音频文件路径"""
    for ext in [".mp3", ".m4a", ".webm", ".opus", ".wav"]:
        p = AUDIO_DIR / f"{bv}{ext}"
        if p.exists():
            return p
    return AUDIO_DIR / f"{bv}.mp3"  # 默认 mp3


def get_srt_path(bv: str) -> Path:
    """获取输出 SRT 文件路径"""
    return OUTPUT_SRT_DIR / f"{bv}.srt"


def format_timestamp(seconds: float) -> str:
    """格式化为 SRT 时间戳 HH:MM:SS,mmm"""
    td = timedelta(seconds=seconds)
    total_secs = int(td.total_seconds())
    hrs = total_secs // 3600
    mins = (total_secs % 3600) // 60
    secs = total_secs % 60
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def gen_no_subtitle_bv_list():
    """生成无字幕 BV 列表（已有字幕的排除）"""
    import re

    # 从已有字幕文件中提取已完成的 BV 号
    have_subs = set()
    subtitle_dirs = [
        PROJECT_ROOT / "raw" / "subtitles" / "all",
        PROJECT_ROOT / "raw" / "subtitles" / "zhuyi",
        PROJECT_ROOT / "raw" / "subtitles" / "merged",
    ]
    for sdir in subtitle_dirs:
        if sdir.exists():
            for f in sdir.iterdir():
                m = re.match(r'(BV[0-9a-zA-Z]+)', f.name)
                if m:
                    have_subs.add(m.group(1))

    print(f"已有字幕视频: {len(have_subs)} 个")

    # 从 video_list_full.json 获取全部视频
    video_list_file = PROJECT_ROOT / "video_list_full.json"
    if not video_list_file.exists():
        print(f"错误: {video_list_file} 不存在，请先运行:")
        print(f"  uv run fetch_bilibili_videos.py 23191782 未明子")
        return

    with open(video_list_file, "r", encoding="utf-8") as f:
        videos = json.load(f)

    all_bvs = [v["bvid"] for v in videos if "bvid" in v]
    no_sub_bvs = [bv for bv in all_bvs if bv not in have_subs]

    print(f"全部视频: {len(all_bvs)} 个")
    print(f"无字幕视频: {len(no_sub_bvs)} 个")

    BV_LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BV_LIST_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(no_sub_bvs) + "\n")

    print(f"已保存到: {BV_LIST_FILE}")
    return no_sub_bvs


def download_audio():
    """批量下载无字幕视频的音频（B站直连，不走代理）"""
    # 清除代理（B站是国内站）
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(key, None)

    if not BV_LIST_FILE.exists():
        print(f"错误: {BV_LIST_FILE} 不存在，请先运行 --gen-bv-list")
        return

    bv_list = [l.strip() for l in BV_LIST_FILE.read_text().strip().split("\n") if l.strip()]
    print(f"准备下载 {len(bv_list)} 个视频的音频...")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    cookie_args = ["--cookies", str(COOKIE_FILE)] if COOKIE_FILE.exists() else []

    success = 0
    fail = 0
    for i, bv in enumerate(bv_list):
        audio_path = get_audio_path(bv)
        if audio_path.exists():
            # 检查文件是否有效（> 1KB）
            if audio_path.stat().st_size > 1024:
                continue  # 跳过已下载

        url = f"https://www.bilibili.com/video/{bv}"
        out_tmpl = str(AUDIO_DIR / f"%(id)s.%(ext)s")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            url, "-o", out_tmpl,
            *cookie_args,
            "--no-playlist",
            "--socket-timeout", "30",
        ]

        print(f"[{i+1}/{len(bv_list)}] 下载 {bv} ...", end=" ", flush=True)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("OK")
                success += 1
            else:
                print(f"失败: {result.stderr[-200:] if result.stderr else 'unknown'}")
                fail += 1
        except subprocess.TimeoutExpired:
            print("超时")
            fail += 1
        except Exception as e:
            print(f"错误: {e}")
            fail += 1

        # 短暂休息防止被限流
        if i % 5 == 4:
            time.sleep(3)
        else:
            time.sleep(1)

    print(f"\n下载完成: 成功 {success}, 失败 {fail}")


def transcribe_bv(bv: str, model, srts_written: int = 0):
    """对单个 BV 视频进行 Whisper 转写"""
    audio_path = get_audio_path(bv)
    srt_path = get_srt_path(bv)

    if srt_path.exists() and srt_path.stat().st_size > 100:
        return None, "skipped"  # 已处理

    if not audio_path.exists():
        return None, f"no_audio: {audio_path}"

    try:
        segments, info = model.transcribe(
            str(audio_path),
            language=LANGUAGE,
            vad_filter=VAD_FILTER,
            beam_size=BEAM_SIZE,
        )

        srt_lines = []
        for i, seg in enumerate(segments, 1):
            start = format_timestamp(seg.start)
            end = format_timestamp(seg.end)
            text = seg.text.strip()
            srt_lines.append(f"{i}\n{start} --> {end}\n{text}\n")

        srt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        return len(srt_lines), "ok"
    except Exception as e:
        return None, f"error: {e}"


def transcribe_all():
    """批量转写所有无字幕视频"""
    if not BV_LIST_FILE.exists():
        print(f"错误: {BV_LIST_FILE} 不存在，请先运行 --gen-bv-list")
        return

    bv_list = [l.strip() for l in BV_LIST_FILE.read_text().strip().split("\n") if l.strip()]

    print(f"=" * 60)
    print(f"加载 faster-whisper 模型: {MODEL_PATH}")
    print(f"设备: {DEVICE} ({COMPUTE_TYPE})")
    print(f"待处理: {len(bv_list)} 个视频")
    print(f"=" * 60)

    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL_PATH, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("模型加载完成!\n")

    stats = {"ok": 0, "skipped": 0, "no_audio": 0, "error": 0, "total_segments": 0}
    start_time = time.time()

    for i, bv in enumerate(bv_list):
        count, status = transcribe_bv(bv, model)
        pct = (i + 1) / len(bv_list) * 100

        if status == "ok":
            stats["ok"] += 1
            stats["total_segments"] += (count or 0)
            print(f"[{i+1}/{len(bv_list)} {pct:.1f}%] {bv}: {count} 段 ✓")
        elif status == "skipped":
            stats["skipped"] += 1
        elif status and status.startswith("no_audio"):
            stats["no_audio"] += 1
            print(f"[{i+1}/{len(bv_list)} {pct:.1f}%] {bv}: 无音频 ⚠")
        else:
            stats["error"] += 1
            print(f"[{i+1}/{len(bv_list)} {pct:.1f}%] {bv}: {status} ✗")

        # 每 10 个输出进度统计
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            done = stats["ok"] + stats["skipped"]
            rate = done / elapsed * 60 if elapsed > 0 else 0
            eta = (len(bv_list) - i - 1) / rate if rate > 0 else 0
            print(f"  --- 进度: {done} 完成, {stats['no_audio']} 缺音频, "
                  f"{stats['error']} 错误 | {rate:.1f} 个/分 | "
                  f"预计剩余: {eta:.0f}分 ---")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"转写完成!")
    print(f"  成功: {stats['ok']}")
    print(f"  跳过: {stats['skipped']}")
    print(f"  缺音频: {stats['no_audio']}")
    print(f"  错误: {stats['error']}")
    print(f"  总段数: {stats['total_segments']}")
    print(f"  总耗时: {elapsed/60:.1f} 分钟")
    print(f"{'=' * 60}")


def copy_to_subtitles():
    """将转写结果复制到 raw/subtitles/whisper/"""
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for srt_file in OUTPUT_SRT_DIR.glob("*.srt"):
        dest = SUBTITLE_DIR / srt_file.name
        if not dest.exists():
            import shutil
            shutil.copy2(srt_file, dest)
            copied += 1
    print(f"已复制 {copied} 个 SRT 文件到 {SUBTITLE_DIR}")


def main():
    parser = argparse.ArgumentParser(description="未明子视频 Whisper 转写工具")
    parser.add_argument("--gen-bv-list", action="store_true", help="生成无字幕 BV 列表")
    parser.add_argument("--download-audio", action="store_true", help="批量下载音频")
    parser.add_argument("--transcribe", action="store_true", help="批量转写")
    parser.add_argument("--all", action="store_true", help="全流程（生成列表+下载+转写）")
    parser.add_argument("--bv", type=str, help="只处理单个 BV 号")
    parser.add_argument("--copy", action="store_true", help="复制结果到 raw/subtitles/whisper/")
    parser.add_argument("--model", type=str, default=MODEL_PATH, help=f"模型路径 (默认: {MODEL_PATH})")
    parser.add_argument("--compute-type", type=str, default=COMPUTE_TYPE, help=f"计算精度 (默认: {COMPUTE_TYPE})")
    parser.add_argument("--skip-download", action="store_true", help="--all 模式下跳过下载")
    args = parser.parse_args()

    if args.all:
        args.gen_bv_list = True
        args.download_audio = not args.skip_download
        args.transcribe = True

    if args.gen_bv_list:
        print("\n>>> 步骤 1: 生成无字幕 BV 列表")
        gen_no_subtitle_bv_list()

    if args.download_audio:
        print("\n>>> 步骤 2: 下载音频")
        download_audio()

    if args.transcribe:
        if args.bv:
            # 单个文件转写
            from faster_whisper import WhisperModel
            model_path = args.model if args.model != MODEL_PATH else MODEL_PATH
            model = WhisperModel(model_path, device=DEVICE, compute_type=args.compute_type)
            print(f"转写单个视频: {args.bv}")
            count, status = transcribe_bv(args.bv, model)
            if status == "ok":
                print(f"完成: {count} 段 → {get_srt_path(args.bv)}")
            else:
                print(f"状态: {status}")
        else:
            print("\n>>> 步骤 3: 批量 Whisper 转写")
            transcribe_all()

    if args.copy:
        copy_to_subtitles()

    if not any([args.gen_bv_list, args.download_audio, args.transcribe, args.copy]):
        parser.print_help()
        print(f"\n当前设备配置:")
        print(f"  GPU: GTX 1050 Ti (4GB VRAM, Pascal CC 6.1)")
        print(f"  模型: {MODEL_PATH} ({COMPUTE_TYPE})")
        print(f"  实测 VRAM 占用: ~2.5GB / 4GB")
        print(f"  转写速度: ~3x 实时")


if __name__ == "__main__":
    main()
