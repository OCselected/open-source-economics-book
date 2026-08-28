# 开源的经济学 · 书籍仓库

*The Economics of Open Source* · 「开源之道」·适兕 · 2026

本仓库是《开源的经济学》书籍项目，同时也是「开源的经济学」12 讲幻灯片的唯一事实源。

## 架构

```
open-source-economics-book/          ← 书籍 + 幻灯片事实源
├── src/slides/                      ← LLM 渲染的 slide 源（12 讲，## Slide N 格式）
├── src/chapters/                    ← 书籍散文章节（12 章，对应 12 讲）
├── references/bibliography.bib      ← BibTeX 学术引用库
├── styles/book.latex                ← PDF 排版模板（开源之道风）
├── styles/book.css                  ← HTML/EPUB 样式
├── meta/book.yaml                   ← 元数据（12 讲映射、封面信息）
├── build/compile.py                 ← 多格式编译引擎
├── scripts/sync_from_book.sh        ← Hugo 站点的同步脚本
└── output/                          ← 构建产物（html/pdf/epub）
```

## 构建命令

| 命令 | 产物 | 说明 |
|------|------|------|
| `make html` | `output/open-source-economics.html` | 整书 HTML（pandoc） |
| `make pdf`  | `output/open-source-economics.pdf` | PDF（xelatex + ctex + biblatex） |
| `make epub` | `output/open-source-economics.epub` | EPUB3（pandoc） |
| `make slides` | `static/slides_decks/{deck}/pages/` | LLM 渲染 slide HTML |
| `make toc` | stdout | 列出所有章节/幻灯片状态 |

## 书籍风格

- **配色**：暖白 #F5F0E8 + 普鲁士蓝 #1B3B6B + 古铜色 #8B7355
- **字体**：Source Han Serif SC（衬线）+ Source Han Sans SC（无衬线）
- **排版**：12 讲对应 12 章，学术引用（BibTeX），大字号标题、宽松行距
- **视觉**：Bauhaus 几何装饰元素（圆、方、线），dark academic 调性

## Hugo 站点集成

`os-economic-slides` 仓库通过 `scripts/sync_from_book.sh` 自动同步本仓库的 slide 源：

```yaml
# os-economic-slides/.github/workflows/pages.yml 新增步骤：
- name: Sync slide sources from book repo
  run: bash scripts/sync_from_book.sh
```

## 目录

1. `src/slides/` — LLM slide 源（当前唯一事实源）
2. `src/chapters/` — 散文章节（待撰写）
3. `references/` — 学术引用
4. `styles/` — 排版样式
5. `build/` — 编译引擎
6. `meta/` — 书籍元数据
7. `Makefile` — 构建入口

## 依赖

- `pandoc` (>= 2.19) — HTML/PDF/EPUB 编译
- `xelatex` + `ctex` — PDF 中文排版
- `biber` + `biblatex` — BibTeX 文献管理
- `python3` + `PyYAML` — 编译引擎
- `sensenova-6.8-flash-lite` API — slide LLM 渲染

## 许可证

书籍内容：CC BY-NC-SA 4.0
