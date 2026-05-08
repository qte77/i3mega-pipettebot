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

// ---------- Top wrap-over stabilizer ----------
// The L-shaped carriage bracket cantilevers off the X-carriage with
// only its top flange bolted up. Adding a pipette puts a forward
// moment on it and the L will flex / twist. The wrap-over:
//   1. Extends UP from the mount plate's top edge by `l_face_h`
//      (the height of the L's vertical face — measure on yours).
//   2. Folds BACK by `wrap_depth_y` across the TOP of the L's
//      horizontal flange.
// Net effect: the mount's load path now reaches the carriage via
// both the L's vertical face (4 inner M3 screws) AND the L's top
// flange (this wrap resting on it), turning the cantilever into
// a closed truss. No new holes need to be drilled.
//
// Optional: a single M3 through-hole in the wrap (`wrap_bolt_d` > 0)
// lets you use a longer-than-stock bolt that goes through wrap +
// L flange + carriage in one shot for positive lock.
l_face_h           = 55.0;   // [mm] height of the L's vertical face — MEASURE
wrap_depth_y       = 22.0;   // [mm] how far back the wrap extends over the L's top
wrap_t             = 4.0;    // [mm] thickness of the wrap walls
wrap_bolt_d        = 0.0;    // [mm] M3 clearance through-hole; 0 to disable
wrap_bolt_offset_y = 11.0;   // [mm] bolt position from L vertical face (along wrap)

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

// Top wrap-over: rises above the mount plate to span the L's vertical
// face, then folds back over the L's horizontal top flange. Bolts to
// the same plate (printed monolithic) so all loads transfer through
// the printed material — no fasteners needed unless `wrap_bolt_d > 0`.
//
// Geometry (cross-section in the YZ plane, looking from +X):
//
//        +Z
//         │
//         │   ┌──────────────────┐ ← horizontal arm of wrap (rests on
//         │   │                  │   top of L's horizontal flange)
//         │   │                  │
//   ──────┼───┴──────────────────┴─── y=0 plane (top of L's vertical face)
//         │   │ ↑
//         │   │ │
//         │   │ │ rises along the BACK side of the L's vertical face,
//         │   │ │ aligned with the mount plate's back edge
//         │   │ ↓
//   ──────┼───┴────────────────────── top of mount plate (z = plate_t)
//         │   ░
//         │   ░ ← mount plate (here)
//         │   ░
//         └─────► +Y (forward, away from carriage)
//
// Note: the wrap's vertical riser is OUTSIDE the L (against the back
// of the L's vertical face, i.e. the side facing the carriage), so it
// doesn't fight the 4 M3 mount screws. It does increase the standoff
// of the mount plate from the L's vertical face by `wrap_t` — bake
// that into bolt-length selection (M3 × 12 instead of M3 × 8).
module top_wrap() {
    // Wrap rises at the BACK edge of the mount plate (y = -plate_h/2),
    // goes up by l_face_h, then folds back further by wrap_depth_y.
    // The riser hugs the top edge of the L's vertical face.
    union() {
        // Vertical riser (against back of L's vertical face).
        // Extend DOWN through the plate so the riser shares a clean
        // face with the plate (rather than meeting it edge-to-edge,
        // which CGAL flags as non-manifold).
        translate([-plate_w/2, -plate_h/2 - wrap_t, 0])
            cube([plate_w, wrap_t, l_face_h + plate_t]);

        // Horizontal arm (sits on top of L's horizontal flange).
        // Overlaps the riser by `wrap_t` on the +Z side for the same
        // manifold reason.
        translate([-plate_w/2, -plate_h/2 - wrap_t, l_face_h + plate_t - 0.01])
            difference() {
                cube([plate_w, wrap_t + wrap_depth_y, wrap_t + 0.01]);
                if (wrap_bolt_d > 0)
                    translate([0, wrap_t + wrap_bolt_offset_y, -0.1])
                        cylinder(d=wrap_bolt_d, h=wrap_t + 0.4);
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
    top_wrap();
}
