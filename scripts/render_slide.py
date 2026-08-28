#!/usr/bin/env python3
"""
Incremental single-slide / delta-deck renderer.

Only generates HTML for slides that are missing or explicitly requested.
This is the cost-efficient way to update content: edit the source .md,
then render only the changed slides.

Source markdown lives at:  scripts/slides_decks_source/{deck}.md
Output HTML lives at:       static/slides_decks/{deck}/pages/page_NNN.html

Usage:
  # Re-render only missing slides for a deck (delta mode):
  python3 scripts/render_slide.py --deck 01-software-business

  # Force re-render a specific slide:
  python3 scripts/render_slide.py --deck 01-software-business --slide 12

  # Force re-render a range of slides:
  python3 scripts/render_slide.py --deck 01-software-business --range 10-15

  # List all slides in a deck (dry run):
  python3 scripts/render_slide.py --deck 01-software-business --list

Notes:
  - Uses the same SYSTEM prompt and generate logic as generate_deck_slides.py
  - Does NOT touch .state.json (full-deck tool uses that for progress)
  - Skips any slide whose page_NNN.html already exists unless --slide/--range forces it
"""
import re, sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.hermes' / 'skills' / 'sn-ppt-standard' / 'lib'))
from model_client import llm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / 'scripts' / 'slides_decks_source'
OUT_DIR = ROOT / 'static' / 'slides_decks'

SYSTEM = """You are a slide designer. Generate ONE complete standalone HTML document for a single slide.

Style system (Bauhaus academic):
- canvas: 1600 x 900 exactly
- background: warm parchment #F5F0E8
- primary ink: Prussian blue #1B3B6B
- secondary: copper #8B7355, muted gray #555
- fonts: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', serif for headings; 'Noto Sans SC' for body
- Bauhaus geometric composition: circles, squares, lines as decoration
- dark academic tone, restrained, intellectual
- no emoji, no icons, no gradients except subtle parchment texture
- use the provided visual metaphor as the central visual element

HTML contract:
- output ONLY the HTML document, no markdown fences, no explanation
- <!DOCTYPE html><html><head><meta charset="UTF-8"><title>... title ...</title><style>... all CSS inline ...</style></head><body>...</body></html>
- body/html must set width:1600px; height:900px; overflow:hidden; margin:0
- all positioning absolute or flex within 1600x900
- no viewport units (vw/vh), no @media queries, no transform:scale
- decorative classes are fine but must be defined in the <style>
- content language zh-CN
"""


def parse_deck(path):
    text = Path(path).read_text()
    header_m = re.match(r'^(.*?)(?=\n## Slide \d+)', text, re.DOTALL)
    header = header_m.group(1).strip() if header_m else ''
    slides = []
    for m in re.finditer(r'## Slide (\d+)\s*(.*?)(?=\n## Slide \d+|\Z)', text, re.DOTALL):
        slides.append({'num': int(m.group(1)), 'content': m.group(2).strip()})
    return header, slides


def generate_slide(header, slide, retries=3):
    prompt = f"""Context (deck-wide style and theme):
{header}

Generate the HTML for this slide:
{slide['content']}
"""
    for i in range(retries):
        try:
            raw = llm(SYSTEM, prompt, timeout=300, model='sensenova-6.8-flash-lite')
            raw = re.sub(r'^```html\s*', '', raw, flags=re.IGNORECASE | re.MULTILINE)
            raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE)
            if '<!DOCTYPE html>' not in raw and '<html' not in raw.lower():
                raise ValueError('output missing HTML doctype/html tag')
            if '<style>' not in raw:
                raise ValueError('output missing inline <style>')
            return raw
        except Exception as e:
            print(f'  retry {i+1}/{retries}: {e}', file=sys.stderr)
            time.sleep(2 ** i)
    raise SystemExit(f'FAILED after {retries} retries')


def list_slides(deck_name):
    src = SOURCE_DIR / f'{deck_name}.md'
    if not src.exists():
        print(f'ERROR: {src} not found', file=sys.stderr)
        sys.exit(1)
    _, slides = parse_deck(src)
    out = OUT_DIR / deck_name / 'pages'
    print(f'Deck: {deck_name}  |  Source: {src}')
    print(f'{"Slide":>6}  {"File":<22}  {"Status"}')
    print('-' * 45)
    for s in slides:
        page = out / f'page_{s["num"]:03d}.html'
        exists = '✓' if page.exists() else '✗ MISSING'
        print(f'{s["num"]:>6}  {page.name:<22}  {exists}')
    present = sum(1 for s in slides if (out / f'page_{s["num"]:03d}.html').exists())
    print(f'\nTotal: {len(slides)} slides, {present} present')


def render(deck_name, slide_num=None, slide_range=None):
    src = SOURCE_DIR / f'{deck_name}.md'
    if not src.exists():
        print(f'ERROR: {src} not found', file=sys.stderr)
        sys.exit(1)

    header, slides = parse_deck(src)
    out = OUT_DIR / deck_name / 'pages'
    out.mkdir(parents=True, exist_ok=True)

    # Determine which slides to render
    targets = set()
    if slide_num is not None:
        targets = {slide_num}
        print(f'[force] Render slide {slide_num}')
    elif slide_range is not None:
        m = re.match(r'(\d+)-(\d+)', slide_range)
        if not m:
            print(f'ERROR: --range must be N-M, got {slide_range}', file=sys.stderr)
            sys.exit(1)
        lo, hi = int(m.group(1)), int(m.group(2))
        targets = set(range(lo, hi + 1))
        print(f'[force] Render slides {lo}-{hi}')
    else:
        # Delta mode: only missing slides
        for s in slides:
            page = out / f'page_{s["num"]:03d}.html'
            if not page.exists():
                targets.add(s["num"])
        if not targets:
            print(f'Deck {deck_name}: all {len(slides)} slides already rendered. Nothing to do.')
            return
        print(f'[delta] Rendering {len(targets)} missing slide(s): {sorted(targets)}')

    n_total = len(slides)
    for slide in slides:
        n = slide["num"]
        if n not in targets:
            continue
        page_path = out / f'page_{n:03d}.html'
        print(f'  [{n:3d}/{n_total:3d}] generating slide {n}...', end=' ', flush=True)
        html = generate_slide(header, slide)
        page_path.write_text(html)
        print(f'OK ({len(html)} chars)')
        time.sleep(0.5)

    print(f'\nDone. Rendered {len(targets)} slide(s) for deck {deck_name}.')


def main():
    deck = None
    slide = None
    slide_range = None
    list_only = False

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--deck' and i + 1 < len(sys.argv):
            deck = sys.argv[i + 1]; i += 2
        elif arg == '--slide' and i + 1 < len(sys.argv):
            slide = int(sys.argv[i + 1]); i += 2
        elif arg == '--range' and i + 1 < len(sys.argv):
            slide_range = sys.argv[i + 1]; i += 2
        elif arg == '--list':
            list_only = True; i += 1
        elif arg in ('-h', '--help'):
            print(__doc__); return
        else:
            print(f'Unknown arg: {arg}', file=sys.stderr); sys.exit(1)

    if not deck:
        print('ERROR: --deck {deck-id} is required', file=sys.stderr)
        print(__doc__); sys.exit(1)

    if list_only:
        list_slides(deck)
    else:
        render(deck, slide_num=slide, slide_range=slide_range)


if __name__ == '__main__':
    main()