#!/usr/bin/env bash
# Sync slide sources from open-source-economics-book repo into os-economic-slides.
# Used by os-economic-slides' GitHub Actions workflow.
#
# Usage:
#   BOOK_REPO_URL="https://github.com/OCselected/open-source-economics-book.git" \
#   SYNC_TARGET="scripts/slides_decks_source" \
#   bash scripts/sync_from_book.sh

set -euo pipefail

BOOK_REPO_URL="${BOOK_REPO_URL:-https://github.com/OCselected/open-source-economics-book.git}"
SYNC_TARGET="${SYNC_TARGET:-scripts/slides_decks_source}"
CLONE_DIR="${CLONE_DIR:-/tmp/open-source-economics-book}"

rm -rf "$CLONE_DIR"

# If GITHUB_TOKEN available (e.g. private repo), use it
if [ -n "${GITHUB_TOKEN:-}" ]; then
  git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/OCselected/open-source-economics-book.git" "$CLONE_DIR"
else
  git clone --depth 1 "$BOOK_REPO_URL" "$CLONE_DIR"
fi

mkdir -p "$SYNC_TARGET"
cp -f "$CLONE_DIR/src/slides/"*.md "$SYNC_TARGET/"

# Also sync data/slides_decks.json if book repo has it
if [ -f "$CLONE_DIR/data/slides_decks.json" ]; then
  cp -f "$CLONE_DIR/data/slides_decks.json" data/slides_decks.json
fi

# Sync meta/book.yaml to data/book.yaml for Hugo data templates
if [ -f "$CLONE_DIR/meta/book.yaml" ]; then
  mkdir -p data
  cp -f "$CLONE_DIR/meta/book.yaml" data/book.yaml
fi

echo "Synced $(ls "$SYNC_TARGET"/*.md | wc -l) slide files from book repo"
