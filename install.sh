#!/usr/bin/env bash
# Install `ir` (install-release) as a standalone binary.
#
#   curl -fsSL https://raw.githubusercontent.com/Rishang/install-release/main/install.sh | bash
#
# Downloads the right release binary for this OS/arch to /tmp, then lets it
# install itself into ~/bin as `ir` so `ir upgrade` keeps it updated.
set -euo pipefail

REPO="Rishang/install-release"
BASE_URL="https://github.com/${REPO}/releases/latest/download"

red() { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
bold() { printf '\033[1m%s\033[0m\n' "$*"; }
die() { red "error: $*" >&2; exit 1; }

os="$(uname -s)"
arch="$(uname -m)"
case "$os" in
  Linux)
    case "$arch" in
      x86_64 | amd64) asset="install-release-linux-x86_64" ;;
      aarch64 | arm64) asset="install-release-linux-aarch64" ;;
      *) die "unsupported Linux architecture: $arch" ;;
    esac
    ;;
  Darwin) asset="install-release-darwin" ;;
  *) die "unsupported OS: $os (supported: Linux, macOS, WSL)" ;;
esac

tmp_dir="$(mktemp -d /tmp/install-release.XXXXXX)"
trap 'rm -rf "$tmp_dir"' EXIT
cli="$tmp_dir/ir-cli"

bold "Downloading $asset ..."
if command -v wget >/dev/null 2>&1; then
  wget -q --show-progress -O "$cli" "$BASE_URL/$asset"
elif command -v curl >/dev/null 2>&1; then
  curl -fL --progress-bar -o "$cli" "$BASE_URL/$asset"
else
  die "need wget or curl"
fi
chmod +x "$cli"

bold "Installing ir into ~/bin ..."
cd "$tmp_dir"
# -y: no prompt, so this also works when piped from curl
./ir-cli get "https://github.com/${REPO}" -n ir -y

echo
green "✔ ir installed to ~/bin/ir"
echo

case ":$PATH:" in
  *":$HOME/bin:"*) on_path=1 ;;
  *) on_path=0 ;;
esac

bold "Recommended next steps:"
if [ "$on_path" -eq 0 ]; then
  echo "  1. Add ~/bin to your PATH:"
  case "$(basename "${SHELL:-}")" in
    zsh) echo "       echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc" ;;
    fish) echo "       echo 'set -gx PATH \$HOME/bin \$PATH' >> ~/.config/fish/config.fish" ;;
    *) echo "       echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc" ;;
  esac
else
  echo "  1. ~/bin is already on your PATH ✔"
fi
echo "  2. Make sure libmagic is installed (runtime dependency):"
echo "       Debian/Ubuntu: sudo apt install libmagic1"
echo "       Fedora/RHEL:   sudo dnf install file-libs"
echo "       macOS:         brew install libmagic"
echo "  3. Try it:"
echo "       ir get https://github.com/tomnomnom/gron"
echo "       ir ls"
echo "       ir upgrade"
