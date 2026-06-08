# PPT Master — AI 先生成可审稿骨架，再生成原生可编辑 PPTX

[![Version](https://img.shields.io/badge/version-v2.3.0-blue.svg)](https://github.com/hugohe3/ppt-master/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/hugohe3/ppt-master.svg)](https://github.com/hugohe3/ppt-master/stargazers)
[![AtomGit stars](https://atomgit.com/hugohe3/ppt-master/star/badge.svg)](https://atomgit.com/hugohe3/ppt-master)

[English](./README.md) | 中文

> **原官方渠道 —** 本项目**仅**在 [GitHub](https://github.com/hugohe3/ppt-master)（主仓库）和 [AtomGit](https://atomgit.com/hugohe3/ppt-master)（自动同步镜像）发布。其他平台上的转发版本均为非官方版本，不由作者维护。遵循 MIT 协议——使用需保留署名。

---
丢进一份 PDF、DOCX、网址或 Markdown，先拿回一份**可审稿的演示骨架**（`main_content.md`、`design_spec.md`、`preview/index.html`），结构确认后再生成**原生可编辑的 PowerPoint**。

> **运作方式** —— PPT Master 是一套为**人机协作**设计的工作流（一个 "skill"），主要在 **Codex app** 中使用（也支持 Claude Code / Cursor / VS Code + Copilot 等 AI IDE）。你在对话框里跟 AI 说"用这份 PDF 做一份 PPT"，AI 会先在你本机生成可审稿骨架和 **HTML 草稿**；然后你在 Codex app 里直接打开这份 HTML 草稿，**逐页翻看并在浏览器里批注**（改标题、改收口、换素材、调页序），点 **"复制全部批注"**，把批注粘回对话框。AI 据此修改并重新生成草稿——你和它一轮轮迭代，直到结构满意。**只有在你确认之后**，同一个工作流才会自动衔接进 native-editable 重建步骤产出最终 `.pptx`。你不写任何代码——IDE 只是你和 AI 对话的地方。
>
> **你要做的**：装 Python、装一个 AI IDE、把资料放进来。第一次配置约 15 分钟；之后每做一份 PPT 大约 10–20 分钟的聊天。

市面上不缺 AI PPT 工具——缺的是一个**生成出来的 PPT 能真正拿去用**的工具。我每天都在做 PPT，但大部分产品输出的是图片或网页截图，好看但改不了；要么就是基础到只有文本框和列表。你还得按月充会员，把文件传到别人的服务器上，被锁在某个平台里。

PPT Master 不一样：

- **先审结构，再出成品** — 不假设 AI 一次就能完成所有细修，而是先把结构、结论、素材审清楚，再生成最终可编辑成品
- **你全程在环** — 在 Codex app 里审阅 HTML 草稿，直接在浏览器里批注每一页，把批注复制回对话框与 AI 迭代，结构锁定后才进行最终渲染
- **真正的 PPT** — 推荐的最终交付路径是 native editable 重建，而不是截图式导出或网页快照
- **成本透明可控** — 工具免费开源，唯一成本是你自己的 AI 编辑器，花了多少钱你清清楚楚。VS Code Copilot 下最低 **$0.08/份**
- **数据不出本地** — 你的文件不应该为了做一份 PPT 就被上传到别人的服务器。除与 AI 模型的对话外，全流程在你的电脑上完成
- **不锁定平台** — 你的工作流不应该被任何一家公司绑架。Claude Code、Cursor、VS Code Copilot 等均可驱动；Claude、GPT、Gemini、Kimi 等模型均可使用


## 快速开始

### 1. 前置条件

**只需装 Python 即可。** 其余依赖通过 `pip install -r requirements.txt` 一次装齐。

| 依赖 | 是否必须 | 用途 |
|------|:--------:|------|
| [Python](https://www.python.org/downloads/) 3.10+ | ✅ **必需** | 核心运行时——唯一真正需要安装的东西 |

> **一句话总结** — 装好 Python，跑一行 `pip install -r requirements.txt`，就可以开始生成 PPT 了。

<details open>
<summary><strong>Windows</strong> — 请看专门的手把手安装指南 ⚠️</summary>

Windows 需要一些额外步骤（PATH 设置、执行策略等）。我们为 Windows 用户写了一份**手把手安装指南**：

**📖 [Windows 安装指南](./docs/zh/windows-installation.md)** — 从零到跑通第一份 PPT，10 分钟搞定。

简要流程：从 [python.org](https://www.python.org/downloads/) 下载 Python → **安装时勾选 "Add to PATH"** → `pip install -r requirements.txt` → 完成。
</details>

<details>
<summary><strong>macOS / Linux</strong> — 安装即用</summary>

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
<summary><strong>边缘场景备用方案</strong> — 99% 的用户用不到</summary>

下面两个外部程序只作为极端场景的兜底。**绝大多数用户根本不需要装**，只有遇到以下具体场景才装：

| 备用方案 | 只在以下情况才装 |
|---------|-----------------|
| [Node.js](https://nodejs.org/) 18+ | 你需要抓取微信公众号文章，**且**你的 Python + 系统 + CPU 组合下 `curl_cffi`（`requirements.txt` 里已默认安装）没有预编译 wheel。正常安装下 `web_to_md.py` 已能通过 `curl_cffi` 直接抓微信。 |
| [Pandoc](https://pandoc.org/) | 你需要转 `.doc`、`.odt`、`.rtf`、`.tex`、`.rst`、`.org`、`.typ` 这些小众格式。`.docx`、`.html`、`.epub`、`.ipynb` 已由 Python 原生处理，不需要 pandoc。 |

```bash
# macOS（仅在上述条件成立时才装）
brew install node
brew install pandoc

# Ubuntu / Debian
sudo apt install nodejs npm
sudo apt install pandoc
```
</details>

### 2. 选择 AI 编辑器

| 工具 | 推荐度 | 说明 |
|------|:------:|------|
| **[Codex app](https://openai.com/codex/)** | ⭐⭐⭐ | 主力体验——在 app 内打开 HTML 草稿、浏览器里批注每页、与 AI 迭代后再渲染 |
| **[Claude Code](https://claude.ai/)** | ⭐⭐⭐ | 效果最佳——原生 Opus，上下文最充裕 |
| [Cursor](https://cursor.sh/) / [VS Code + Copilot](https://code.visualstudio.com/) | ⭐⭐ | 不错的替代方案 |
| Codebuddy IDE | ⭐⭐ | 国产模型最佳选择（Kimi 2.5、MiniMax-M2.7） |

### 3. 配置项目

**方式 A — 下载 ZIP**（无需安装 Git）：
[GitHub](https://github.com/hugohe3/ppt-master) → **Code → Download ZIP** · [AtomGit](https://atomgit.com/hugohe3/ppt-master) → **克隆/下载 → 下载ZIP**（国内网速更快）

**方式 B — Git clone**（需先安装 [Git](https://git-scm.com/downloads)）：

```bash
# GitHub
git clone https://github.com/hugohe3/ppt-master.git
# AtomGit（国内网速更快）
git clone https://atomgit.com/hugohe3/ppt-master.git
cd ppt-master
```

然后安装依赖：

```bash
pip install -r requirements.txt
```

日常更新（仅方式 B）：`python3 skills/ppt-master/scripts/update_repo.py`

### 4. 开始创作

**提供原始材料（推荐）：** 将 PDF、DOCX、图片等文件放入 `projects/` 目录下，在 AI 聊天面板中告诉它使用哪些文件。获取路径的最快方式：在文件管理器或 IDE 侧边栏中右键文件 → **复制路径**（Copy Path / Copy Relative Path），直接粘贴进聊天框。

```
你：请用 projects/q3-report/sources/report.pdf 这份文件生成一份 PPT
```

**直接输入内容：** 也可以把文字内容直接粘贴进聊天窗口，AI 会根据这些内容生成 PPT。

```
你：请根据以下内容制作成 PPT：[粘贴你的文字内容...]
```

两种方式下 AI 都会先确认设计规范：

```
AI：好的，先确认设计规范：
   [模板] B) 自由设计
   [格式] PPT 16:9
   [页数] 8-10 页
   ...
```

AI 端到端跑完整条流水线——内容分析、设计规范、SVG 骨架、配套 handoff 文件和 HTML 审稿页——然后**停下来等你审稿**。这一步就是人机协作的核心：

1. 在 Codex app 里打开 `preview/index.html`（AI 会给你一个可点击的链接）。
2. 逐页翻看并**直接在浏览器里批注**——批注会随手保存在本地。可调整标题、收口、要点、素材、页序或风格方向。
3. 点 **"复制全部批注"**，把批注粘回对话框。
4. AI 据此修改、重新生成草稿，如此往复，直到骨架满意为止。

结构锁定后，工作流会自动衔接进 native editable 重建阶段产出最终 `.pptx`。

> **默认输出：** 项目目录中的可审稿骨架包——`main_content.md`、`design_spec.md`、`style_sheet.md`、`asset_manifest.md`、`notes/`、`svg_output/` 和 `preview/index.html`（你审阅并批注的草稿）。
>
> **最终可编辑输出：** 骨架确认后，ppt-master 自动进入内置的[原生可编辑重建步骤](./skills/ppt-master/references/native-editable.md)生成最终 `.pptx`。
>
> **兼容导出：** `ppt-master` 仍可通过 `svg_to_pptx.py` 直接导出 `.pptx`，但这已经是显式兼容路径，不再是默认的可编辑交付方式。

> **AI 迷失上下文？** 让它先读 `skills/ppt-master/SKILL.md`。

> **遇到问题？** 查看 **[常见问题](./docs/zh/faq.md)** — 涵盖模型选择、排版问题、导出异常等，基于真实用户反馈持续更新。

### 5. AI 生图配置（可选）

```bash
cp .env.example .env    # 然后填入你的 API Key
```

```env
IMAGE_BACKEND=gemini                        # 必填——必须显式指定
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=gemini-3.1-flash-image-preview
```

支持的后端：`gemini` · `openai` · `qwen` · `zhipu` · `volcengine` · `stability` · `bfl` · `ideogram` · `siliconflow` · `fal` · `replicate`

运行 `python3 skills/ppt-master/scripts/image_gen.py --list-backends` 查看分级。环境变量优先于 `.env`。使用各家独立的 Key（`GEMINI_API_KEY`、`OPENAI_API_KEY` 等）——不支持全局 `IMAGE_API_KEY`。

> **建议：** 高质量图片推荐在 [Gemini](https://gemini.google.com/) 中生成并选择 **Download full size**。去水印可用 `scripts/gemini_watermark_remover.py`。

---

## 文档导航

| | 文档 | 说明 |
|---|------|------|
| 🪟 | [Windows 安装指南](./docs/zh/windows-installation.md) | Windows 用户手把手安装教程 |
| 📖 | [SKILL.md](./skills/ppt-master/SKILL.md) | 核心流程与规则 |
| 🧱 | [原生可编辑重建](./skills/ppt-master/references/native-editable.md) | 骨架审稿后的最终原生可编辑重建步骤（已并入主 skill） |
| 📐 | [画布格式](./skills/ppt-master/references/canvas-formats.md) | PPT 16:9、小红书、朋友圈等 10+ 种格式 |
| 🛠️ | [脚本与工具](./skills/ppt-master/scripts/README.md) | 所有脚本和命令 |
| ❓ | [常见问题](./docs/zh/faq.md) | 模型选择、费用、排版问题排查、自定义模板 |


## 开源协议

[MIT](LICENSE)


[⬆ 回到顶部](#ppt-master--ai-先生成可审稿骨架再生成原生可编辑-pptx)
