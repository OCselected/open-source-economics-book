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
        parts.append(generate_references_html_pdf())
        out.write_text('\n'.join(parts), encoding='utf-8')
        print(f'HTML: {out} (fallback: from slides)')
        return

    parts = [generate_cover_html()]
    parts.append(generate_toc_html(chapters))
    for ch in chapters:
        parts.append(generate_chapter_html(ch))
    parts.append(generate_references_html_pdf())
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
    content = md_path.read_text(encoding='utf-8')
    # Strip YAML frontmatter before pandoc
    body = re.sub(r'^---\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
    # Write temp file without frontmatter
    tmp = OUTPUT / f'_ch_{md_path.stem}.md'
    tmp.write_text(body, encoding='utf-8')
    # Convert markdown to HTML
    try:
        html = run(
            f"pandoc {tmp} --from markdown --to html 2>/dev/null"
        )
    except Exception:
        html = _md_to_html(body)
    title = ''
    m = re.search(r'title:\s*"(.+?)"', content)
    if m:
        title = m.group(1)
    slug = md_path.stem
    return f'<div class="container" id="{slug}"><h1>{title}</h1>{html}</div>'


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


def generate_references_html_pdf():
    return f"""<div class="page" id="references">
<h2>参考文献</h2>
<p>参考文献库见 <code>references/bibliography.bib</code></p>
</div>
</body></html>"""


# ── PDF-specific helpers ────────────────────────────────────────────────

def generate_cover_html_pdf():
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<style>
@page {
  size: A4;
  margin: 0;
}
html, body {
  margin: 0; padding: 0;
  font-family: 'Source Han Serif SC', 'Noto Serif SC', 'Songti SC', 'STSong', serif;
  color: #1A1A1A;
}
.page {
  padding: 60px 60px;
  page-break-after: always;
}
.cover-page {
  background: #1B3B6B;
  color: #F5F0E8;
  text-align: center;
  height: 100vh;
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  position: relative;
  padding: 0;
}
.cover-page h1 {
  font-size: 56px; font-weight: 700;
  letter-spacing: 0.2em; margin-bottom: 16px;
  color: #F5F0E8;
}
.cover-page .subtitle {
  font-style: italic; font-size: 22px;
  color: #D9A441; letter-spacing: 0.1em;
  margin-bottom: 60px;
}
.cover-page .author {
  font-size: 18px; opacity: 0.9;
}
.cover-page .year {
  margin-top: 12px; font-size: 16px;
  letter-spacing: 0.6em; color: #D9A441;
}
.cover-deco-circle {
  position: absolute; width: 300px; height: 300px;
  border-radius: 50%; border: 2px solid #D9A441;
  opacity: 0.3;
}
.cover-deco-1 { top: -80px; left: -80px; }
.cover-deco-2 { bottom: -80px; right: -80px; }
.cover-deco-square {
  position: absolute; width: 200px; height: 200px;
  border: 1px solid #F5F0E8; opacity: 0.2;
}
.cover-deco-3 { top: 50px; right: 100px; }
/* TOC */
.toc-page h2 {
  color: #1B3B6B; font-size: 28px;
  border-bottom: 2px solid #8B7355; padding-bottom: 8px;
  margin-bottom: 20px;
}
.toc-page ul { list-style: none; padding: 0; }
.toc-page li {
  display: flex; align-items: baseline;
  padding: 8px 0; border-bottom: 1px dotted #8B7355;
}
.toc-page .toc-num {
  color: #8B7355; font-weight: 700; margin-right: 16px;
  min-width: 36px; font-size: 14px;
}
.toc-page .toc-title {
  color: #1B3B6B; font-size: 16px; flex: 1;
}
/* Chapter */
.chapter-page h2 {
  color: #1B3B6B; font-size: 26px;
  border-bottom: 2px solid #8B7355; padding-bottom: 8px;
}
.chapter-page h3 {
  color: #8B7355; font-size: 18px; margin-top: 20px;
}
.chapter-page p {
  font-size: 14px; line-height: 1.85;
  text-align: justify; text-indent: 2em;
  margin-bottom: 10px;
}
.chapter-page blockquote {
  border-left: 3px solid #8B7355; padding: 10px 20px;
  margin: 16px 0; font-style: italic;
  background: #EFE8D8; color: #1B3B6B;
  font-size: 13px;
}
.chapter-page ul { font-size: 13px; margin: 8px 0; padding-left: 28px; }
.chapter-page li { margin-bottom: 4px; }
.chapter-page table {
  width: 100%; border-collapse: collapse;
  margin: 16px 0; font-size: 12px;
}
.chapter-page th, .chapter-page td {
  border: 1px solid #8B7355; padding: 6px 8px; text-align: left;
}
.chapter-page th { background: #1B3B6B; color: #F5F0E8; }
</style></head><body>
<div class="cover-page">
  <div class="cover-deco-circle cover-deco-1"></div>
  <div class="cover-deco-circle cover-deco-2"></div>
  <div class="cover-deco-square cover-deco-3"></div>
  <h1>开源的<br/>经济学</h1>
  <div class="subtitle">The Economics of Open Source</div>
  <div class="author">「开源之道」·适兕</div>
  <div class="year">MMXXVI</div>
</div>"""


def generate_toc_html_pdf(chapters):
    items = ''
    for i, ch in enumerate(chapters):
        title = ch.stem.replace('-', ' ').replace('_', ' ').strip()
        # Try to extract chapter title from frontmatter
        content = ch.read_text(encoding='utf-8')
        fm_title = ''
        m = re.search(r'title:\s*"(.+?)"', content)
        if m:
            fm_title = m.group(1)
        items += f'<li><span class="toc-num">{i:02d}</span><span class="toc-title">{fm_title}</span></li>\n'
    return f"""<div class="page toc-page">
<h2>目  录</h2>
<ul>
{items}
</ul>
</div>"""


def generate_chapter_html_pdf(md_path):
    content = md_path.read_text(encoding='utf-8')
    # Strip YAML frontmatter
    body = re.sub(r'^---\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
    # Basic markdown → HTML
    html = _md_to_html(body)
    # Extract chapter title
    fm_title = ''
    m = re.search(r'title:\s*"(.+?)"', content)
    if m:
        fm_title = m.group(1)
    slug = md_path.stem
    return f"""<div class="page chapter-page" id="{slug}">
<h2>{fm_title}</h2>
{html}
</div>"""


def generate_coda_html():
    return """<div class="page chapter-page" id="coda">
<h2>结语：开源经济学，也是 The Economics of Open Source</h2>
<p>当我们回顾这 12 讲的内容——软件生产、知识财产、商业模式、劳动力市场、交易成本、组织治理、文化作用、政治经济学、信息规则、排他与容他、劳动报酬——我们实际上是在回答一个被主流经济学长期忽视的问题：</p>
<blockquote>在没有雇佣关系、没有层级命令、没有价格信号的前提下，人类如何实现大规模、高可靠、持续几十年的协作？</blockquote>
<p>这个问题不是边缘问题。它和 The Economics of Crime（Becker）、The Economics of AI（Agrawal）、The Economics of Knowledge（Foray）、The Economics of the Commons（Ostrom）、Doughnut Economics（Raworth）属于同一个家族。</p>
<p><strong>开源经济学属于这个家族。</strong>它不是关于钱的，而是关于选择的。开源经济学不是关于代码的，而是关于不靠钱和权也能协作的选择。</p>
<blockquote>——「开源之道」·适兕</blockquote>
</div>"""


def _md_to_html(text):
    """Simple markdown → HTML converter (no pandoc dependency)."""
    # Blockquotes
    text = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    # Headers
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    # Code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # Horizontal rules
    text = re.sub(r'^---$', r'<hr/>', text, flags=re.MULTILINE)
    # Tables
    if '|---' in text:
        lines = text.split('\n')
        out = []
        i = 0
        while i < len(lines):
            if lines[i].startswith('|') and i + 1 < len(lines) and '---' in lines[i+1]:
                # header row
                headers = [c.strip() for c in lines[i].split('|')[1:-1]]
                out.append('<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>')
                i += 2
                while i < len(lines) and lines[i].startswith('|'):
                    cells = [c.strip() for c in lines[i].split('|')[1:-1]]
                    out.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
                    i += 1
                out.append('</tbody></table>')
            else:
                out.append(lines[i])
                i += 1
        text = '\n'.join(out)
    # Unordered lists
    text = re.sub(r'^\* (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*?</li>\n?)+', lambda m: f'<ul>{m.group(0)}</ul>', text, flags=re.DOTALL)
    # Paragraphs
    text = re.sub(r'\n\n', r'</p><p>', text)
    text = '<p>' + text + '</p>'
    # Footnote references
    text = re.sub(r'\[\^(\w+)\]', r'<sup>[\1]</sup>', text)
    return text


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


def target_pdf():
    """Compile book PDF via Pandoc HTML + WeasyPrint."""
    from weasyprint import HTML as WeasyHTML
    out_pdf = OUTPUT / 'open-source-economics.pdf'
    OUTPUT.mkdir(exist_ok=True)

    chapters = sorted(SRC_CHAPTERS.glob('*.md'))

    # Build standalone HTML with PDF-friendly styling
    tmp_html = OUTPUT / '_book_pdf.html'
    cover_html = generate_cover_html_pdf()
    toc_html = generate_toc_html_pdf(chapters)
    body_parts = [cover_html, toc_html]
    for ch in chapters:
        body_parts.append(generate_chapter_html_pdf(ch))
    body_parts.append(generate_coda_html())
    body_parts.append(generate_references_html_pdf())
    tmp_html.write_text('\n'.join(body_parts), encoding='utf-8')

    WeasyHTML(str(tmp_html)).write_pdf(str(out_pdf))
    print(f'PDF: {out_pdf} ({out_pdf.stat().st_size/1024:.0f}KB, {len(chapters)} chapters)')


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
