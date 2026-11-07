#!/bin/bash
# Publish the site to GitHub Pages (the gh-pages branch).
#
# The map tiles are built locally and are too large and change too often to keep in the main branch's history, so
# the site is built here and pushed as a single fresh commit to gh-pages (history of that branch is not kept).
#
# Usage (from web/):
#   CNAME=isometric.lu scripts/deploy-pages.sh            # custom domain
#   VITE_BASE=/isometric-luxembourg/ scripts/deploy-pages.sh   # https://<user>.github.io/isometric-luxembourg/
# Optional: VITE_FEATURES_OFF="christmas,transit" to ship with features switched off. REMOTE (default origin).
set -euo pipefail
cd "$(dirname "$0")/.."
REMOTE_URL=$(git remote get-url "${REMOTE:-origin}")
# commit as the same author as this repo (GitHub refuses pushes that expose a private email)
export GIT_AUTHOR_NAME="$(git config user.name)" GIT_AUTHOR_EMAIL="$(git config user.email)"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
[ -f public/tiles/meta.json ] || { echo "public/tiles is missing: run pipeline/build_tiles.py first" >&2; exit 1; }

npm run build
[ ! -e dist/live ] && [ ! -e dist/style-test ] && [ ! -e dist/compare ] || { echo "local-only pages leaked into dist" >&2; exit 1; }
SIZE=$(du -sm dist | cut -f1)
echo "site size: ${SIZE} MB (GitHub Pages limit: 1024 MB)"
[ "$SIZE" -lt 1000 ] || { echo "too large for GitHub Pages: serve tiles from R2 (TILES_URL)" >&2; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp -R dist/. "$TMP"
cd "$TMP"
git init -q -b gh-pages
git add -A
git commit -q -m "Publish site $(date -u +%Y-%m-%dT%H:%MZ)"
git push -f "$REMOTE_URL" gh-pages
echo "pushed to gh-pages; GitHub Pages serves it in a minute or two"
