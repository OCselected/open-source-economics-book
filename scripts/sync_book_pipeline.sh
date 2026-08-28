#!/bin/bash
set -euo pipefail
# Book pipeline: rebuild HTML/PDF/EPUB from src/chapters/*.md
# and sync artifacts to os-economic-slides/static/book/
#
# Called by: sync_slides_pipeline.sh (when chapters changed)
# or by: webhook slides-sync agent

BOOK_REPO="${BOOK_REPO:-/home/lee/developing/open-source-economics-book}"
SITE_REPO="${SITE_REPO:-/home/lee/developing/os-economic-slides}"
BOOK_STATE="${BOOK_REPO}/.last_book_sync_commit"

echo "=== Book sync pipeline $(date) ==="

cd "$BOOK_REPO"
git fetch origin 2>/dev/null
CURRENT_COMMIT="$(git rev-parse origin/main)"

# Check if book state is up-to-date
if [ -f "$BOOK_STATE" ]; then
    PREV="$(cat "$BOOK_STATE")"
    if [ "$CURRENT_COMMIT" = "$PREV" ]; then
        echo "[skip] Book already synced to $CURRENT_COMMIT"
        exit 0
    fi
fi

# Ensure slides repo is current
git -C "$SITE_REPO" fetch origin 2>/dev/null
git -C "$SITE_REPO" checkout main 2>/dev/null
git -C "$SITE_REPO" pull origin main --ff-only 2>/dev/null

# Build all book formats
echo "[build] Compiling book formats..."
python3 build/compile.py html 2>&1
python3 build/compile.py pdf 2>&1
python3 build/compile.py epub 2>&1

# Copy artifacts to slides repo
echo "[sync] Copying to $SITE_REPO/static/book/"
cp output/open-source-economics.html "$SITE_REPO/static/book/"
cp output/open-source-economics.pdf  "$SITE_REPO/static/book/"
cp output/open-source-economics.epub "$SITE_REPO/static/book/"
cp styles/book.css                  "$SITE_REPO/static/book/"

# Fix CSS path in HTML for website context
sed -i 's|href="\.\./book.css"|href="book.css"|g' "$SITE_REPO/static/book/open-source-economics.html"

# Commit
cd "$SITE_REPO"
CHANGED_COUNT=$(git diff --name-only -- 'static/book/' | wc -l)
if [ "$CHANGED_COUNT" -eq 0 ]; then
    echo "[skip] No book artifacts changed."
else
    git add static/book/
    git commit -m "auto: sync book from open-source-economics-book@${CURRENT_COMMIT:0:7}

Chapter changes detected. Book rebuilt:
  HTML: open-source-economics.html
  PDF:  open-source-economics.pdf
  EPUB: open-source-economics.epub
Trigger: sync_book_pipeline.sh" \
        --author="auto-sync <narrow-corridor@opensourceway.community>"

    git push origin main
    echo "[push] ✓ Book artifacts committed and pushed"
fi

# Save state
echo "$CURRENT_COMMIT" > "$BOOK_STATE"
echo "=== Book sync done ==="
