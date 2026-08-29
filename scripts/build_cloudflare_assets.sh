#!/bin/sh
set -eu
rm -rf dist
mkdir -p dist/assets
cp web/index.html dist/index.html
cp web/app.js web/styles.css dist/assets/
