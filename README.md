# extract-video-notes

一个供 Codex 使用的本地 Skill：把用户自己提供的 macOS 或 Windows 录屏，整理成去重后的笔记图片、OCR 全文、PDF、学术价值初筛和可交给 GPT 深入研究的材料包。

它适合处理图片型长笔记、文档翻页、网页阅读录屏等内容。设计重点是“录下来再本地整理”，不会登录、抓取或高速浏览社交平台账号。

## 使用目的

一段录屏通常包含重复画面、滚动模糊、界面按钮和大量图片，直接逐张截图再上传给 GPT 很费时间。这个 Skill 会依次完成：

1. 定时抽取视频帧。
2. 排除滚动画面并合并重复页面。
3. 按可调整的区域裁剪正文。
4. 在本机执行中英文 OCR。
5. 生成连续全文，不使用“第 X 页”作为人为标题。
6. 可选使用本地 Ollama 模型校订 OCR，并对内容的学术研究价值进行初筛。
7. 生成一份可交给 GPT 网页版或其他研究模型继续讨论的 `research_package.md`。

## 支持平台

| 平台 | 视频抽帧 | OCR | 状态 |
| --- | --- | --- | --- |
| macOS | AVFoundation | Apple Vision | 已做端到端测试 |
| Windows 10/11 | FFmpeg | RapidOCR + ONNX Runtime | 后端已做端到端测试；请在实际 Windows 机器上复核路径与安装体验 |

共享的 Python 流程负责页面稳定性判断、去重、裁剪、PDF、全文整理和 Ollama 调用。

## 安装 Skill

### 方法一：让 Codex 从 GitHub 安装

在 Codex 对话中输入下面内容，不是在终端里运行：

```text
$skill-installer
请从 https://github.com/asandstar/extract-video-notes 安装路径 .agents/skills/extract-video-notes
```

Skill 通常会在下一轮对话中可用；如果没有出现，重启 Codex。

### 方法二：作为项目 Skill 使用

```bash
git clone https://github.com/asandstar/extract-video-notes.git
cd extract-video-notes
codex
```

Codex 会从仓库根目录的 `.agents/skills/extract-video-notes` 发现它。这种方式适合先试用或参与修改。

## 首次配置

Skill 会把 Python 依赖安装到自身的 `.venv` 中，不修改全局 Python 环境。普通处理在本机完成；首次下载 Python 包需要网络。

### macOS

需要 Python 3.9+ 和 Xcode Command Line Tools。进入 Skill 目录后运行：

```bash
cd .agents/skills/extract-video-notes
python3 scripts/setup_runtime.py
```

如果没有 `swift`，先运行 `xcode-select --install`。完整说明见 [macOS 安装指南](.agents/skills/extract-video-notes/references/install-macos.md)。

### Windows

需要 64 位 Python 3.9+，并安装 FFmpeg、把其 `bin` 目录加入 `PATH`。进入 Skill 目录后，在 PowerShell 运行：

```powershell
cd .agents\skills\extract-video-notes
py scripts\setup_runtime.py
```

FFmpeg 下载入口和检查命令见 [Windows 安装指南](.agents/skills/extract-video-notes/references/install-windows.md)。

### 可选：Ollama 本地校订

不装 Ollama 也能完成抽帧、去重、OCR、PDF 和确定性全文整理。需要本地模型校订与学术初筛时，安装 Ollama 后运行：

```bash
ollama pull qwen3.5:9b
```

模型约占数 GB；内存或磁盘紧张时可以跳过，并在处理时使用 `--skip-ollama`。

## 使用方法

最省事的方法是把录屏文件交给 Codex，并说明：

```text
$extract-video-notes 请处理这些录屏，整理 OCR 全文，筛选学术价值较高的内容，并生成深入研究材料。
```

也可以手动运行。macOS 示例：

```bash
python3 scripts/run_pipeline.py /absolute/path/note.mp4 \
  --work-dir ./work/video-notes \
  --output-dir ./outputs/video-notes
```

Windows PowerShell 示例：

```powershell
py scripts\run_pipeline.py "D:\Videos\note.mp4" `
  --work-dir ".\work\video-notes" `
  --output-dir ".\outputs\video-notes"
```

一次可以传入多个 `.mp4`、`.mov` 或 `.m4v` 文件，程序会顺序处理并生成总索引。只做 OCR 时添加 `--skip-ollama`。

## 主要输出

每个录屏对应一个结果目录：

- `pages/`：裁剪、去重后的页面图片。
- `pages_contact_sheet.jpg`：用于快速检查漏页、重复和错误裁剪。
- `pages.pdf`：按顺序合成的图片 PDF。
- `ocr_pages/`：逐页原始 OCR。
- `ocr_raw.md`：带原图页标记的审计文本。
- `ocr_clean.md`：不带人工页码标题的连续全文。
- `academic_assessment.md`：可选的本地模型学术价值初筛。
- `research_package.md`：供 GPT 继续核验、研究和讨论的材料包。
- `manifest.csv`、`run_summary.json`：页面来源、参数和运行记录。

## 常用调节

```text
--step 0.25               每 0.25 秒采样一帧
--stable-threshold 0.010  调低可更严格排除滚动画面
--dedup-threshold 0.018   调高可更积极合并重复页
--crop-top 0.165          正文裁剪上边界，0 到 1
--crop-bottom 0.903       正文裁剪下边界，0 到 1
--skip-ollama             不调用本地大语言模型
--frame-backend auto      自动选择 avfoundation 或 ffmpeg
--ocr-backend auto        自动选择 vision 或 rapidocr
```

默认裁剪参数来自竖屏笔记录屏。处理其他界面时，先查看 `pages_contact_sheet.jpg`，再调四个 `--crop-*` 参数。更完整的说明见 [处理流程与调参](.agents/skills/extract-video-notes/references/pipeline.md)。

## 准确性与隐私

- 原始录屏和提取图片才是事实依据；OCR 和模型校订都可能出错。
- 人名、数字、论文题目、网址和引文应对照原图复核。
- 学术评分只表示“是否值得继续研究”，不表示原作者观点正确。
- 不要把未核验的模型校订当作逐字引文。
- 录屏可能包含私信、通知或个人信息。发布结果前请检查页面图片、PDF、OCR 和运行摘要。
- 本仓库不包含录屏、OCR 结果、账号凭据或模型文件。

## 开发与验证

检查依赖：

```bash
python3 scripts/doctor.py --skip-ollama
```

检查所有 Python 文件语法：

```bash
python3 -m compileall scripts
```

Skill 的行为规则见 [SKILL.md](.agents/skills/extract-video-notes/SKILL.md)，OCR 与学术评估边界见 [OCR 规则](.agents/skills/extract-video-notes/references/ocr-and-academic-rules.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。第三方组件分别遵循各自许可证。

## 参考

- [OpenAI：Build skills](https://learn.chatgpt.com/docs/build-skills)
- [FFmpeg 官方下载入口](https://ffmpeg.org/download.html)
- [RapidOCR 安装文档](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/install/)
