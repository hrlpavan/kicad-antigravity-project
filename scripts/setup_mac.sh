#!/usr/bin/env bash
# scripts/setup_mac.sh - Automated Mac Client Setup for KiCad MCP
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================================="
echo "⚡ Antigravity + KiCad MCP: macOS Client Setup"
echo "=========================================================="

# 1. SSH Key Verification / Generation
echo "[1/4] Checking macOS SSH Key..."
KEY_FILE="$HOME/.ssh/id_ed25519"
if [[ ! -f "$KEY_FILE" ]]; then
    echo "  [INFO] Generating new Ed25519 SSH key at $KEY_FILE..."
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    ssh-keygen -t ed25519 -N "" -f "$KEY_FILE" -C "antigravity-kicad-mac"
    echo "  [OK] Key generated successfully."
else
    echo "  [OK] Existing SSH key found at: $KEY_FILE"
fi

# 2. Inspect Thunderbolt Bridge (bridge0)
echo "[2/4] Inspecting Thunderbolt Bridge interface..."
if ifconfig bridge0 2>/dev/null | grep -q "status: active"; then
    echo "  [OK] Thunderbolt Bridge (bridge0) is ACTIVE!"
else
    echo "  [INFO] Thunderbolt Bridge (bridge0) is currently inactive."
    echo "         (If using direct Thunderbolt 3/4 or USB4 cable, plug in cable between Mac & Windows)."
    echo "         (Automatic Wi-Fi fallback will be used when bridge0 is inactive)."
fi

# 3. Display Public Key for Windows pairing
echo "[3/4] Your Mac's Public SSH Key:"
echo "----------------------------------------------------------"
cat "${KEY_FILE}.pub"
echo "----------------------------------------------------------"
echo "👉 Add the line above to the Windows machine at:"
echo "   C:\\Users\\<WindowsUsername>\\.ssh\\authorized_keys"

# 4. Run Pre-flight test
echo ""
echo "[4/4] Running pre-flight diagnostic..."
python3 "${ROOT}/scripts/test_kicad_mcp.py" --skip-remote || true

echo ""
echo "=========================================================="
echo "🎉 Mac Client Ready! Open this folder in Antigravity to begin."
echo "=========================================================="
