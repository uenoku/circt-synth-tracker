#!/bin/bash
# Download and install the latest Bitwuzla static binary to /usr/local/bin.
set -euo pipefail

apt-get install -y unzip
BITWUZLA_VERSION=$(curl -s https://api.github.com/repos/bitwuzla/bitwuzla/releases/latest | jq -r '.tag_name')
curl -fsSL "https://github.com/bitwuzla/bitwuzla/releases/download/${BITWUZLA_VERSION}/Bitwuzla-Linux-x86_64-static.zip" \
  -o bitwuzla.zip
unzip -j bitwuzla.zip '*/bin/bitwuzla' -d /usr/local/bin/
rm bitwuzla.zip
chmod +x /usr/local/bin/bitwuzla
bitwuzla --version
