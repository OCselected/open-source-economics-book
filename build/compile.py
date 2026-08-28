#!/usr/bin/env python3
"""
开源的经济学 — 多格式编译引擎

make html     → output/opensources-economics.html        (整书 HTML)
make pdf      → output/opensources-economics.pdf         (xelatex)
make epub     → output/opensources-economics.epub        (pandoc EPUB3)
make toc      → 生成目录页 + 各章节页面
make slides   → 生成 slide HTML (LLM 渲染, 需 API)
make all      → html + pdf + epub

依赖:
  - pandoc (>= 2.19)
  - xelatex + ctex + biblatex + biber (pdf 用)
  - python3 + PyYAML
"""

import os, re, sys, json, subprocess, shutil, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_SLIDES = ROOT / 'src' / 'slides'
SRC_CHAPTERS = ROOT / 'src' / 'chapters'
REFERENCES = ROOT / 'references'
STYLES = ROOT / 'styles'
OUTPUT = ROOT / 'output'
STATIC = ROOT / 'static'
META = ROOT / 'meta' / 'book.yaml'

SYSTEM_PROMPT = """You are a slide designer. Generate ONE complete standalone HTML document for a single slide.

Style system (Bauhaus academic):
- canvas: 1600 x 900 exactly
- background: warm parchment #F5F0E8
- primary ink: Prussian blue #1B3B6B
- secondary: copper #8B7355, muted gray #555
- fonts: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', serif for headings; 'Noto Sans SC' for body
- Bauhaus geometric composition: circles, squares, lines as decoration
- dark academic tone, restrained, intellectual
- no emoji, no icons, no gradients except subtle parchment texture

HTML contract:
- output ONLY the HTML document, no markdown fences, no explanation
- <!DOCTYPE html><html><head><meta charset="UTF-8"><title>...</title><style>...</style></head><body>...</body></html>
- body/html must set width:1600px; height:900px; overflow:hidden; margin:0
- all positioning absolute or flex within 1600x900
- no viewport units (vw/vh), no @media queries, no transform:scale
"""


# ── Helpers ──────────────────────────────────────────────────────────────

def run(cmd, cwd=None, check=True):
    """Run shell command, return stdout."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd or ROOT)
    if check and r.returncode != 0:
        print(f'FAIL: {cmd}')
        print(r.stderr)
        sys.exit(1)
    return r.stdout


def read_md(path):
    return Path(path).read_text(encoding='utf-8')


def parse_slide_deck(text):
    """Parse slide deck .md into (header, [(num, content), ...])."""
    header_m = re.match(r'^(.*?)(?=\n## Slide \d+)', text, re.DOTALL)
    header = header_m.group(1).strip() if header_m else ''
    slides = []
    for m in re.finditer(r'## Slide (\d+)\s*(.*?)(?=\n## Slide \d+|\Z)', text, re.DOTALL):
        slides.append((int(m.group(1)), m.group(2).strip()))
    return header, slides


def parse_bib_citations(text):
    """Find [^key] citations and return {key: line_number}."""
    return {m.group(1): m.start() for m in re.finditer(r'\[\\?^([a-zA-Z0-9_]+)\]', text)}


# ── Targets ──────────────────────────────────────────────────────────────

def target_html():
    """Compile 12 chapters + references into a single HTML book."""
    out = OUTPUT / 'open-source-economics.html'
    OUTPUT.mkdir(exist_ok=True)

    # Build chapter HTML from individual .md files
    chapters = sorted(SRC_CHAPTERS.glob('*.md'))
    if not chapters:
        print('WARN: no chapter files found, building from slide sources as placeholders')
        # Fallback: create simple chapter list from slide files
        slides_files = sorted(SRC_SLIDES.glob('*.md'))
        parts = [generate_cover_html()]
        parts.append(generate_toc_html(slides_files))
        for f in slides_files:
            parts.append(generate_slide_chapter_html(f))
        parts.append(generate_references_html())
        out.write_text('\n'.join(parts), encoding='utf-8')
        print(f'HTML: {out} (fallback: from slides)')
        return

    parts = [generate_cover_html()]
    parts.append(generate_toc_html(chapters))
    for ch in chapters:
        parts.append(generate_chapter_html(ch))
    parts.append(generate_references_html())
    out.write_text('\n'.join(parts), encoding='utf-8')
    print(f'HTML: {out} ({len(chapters)} chapters)')


def generate_cover_html():
    title = '开源的经济学'
    subtitle = 'The Economics of Open Source'
    author = '「开源之道」·适兕'
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>{title}</title>
<link rel="stylesheet" href="book.css">
</head><body>
<section class="cover">
  <div class="cover-deco cover-deco-1"></div>
  <div class="cover-deco cover-deco-2"></div>
  <h1>{title}</h1>
  <div class="subtitle">{subtitle}</div>
  <div class="author">{author}</div>
  <div class="year">MMXXVI</div>
</section>"""


def generate_toc_html(files):
    items = ''
    for i, f in enumerate(files):
        num = i
        name = f.stem.replace('-', ' ').replace('_', ' ').strip()
        slug = f.stem
        items += f'<li><span class="toc-num">{num:02d}</span><a href="#{slug}">{name}</a></li>\n'
    return f"""<div class="container" id="toc">
<h1>目录</h1>
<ul class="toc-list">
{items}
</ul>
</div>"""


def generate_chapter_html(md_path):
    content = read_md(md_path)
    # Strip Pandoc-style citation keys [^key] → numbered footnotes later
    slug = md_path.stem
    # Simple markdown → HTML (full pandoc would be better; use it in target_html_pandoc)
    title = slug.replace('-', ' ').replace('_', ' ').strip()
    # Use pandoc for proper rendering
    try:
        html = run(
            f"pandoc {md_path} --from markdown+citeproc --to html --standalone=false "
            f"--metadata title='{title}' "
            f"--filter pandoc-citeproc "
            f"--bibliography {REFERENCES / 'bibliography.bib'} 2>/dev/null || "
            f"pandoc {md_path} --from markdown --to html --standalone=false"
        )
    except Exception:
        html = content.replace('\n', '<br>')
    return f"""<div class="container" id="{slug}">
<h1>{title}</h1>
{html}
</div>"""


def generate_slide_chapter_html(md_path):
    """Generate a chapter page from slide source (when no prose chapter exists yet)."""
    slug = md_path.stem
    header, slides = parse_slide_deck(read_md(md_path))
    title = slug.replace('-', ' ').replace('_', ' ').strip()
    body = '<h2>Slide 概览</h2><ul>\n'
    for num, content in slides[:5]:
        short = content[:80].replace('\n', ' ')
        body += f'<li><strong>Slide {num}</strong>: {short}...</li>\n'
    if len(slides) > 5:
        body += f'<li>...共 {len(slides)} 张 slide（散文章节待撰写）</li>\n'
    body += '</ul>'
    return f'<div class="container" id="{slug}"><h1>{title}</h1>{body}</div>'


def generate_references_html():
    return f"""<div class="container references">
<h1>参考文献</h1>
<p>参考文献库见 <code>references/bibliography.bib</code>（{len(list(REFERENCES.glob('*.bib')))} 篇）</p>
</div>
</body></html>"""


def target_pdf():
    """Compile book PDF via Pandoc + XeLaTeX."""
    out_pdf = OUTPUT / 'open-source-economics.pdf'
    OUTPUT.mkdir(exist_ok=True)

    # Collect chapter content into one pandoc doc
    chapters = sorted(SRC_CHAPTERS.glob('*.md'))
    slides_files = sorted(SRC_SLIDES.glob('*.md'))

    if chapters:
        # Join chapters with pagebreaks
        tmp = OUTPUT / '_book_combined.md'
        lines = [
            f'# 开源的经济学\n',
            f'_The Economics of Open Source_\n',
            f'_「开源之道」· 适兕 · MMXXVI_\n\n',
            '\\\\[pagebreak]\n',
        ]
        for ch in chapters:
            lines.append(read_md(ch))
            lines.append('\n\n\\\\[pagebreak]\n')
        tmp.write_text('\n'.join(lines), encoding='utf-8')
        src_file = str(tmp)
    else:
        # Fallback: generate from slide files
        tmp = OUTPUT / '_book_combined.md'
        lines = [
            '# 开源的经济学\n',
            '_The Economics of Open Source_\n\n',
            '\\\\[pagebreak]\n',
        ]
        for f in slides_files:
            header, slides = parse_slide_deck(read_md(f))
            title = f.stem.replace('-', ' ').strip()
            lines.append(f'## 第 {f.stem.split("-")[0]} 讲 · {title}\n')
            for num, content in slides:
                lines.append(f'### Slide {num}\n\n{content}\n')
            lines.append('\n\\\\[pagebreak]\n')
        tmp.write_text('\n'.join(lines), encoding='utf-8')
        src_file = str(tmp)

    # Pandoc → LaTeX → XeLaTeX
    tmp_latex = OUTPUT / '_book.tex'
    run(
        f"pandoc {src_file} --to latex --template={STYLES / 'book.latex'} "
        f"--metadata pagetitle='开源的经济学' "
        f"--bibliography={REFERENCES / 'bibliography.bib'} "
        f"--citeproc --number-sections "
        f"--output {tmp_latex}"
    )
    # XeLaTeX + Biber
    try:
        # First pass
        run(f"xelatex -interaction=nonstopmode -output-directory={OUTPUT} {tmp_latex}")
        # Biber
        run(f"biber _book")
        # Two more passes for cross-refs
        run(f"xelatex -interaction=nonstopmode -output-directory={OUTPUT} {tmp_latex}")
        run(f"xelatex -interaction=nonstopmode -output-directory={OUTPUT} {tmp_latex}")
        shutil.move(str(OUTPUT / '_book.pdf'), str(out_pdf))
        print(f'PDF: {out_pdf}')
    except Exception as e:
        print(f'PDF build FAILED: {e}')
        print('PDF requires: pandoc, xelatex, ctex, biber, biblatex')
        # Leave combined.md for manual build
        print(f'  Intermediate Markdown: {tmp}')
        print(f'  LaTeX template: {STYLES / "book.latex"}')


def target_epub():
    """Compile book EPUB3 via Pandoc."""
    out_epub = OUTPUT / 'open-source-economics.epub'
    OUTPUT.mkdir(exist_ok=True)

    chapters = sorted(SRC_CHAPTERS.glob('*.md'))
    slides_files = sorted(SRC_SLIDES.glob('*.md'))

    tmp = OUTPUT / '_book_epub.md'
    if chapters:
        lines = [
            f'# 开源的经济学\n',
            f'_The Economics of Open Source · 「开源之道」·适兕 · 2026_\n\n',
        ]
        for ch in chapters:
            lines.append(read_md(ch))
            lines.append('\n\n\\newpage\n')
        tmp.write_text('\n'.join(lines), encoding='utf-8')
    else:
        lines = [
            '# 开源的经济学\n',
            '_The Economics of Open Source_\n\n',
        ]
        for f in slides_files:
            header, slides = parse_slide_deck(read_md(f))
            title = f.stem.replace('-', ' ').strip()
            lines.append(f'## {title}\n')
            for num, content in slides:
                lines.append(f'### Slide {num}\n\n{content}\n')
            lines.append('\n')
        tmp.write_text('\n'.join(lines), encoding='utf-8')

    run(
        f"pandoc {tmp} --to epub3 "
        f"--metadata title='开源的经济学' "
        f"--metadata author='「开源之道」·适兕' "
        f"--metadata lang='zh-CN' "
        f"--css={STYLES / 'book.css'} "
        f"--bibliography={REFERENCES / 'bibliography.bib'} "
        f"--citeproc "
        f"--number-sections "
        f"--output {out_epub}"
    )
    print(f'EPUB: {out_epub}')


def target_slides():
    """Render slide HTML from src/slides/*.md via LLM (incremental)."""
    from model_client import llm
    total = 0
    for src in sorted(SRC_SLIDES.glob('*.md')):
        deck_id = src.stem
        out_dir = STATIC / 'slides_decks' / deck_id / 'pages'
        out_dir.mkdir(parents=True, exist_ok=True)

        header, slides = parse_slide_deck(read_md(src))
        for num, content in slides:
            page_path = out_dir / f'page_{num:03d}.html'
            if page_path.exists() and page_path.stat().st_size > 500:
                continue
            print(f'  [{deck_id}] slide {num}...', end=' ', flush=True)
            prompt = f"""Context:
{header}

Generate the HTML for this slide:
{content}
"""
            raw = llm(SYSTEM_PROMPT, prompt, timeout=300, model='sensenova-6.8-flash-lite')
            raw = re.sub(r'^```html\s*', '', raw, flags=re.IGNORECASE | re.MULTILINE)
            raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE)
            page_path.write_text(raw, encoding='utf-8')
            print(f'OK ({len(raw)} chars)')
            total += 1
            time.sleep(0.5)
    print(f'Slides: {total} slide(s) rendered → {STATIC}/slides_decks/')


def target_toc():
    """List all chapters and slides with status."""
    chapters = sorted(SRC_CHAPTERS.glob('*.md'))
    slides_files = sorted(SRC_SLIDES.glob('*.md'))

    print(f'开源的经济学 · 内容清单')
    print(f'{"─"*60}')
    print(f'\n章节 (src/chapters/): {len(chapters)}')
    for ch in chapters:
        lines = ch.read_text(encoding='utf-8').count('\n')
        print(f'  ✓ {ch.stem:<35} ({lines:>3} lines)')

    print(f'\nSlide 源 (src/slides/): {len(slides_files)}')
    for sf in slides_files:
        _, slides = parse_slide_deck(sf.read_text(encoding='utf-8'))
        page_dir = STATIC / 'slides_decks' / sf.stem / 'pages'
        rendered = len(list(page_dir.glob('*.html'))) if page_dir.exists() else 0
        print(f'  {sf.stem:<35} ({len(slides):>2} slides, {rendered} rendered)')
    print(f'\nBibTeX: {len(list(REFERENCES.glob("*.bib")))} bibliography files')


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    targets = {
        'html': target_html,
        'pdf': target_pdf,
        'epub': target_epub,
        'slides': target_slides,
        'toc': target_toc,
    }
    cmd = sys.argv[1]
    if cmd in ('all',):
        target_html()
        target_pdf()
        target_epub()
    elif cmd in targets:
        targets[cmd]()
    else:
        print(f'Unknown target: {cmd}. Available: {list(targets.keys())}')
        sys.exit(1)
