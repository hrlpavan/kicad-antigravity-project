#!/usr/bin/env python3
"""Compile HRL Core Telemetry Node PCB with penetrated HRL Main Logo (KiCad 10)."""
import json
import math
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "hardware" / "assets"
SCRATCH = Path("/Users/pavankumars/.gemini/antigravity/brain/d68fb3ab-81e0-48c0-a085-c75203409d58/scratch")


def uid() -> str:
    return str(uuid.uuid4())


def replace_sexpr_blocks(text: str, head_prefix: str, transform) -> str:
    """Linear-time O(N) balanced-parenthesis S-expression block transformer."""
    out = []
    pos = 0
    n = len(text)
    while True:
        idx = text.find(head_prefix, pos)
        if idx == -1:
            out.append(text[pos:])
            break
        out.append(text[pos:idx])
        depth = 0
        in_str = False
        esc = False
        end = idx
        while end < n:
            ch = text[end]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        end += 1
                        break
            end += 1
        out.append(transform(text[idx:end]))
        pos = end
    return "".join(out)


def clean_schematic_overlaps(sch_path: Path) -> None:
    """Separate vertical stub wires between R2/R3/R4 in project.kicad_sch so schematic parity is exact."""
    sch = sch_path.read_text()
    sch = sch.replace("(at 190.5 95.25 270)", "(at 190.5 90.17 270)")
    sch = sch.replace("(pts (xy 190.5 85.09) (xy 190.5 95.25))", "(pts (xy 190.5 85.09) (xy 190.5 90.17))")
    sch = sch.replace("(at 190.5 92.71 90)", "(at 190.5 97.79 90)")
    sch = sch.replace("(pts (xy 190.5 92.71) (xy 190.5 102.87))", "(pts (xy 190.5 97.79) (xy 190.5 102.87))")
    sch = sch.replace("(at 190.5 118.11 90)", "(at 190.5 123.19 90)")
    sch = sch.replace("(pts (xy 190.5 118.11) (xy 190.5 128.27))", "(pts (xy 190.5 123.19) (xy 190.5 128.27))")
    # Move #PWR14253 (+5V on R3.2) from y=120.65 to y=115.57
    sch = sch.replace("(at 190.5 120.65 0)", "(at 190.5 115.57 0)")
    sch = sch.replace("(pts (xy 190.5 110.49) (xy 190.5 120.65))", "(pts (xy 190.5 110.49) (xy 190.5 115.57))")
    # Remove accidental overlap junctions on column x=190.5
    sch = replace_sexpr_blocks(sch, "(junction (at 190.5 ", lambda _: "")
    sch_path.write_text(sch)


def instantiate_footprint(
    raw_mod: str,
    lib_prefix: str,
    ref: str,
    val: str,
    x: float,
    y: float,
    pad_nets: dict[str, tuple[int, str]],
    sch_uuid: str | None = None,
    hide_ref: bool = False,
    board_only: bool = False,
    ref_offset: tuple[float, float] | None = None,
) -> str:
    # Refresh any pre-existing UUIDs inside library footprint
    s = re.sub(r'\(uuid\s+"[^"]+"\)', lambda _: f'(uuid "{uid()}")', raw_mod)

    mod_name_m = re.match(r'\s*\(footprint\s+"([^"]+)"', s)
    assert mod_name_m, f"Invalid footprint header for {ref}"
    mod_name = mod_name_m.group(1)
    path_clause = f'\n\t(path "/{sch_uuid}")' if sch_uuid else ""
    header = f'(footprint "{lib_prefix}:{mod_name}"\n\t(at {x:.4f} {y:.4f} 0)\n\t(uuid "{uid()}"){path_clause}'
    s = re.sub(r'^\s*\(footprint\s+"[^"]+"', header, s, count=1)
    s = re.sub(r'\(version\s+\d+\)\s*', "", s, count=1)
    s = re.sub(r'\(generator\s+"[^"]+"\)\s*', "", s, count=1)
    s = re.sub(r'\(generator_version\s+"[^"]+"\)\s*', "", s, count=1)

    if board_only:
        s = s.replace(
            "(attr exclude_from_pos_files exclude_from_bom)",
            "(attr board_only exclude_from_pos_files exclude_from_bom)",
        )

    def repl_prop(block: str) -> str:
        m = re.match(r'^\(property\s+"([^"]+)"\s+"[^"]*"', block)
        if not m:
            return block
        pname = m.group(1)
        if pname == "Reference":
            b = re.sub(r'^\(property\s+"Reference"\s+"[^"]*"', f'(property "Reference" "{ref}"', block, count=1)
            if ref_offset is not None:
                b = re.sub(
                    r'\(at\s+[-\d.]+\s+[-\d.]+(\s+[-\d.]+)?\)',
                    f"(at {ref_offset[0]:.3f} {ref_offset[1]:.3f} 0)",
                    b,
                    count=1,
                )
            if hide_ref and "(hide yes)" not in b:
                b = b[:-1].rstrip() + "\n\t\t(hide yes)\n\t)"
            return b
        if pname == "Value":
            return re.sub(r'^\(property\s+"Value"\s+"[^"]*"', f'(property "Value" "{val}"', block, count=1)
        return block

    s = replace_sexpr_blocks(s, '(property "', repl_prop)

    def repl_pad(block: str) -> str:
        m = re.match(r'^\(pad\s+"([^"]*)"', block)
        if not m:
            return block
        pnum = m.group(1)
        inner = block[:-1].rstrip()
        if pnum in pad_nets:
            nid, nname = pad_nets[pnum]
            inner += f'\n\t\t(net {nid} "{nname}")'
        if "(uuid " not in inner:
            inner += f'\n\t\t(uuid "{uid()}")'
        return inner + "\n\t)"

    s = replace_sexpr_blocks(s, '(pad "', repl_pad)
    return s


def main() -> None:
    clean_schematic_overlaps(ROOT / "hardware/project.kicad_sch")
    mods_file = (ASSETS / "footprints/mods.json") if (ASSETS / "footprints/mods.json").exists() else (SCRATCH / "footprints/mods.json")
    logo_file = (ASSETS / "hrl_logo_contours.json") if (ASSETS / "hrl_logo_contours.json").exists() else (SCRATCH / "hrl_logo_contours.json")
    mods = json.loads(mods_file.read_text())
    logo = json.loads(logo_file.read_text())

    nets = [
        (0, ""),
        (1, "GND"),
        (2, "+5V"),
        (3, "UART_RX"),
        (4, "UART_TX"),
        (5, "nRST"),
        (6, "BTN_IN"),
        (7, "LED_STAT"),
        (8, "LED_STAT_A"),
        (9, "LED_ACT"),
        (10, "LED_ACT_A"),
        (11, "LED_PWR_A"),
    ]
    net_map = {name: (nid, name) for nid, name in nets}

    # Update project.kicad_pro so +5V is explicitly mapped to Power netclass (0.50-1.00mm)
    pro_path = ROOT / "hardware/project.kicad_pro"
    pro = json.loads(pro_path.read_text())
    pro.setdefault("net_settings", {})["netclass_assignments"] = {"+5V": "Power"}
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")

    fps = [
        # Mounting holes (4 corners, 4.5mm inset, board_only mechanical)
        instantiate_footprint(mods["MountingHole_M3"], "MountingHole", "H1", "M3", 104.5, 104.5, {}, hide_ref=True, board_only=True),
        instantiate_footprint(mods["MountingHole_M3"], "MountingHole", "H2", "M3", 173.5, 104.5, {}, hide_ref=True, board_only=True),
        instantiate_footprint(mods["MountingHole_M3"], "MountingHole", "H3", "M3", 104.5, 145.5, {}, hide_ref=True, board_only=True),
        instantiate_footprint(mods["MountingHole_M3"], "MountingHole", "H4", "M3", 173.5, 145.5, {}, hide_ref=True, board_only=True),

        # Left-edge connectors & tactile input
        instantiate_footprint(
            mods["PinHeader_1x04"], "Connector_PinHeader_2.54mm", "J1", "PWR_UART", 109.0, 115.0,
            {"1": net_map["+5V"], "2": net_map["GND"], "3": net_map["UART_RX"], "4": net_map["UART_TX"]},
            sch_uuid="376c493a-0dbd-49a6-af7c-0c195b5e9ff8", ref_offset=(-3.3, 3.81),
        ),
        instantiate_footprint(
            mods["SW_TL3342"], "Button_Switch_SMD", "SW1", "USER_BTN", 109.5, 136.5,
            {"1": net_map["BTN_IN"], "2": net_map["GND"]},
            sch_uuid="df6a1ca6-4631-4168-a118-36b51b2468af", ref_offset=(0.0, 4.3),
        ),

        # Central MCU & decoupling (C1 pad 1 is 2.395mm < 2.5mm from U1 Pin 8 +5V)
        instantiate_footprint(
            mods["SOIC-8"], "Package_SO", "U1", "ATtiny85-20S", 126.0, 125.0,
            {
                "1": net_map["nRST"], "2": net_map["UART_RX"], "3": net_map["UART_TX"], "4": net_map["GND"],
                "5": net_map["BTN_IN"], "6": net_map["LED_ACT"], "7": net_map["LED_STAT"], "8": net_map["+5V"],
            },
            sch_uuid="16a47732-fa07-4bc5-8494-c78dcd29489d", ref_offset=(0.0, 4.1),
        ),
        instantiate_footprint(
            mods["C_0805"], "Capacitor_SMD", "C1", "100nF", 129.425, 120.7,
            {"1": net_map["+5V"], "2": net_map["GND"]},
            sch_uuid="a6f6c29b-76a6-40d5-87b9-c4716150fef1", ref_offset=(0.0, -1.95),
        ),
        instantiate_footprint(
            mods["C_0805"], "Capacitor_SMD", "C2", "10uF", 115.45, 113.5,
            {"1": net_map["+5V"], "2": net_map["GND"]},
            sch_uuid="ec925ba5-123a-411b-8375-102ddb9228b2", ref_offset=(0.0, 1.95),
        ),
        instantiate_footprint(
            mods["R_0805"], "Resistor_SMD", "R1", "10k", 122.6125, 117.5,
            {"1": net_map["+5V"], "2": net_map["nRST"]},
            sch_uuid="7a627f75-6d21-40eb-8db2-3475e8942c9b", ref_offset=(-2.9, 0.0),
        ),

        # Top Power LED (D2 + R3)
        instantiate_footprint(
            mods["LED_0805"], "LED_SMD", "D2", "PWR_GOLD", 121.5, 105.5,
            {"1": net_map["GND"], "2": net_map["LED_PWR_A"]},
            sch_uuid="0d2b9e69-e15a-4547-9e26-d992f4c49986", ref_offset=(0.0, -1.95),
        ),
        instantiate_footprint(
            mods["R_0805"], "Resistor_SMD", "R3", "330R", 125.8, 105.5,
            {"1": net_map["LED_PWR_A"], "2": net_map["+5V"]},
            sch_uuid="6a48f544-372d-42ea-b1cf-a71ee6dccd21", ref_offset=(0.0, -1.95),
        ),

        # Bottom Activity LED (D3 + R4, inner concentric channel y=138.0)
        instantiate_footprint(
            mods["LED_0805"], "LED_SMD", "D3", "HRL_ACT_RED", 121.5, 138.0,
            {"1": net_map["GND"], "2": net_map["LED_ACT_A"]},
            sch_uuid="4679484d-a81f-4bff-9057-7f21e10c2ce5", ref_offset=(0.0, -1.95),
        ),
        instantiate_footprint(
            mods["R_0805"], "Resistor_SMD", "R4", "330R", 125.8, 138.0,
            {"1": net_map["LED_ACT_A"], "2": net_map["LED_ACT"]},
            sch_uuid="cc64935a-ac24-4f6b-9e0a-0c17ee0ded22", ref_offset=(0.0, -1.95),
        ),

        # Bottom Status LED (D1 + R2, outer concentric channel y=143.0)
        instantiate_footprint(
            mods["LED_0805"], "LED_SMD", "D1", "HRL_STAT_RED", 121.5, 143.0,
            {"1": net_map["GND"], "2": net_map["LED_STAT_A"]},
            sch_uuid="dde86623-1ea6-4c34-989e-c685712d6120", ref_offset=(0.0, 1.95),
        ),
        instantiate_footprint(
            mods["R_0805"], "Resistor_SMD", "R2", "330R", 125.8, 143.0,
            {"1": net_map["LED_STAT_A"], "2": net_map["LED_STAT"]},
            sch_uuid="fe13b368-109d-466b-ae32-e2bee46fc5ad", ref_offset=(0.0, 1.95),
        ),
    ]

    # Rounded rectangular board outline (78.0 x 50.0 mm at (100,100)..(178,150), R=2.5mm)
    s45 = 2.5 * (1.0 - math.sqrt(0.5))
    x0, y0, x1, y1, r = 100.0, 100.0, 178.0, 150.0, 2.5
    outline = [
        f'(gr_line (start {x0+r} {y0}) (end {x1-r} {y0}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
        f'(gr_line (start {x1} {y0+r}) (end {x1} {y1-r}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
        f'(gr_line (start {x1-r} {y1}) (end {x0+r} {y1}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
        f'(gr_line (start {x0} {y1-r}) (end {x0} {y0+r}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
        f'(gr_arc (start {x0} {y0+r}) (mid {x0+s45:.4f} {y0+s45:.4f}) (end {x0+r} {y0}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
        f'(gr_arc (start {x1-r} {y0}) (mid {x1-s45:.4f} {y0+s45:.4f}) (end {x1} {y0+r}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
        f'(gr_arc (start {x1} {y1-r}) (mid {x1-s45:.4f} {y1-s45:.4f}) (end {x1-r} {y1}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
        f'(gr_arc (start {x0+r} {y1}) (mid {x0+s45:.4f} {y1-s45:.4f}) (end {x0} {y1-r}) (stroke (width 0.15) (type solid)) (layer "Edge.Cuts") (uuid "{uid()}"))',
    ]

    # Penetrated HRL Main Logo centered at (156.5, 125.0) across F.Cu (24K ENIG Gold), F.Mask, and B.Mask
    lx, ly = 156.5, 125.0
    logo_polys = []
    for layer in ("F.Cu", "F.Mask", "B.Mask"):
        for poly in logo["polygons"]:
            pts_str = " ".join(f"(xy {lx + px:.4f} {ly + py:.4f})" for px, py in poly)
            logo_polys.append(
                f'(gr_poly (pts {pts_str}) (stroke (width 0) (type solid)) (fill solid) (layer "{layer}") (uuid "{uid()}"))'
            )

    # Silkscreen framing & labels (strictly outside F.Mask openings and vias)
    silk = [
        f'(gr_rect (start 138.0 116.5) (end 175.0 133.5) (stroke (width 0.18) (type solid)) (fill none) (layer "F.SilkS") (uuid "{uid()}"))',
        f'(gr_text "HRL INTERNATIONAL" (at 156.5 113.8 0) (layer "F.SilkS") (uuid "{uid()}") (effects (font (size 1.35 1.35) (thickness 0.22) bold)))',
        f'(gr_text "CORE TELEMETRY NODE v1.0" (at 156.5 136.4 0) (layer "F.SilkS") (uuid "{uid()}") (effects (font (size 1.0 1.0) (thickness 0.16))))',
        f'(gr_text "ANTIGRAVITY x KICAD 10 MCP" (at 156.5 145.6 0) (layer "F.SilkS") (uuid "{uid()}") (effects (font (size 0.9 0.9) (thickness 0.15))))',
    ]

    # 45-degree mitered routing helper
    segments = []

    def route(net_name: str, width: float, pts: list[tuple[float, float]], layer: str = "F.Cu") -> None:
        nid = net_map[net_name][0]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            if abs(ax - bx) < 1e-6 and abs(ay - by) < 1e-6:
                continue
            segments.append(
                f'(segment (start {ax:.4f} {ay:.4f}) (end {bx:.4f} {by:.4f}) (width {width:.3f}) (layer "{layer}") (net {nid}) (uuid "{uid()}"))'
            )

    # +5V Power Distribution (0.60mm width, 45-deg mitered bends, exact shared T-junction vertices)
    route(
        "+5V",
        0.60,
        [
            (109.0, 115.0),
            (113.5, 110.5),
            (114.5, 109.5),
            (120.7, 109.5),
            (125.7125, 109.5),
            (127.475, 109.5),
            (128.475, 110.5),
            (128.475, 120.7),
            (128.475, 123.095),
        ],
    )
    route("+5V", 0.60, [(113.5, 110.5), (114.5, 111.5), (114.5, 113.5)])           # Tap to C2.1
    route("+5V", 0.60, [(120.7, 109.5), (121.7, 110.5), (121.7, 117.5)])           # Tap to R1.1
    route("+5V", 0.60, [(125.7125, 109.5), (126.7125, 108.5), (126.7125, 105.5)])  # Tap to R3.2

    # Signal Nets (0.25mm width, strictly 45-deg mitered bends)
    route("nRST", 0.25, [(123.525, 117.5), (123.525, 123.095)])
    route("UART_RX", 0.25, [(109.0, 120.08), (115.0, 120.08), (119.285, 124.365), (123.525, 124.365)])
    route("UART_TX", 0.25, [(109.0, 122.62), (113.8, 122.62), (116.815, 125.635), (123.525, 125.635)])
    route("BTN_IN", 0.25, [(106.35, 134.6), (112.65, 134.6), (125.875, 134.6), (128.475, 132.0), (128.475, 126.905)])
    route("LED_ACT", 0.25, [(128.475, 125.635), (129.8, 125.635), (130.8, 126.635), (130.8, 136.5), (129.3, 138.0), (126.7125, 138.0)])
    route("LED_STAT", 0.25, [(128.475, 124.365), (131.6, 124.365), (132.8, 125.565), (132.8, 141.2), (131.0, 143.0), (126.7125, 143.0)])
    route("LED_PWR_A", 0.25, [(122.4375, 105.5), (124.8875, 105.5)])
    route("LED_ACT_A", 0.25, [(122.4375, 138.0), (124.8875, 138.0)])
    route("LED_STAT_A", 0.25, [(122.4375, 143.0), (124.8875, 143.0)])

    # GND return stubs & tented stitching vias into B.Cu continuous GND plane (0.6mm / 0.3mm)
    vias = []

    def gnd_via(vx: float, vy: float, pad_pt: tuple[float, float] | None = None, width: float = 0.40) -> None:
        if pad_pt is not None:
            route("GND", width, [pad_pt, (vx, vy)])
        vias.append(f'(via (at {vx:.4f} {vy:.4f}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1) (uuid "{uid()}"))')

    gnd_via(111.5, 117.54, (109.0, 117.54), 0.50)       # J1.2 GND
    gnd_via(118.0, 113.5, (116.4, 113.5), 0.50)         # C2.2 GND
    gnd_via(132.0, 120.7, (130.375, 120.7), 0.50)       # C1.2 decoupling GND
    gnd_via(121.2, 126.905, (123.525, 126.905), 0.50)   # U1.4 MCU GND
    route("GND", 0.40, [(106.35, 138.4), (112.65, 138.4)])
    gnd_via(114.4, 138.4, (112.65, 138.4), 0.40)        # SW1.2 GND
    gnd_via(119.0, 105.5, (120.5625, 105.5), 0.35)      # D2.1 GND
    gnd_via(119.0, 138.0, (120.5625, 138.0), 0.35)      # D3.1 GND
    gnd_via(119.0, 143.0, (120.5625, 143.0), 0.35)      # D1.1 GND
    # Stitched F.Cu <-> B.Cu GND Faraday guard bar isolating digital domain from HRL logo showcase
    route("GND", 0.40, [(135.5, 108.0), (135.5, 125.0), (135.5, 142.0)])
    for sx, sy in [(135.5, 108.0), (135.5, 125.0), (135.5, 142.0)]:
        gnd_via(sx, sy)

    # B.Cu Keepout cutout behind HRL Main Logo (penetrates bottom GND plane so light shines through FR-4!)
    keepout_zone = f"""
  (zone
    (net 0)
    (net_name "")
    (layer "B.Cu")
    (uuid "{uid()}")
    (hatch edge 0.5)
    (connect_pads (clearance 0))
    (min_thickness 0.25)
    (filled_areas_thickness no)
    (keepout
      (tracks not_allowed)
      (vias not_allowed)
      (pads not_allowed)
      (copperpour not_allowed)
      (footprints not_allowed)
    )
    (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))
    (polygon
      (pts
        (xy 138.5 117.2) (xy 174.5 117.2) (xy 174.5 132.8) (xy 138.5 132.8)
      )
    )
  )"""

    # B.Cu Continuous GND Copper Pour across entire board (filled via pcbnew.ZONE_FILLER)
    gnd_zone = f"""
  (zone
    (net 1)
    (net_name "GND")
    (layer "B.Cu")
    (uuid "{uid()}")
    (hatch edge 0.5)
    (connect_pads (clearance 0.25))
    (min_thickness 0.25)
    (filled_areas_thickness no)
    (fill yes (thermal_gap 0.4) (thermal_bridge_width 0.4))
    (polygon
      (pts
        (xy 101.0 101.0) (xy 177.0 101.0) (xy 177.0 149.0) (xy 101.0 149.0)
      )
    )
  )"""

    nets_sexpr = "\n  ".join(f'(net {nid} "{nname}")' for nid, nname in nets)
    pcb_text = f"""(kicad_pcb
  (version 20240108)
  (generator "pcbnew")
  (generator_version "10.0")
  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )
  (paper "A4")
  (title_block
    (title "HRL Core Telemetry & Brand Showcase Node")
    (date "2026-10-31")
    (rev "1.0")
    (company "HRL International Pvt. Ltd.")
    (comment 1 "Autonomous Antigravity + KiCad 10 MCP Design")
    (comment 2 "Matte Black + 24K ENIG Gold + Penetrated HRL Main Logo")
  )
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (44 "Edge.Cuts" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )
  (setup
    (stackup
      (layer "F.SilkS" (type "Top Silk Screen") (color "White"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01) (color "Black"))
      (layer "F.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness 0.035))
      (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01) (color "Black"))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
      (copper_finish "ENIG")
      (dielectric_constraints no)
    )
    (pad_to_mask_clearance 0)
  )
  {nets_sexpr}

  {chr(10).join(fps)}

  {chr(10).join(outline)}
  {chr(10).join(logo_polys)}
  {chr(10).join(silk)}
  {chr(10).join(segments)}
  {chr(10).join(vias)}
  {keepout_zone}
  {gnd_zone}
)
"""
    out_pcb = ROOT / "hardware/project.kicad_pcb"
    out_pcb.write_text(pcb_text)
    print(
        f"Compiled {out_pcb} ({len(fps)} footprints, {len(segments)} 45-deg segments, "
        f"{len(vias)} GND vias, {len(logo_polys)} HRL logo polygons)."
    )


if __name__ == "__main__":
    main()
