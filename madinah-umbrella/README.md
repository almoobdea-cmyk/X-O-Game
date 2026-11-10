# Madinah Piazza Umbrella — parametric 3D model

A 3D model of the 25.5 m convertible shading umbrella in the piazza of the
Prophet's Mosque in Madinah (SL Rasch "U26 Piazza", 250 units, completed 2010–11).

| File | What it is |
|---|---|
| `madinah_umbrella_low.glb` | Open umbrella, arm tips at 14.5 m |
| `madinah_umbrella_high.glb` | Open umbrella, arm tips at 15.3 m (the neighbour that overlaps the low one) |
| `viewer.html` | Self-contained interactive viewer (both models embedded; needs internet once for three.js) |
| `build_umbrella.py` | The generator — every dimension is a named constant at the top |
| `textures/` | Generated textures (membrane ornament, stone, carved capital, frieze, mosaic, glass, floor) |
| `renders/` | Views rendered from the model |

Units are metres, Y is up, the origin is on the piazza floor at the column axis.
The GLB opens directly in Blender, Windows 3D Viewer, macOS Quick Look (after
conversion), three.js, Unity and Unreal. Rebuild with `python3 build_umbrella.py`
(needs `numpy` and `Pillow`).

## Where the geometry comes from

Three levels of confidence, marked in the script as `[D]`, `[M]`, `[P]`:

**[D] Published by the designer** (SL Rasch project page)

- Folded height 21.7 m; deployed height 14.4/14.5 m or 15.3 m (two heights so the membranes overlap)
- 4 middle arms, 4 diagonal arms, 16 passive arms; folding arm system with six hinges
- PTFE membrane with coloured tapes and seams; GRP cladding panels with glass mosaic on the arms
- Shaded area about 600 m² per umbrella; 40 t; electric spindle drive
- Membrane 25.5 × 25.5 m (Sefar / Architect Magazine)
- 16 mist outlets per cooling fan (Saudi Press Agency reports)

**[M] Measured off the designer's section drawing** (scaled from the 21.7 m folded
height; cross-checked against the +15.3 and +14.5 level marks and the 1.75 m figure)

| Item | Value |
|---|---|
| Base plinth width / height | 1.88 m / 1.40 m to the shaft |
| Lower column shaft | 1.10 m across flats, 1.40 → 5.50 m |
| Cooling-fan axis | 3.96 m, drum Ø 1.12 m |
| Capital | 5.70 → 6.67 m |
| Frieze band | 6.75 → 7.55 m, 1.42 m wide |
| Lantern (piazza and facade lighting) | 7.90 → 9.35 m, 2.4 m across the bays |
| Membrane collar | 10.3 m |
| Lower strut hinge / arm root hinge / upper strut hinge | 10.86 / 14.15 / 16.20 m |
| Arm elbow radius | 6.6 m (middle arm), ×√2 on the diagonal |
| Membrane profile | steep funnel at the mast, 85 % of its rise reached at half span |
| Grid pitch between columns | about 24.1 m (so neighbours overlap by about 1.4 m) |

**[P] Interpreted from photographs** — these are plausible, not surveyed

- Octagonal column with granite-like cladding, torus base mouldings, astragal rings
- Capital changing from octagon to chamfered square, with a carved shield medallion per face
- Dark frieze with a framed plaque per face
- Four gilded bay lanterns with arched spandrels, louvred glass and gable roofs; gilded crown
- Lotus ornament on the membrane: two inner petal tiers, a ring of 24 large blue diamonds,
  a ring of small diamonds, tall outer arches, blue scalloped edge trim; 6 scallops per side
- Gilded fluted crown and lance at the mast head (its height above the open arms is estimated)
- Fan drum, seven blades, guard rings, bracket housing

## Lighting design in the model

The lantern does two jobs, as labelled on the section drawing ("Piazza – and Facade Lighting"):

- 8 uplights on the lantern crown wash the underside of the membrane, which then
  works as a large soft reflector (`Membrane_Uplight_0…7`, warm white)
- 4 downlights, one per bay lantern, light the piazza floor (`Piazza_Downlight_0…3`)
- The bay glass is an emissive material

They are stored in the GLB as `KHR_lights_punctual` spot lights. The viewer's
"Night lighting" button switches them on.

## Known limits

- Only the open state is modelled. The folded state (arms upright, cladding
  closed into a prismatic casing, 21.7 m tall) is not.
- This is a reconstruction from one section drawing and published photographs,
  not from a survey or the fabrication drawings. Treat the `[P]` items and all
  small-part sizes as approximate (roughly ±10 %).
- The frieze plaques on the real columns carry inscriptions. The model uses an
  abstract geometric band instead of imitating them.
- Carving is painted into the texture, not modelled as relief.

## Sources

- SL Rasch, Madinah Piazza Shading Project — https://www.sl-rasch.com/en/projects/u-26-piazza/
- Wikipedia, Medina Haram Piazza — https://en.wikipedia.org/wiki/Medina_Haram_Piazza
- Premier Composite Technologies, 25 m umbrellas — https://www.pct.ae/25m-umbrellas
- TensiNet project database — https://www.tensinet.com/index.php/projects-database/projects/3761
- Architect Magazine — https://www.architectmagazine.com/project-gallery/medina-haram-piazza/
- Saudi Press Agency — https://www.spa.gov.sa/en/N2111564
