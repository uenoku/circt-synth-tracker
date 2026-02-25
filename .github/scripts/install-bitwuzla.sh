#!/bin/bash
# Download and install the latest Bitwuzla static binary to /usr/local/bin.
set -euo pipefail

apt-get install -y unzip
BITWUZLA_VERSION=$(curl -s https://api.github.com/repos/bitwuzla/bitwuzla/releases/latest | jq -r '.tag_name')
CACHE_DIR="${BITWUZLA_CACHE_DIR:-.}"
BITWUZLA_ZIP="$CACHE_DIR/bitwuzla-${BITWUZLA_VERSION}.zip"

# Use cached version if available
if [ -f "$BITWUZLA_ZIP" ]; then
  echo "Using cached Bitwuzla binary ($BITWUZLA_VERSION)"
else
  echo "Downloading Bitwuzla $BITWUZLA_VERSION..."
  curl -fsSL "https://github.com/bitwuzla/bitwuzla/releases/download/${BITWUZLA_VERSION}/Bitwuzla-Linux-x86_64-static.zip" \
    -o "$BITWUZLA_ZIP"
fi

unzip -j "$BITWUZLA_ZIP" '*/bin/bitwuzla' -d /usr/local/bin/
chmod +x /usr/local/bin/bitwuzla
bitwuzla --version
