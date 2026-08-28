#!/bin/bash
set -euo pipefail
# Master sync pipeline: receives changed files list, routes to
# slides pipeline and/or book pipeline.
#
# Usage (called by webhook agent or manually):
#   bash sync_slides_pipeline.sh
#
# This script:
#   1. Fetches origin/main of book repo
#   2. Computes diff since last full sync
#   3. Routes: slides/.md -> slides pipeline, chapters/.md -> book pipeline
#   4. Saves full sync state

BOOK_REPO="${BOOK_REPO:-/home/lee/developing/open-source-economics-book}"
SITE_REPO="${SITE_REPO:-/home/lee/developing/os-economic-slides}"
FULL_STATE="${BOOK_REPO}/.last_full_sync_commit"
SN_PATH="/home/lee/.hermes/skills/sn-ppt-standard/lib"
DECKS_DIR="${BOOK_REPO}/src/slides"

echo "=== Sync pipeline $(date) ==="

cd "$BOOK_REPO"
git fetch origin 2>/dev/null
CURRENT_COMMIT="$(git rev-parse origin/main)"

# ── Check full sync state ──
PREV_COMMIT=""
[ -f "$FULL_STATE" ] && PREV_COMMIT="$(cat "$FULL_STATE")"

if [ "$CURRENT_COMMIT" = "$PREV_COMMIT" ]; then
    echo "[skip] No new commits."
    exit 0
fi

echo "[new] ${PREV_COMMIT:-none} → ${CURRENT_COMMIT}"

# ── Compute changed files under src/ ──
if [ -z "$PREV_COMMIT" ]; then
    CHANGED_FILES="$(git ls-files 'src/slides/*.md' 'src/chapters/*.md')"
else
    CHANGED_FILES="$(git diff --name-only "$PREV_COMMIT" "$CURRENT_COMMIT" -- 'src/slides/' 'src/chapters/')"
fi

if [ -z "$CHANGED_FILES" ]; then
    echo "[skip] No slide or chapter files changed."
    echo "$CURRENT_COMMIT" > "$FULL_STATE"
    exit 0
fi

echo "[changed]:"
echo "$CHANGED_FILES" | sed 's/^/    /'

# ── Route to pipelines ──
HAS_SLIDES=false
HAS_CHAPTERS=false
echo "$CHANGED_FILES" | grep -q '^src/slides/' && HAS_SLIDES=true
echo "$CHANGED_FILES" | grep -q '^src/chapters/' && HAS_CHAPTERS=true

# ── SLIDES PIPELINE ──
if [ "$HAS_SLIDES" = true ]; then
    echo "─────────────────────────────────────"
    echo "[route] → slides pipeline"
    echo "─────────────────────────────────────"

    git -C "$SITE_REPO" fetch origin 2>/dev/null
    git -C "$SITE_REPO" checkout main 2>/dev/null
    git -C "$SITE_REPO" pull origin main --ff-only 2>/dev/null

    DECKS_TO_RENDER=""
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        DECK="$(basename "$f" .md)"
        DECKS_TO_RENDER="$DECKS_TO_RENDER $DECK"
    done < <(echo "$CHANGED_FILES" | grep '^src/slides/')

    for DECK in ${DECKS_TO_RENDER}; do
        SRC_MD="${DECKS_DIR}/${DECK}.md"
        DEST_DIR="${SITE_REPO}/scripts/slides_decks_source"
        mkdir -p "$DEST_DIR"
        cp "$SRC_MD" "${DEST_DIR}/${DECK}.md"

        # Detect source content change
        NEW_HASH="$(sha256sum "$SRC_MD" | cut -d' ' -f1)"
        OLD_HASH="$(git -C "$SITE_REPO" show HEAD:scripts/slides_decks_source/${DECK}.md 2>/dev/null | sha256sum | cut -d' ' -f1 || echo '')"

        if [ "$NEW_HASH" != "$OLD_HASH" ]; then
            echo "[source] $DECK content changed"

            # Identify changed slide sections via diff
            git -C "$SITE_REPO" show HEAD:scripts/slides_decks_source/${DECK}.md > /tmp/old_${DECK}.md 2>/dev/null || true
            CHANGED_SLIDES="$(python3 -c "
import re
old = open('/tmp/old_${DECK}.md', 'r').read() if __import__('os').path.exists('/tmp/old_${DECK}.md') else ''
new = open('${SRC_MD}', 'r').read()

def slide_map(text):
    return {int(m.group(1)): (m.start(), m.end()) for m in re.finditer(r'^## Slide (\d+)', text, re.MULTILINE)}
    for m in re.finditer(r'^## Slide (\d+)', text, re.MULTILINE):
        yield int(m.group(1)), m.start()

def slide_ranges(text):
    boundaries = list(slide_map(text))
    ranges = {}
    for i, (num, start) in enumerate(boundaries):
        end = boundaries[i+1][1] if i+1 < len(boundaries) else len(text)
        ranges[num] = (start, end)
    return ranges

old_ranges = slide_ranges(old)
new_ranges = slide_ranges(new)

# Find slides whose content changed or were added
changed = set()
for num, (ns, ne) in new_ranges.items():
    if num not in old_ranges:
        changed.add(num)  # new slide
    else:
        os_, oe_ = old_ranges[num]
        if new[ns:ne].strip() != old[os_:oe_].strip():
            changed.add(num)  # content changed
# Find deleted slides
deleted = set(old_ranges.keys()) - set(new_ranges.keys())

print(' ' + ' '.join(str(s) for s in sorted(changed)))
" 2>/dev/null || echo ' unknown")"

            if [ -n "$CHANGED_SLIDES" ]; then
                echo "[changed slides] ${CHANGED_SLIDES}"
            fi
        fi

        echo "[render] Deck: $DECK"
        if [ -n "$CHANGED_SLIDES" ]; then
            # Re-render only the changed slides
            for SLIDE_NUM in ${CHANGED_SLIDES}; do
                echo "  [render] slide ${SLIDE_NUM}"
                python3 "${SITE_REPO}/scripts/render_slide.py" --deck "$DECK" --slide "$SLIDE_NUM" || \
                    echo "  [render] ✗ slide ${SLIDE_NUM} failed"
            done
        else
            # No source change: use delta mode (render missing pages only)
            python3 "${SITE_REPO}/scripts/render_slide.py" --deck "$DECK"
        fi
        echo "[render] ✓ $DECK"
    done

    cd "$SITE_REPO"
    HAS_HTML_CHANGES=false
    if [ "$(git diff --name-only -- 'static/slides_decks/' | wc -l)" -gt 0 ]; then
        HAS_HTML_CHANGES=true
    fi
    HAS_SOURCE_CHANGES=false
    if [ "$(git diff --name-only -- 'scripts/slides_decks_source/' | wc -l)" -gt 0 ]; then
        HAS_SOURCE_CHANGES=true
    fi

    if [ "$HAS_SOURCE_CHANGES" = true ] || [ "$HAS_HTML_CHANGES" = true ]; then
        git add static/slides_decks/ scripts/slides_decks_source/
        git commit -m "auto: sync slides from open-source-economics-book@${CURRENT_COMMIT:0:7}

Decks: ${DECKS_TO_RENDER}
Trigger: sync_slides_pipeline.sh" \
            --author="auto-sync <narrow-corridor@opensourceway.community>"
        git push origin main
        echo "[push] ✓ Slides committed (source: $HAS_SOURCE_CHANGES, html: $HAS_HTML_CHANGES)"
    fi
fi

# ── BOOK PIPELINE ──
if [ "$HAS_CHAPTERS" = true ]; then
    echo "─────────────────────────────────────"
    echo "[route] → book pipeline"
    echo "─────────────────────────────────────"

    git -C "$BOOK_REPO" checkout main 2>/dev/null
    git -C "$BOOK_REPO" pull origin main 2>/dev/null

    cd "$BOOK_REPO"
    python3 build/compile.py html
    python3 build/compile.py pdf
    python3 build/compile.py epub

    git -C "$SITE_REPO" fetch origin 2>/dev/null
    git -C "$SITE_REPO" checkout main 2>/dev/null
    git -C "$SITE_REPO" pull origin main --ff-only 2>/dev/null

    cp output/open-source-economics.html "$SITE_REPO/static/book/"
    cp output/open-source-economics.pdf  "$SITE_REPO/static/book/"
    cp output/open-source-economics.epub "$SITE_REPO/static/book/"
    cp styles/book.css                  "$SITE_REPO/static/book/"
    sed -i 's|href="\.\./book.css"|href="book.css"|g' "$SITE_REPO/static/book/open-source-economics.html"

    cd "$SITE_REPO"
    if [ "$(git diff --name-only -- 'static/book/' | wc -l)" -gt 0 ]; then
        git add static/book/
        git commit -m "auto: sync book from open-source-economics-book@${CURRENT_COMMIT:0:7}

Trigger: sync_book_pipeline.sh" \
            --author="auto-sync <narrow-corridor@opensourceway.community>"
        git push origin main
        echo "[push] ✓ Book committed"
    fi
fi

# ── Save state ──
echo "$CURRENT_COMMIT" > "$FULL_STATE"
echo "=== Done ==="
