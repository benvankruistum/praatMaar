#!/usr/bin/env bash
# Build macOS release (indie / OSS): PyInstaller .app + zip.
# Geen code signing / notarisatie (bewust — zie docs/release-macos.md).
#
# Usage:
#   ./scripts/build-macos.sh [VERSION]
# VERSION default: project.version uit pyproject.toml (zonder "v").

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${1:-}" ]]; then
  VERSION="${1#v}"
else
  VERSION="$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
fi

ARCH="$(uname -m)"
case "$ARCH" in
  arm64) ARCH_TAG="arm64" ;;
  x86_64) ARCH_TAG="x64" ;;
  *) ARCH_TAG="$ARCH" ;;
esac

PYINSTALLER="$ROOT/.venv/bin/pyinstaller"
if [[ ! -x "$PYINSTALLER" ]]; then
  PYINSTALLER="pyinstaller"
fi

echo "==> PyInstaller (praatMaar.spec) version=$VERSION arch=$ARCH_TAG"
"$PYINSTALLER" praatMaar.spec --clean

APP="$ROOT/dist/praatMaar.app"
if [[ ! -d "$APP" ]]; then
  echo "Geen dist/praatMaar.app gevonden." >&2
  exit 1
fi

RELEASE_DIR="$ROOT/release"
mkdir -p "$RELEASE_DIR"

ZIP_PATH="$RELEASE_DIR/praatMaar-${VERSION}-macos-${ARCH_TAG}.zip"
rm -f "$ZIP_PATH"
echo "==> Zip: $ZIP_PATH"
(
  cd "$ROOT/dist"
  zip -ry "$ZIP_PATH" praatMaar.app
)

echo ""
echo "Klaar. Artefacten in: $RELEASE_DIR"
ls -la "$RELEASE_DIR"
