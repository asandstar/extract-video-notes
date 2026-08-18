#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def available_models() -> set[str]:
    if shutil.which("ollama") is None:
        raise RuntimeError("Ollama is not installed or is not on PATH")
    result = subprocess.run(
        ["ollama", "list"], text=True, capture_output=True, timeout=30, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot contact Ollama: {result.stderr.strip() or result.stdout.strip()}")
    models: set[str] = set()
    for line in result.stdout.splitlines()[1:]:
        columns = line.split()
        if columns:
            models.add(columns[0])
    return models


def run_model(model: str, prompt: str, timeout: int) -> str:
    result = subprocess.run(
        ["ollama", "run", model, "--think=false"],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ollama exited with code {result.returncode}")
    output = ANSI_ESCAPE_RE.sub("", result.stdout).replace("\r", "").strip()
    if not output:
        raise RuntimeError("Ollama returned empty output")
    return output


def refine_prompt(text: str) -> str:
    return f"""你是忠实的中文 OCR 校订器。请整理下面这一页 OCR 文本。

必须遵守：
1. 只修复有充分把握的错别字、断词、空格和段落换行。
2. 不总结、不删减、不扩写、不翻译，不补充原文没有的事实或引用。
3. 人名、书名、论文名、数字、日期、网址和术语不确定时保持原样。
4. 不要添加“第X页”“本页内容”等人工标题；只有原文明确存在的标题才可保留。
5. 只返回校订后的正文，不要解释修改过程，不要使用代码块。

OCR 文本：
---
{text}
---
"""


def assessment_prompt(text: str) -> str:
    return f"""请评估下面这篇从录屏 OCR 得到的笔记是否值得进一步学术研究。只能依据给出的文字，不能假装核验过原文、论文或外部资料，也不能虚构引用。

请严格按照以下 Markdown 结构回答：

# 学术价值评估

- 总分：0-100
- 分级：高 / 中高 / 混合 / 低
- 一句话判断：

## 分项评分

- 概念深度：0-5，并给一句依据
- 证据质量：0-5，并给一句依据
- 方法意识：0-5，并给一句依据
- 来源基础：0-5，并给一句依据
- 研究用途：0-5，并给一句依据

## 文本中确实出现的学术线索

只列出原文明确出现的理论、作者、书目、论文、方法、案例或可核查线索；没有就写“未发现明确线索”。

## 值得向 GPT 深入讨论的问题

提出 3-6 个具体研究问题，并明确这些问题是建议，不是原作者结论。

## 核验提醒

列出 OCR 误识别、来源缺失、论证跳跃或需要查看原图的位置。

待评估文本：
---
{text}
---
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Use a local Ollama model for faithful OCR cleanup and academic screening.")
    parser.add_argument("ocr_dir", type=Path)
    parser.add_argument("--clean-out", type=Path, required=True)
    parser.add_argument("--assessment-out", type=Path, required=True)
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--title", default="录屏笔记 OCR 全文")
    parser.add_argument("--assessment-max-chars", type=int, default=60000)
    args = parser.parse_args()

    models = available_models()
    if args.model not in models:
        choices = ", ".join(sorted(models)) or "none"
        raise SystemExit(f"model {args.model!r} is not installed; available models: {choices}")

    paths = sorted(args.ocr_dir.glob("page*.txt"))
    if not paths:
        raise SystemExit(f"no page OCR text found in {args.ocr_dir}")

    cleaned_pages: list[str] = []
    failures: list[str] = []
    for index, path in enumerate(paths, start=1):
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            continue
        print(f"Ollama cleanup {index}/{len(paths)}: {path.name}", file=sys.stderr, flush=True)
        try:
            cleaned_pages.append(run_model(args.model, refine_prompt(raw), args.timeout))
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            failures.append(f"{path.name}: {error}")
            cleaned_pages.append(raw)

    combined = f"# {args.title}\n\n" + "\n\n".join(cleaned_pages).strip() + "\n"
    args.clean_out.parent.mkdir(parents=True, exist_ok=True)
    args.clean_out.write_text(combined, encoding="utf-8")

    assessment_text = combined
    clipped = False
    if len(assessment_text) > args.assessment_max_chars:
        half = args.assessment_max_chars // 2
        assessment_text = assessment_text[:half] + "\n\n[中间部分因上下文长度省略]\n\n" + assessment_text[-half:]
        clipped = True

    print("Ollama academic assessment", file=sys.stderr, flush=True)
    assessment = run_model(args.model, assessment_prompt(assessment_text), args.timeout)
    if clipped:
        assessment += "\n\n> 注意：文本过长，本次快速评估只读取了开头和结尾；正式研究前应分段复核。"
    if failures:
        assessment += "\n\n## 自动校订异常\n\n" + "\n".join(f"- {item}" for item in failures)
    args.assessment_out.parent.mkdir(parents=True, exist_ok=True)
    args.assessment_out.write_text(assessment.rstrip() + "\n", encoding="utf-8")
    print(f"pages={len(paths)} failures={len(failures)} model={args.model}")


if __name__ == "__main__":
    main()
