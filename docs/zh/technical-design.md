# 技术路线

[English](../technical-design.md) | [中文](./technical-design.md)

---

## 设计哲学 —— AI 是你的设计师，不是完工师

可审稿骨架包和后续重建出的 PPTX，本质上都还是**设计交付物**，不是一键完美成品。可以把它理解成建筑师的效果图加施工模型：AI 负责视觉方向、版式结构和大部分搭建工作，但最后一公里的判断仍然属于人。这个工具的目标是消除 90% 的从零开始工作量，而不是替代人的最终品味与判断。

**工具的上限是你的上限。** PPT Master 放大的是你已有的能力——你有设计感和内容判断力，它帮你快速落地；你不知道一个好的演示文稿应该长什么样，它也没法替你知道。输出的质量，归根结底是你自身品味与判断力的映射。

---

## 系统架构

```
用户输入 (PDF/DOCX/URL/Markdown)
    ↓
[源内容转换] → source_to_md/pdf_to_md.py / doc_to_md.py / web_to_md.py
    ↓
[创建项目] → project_manager.py init <项目名> --format <格式>
    ↓
[模板选项] A) 使用已有模板 B) 自由设计
    ↓
[需要新模板？] → 使用 /create-template 工作流单独创建
    ↓
[Strategist] 策略师 - 八项确认与设计规范
    ↓
[Image_Generator] 图片生成师（当选择 AI 生成时）
    ↓
[Skeleton Executor] 骨架执行阶段
    ├── SVG 草稿页面 → svg_output/
    ├── main_content.md / design_spec.md / style_sheet.md / asset_manifest.md
    ├── 演讲备注 → notes/total.md
    └── HTML 审稿页 → preview/index.html
    ↓
[人工审稿回路] → 在 preview/index.html 中确认结构、结论、素材与备注
    ↓
[Native Editable Rebuild] → repo 内的 ppt-master-native-editable
    ↓
输出: 以 PowerPoint 原生文本、形状、表格、媒体重建的最终可编辑 .pptx

兼容分支（仅显式要求时使用）：
    骨架草稿 / svg_output/
        ↓
    total_md_split.py → finalize_svg.py → svg_to_pptx.py
        ↓
    exports/<timestamp>.pptx + exports/<timestamp>_svg.pptx
```

---

## 技术流程

**默认流程：AI 先生成可审稿的 SVG 骨架，再由单独的 native-editable 重建生成最终 PPTX。**

整个流程现在分为四个阶段：

**第一阶段：内容理解与设计规划**
源文档（PDF/DOCX/URL/Markdown）经过转换变为结构化文本，由 Strategist 角色完成内容分析、页面规划和设计风格确认，输出完整的设计规格。

**第二阶段：骨架草稿生成**
Executor 角色逐页生成 SVG 草稿，并同步维护 `main_content.md`、`style_sheet.md`、`asset_manifest.md`、`notes/total.md`。这个阶段的产物是**审稿包**，而非成品。

**第三阶段：人工审稿回路**
通过 `preview/index.html` 审核结构、takeaway、素材和备注，在尝试最终 PowerPoint 构建前把内容骨架先锁定。

**第四阶段：原生可编辑重建**
骨架确认后，由下游 `ppt-master-native-editable` skill 用 PowerPoint 原生对象重建最终 `.pptx`。这是当前优先推荐的可编辑交付路径。

**兼容分支：工程化转换**
`svg_to_pptx.py` 仍然存在，但它现在是兼容导出路径，不再是默认的最终可编辑交付方式。

---

## 为什么是 SVG？

SVG 仍然是这套草稿流程的核心枢纽。这个选择是通过逐一排除其他方案得出的。

**直接生成 DrawingML** 看起来最直接——跳过中间格式，AI 直接输出 PowerPoint 的底层 XML。但 DrawingML 极其繁琐，一个简单的圆角矩形就需要数十行嵌套 XML，AI 的训练数据中远少于 SVG，生成质量不稳定，调试几乎无法肉眼完成。

**HTML/CSS** 是 AI 最熟悉的格式之一，但 HTML 和 PowerPoint 有根本不同的世界观。HTML 描述的是**文档**——标题、段落、列表，元素的位置由内容流动决定。PowerPoint 描述的是**画布**——每个元素都是独立的、绝对定位的对象，没有流，没有上下文关系。这不只是排版计算的问题，而是两种完全不同的内容组织方式之间的鸿沟。就算解决了浏览器排版引擎的问题（Chromium 用数百万行代码做这件事），HTML 里的一个 `<table>` 也没法自然地变成 PPT 里的几个独立形状。

**WMF/EMF**（Windows 图元文件）是微软自家的原生矢量图形格式，与 DrawingML 有直接的血缘关系——理论上转换损耗最小。但 AI 对它几乎没有训练数据，这条路死在起点。值得注意的是：连微软自家的格式在这里都输给了 SVG。

**SVG 作为嵌入图片** 是最简单的路线——把整张幻灯片渲染成图片塞进 PPT。但这样完全丧失可编辑性，形状变成像素，文字无法选中，颜色无法修改，和截图没有本质区别。

SVG 胜出，因为它与 DrawingML 拥有相同的世界观：两者都是绝对坐标的二维矢量图形格式，共享同一套概念体系：

| SVG | DrawingML |
|---|---|
| `<path d="...">` | `<a:custGeom>` |
| `<rect rx="...">` | `<a:prstGeom prst="roundRect">` |
| `<circle>` / `<ellipse>` | `<a:prstGeom prst="ellipse">` |
| `transform="translate/scale/rotate"` | `<a:xfrm>` |
| `linearGradient` / `radialGradient` | `<a:gradFill>` |
| `fill-opacity` / `stroke-opacity` | `<a:alpha>` |

转换不是格式错配，而是两种方言之间的精确翻译。

SVG 也是唯一同时满足草稿阶段所有角色需要的格式：**AI 能可靠地生成它，人能在任意浏览器里直接预览和调试，脚本能精确地转换或重解释它**。这也是为什么 SVG 仍然是审稿阶段的视觉意图载体，即使当前优先推荐的最终可编辑交付路径已经变成下游 native rebuild，而不是直接转换。
