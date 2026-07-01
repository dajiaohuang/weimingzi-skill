# Whisper ASR Handover

> 用于在其他环境中对未明子无字幕视频进行 Whisper 语音转文字

## 概况

- **UP主**：未明子（B站 UID: 23191782）
- **总视频数**：1682
- **已有字幕**：52 个视频（B站CC字幕，通过 yt-dlp 下载）
- **无字幕视频**：1630 个
- **无字幕 BV 号列表**：[no_subtitle_bv_list.txt](references/no_subtitle_bv_list.txt)

## 已有数据

### 已完成字幕（52个视频，约52.8万字）
- 主义主义系列（总纲 + 各主义单集）
- 一分钟哲学课（37集全）
- 拉康精神分析系列
- 康德/黑格尔系列
- 辩证法系列
- 社会观察/批判系列
- 符号学系列
- 爱欲经济学系列

### 字幕文件位置
```
raw/subtitles/merged/      # 合并去重后的 SRT 字幕
raw/subtitles/all/         # 原始下载的 SRT 字幕
raw/subtitles/zhuyi/       # 主义主义系列字幕
raw/texts/                 # SRT 转纯文本
```

## Whisper 处理指南

### 1. 下载视频音频

使用 yt-dlp 下载音频（不需要视频画面）：

```bash
# 单个视频
yt-dlp -x --audio-format mp3 --audio-quality 0 \
  "https://www.bilibili.com/video/BVxxxxxx" \
  --cookies cookies.txt \
  -o "audio/%(id)s.%(ext)s"

# 批量下载（从 BV 列表）
while IFS= read -r bv; do
  yt-dlp -x --audio-format mp3 --audio-quality 0 \
    "https://www.bilibili.com/video/$bv" \
    --cookies cookies.txt \
    -o "audio/${bv}.%(ext)s" \
    --skip-download-existing
done < no_subtitle_bv_list.txt
```

### 2. Whisper 转写

推荐使用 faster-whisper 或 openai-whisper：

#### 方案 A：faster-whisper（推荐，速度快）

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")

import json
from pathlib import Path

bv_list = Path("no_subtitle_bv_list.txt").read_text().strip().split("\n")
for bv in bv_list:
    audio_path = f"audio/{bv}.mp3"
    if not Path(audio_path).exists():
        continue
    segments, info = model.transcribe(audio_path, language="zh", 
                                       vad_filter=True,
                                       beam_size=5)
    # 保存为 SRT
    srt_path = f"output/{bv}.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp(seg.start)
            end = format_timestamp(seg.end)
            f.write(f"{i}\n{start} --> {end}\n{seg.text.strip()}\n\n")
```

#### 方案 B：openai-whisper

```python
import whisper
model = whisper.load_model("large-v3")
result = model.transcribe("audio/BVxxxxxx.mp3", language="zh")
# result["text"] 是完整文本
# result["segments"] 是带时间戳的分段
```

### 3. 显存要求参考

| 模型 | 参数量 | 显存（FP16） | 显存（INT8） | 速度 | 准确度 |
|------|--------|-------------|-------------|------|--------|
| tiny | 39M | ~1GB | ~0.5GB | 最快 | 低 |
| base | 74M | ~1GB | ~0.5GB | 很快 | 一般 |
| small | 244M | ~2GB | ~1GB | 快 | 还行 |
| medium | 769M | ~5GB | ~2.5GB | 中等 | 好 |
| large-v3 | 1550M | ~10GB | ~4GB | 慢 | 最好 |

**推荐**：`large-v3` + INT8 量化（faster-whisper），4GB 显存即可运行，准确度最佳。

### 4. 输出格式

建议输出为 SRT 格式，与已有字幕格式一致，方便后续合并处理。

SRT 时间戳格式化函数：
```python
def format_timestamp(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"
```

## 注意事项

1. **B站 Cookies**：下载视频音频需要 B站登录 cookies。cookies.txt 为 Netscape 格式。
2. **视频时长差异大**：未明子的视频从几十秒到几小时不等，直播录播通常很长（2-4小时）。
3. **直播内容**：大量直播切片/录播没有CC字幕，是 Whisper 处理的重点。
4. **语言**：全部为中文，Whisper 设 `language="zh"` 即可。
5. **VAD 滤波**：建议开启 `vad_filter=True` 去除静音段，提升效率和准确度。
6. **去重**：BV 列表已与已有字幕去重，可直接使用。
7. **断点续传**：建议处理时检查输出目录是否已存在对应文件，跳过已处理的。

## 文件清单

| 文件 | 说明 |
|------|------|
| `references/no_subtitle_bv_list.txt` | 1630 个无字幕视频的 BV 号列表（每行一个） |
| `cookies.txt` | B站登录 cookies（Netscape 格式） |

## 后续整合

Whisper 转写完成后，将 SRT 文件放入 `raw/subtitles/whisper/` 目录，然后用现有的 `process_subtitles.py` 脚本进行清洗、去重、转纯文本：

```bash
python scripts/process_subtitles.py raw/subtitles/whisper/ raw/texts/whisper/
```
