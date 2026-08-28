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

        echo "[render] Deck: $DECK"
        if python3 "${SITE_REPO}/scripts/render_slide.py" --deck "$DECK"; then
            echo "[render] ✓ $DECK"
        else
            echo "[render] ✗ $DECK failed"
        fi
    done

    cd "$SITE_REPO"
    if [ "$(git diff --name-only -- 'static/slides_decks/' | wc -l)" -gt 0 ]; then
        git add static/slides_decks/
        git commit -m "auto: sync slides from open-source-economics-book@${CURRENT_COMMIT:0:7}

Decks: ${DECKS_TO_RENDER}
Trigger: sync_slides_pipeline.sh" \
            --author="auto-sync <narrow-corridor@opensourceway.community>"
        git push origin main
        echo "[push] ✓ Slides committed"
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
