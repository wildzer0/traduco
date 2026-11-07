#!/usr/bin/env bash
# Traduco launcher bootstrap (Linux/macOS): installs uv into .runtime/uv (no admin rights),
# then hands over to the Python launcher. All logic lives in launcher/.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
UV_VERSION="0.13.4"
export UV_UNMANAGED_INSTALL="$ROOT/.runtime/uv" UV_NO_MODIFY_PATH=1
export UV_PYTHON_INSTALL_DIR="$ROOT/.runtime/python" UV_CACHE_DIR="$ROOT/.runtime/uv-cache"
export UV_PROJECT_ENVIRONMENT="$ROOT/.runtime/launcher-venv"
export PYTHONUTF8=1
UV="$UV_UNMANAGED_INSTALL/uv"

if [ ! -x "$UV" ]; then
  if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
  else
    echo "[0] Installing uv $UV_VERSION into .runtime/uv ..."
    URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-installer.sh"
    mkdir -p .runtime
    # curl and wget both honour HTTPS_PROXY; the installer verifies the archive checksum.
    if command -v curl >/dev/null 2>&1; then curl -LsSf "$URL" | sh
    elif command -v wget >/dev/null 2>&1; then wget -qO- "$URL" | sh
    else echo "[E000] curl or wget is required to download uv." >&2; exit 1; fi
  fi
fi

# --offline: no network at all, not even for uv (the bundle carries Python, wheels and Pandoc)
for arg in "$@"; do [ "$arg" = "--offline" ] && export UV_OFFLINE=1; done

export TRADUCO_UV="$UV"
exec "$UV" run --frozen --no-dev --project launcher python -m launcher "$@"
