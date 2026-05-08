// hardware/pipette_mount.scad
// Anycubic i3 Mega → DLAB dPette pipette mount adapter (v0)
//
// Bolts onto the X-carriage's stock 4-hole hot-end mounting pattern
// (the holes that previously held the heat-block in place — see
// docs/hardware.md, AGENT_REQUESTS.md). Drops the pipette body
// vertically into a split-clamp, which sits forward of the carriage
// face so the dPette tip is in the bed coordinate frame.
//
// PARAMETRIC. Every named dimension below is a measurement to verify
// against your own i3 Mega + dPette before printing. See README.md
// for the measurement workflow.
//
// Tested geometry (this revision):
//   - Designed for the i3 Mega-S "L-shaped" carriage front plate
//     (visible in `signal-2026-05-08-192633*.jpeg` reference photos),
//     with the 4 inner M3 holes arranged in a square around the
//     hot-end bore.
//
// Print suggestions:
//   Material:     PETG (PLA OK for bench testing, swap before any
//                 sustained operation since carriage warms slightly)
//   Layer:        0.2 mm
//   Walls:        4 perimeters
//   Infill:       50% gyroid
//   Orientation:  carriage-plate face on the bed, clamp axis pointing up
//   Supports:     none needed
//   Estimated:    ~25 g filament, ~2 h print time
//
// Render with: openscad pipette_mount.scad
// Export STL:  openscad -o pipette_mount.stl pipette_mount.scad

// =============================================================
// PARAMETERS — measure your unit and adjust
// =============================================================

// ---------- dPette barrel ----------
// The cylindrical grip section the clamp wraps around. Use calipers
// at the mid-grip; the dPette body has subtle ergonomic curves so
// 1-2 mm of slop in the bore is fine.
dpette_d           = 32.0;   // [mm] OD of the dPette barrel at clamp height
dpette_clamp_h     = 45.0;   // [mm] vertical clamp length
dpette_clamp_drop  = 35.0;   // [mm] vertical distance from carriage plate to TOP of clamp

// ---------- Carriage hot-end mounting pattern ----------
// The 4 M3 holes that held the V6 / MK7 / stock hot-end. Form a
// rectangle (often square at ~30 mm). Measure with calipers between
// hole centres on the actual carriage.
mount_hole_d       = 3.4;    // [mm] M3 clearance, with 0.2 mm play
mount_pattern_w    = 30.0;   // [mm] horizontal hole spacing (MEASURE)
mount_pattern_h    = 30.0;   // [mm] vertical hole spacing (MEASURE)

// ---------- Carriage interface plate ----------
plate_w            = 60.0;   // [mm] >= mount_pattern_w + 2 * 12 (border)
plate_h            = 60.0;   // [mm] >= mount_pattern_h + 2 * 12 (border)
plate_t            = 4.0;    // [mm] structural thickness in PETG
plate_relief_d     = 18.0;   // [mm] central pass-through for hot-end bore
                              //      (so the existing hot-end recess
                              //      doesn't push the plate off the
                              //      carriage face); 0 to disable

// ---------- Forward bridge ----------
// Connects the carriage plate to the clamp. The clamp sits forward
// of the carriage face so the pipette body clears the linear rails.
bridge_t           = 6.0;    // [mm] thickness of the bridge wall
bridge_offset_y    = 32.0;   // [mm] forward offset of clamp center from plate face
bridge_rib_w       = 12.0;   // [mm] gusset width on each side for stiffness

// ---------- Back brace + carriage-top anchor (replaces wrap-over) ----------
// The L bracket alone is a single mounting region. The user observed
// (image #13 in design discussion) that the pipette needs to be
// supported by BOTH parts of the carriage — the L bracket AND the
// carriage body's top face above it.
//
// This stabilizer is one continuous structure:
//   1. Back riser: vertical wall extending UP from the mount plate
//      top edge, passing BEHIND the L's vertical face (offset back
//      by `back_riser_t`) and BEHIND the carriage's vertical face
//      above the L. Total height = l_face_h + carriage_above_l_h.
//      This assumes the L's vertical face and the carriage's
//      vertical face are roughly flush in Y; if your unit has a
//      step, increase `back_riser_t` to bridge the gap.
//   2. Top arm: horizontal flange at the very top, extends BACK
//      across the carriage's top face by `top_arm_y`. Has 2 M3
//      bolt holes that align with the carriage's top corner mount
//      holes (the screws visible at the upper-left and upper-right
//      of the carriage's top plate in reference photos).
//
// Net effect: the load path now reaches the carriage via two
// regions — the L (4 lower M3 screws) and the carriage top
// (2 upper M3 screws). True triangulation; the cantilever
// becomes a fully-closed two-anchor truss.
//
// Set `carriage_above_l_h = 0` to disable the upper anchor entirely
// (e.g. if your carriage doesn't have usable top corner holes).

l_face_h            = 55.0;  // [mm] height of L's vertical face — MEASURE
carriage_above_l_h  = 25.0;  // [mm] height of carriage body above L's top — MEASURE; 0 disables
back_riser_t        = 4.0;   // [mm] thickness of the back riser wall

top_arm_y           = 30.0;  // [mm] depth of top arm across carriage top
top_arm_t           = 4.0;   // [mm] thickness of top arm
top_mount_pattern_w = 50.0;  // [mm] X spacing of carriage top corner holes — MEASURE
top_mount_offset_y  = 8.0;   // [mm] Y offset from carriage front face to corner holes — MEASURE
top_mount_d         = 3.4;   // [mm] M3 clearance for top corner mount screws

// ---------- Split clamp ----------
clamp_wall_t       = 4.0;    // [mm] wall around the bore
clamp_kerf         = 1.6;    // [mm] split width (kerf for tightening)
clamp_screw_d      = 3.4;    // [mm] M3 clearance for the tightening screw
clamp_nut_w        = 5.7;    // [mm] M3 nut across-flats (DIN 934)
clamp_nut_t        = 2.6;    // [mm] M3 nut thickness
clamp_ear_w        = 12.0;   // [mm] width of each "ear" beside the kerf

// ---------- Cosmetic ----------
fillet_r           = 1.5;
$fn                = 96;

// =============================================================
// DERIVED
// =============================================================

bore_r       = dpette_d / 2;
clamp_outer_r = bore_r + clamp_wall_t;
clamp_y      = bridge_offset_y;          // clamp axis Y position (forward of plate face)
clamp_z_top  = -dpette_clamp_drop;       // top of clamp, below the plate
clamp_z_bot  = clamp_z_top - dpette_clamp_h;

// =============================================================
// MODULES
// =============================================================

// Plate that bolts to the X-carriage's 4 hot-end mounting holes.
// Plate face lies in the XY plane, +Z points away from the carriage,
// +Y points forward (toward the bed in the printer's frame).
module carriage_plate() {
    difference() {
        translate([-plate_w/2, -plate_h/2, 0])
            cube([plate_w, plate_h, plate_t]);

        // 4 M3 mounting holes
        for (x = [-mount_pattern_w/2, mount_pattern_w/2])
            for (y = [-mount_pattern_h/2, mount_pattern_h/2])
                translate([x, y, -0.1])
                    cylinder(d=mount_hole_d, h=plate_t + 0.2);

        // Center relief for original hot-end bore (so the plate sits flat)
        if (plate_relief_d > 0)
            translate([0, 0, -0.1])
                cylinder(d=plate_relief_d, h=plate_t + 0.2);
    }
}

// Bridge: a vertical web from the plate forward edge dropping to the
// clamp. Simple flat wall, with optional gussets for stiffness.
module bridge() {
    // Main vertical wall, hugging the front edge of the plate
    translate([-bridge_t/2, plate_h/2 - bridge_t, clamp_z_top])
        cube([bridge_t, bridge_offset_y + bridge_t, dpette_clamp_drop + plate_t]);

    // Two side gussets (triangular ribs) for torsional stiffness
    for (mx = [-1, 1])
        translate([mx * (bridge_t/2 + bridge_rib_w/2), plate_h/2 - bridge_t, clamp_z_top])
        translate([0, 0, 0])
        difference() {
            cube([bridge_rib_w, bridge_offset_y + bridge_t, dpette_clamp_drop + plate_t]);
            // Cut a diagonal so it's a triangular gusset (not a full block)
            translate([-0.1, 0, 0])
                rotate([0, 0, 0])
                rotate([atan2(dpette_clamp_drop, bridge_offset_y), 0, 0])
                    translate([-0.1, 0, 0])
                        cube([bridge_rib_w + 0.2,
                              sqrt(pow(bridge_offset_y, 2) + pow(dpette_clamp_drop, 2)) + 5,
                              dpette_clamp_drop + plate_t + 5]);
        }
}

// Vertical split clamp for the dPette body. Bore axis is parallel to Z
// (vertical when printer is upright). The kerf opens along +Y (toward
// the front of the printer), so tightening pulls the clamp around
// the pipette without pushing it backward into the carriage.
module clamp() {
    translate([0, clamp_y, clamp_z_bot])
    difference() {
        // Clamp body + ears
        union() {
            cylinder(r=clamp_outer_r, h=dpette_clamp_h);
            // Tightening ears on +Y side, straddling the kerf
            translate([-clamp_ear_w/2 - clamp_kerf/2 - clamp_outer_r/2, 0, 0])
                cube([clamp_outer_r + clamp_kerf + clamp_ear_w, clamp_outer_r + clamp_ear_w, dpette_clamp_h]);
        }

        // Bore for the dPette
        translate([0, 0, -0.1])
            cylinder(r=bore_r, h=dpette_clamp_h + 0.2);

        // Kerf — splits the clamp on the +Y side
        translate([-clamp_kerf/2, 0, -0.1])
            cube([clamp_kerf, clamp_outer_r + clamp_ear_w + 1, dpette_clamp_h + 0.2]);

        // M3 screw clearance through right ear
        translate([clamp_kerf/2 + clamp_ear_w/2, clamp_outer_r + clamp_ear_w/2, dpette_clamp_h/2])
            rotate([0, 90, 0])
                cylinder(d=clamp_screw_d, h=clamp_ear_w + 2, center=true);

        // M3 nut inset on left ear (hex pocket)
        translate([-(clamp_kerf/2 + clamp_ear_w - clamp_nut_t/2), clamp_outer_r + clamp_ear_w/2, dpette_clamp_h/2])
            rotate([0, 90, 0])
                cylinder(d=clamp_nut_w / cos(30) + 0.4, h=clamp_nut_t, center=true, $fn=6);
    }
}

// Back brace + carriage-top anchor: one continuous riser from the
// mount plate top up past the L's vertical face AND the carriage
// body's vertical face, terminating in a horizontal flange that
// bolts to the carriage's top corner holes.
//
// Cross-section in the YZ plane, looking from +X:
//
//        +Z
//         │
//         │  ┌────────────────────┐ ← top arm (sits on carriage top,
//         │  │  ○             ○   │   2 M3 holes for corner mounts)
//         │  └─┬──────────────────┘
//         │    ░  ← back riser (passes BEHIND L + carriage faces)
//         │    ░     `carriage_above_l_h` mm of carriage body height
//         │    ░
//   ──────┼────░──────────────────── top of L's vertical face
//         │    ░     `l_face_h` mm of L's vertical face height
//         │    ░
//   ──────┼────┴────────────────── top of mount plate (z = plate_t)
//         │  ▒▒▒
//         │  ▒▒▒  ← mount plate (4 M3 holes into L's vertical face)
//         │  ▒▒▒
//         └────────► +Y (forward, away from carriage)
//
// Two anchor regions = triangulated load path. Pipette no longer
// hangs off a single attachment point.
module back_brace() {
    // Back riser — extend down through the plate by plate_t for a
    // clean union (avoids CGAL non-manifold-edge warning).
    total_riser_h = plate_t + l_face_h + carriage_above_l_h;
    translate([-plate_w/2, -plate_h/2 - back_riser_t, 0])
        cube([plate_w, back_riser_t, total_riser_h]);

    // Top arm — only emit if the carriage anchor is enabled.
    if (carriage_above_l_h > 0) {
        translate([-plate_w/2, -plate_h/2 - back_riser_t, total_riser_h - 0.01])
        difference() {
            cube([plate_w, back_riser_t + top_arm_y, top_arm_t + 0.01]);
            // 2 M3 holes for carriage top corner mounts
            for (xc = [(plate_w - top_mount_pattern_w)/2,
                       (plate_w + top_mount_pattern_w)/2])
                translate([xc, back_riser_t + top_mount_offset_y, -0.1])
                    cylinder(d=top_mount_d, h=top_arm_t + 0.4);
        }
    }
}

// =============================================================
// ASSEMBLY
// =============================================================

union() {
    carriage_plate();
    bridge();
    clamp();
    back_brace();
}
