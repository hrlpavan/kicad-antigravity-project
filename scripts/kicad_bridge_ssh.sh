#!/usr/bin/env bash
# scripts/kicad_bridge_ssh.sh - Stdio MCP bridge: prefers Thunderbolt Bridge (bridge0), falls back to Wi-Fi
# stdout is strictly reserved for MCP JSON-RPC; all diagnostics go to stderr.
set -euo pipefail

IFACE="${KICAD_BRIDGE_IFACE:-bridge0}"
REMOTE_OS="${KICAD_REMOTE_OS:-windows}"
SSH_USER="${KICAD_SSH_USER:-Neil Gibson Pinto}"
SSH_HOST="${KICAD_SSH_HOST:-}"
FALLBACK_HOST="${KICAD_FALLBACK_HOST:-192.168.250.243}"
REMOTE_PROJECT_DIR="${KICAD_MCP_PROJECT_DIR:-C:/kicad-antigravity-project/hardware}"
PROFILE="${KICAD_MCP_PROFILE:-agent_full}"
MODE="${KICAD_MCP_OPERATING_MODE:-experimental}"

# 1. Prefer Thunderbolt Bridge (bridge0) peer auto-discovery whenever bridge0 is active
if [[ -z "$SSH_HOST" ]] && ifconfig "$IFACE" 2>/dev/null | grep -q "status: active"; then
    LOCAL_V4="$(ifconfig "$IFACE" | awk '/inet /{print $2; exit}')"
    BCAST_V4="$(ifconfig "$IFACE" | awk '/broadcast /{print $NF; exit}')"
    [[ -n "$BCAST_V4" ]] && /sbin/ping -c 1 -t 1 "$BCAST_V4" >/dev/null 2>&1 || true
    /sbin/ping6 -c 1 -I "$IFACE" ff02::1 >/dev/null 2>&1 || true

    SSH_HOST="$(arp -an -i "$IFACE" 2>/dev/null \
        | awk -v self="($LOCAL_V4)" -v bc="($BCAST_V4)" \
          '$2 != self && $2 != bc && $4 != "(incomplete)" && $4 != "ff:ff:ff:ff:ff:ff" {gsub(/[()]/, "", $2); print $2; exit}')"

    if [[ -z "$SSH_HOST" ]]; then
        SSH_HOST="$(ndp -an 2>/dev/null \
            | awk -v ifc="$IFACE" '$3 == ifc && $2 != "(incomplete)" && $4 != "permanent" && $1 ~ /^fe80:/ {print $1; exit}')"
    fi
fi

# 2. Automatic Wi-Fi fallback when bridge0 is inactive (prior to Thunderbolt cable swap)
if [[ -z "$SSH_HOST" ]]; then
    if [[ -n "$FALLBACK_HOST" ]]; then
        SSH_HOST="$FALLBACK_HOST"
    else
        echo "[kicad-bridge] $IFACE is inactive and no KICAD_FALLBACK_HOST set." >&2
        exit 1
    fi
fi

if [[ "$REMOTE_OS" == "windows" ]]; then
    # Raw cmd.exe preserves binary-clean Win32 stdin/stdout pipes for MCP JSON-RPC.
    # %~sI resolves 8.3 short TEMP path so Win32 named pipe matches KiCad GUI's NNG IPC socket when username has spaces.
    REMOTE_CMD="for %I in (\"%LOCALAPPDATA%\\Temp\") do @set \"KICAD_API_SOCKET=ipc://%~sI\\kicad\\api.sock\" && set \"KICAD_MCP_PROJECT_DIR=${REMOTE_PROJECT_DIR}\" && set \"KICAD_MCP_PROFILE=${PROFILE}\" && set \"KICAD_MCP_OPERATING_MODE=${MODE}\" && set \"PATH=%USERPROFILE%\\.local\\bin;%USERPROFILE%\\.cargo\\bin;C:\\Program Files\\KiCad\\10.0\\bin;C:\\Program Files\\KiCad\\9.0\\bin;C:\\Program Files\\KiCad\\8.0\\bin;%PATH%\" && uvx kicad-mcp-pro"
else
    printf -v REMOTE_CMD 'KICAD_MCP_PROJECT_DIR=%q KICAD_MCP_PROFILE=%q KICAD_MCP_OPERATING_MODE=%q uvx kicad-mcp-pro' \
        "$REMOTE_PROJECT_DIR" "$PROFILE" "$MODE"
fi

SSH_KEY_ARG=()
if [[ -n "${KICAD_SSH_KEY:-}" && -f "$KICAD_SSH_KEY" ]]; then
    SSH_KEY_ARG=(-i "$KICAD_SSH_KEY")
elif [[ -f "$HOME/.ssh/id_ed25519" ]]; then
    SSH_KEY_ARG=(-i "$HOME/.ssh/id_ed25519")
elif [[ -f "$HOME/.ssh/id_rsa" ]]; then
    SSH_KEY_ARG=(-i "$HOME/.ssh/id_rsa")
fi

exec ssh -T -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "${SSH_KEY_ARG[@]}" -l "$SSH_USER" "$SSH_HOST" "$REMOTE_CMD"
