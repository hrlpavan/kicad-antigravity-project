# Antigravity + KiCad MCP: Autonomous PCB Design System Configuration

> **Configuration & Agent Operational Specification**
> **Target:** Google Antigravity Agent Runtime & KiCad 10.0.6 MCP Bridge
> **Host:** ASUS Windows Workstation (`LAPTOP-Q19GA2LS` / `0x1043:0x201f`, user `Neil Gibson Pinto`)
> **Transport:** Thunderbolt Bridge (`bridge0` primary) with automatic Wi-Fi fallback (`192.168.250.243`)
> **Version:** 1.0.3

---

## 1. Workspace Directory Structure

```text
kicad-antigravity-project/
├── AGENTS.md                           # Auto-discovered workspace rules & notification policy
├── .agents/
│   └── plugins/
│       └── kicad/
│           ├── plugin.json             # Workspace plugin manifest (enables scoped MCP discovery)
│           └── mcp_config.json         # Thunderbolt Bridge + Wi-Fi fallback MCP configuration
├── scripts/
│   ├── kicad_bridge_ssh.sh             # Auto-discovers bridge0 peer (or Wi-Fi fallback) & tunnels MCP
│   ├── notify_mac.sh                   # Quote-safe notification dispatcher for macOS client
│   └── test_kicad_mcp.py               # Hardware PD/Thunderbolt + MCP JSON-RPC pre-flight check
├── hardware/
│   ├── project.kicad_pro               # KiCad project & Default/Power netclasses
│   ├── project.kicad_sch               # Schematic design
│   ├── project.kicad_pcb               # 2-layer PCB layout file
│   └── project.kicad_dru               # KiCad custom design rules (auto-loaded with project)
├── exports/                            # Gerbers, drill files, BOM, Pick & Place
└── ANTIGRAVITY_WORKFLOW.md             # This configuration & workflow guide
```

---

## 2. Active MCP Configuration (`.agents/plugins/kicad/mcp_config.json`)

```json
{
  "mcpServers": {
    "kicad": {
      "command": "bash",
      "args": [
        "/Users/pavankumars/.gemini/antigravity/scratch/kicad-antigravity-project/scripts/kicad_bridge_ssh.sh"
      ],
      "env": {
        "KICAD_BRIDGE_IFACE": "bridge0",
        "KICAD_REMOTE_OS": "windows",
        "KICAD_SSH_USER": "Neil Gibson Pinto",
        "KICAD_SSH_HOST": "",
        "KICAD_FALLBACK_HOST": "192.168.250.243",
        "KICAD_MCP_PROJECT_DIR": "C:/kicad-antigravity-project/hardware",
        "KICAD_MCP_PROFILE": "full",
        "KICAD_MCP_OPERATING_MODE": "manufacturing"
      }
    }
  }
}
```

### Transport Priority
1. **Primary (`bridge0`):** Whenever an E-marked Thunderbolt 3/4 or USB4 cable (⚡) links `bridge0` (`status: active`), `kicad_bridge_ssh.sh` auto-discovers the direct point-to-point ASUS peer IP via ARP/NDP.
2. **Automatic Fallback (`192.168.250.243`):** While `bridge0` is inactive, it seamlessly tunnels over Wi-Fi to `LAPTOP-Q19GA2LS` (`C:\Program Files\KiCad\10.0\bin` + `C:\Users\Neil Gibson Pinto\.local\bin\uvx.exe`).

---

## 3. Running & Verifying

1. **Set Active Workspace:** Open `/Users/pavankumars/.gemini/antigravity/scratch/kicad-antigravity-project` as your active workspace in Antigravity.
2. **Run Pre-Flight Check:**
   ```bash
   python3 scripts/test_kicad_mcp.py
   ```
3. **Launch Autonomous PCB Design:**
   ```text
   Read hardware/project.kicad_sch. Establish a 70x50mm 2-layer board outline in hardware/project.kicad_pcb. Place all connectors along the left edge, position the main MCU in the center with decoupling capacitors immediately adjacent to VDD pins, route all signal and power nets, run DRC, and notify my Mac upon reaching each milestone.
   ```
