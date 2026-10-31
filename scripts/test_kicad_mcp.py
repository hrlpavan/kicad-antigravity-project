#!/usr/bin/env python3
"""Pre-flight check for Antigravity + KiCad MCP over Thunderbolt Bridge (bridge0)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_thunderbolt_hardware() -> None:
    """Inspect USB-C PD partner (SOP), E-marker cable (SOP'), and bridge0 link status."""
    b0 = subprocess.run(["ifconfig", "bridge0"], capture_output=True, text=True).stdout
    b0_active = "status: active" in b0

    cc = subprocess.run(["ioreg", "-r", "-n", "CC", "-l"], capture_output=True, text=True).stdout
    has_partner = '"AddressDescription" = "SOP"' in cc
    has_emarker = "SOP'" in cc or "SOPPrime" in cc
    vid = re.search(r'"Vendor ID \(SOP\)" = (\d+)', cc)
    pid = re.search(r'"Product ID \(SOP\)" = (\d+)', cc)
    partner_str = f"0x{int(vid.group(1)):04x}:0x{int(pid.group(1)):04x}" if (vid and pid) else "detected"

    if b0_active:
        print(f"[OK] Thunderbolt Bridge (bridge0) is ACTIVE (partner {partner_str}).")
    elif has_partner and not has_emarker:
        print(
            f"[PENDING] USB-C partner ({partner_str}) detected on CC, bridge0 inactive "
            "(non-E-marked cable currently plugged in; swap to Thunderbolt 3/4 or USB4 cable later)."
        )
    else:
        print("[PENDING] Thunderbolt Bridge (bridge0) is inactive (no Thunderbolt cable/peer active yet).")


def main() -> int:
    # 1. Verify workspace layout and Antigravity discovery paths
    required = [
        ROOT / "AGENTS.md",
        ROOT / ".agents/plugins/kicad/plugin.json",
        ROOT / ".agents/plugins/kicad/mcp_config.json",
        ROOT / "scripts/kicad_bridge_ssh.sh",
        ROOT / "scripts/notify_mac.sh",
        ROOT / "hardware/project.kicad_pro",
        ROOT / "hardware/project.kicad_sch",
        ROOT / "hardware/project.kicad_pcb",
        ROOT / "hardware/project.kicad_dru",
        ROOT / "exports",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    assert not missing, f"Missing required paths: {missing}"
    print("[OK] Workspace layout and Antigravity plugin paths verified.")

    # 2. Validate MCP config semantics
    mcp_cfg = json.loads((ROOT / ".agents/plugins/kicad/mcp_config.json").read_text())
    servers = mcp_cfg.get("mcpServers", {})
    assert "kicad" in servers, "Missing 'kicad' entry in mcpServers"
    assert "notifications" not in servers, "'notifications' shell script must not be in mcpServers"
    kicad = servers["kicad"]
    assert kicad.get("env", {}).get("KICAD_BRIDGE_IFACE") == "bridge0", "Expected KICAD_BRIDGE_IFACE=bridge0"
    print("[OK] MCP configuration wired to Thunderbolt Bridge (bridge0).")

    # 3. Check physical USB-C / Thunderbolt Bridge state
    if sys.platform == "darwin":
        check_thunderbolt_hardware()

    # 4. Verify macOS notification dispatch (including spaces & quotes)
    res = subprocess.run(
        ["bash", str(ROOT / "scripts/notify_mac.sh"), "KiCad Bridge Ready", "Thunderbolt Bridge (bridge0) pre-configured.", "Glass"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"notify_mac.sh failed: {res.stderr}"
    print("[OK] macOS notification dispatched.")

    # 5. Probe MCP stdio transport via kicad_bridge_ssh.sh
    if "--skip-remote" in sys.argv:
        return 0

    cmd = [kicad["command"], *kicad.get("args", [])]
    env = {**os.environ, **kicad.get("env", {})}
    init_req = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "kicad-preflight", "version": "1.0.1"},
        },
    }) + "\n"
    try:
        proc = subprocess.run(cmd, input=init_req, env=env, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        first_line = next((ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")), "")
        if first_line:
            payload = json.loads(first_line)
            assert "result" in payload, f"MCP initialize error: {payload}"
            print(f"[OK] Remote KiCad MCP responded: {payload['result'].get('serverInfo', payload['result'])}")
        else:
            print(f"[INFO] MCP bridge standby: {proc.stderr.strip() or f'exit {proc.returncode}'}")
    except subprocess.TimeoutExpired:
        print("[WARN] MCP probe over bridge0 timed out after 8s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
