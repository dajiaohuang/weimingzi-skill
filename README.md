# 未明子 AI Skill

基于 1000+ 个 B站视频（约 2400 万字字幕）蒸馏的未明子思维框架 AI Skill。

## 内容

```
weimingzi-skill/
├── SKILL.md                           # 主 Skill 定义（9 个心智模型、12 条决策启发式）
├── README.md
├── whisper_handover.md                # Whisper 转写交接文档
└── references/research/
    ├── 01-writings.md                 # 著作/思想体系
    ├── 02-conversations.md            # 对话/即兴思考
    ├── 03-expression-dna.md           # 表达风格 DNA
    ├── 04-external-views.md           # 外部评价
    ├── 05-decisions.md                # 重大决策
    ├── 06-timeline.md                 # 时间线
    └── 07-memes-and-quotes.md         # 梗与名言

raw/texts/                             # 纯文本语料（850+ 文件，约 2400 万字）
```

## 使用

将 `weimingzi-skill/` 目录放入支持 nuwa-skill 格式的 AI 工具中即可激活。

## 数据管线

语料提取使用 [bilibili-pipeline](https://github.com/dajiaohuang/bilibili-pipeline) — B站视频字幕获取与 Whisper ASR 转写工具链。

## 相关项目

- [nuwa-skill](https://github.com/alchaincyf/nuwa-skill) — 女娲 Skill 造人术
- [bilibili-pipeline](https://github.com/dajiaohuang/bilibili-pipeline) — 语料提取管线

## 免责声明

基于未明子公开视频内容提炼，不代表本人观点。仅供研究参考。
