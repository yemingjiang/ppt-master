# PPT Master — AI builds review-first presentation skeletons and native-editable PPTX from any document

[![Version](https://img.shields.io/badge/version-v2.3.0-blue.svg)](https://github.com/hugohe3/ppt-master/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/hugohe3/ppt-master.svg)](https://github.com/hugohe3/ppt-master/stargazers)
[![AtomGit stars](https://atomgit.com/hugohe3/ppt-master/star/badge.svg)](https://atomgit.com/hugohe3/ppt-master)

English | [中文](./README_CN.md)

<p align="center">
  <a href="https://hugohe3.github.io/ppt-master/"><strong>Live Demo</strong></a> ·
  <a href="https://www.hehugo.com/"><strong>About Hugo He</strong></a> ·
  <a href="./examples/"><strong>Examples</strong></a> ·
  <a href="./docs/faq.md"><strong>FAQ</strong></a> ·
  <a href="mailto:heyug3@gmail.com"><strong>Contact</strong></a>
</p>

> **Official channels —** this project is published **only** on [GitHub](https://github.com/hugohe3/ppt-master) (primary) and [AtomGit](https://atomgit.com/hugohe3/ppt-master) (auto-synced mirror). Redistributions on any other platform are unofficial and not maintained by the author. Licensed under MIT — attribution required.

---

Drop in a PDF, DOCX, URL, or Markdown — get back a **reviewable presentation skeleton first** (`main_content.md`, `design_spec.md`, `preview/index.html`), then a **native-editable PowerPoint** when the structure is approved.

> **How it works** — PPT Master is a workflow (a "skill") designed for human–AI collaboration inside the **Codex app** (and other AI IDEs like Claude Code, Cursor, or VS Code + Copilot). You chat with the AI — "make a deck from this PDF" — and it first builds a reviewable skeleton package and an **HTML draft** on your computer. You then open that HTML draft right in the Codex app, **flip through the slides and annotate them in your browser** (rename a title, sharpen a takeaway, swap an asset, reorder pages), click **"Copy all comments"**, and paste them back into the chat. The AI applies your comments and rebuilds the draft — you loop with it until the structure is right. **Only when you approve** does the same workflow continue internally into a native editable rebuild step that produces the final `.pptx`. No coding on your side; the IDE is just where the conversation happens.
>
> **What you'll do**: install Python, install an AI IDE, drop in your material. First-time setup is about 15 minutes. Each deck takes ~10–20 minutes of back-and-forth with the AI.

PPT Master is different:

- **Review-first, editable-final** — instead of pretending one pass can do everything, PPT Master gets the structure reviewed first and only then rebuilds the final deck natively for manual editing
- **You stay in the loop** — review the HTML draft in the Codex app, annotate slides directly in the browser, copy your comments back to the AI, and iterate until the structure is locked before any final render
- **Real PowerPoint where it matters** — the preferred final path is a native editable rebuild, not a screenshot export or a flattened web snapshot
- **Transparent, predictable cost** — the tool is free and open source; the only cost is your own AI editor, and you know exactly what you're paying. As low as **$0.08/deck** with VS Code Copilot
- **Data stays local** — your files shouldn't have to be uploaded to someone else's server just to make a presentation. Apart from AI model communication, the entire pipeline runs on your machine
- **No platform lock-in** — your workflow shouldn't be held hostage by any single company. Works with Claude Code, Cursor, VS Code Copilot, and more; supports Claude, GPT, Gemini, Kimi, and other models

## Quick Start

### 1. Prerequisites

**You only need Python.** Everything else is installed via `pip install -r requirements.txt`.

| Dependency | Required? | What it does |
|------------|:---------:|--------------|
| [Python](https://www.python.org/downloads/) 3.10+ | ✅ **Yes** | Core runtime — the only thing you actually need to install |

> **TL;DR** — Install Python, run `pip install -r requirements.txt`, and you're ready to generate presentations.

<details open>
<summary><strong>Windows</strong> — see the dedicated step-by-step guide ⚠️</summary>

Windows requires a few extra steps (PATH setup, execution policy, etc.). We wrote a **step-by-step guide** specifically for Windows users:

**📖 [Windows Installation Guide](./docs/windows-installation.md)** — from zero to a working presentation in 10 minutes.

Quick version: download Python from [python.org](https://www.python.org/downloads/) → **check "Add to PATH"** during install → `pip install -r requirements.txt` → done.
</details>

<details>
<summary><strong>macOS / Linux</strong> — install and go</summary>

```bash
# macOS
brew install python
pip install -r requirements.txt

# Ubuntu / Debian
sudo apt install python3 python3-pip
pip install -r requirements.txt
```
</details>

<details>
<summary><strong>Edge-case fallbacks</strong> — 99% of users don't need these</summary>

Two external tools exist as fallbacks for edge cases. **Most users will never need them** — install only if you hit one of the specific scenarios below.

| Fallback | Install only if… |
|----------|-----------------|
| [Node.js](https://nodejs.org/) 18+ | You need to import WeChat Official Account articles **and** `curl_cffi` (part of `requirements.txt`) has no prebuilt wheel for your Python + OS + CPU combination. In normal setups `web_to_md.py` handles WeChat directly through `curl_cffi`. |
| [Pandoc](https://pandoc.org/) | You need to convert legacy formats: `.doc`, `.odt`, `.rtf`, `.tex`, `.rst`, `.org`, or `.typ`. `.docx`, `.html`, `.epub`, `.ipynb` are handled natively by Python — no pandoc required. |

```bash
# macOS (only if the above conditions apply)
brew install node
brew install pandoc

# Ubuntu / Debian
sudo apt install nodejs npm
sudo apt install pandoc
```
</details>

### 2. Pick an AI Editor

| Tool | Rating | Notes |
|------|:------:|-------|
| **[Codex app](https://openai.com/codex/)** | ⭐⭐⭐ | Primary experience — open the HTML draft in-app, annotate slides in the browser, and iterate with the AI before rendering |
| **[Claude Code](https://claude.ai/)** | ⭐⭐⭐ | Best results — native Opus, largest context |
| [Cursor](https://cursor.sh/) / [VS Code + Copilot](https://code.visualstudio.com/) | ⭐⭐ | Good alternatives |
| Codebuddy IDE | ⭐⭐ | Best for Chinese models (Kimi 2.5, MiniMax-M2.7) |

### 3. Set Up

**Option A — Download ZIP** (no Git required): click **Code → Download ZIP** on the [GitHub page](https://github.com/hugohe3/ppt-master), then unzip.

**Option B — Git clone** (requires [Git](https://git-scm.com/downloads) installed):

```bash
git clone https://github.com/hugohe3/ppt-master.git
cd ppt-master
```

Then install dependencies:

```bash
pip install -r requirements.txt
```

To update later (Option B only): `python3 skills/ppt-master/scripts/update_repo.py`

### 4. Create

**Provide source materials (recommended):** Place your PDF, DOCX, images, or other files in the `projects/` directory, then tell the AI chat panel which files to use. The quickest way to get the path: right-click the file in your file manager or IDE sidebar → **Copy Path** (or **Copy Relative Path**) and paste it directly into the chat.

```
You: Please create a PPT from projects/q3-report/sources/report.pdf
```

**Paste content directly:** You can also paste text content straight into the chat window and the AI will generate a PPT from it.

```
You: Please turn the following into a PPT: [paste your content here...]
```

Either way, the AI will first confirm the design spec:

```
AI:  Sure. Let's confirm the design spec:
     [Template] B) Free design
     [Format]   PPT 16:9
     [Pages]    8-10 pages
     ...
```

The AI handles the full pipeline end-to-end — content analysis, design spec, SVG skeleton generation, support files, and HTML review draft — then **pauses for your review**. This is where you collaborate:

1. Open `preview/index.html` in the Codex app (the AI gives you a clickable link).
2. Flip through the slides and **annotate them directly in the browser** — comments are saved locally as you go. Adjust titles, takeaways, bullets, assets, page order, or style direction.
3. Click **"Copy all comments"** and paste them back into the chat.
4. The AI applies your comments, rebuilds the draft, and you repeat until the skeleton is right.

Once you confirm the structure is locked, the workflow continues internally into the native editable rebuild step to produce the final `.pptx`.

> **Default output:** a reviewable skeleton package in the project directory — `main_content.md`, `design_spec.md`, `style_sheet.md`, `asset_manifest.md`, `notes/`, `svg_output/`, and `preview/index.html` (the draft you review and annotate).
>
> **Final editable output:** once you approve the skeleton, ppt-master continues automatically into its built-in [native editable rebuild step](./skills/ppt-master/references/native-editable.md) to produce the final `.pptx`.
>
> **Legacy compatibility output:** `ppt-master` can still export `.pptx` directly through `svg_to_pptx.py`, but that is now an explicit compatibility path rather than the preferred editable-delivery route.

> **AI lost context?** Ask it to read `skills/ppt-master/SKILL.md`.

> **Something went wrong?** Check the **[FAQ](./docs/faq.md)** — it covers model selection, layout issues, export problems, and more. Continuously updated from real user reports.

### 5. AI Image Generation (Optional)

```bash
cp .env.example .env    # then edit with your API key
```

```env
IMAGE_BACKEND=gemini                        # required — must be set explicitly
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=gemini-3.1-flash-image-preview
```

Supported backends: `gemini` · `openai` · `qwen` · `zhipu` · `volcengine` · `stability` · `bfl` · `ideogram` · `siliconflow` · `fal` · `replicate`

Run `python3 skills/ppt-master/scripts/image_gen.py --list-backends` to see tiers. Environment variables override `.env`. Use provider-specific keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.) — global `IMAGE_API_KEY` is not supported.

> **Tip:** For best quality, generate images in [Gemini](https://gemini.google.com/) and select **Download full size**. Remove the watermark with `scripts/gemini_watermark_remover.py`.

---

## Documentation

| | Document | Description |
|---|----------|-------------|
| 🪟 | [Windows Installation](./docs/windows-installation.md) | Step-by-step setup guide for Windows users |
| 📖 | [SKILL.md](./skills/ppt-master/SKILL.md) | Core workflow and rules |
| 🧱 | [Native Editable Rebuild](./skills/ppt-master/references/native-editable.md) | Final native editable rebuild step (built into the main skill) |
| 📐 | [Canvas Formats](./skills/ppt-master/references/canvas-formats.md) | PPT 16:9, Xiaohongshu, WeChat, and 10+ formats |
| 🛠️ | [Scripts & Tools](./skills/ppt-master/scripts/README.md) | All scripts and commands |
| ❓ | [FAQ](./docs/faq.md) | Model selection, cost, layout troubleshooting, custom templates |


## License

[MIT](LICENSE)


[⬆ Back to Top](#ppt-master--ai-builds-review-first-presentation-skeletons-and-native-editable-pptx-from-any-document)
