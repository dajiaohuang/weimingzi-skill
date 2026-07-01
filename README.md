# 未明子 AI 项目

未明子（B站 UID: 23191782）的完整 AI 工具链，包含视频字幕获取、Whisper 语音转文字、以及 AI Skill。

## 项目组成

```
weimingzi-skill/
├── weimingzi-skill/              # 未明子 AI Skill（nuwa-skill 格式）
│   ├── SKILL.md                  #   主 Skill 定义（心智模型、表达DNA、决策启发式）
│   ├── references/research/      #   7 个维度的深度调研
│   └── README.md
├── raw/
│   ├── subtitles/                # SRT 字幕（1044 个文件）
│   │   ├── all/                  #   全量（831 个，含 B 站 AI 字幕）
│   │   ├── zhuyi/                #   主义主义系列（99 个）
│   │   └── merged/               #   合并去重（100 个）
│   └── texts/                    # 纯文本（851 个，约 2400 万字）
├── models/faster-whisper-medium/ # Whisper medium 模型（1.5GB）
├── audio/                        # 下载的视频音频
├── output/whisper_srt/           # Whisper 转写结果
│
├── fetch_bilibili_videos.py      # 获取 UP 主全部视频列表（空间 API + WBI 签名）
├── scan_subtitles.py             # 全量扫描并下载 B 站 CC 字幕
├── whisper_transcribe.py         # Whisper 语音转文字（GPU 加速）
├── batch_srt_to_text.py          # 批量 SRT → 纯文本
├── run_whisper.bat               # Windows 一键运行脚本
├── cookies.txt                   # B 站登录 Cookie（Netscape 格式）
│
├── pyproject.toml                # Python 项目配置
└── README.md                     # 本文件
```

## 数据规模

| 维度 | 数量 |
|------|------|
| UP 主全部视频 | 1,682 |
| 已有字幕 | 52（人工）/ 1,630（含 AI） |
| 字幕文件 | 1,044 SRT |
| 纯文本 | 851 个文件，约 **2,468 万字** |

## 快速开始

### 环境要求

- Windows 10+
- NVIDIA GPU（GTX 1050 Ti 4GB 或更高）
- Python 3.12（通过 `uv` 管理）
- B 站 Cookies（`cookies.txt`，Netscape 格式）

### 安装

```bash
# 安装 uv 包管理器
winget install astral-sh.uv

# 创建虚拟环境并安装依赖
uv venv --python 3.12
uv sync
uv pip install faster-whisper nvidia-cublas-cu12

# 安装 ffmpeg（音频转换）
winget install Gyan.FFmpeg
```

### 下载 Whisper 模型

```bash
# 手动下载 medium 模型（1.5GB）
# 从 https://hf-mirror.com/Systran/faster-whisper-medium/resolve/main/model.bin
# 放到 models/faster-whisper-medium/

# 或自动下载（需要代理访问 HuggingFace）
uv run whisper_transcribe.py --transcribe  # 首次运行自动下载
```

### 使用流程

```bash
# 1. 获取全部视频列表（1682 个）
uv run fetch_bilibili_videos.py 23191782

# 2. 扫描并下载所有可用字幕
uv run scan_subtitles.py

# 3. 字幕转纯文本
uv run batch_srt_to_text.py

# 4. Whisper 转写（仅对无字幕视频）
uv run whisper_transcribe.py --transcribe

# 或一键 GUI
run_whisper.bat
```

## GPU 配置

| GPU | 模型 | 量化 | VRAM |
|-----|------|------|------|
| GTX 1050 Ti 4GB | medium | int8 | ~2.5GB |
| GTX 1060+ 6GB | medium | int8 | ~2.5GB |
| RTX 2060+ 6GB | large-v3 | int8_float16 | ~4GB |
| RTX 3060+ 12GB | large-v3 | float16 | ~10GB |

Pascal 架构（GTX 10 系列）仅支持 `int8`，不支持 `float16`/`int8_float16`。

## 相关项目

- [nuwa-skill](https://github.com/alchaincyf/nuwa-skill) — 女娲 Skill 造人术，本项目的 Skill 模板来源

## 免责声明

本项目仅用于研究和教育目的。内容基于未明子公开视频提炼，不代表其本人观点。
