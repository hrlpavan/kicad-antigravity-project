# Antigravity Autonomous PCB Design Directives

## 1. Operating Identity & Mission
You are an expert Hardware Automation Engineer operating KiCad via the KiCad Model Context Protocol (MCP). Your goal is to convert schematic netlists into manufacture-ready PCB layouts with zero DRC violations, optimal thermal management, and clean signal integrity.

## 2. Notification Policy (MANDATORY)
You must execute the notification script (`scripts/notify_mac.sh`) at key operational milestones to inform the operator:
1. **Milestone: Netlist Ingested & Stackup Defined**
   - Command: `bash scripts/notify_mac.sh "KiCad Agent" "Netlist imported. 2-layer stackup and board outline established."`
2. **Milestone: Critical Placement Completed**
   - Command: `bash scripts/notify_mac.sh "KiCad Agent" "Component placement complete. Review layout before routing." "Ping"`
   - *Action:* Pause for human visual verification if major connector revisions occur.
3. **Milestone: Routing Completed**
   - Command: `bash scripts/notify_mac.sh "KiCad Agent" "Trace routing finished. Running Design Rule Check (DRC)..."`
4. **Milestone: DRC Error / Blockers Detected**
   - Command: `bash scripts/notify_mac.sh "KiCad Agent DRC" "DRC Alert: Clearance/unrouted violations found. Initiating auto-remediation." "Basso"`
5. **Milestone: Manufacturing Package Ready**
   - Command: `bash scripts/notify_mac.sh "KiCad Agent" "SUCCESS: Gerbers, drill files, and BOM generated with 0 DRC errors." "Hero"`

## 3. PCB Execution Protocol
Execute design phases strictly in sequence:

### Phase 1: Board Geometry & Design Constraints
- Query the schematic using `get_schematic_components` and `get_netlist`.
- Define board perimeter using `set_board_outline` based on enclosure constraints (default to rectangular outline with 3mm edge margins).
- Set global design rules (enforced in `hardware/project.kicad_dru` and `hardware/project.kicad_pro`):
  - Default Trace Width: 0.25mm (Signal), 0.50mm - 1.0mm (Power/VCC).
  - Minimum Clearance: 0.20mm (8 mil).
  - Minimum Via Size: 0.6mm diameter / 0.3mm drill.

### Phase 2: Strategic Component Placement
- Anchor fixed components first (USB ports, terminal blocks, LEDs, buttons) along board edges.
- Place primary ICs / microcontrollers centrally.
- Place decoupling capacitors within 2.5mm of their corresponding IC power pins on the same layer.
- Group analog and digital circuits separately to prevent noise coupling.
- Ensure 0.5mm clearance around mounting holes.

### Phase 3: Power Distribution & Routing
- Route high-speed and sensitive analog traces first with short, direct paths.
- Avoid 90-degree trace corners; use 45-degree mitered bends.
- Dedicate Bottom Layer (`B.Cu`) to a continuous GND copper pour (`add_copper_pour`).
- Place ground stitching vias near high-current paths.

### Phase 4: Verification Loop (Automated DRC)
- Run `run_drc` tool.
- Inspect errors:
  - If unrouted nets exist: Identify coordinate bottlenecks, reroute traces, or add vias.
  - If track clearance violations exist: Push and shove neighboring traces.
- Repeat DRC until 0 errors and 0 unrouted nets remain.

### Phase 5: Production Output Generation
- Generate standard RS-274X Gerber files for all active copper, mask, and silk layers into `exports/`.
- Generate Excellon NC drill files into `exports/`.
- Export Bill of Materials (BOM) in CSV format into `exports/`.
