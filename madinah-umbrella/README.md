# Madinah Piazza Umbrella — parametric 3D model

A 3D model of the 25.5 m convertible shading umbrella in the piazza of the
Prophet's Mosque in Madinah (SL Rasch "U26 Piazza", 250 units, completed 2010–11).

| File | What it is |
|---|---|
| `madinah_umbrella_low.glb` | Open umbrella, arm tips at 14.5 m |
| `madinah_umbrella_high.glb` | Open umbrella, arm tips at 15.3 m (the neighbour that overlaps the low one) |
| `madinah_umbrella_closed.glb` | Folded umbrella, 21.7 m tall, static |
| `stl/` | STL files for Blender: open (low, high) and closed, each whole and split by material (`export_stl.py` makes them) |
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
| Base pedestal | 1.84 m square, 0.70 m high; shaft starts at 1.27 m |
| Lower column shaft | 0.90 m across flats, 1.40 → 5.50 m |
| Cooling-fan axis | 3.96 m, drum Ø 1.12 m |
| Capital | 5.69 → 6.67 m, 0.90 m wide at the shaft, 1.72 m at the top |
| Slate frieze | 6.78 → 7.48 m, 1.68 m across flats |
| Lantern block | 7.64 → 9.30 m, 1.80 m across flats |
| Lamps (sill to eave) | 7.78 → 9.30 m, 2.67 m eave to eave |
| Membrane collar | 10.0 m |
| Lower strut hinge / arm root hinge / upper strut hinge | 10.86 / 14.15 / 16.20 m |
| Arm elbow radius | 6.6 m (middle arm), ×√2 on the diagonal |
| Membrane profile | steep funnel at the mast, 85 % of its rise reached at half span |
| Grid pitch between columns | about 24.1 m (so neighbours overlap by about 1.4 m) |

**[P] Interpreted from photographs** — these are plausible, not surveyed

- Base (from the close-up photo): square granite pedestal 1.84 m wide and 0.70 m high, its corners
  broached up to an octagonal top, a clipped-corner sunk panel on each face, then a low course,
  a scotia and one large roll under the octagonal shaft
- Three roll mouldings under the capital
- Capital (modelled as real relief, from the close-up photos): octagon at the shaft widening to a
  chamfered square; each main face has a shield medallion with a sphere boss and scrollwork on a
  quilted diamond lattice; each corner face has an arabesque panel with a bud above it
- Slate-blue frieze: bevelled sunk panel with three eight-pointed stars per main face, light chamfer faces
- Dog-tooth cornice under the lantern block
- Granite lantern block with re-entrant corner notches that end in pointed stops
- Four gilded lamps: polished back frame, engraved header with plain borders, engraved side panels
  cut to a quarter-arch with a polished bead, clear glass box bevelled back at the bottom over a
  ribbed reflector, stud band with three studs over a scotia and bottom band, deep eave and hipped roof
- Faceted (antiprism) gold crown from which the membrane pleats emerge
- Lotus ornament on the membrane: two inner petal tiers, a ring of 24 large blue diamonds,
  a ring of small diamonds, tall outer arches, blue scalloped edge trim; 6 scallops per side
- Gilded fluted crown and lance at the mast head (its height above the open arms is estimated)
- Fan drum, seven blades, guard rings, bracket housing

## Lighting design in the model

The lantern does two jobs, as labelled on the section drawing ("Piazza – and Facade Lighting"):

- 8 uplights on the lantern crown wash the underside of the membrane, which then
  works as a large soft reflector (`Membrane_Uplight_0…7`, warm white)
- 4 downlights, one per bay lantern, light the piazza floor (`Piazza_Downlight_0…3`)
- 1 small point light above the crown lifts the gathered pleats (`Collar_Glow`)
- The ribbed reflector behind the clear lamp glass is the emissive (glowing) material

They are stored in the GLB as `KHR_lights_punctual` lights. The viewer's
"Night lighting" button switches them on.

## Opening and closing

`madinah_umbrella_low.glb` and `_high.glb` carry one animation clip, `Close` (open at 0 s,
folded at 12 s; the real umbrella takes 180 s). `madinah_umbrella_closed.glb` is the folded
state as a static model. In the viewer use "Close umbrella" or drag the slider.

How it works, as read from the designer's section drawing (which overlays the folded state and
the arm sweep) and from the cladding maker's photos of bare, half-open and closed umbrellas:

1. An electric spindle inside the telescopic shaft pushes the top hub up by 3.55 m (15.95 → 19.50 m).
2. Each **upper strut** (2.88 m, hub to inner arm) swings its **inner arm** (4.10 m) from 10° above
   horizontal to vertical about the root hinge on the fixed mast at 14.15 m.
3. The **outer arm** (8.31 m) is hinged to the inner arm at the elbow. The **lower strut** (6.49 m, from
   the fixed mast at 10.86 m to a pin 0.90 m past the elbow) forces it to fold downward as the
   elbow rises, so each arm ends as an inverted V: inner arm up, outer arm hanging down.
4. The corner extensions of the diagonal arms and the 16 passive arms fold back along the outer arms first.
5. The mosaic cladding on top of the outer arms then faces outward. The eight panels close into
   the eight-sided casing. Each panel has a shallow ridge down its middle and a pointed petal at
   the elbow end carrying a faceted gilded lozenge.
6. The hub keeps rising until the gilded crown lands on the casing top: its skirt sits behind the
   petals and its eight ridges show in the notches between them, so casing and column read as one piece.
7. At the bottom the casing stays in one plane with no step. The four middle panels run straight
   down behind the pyramid roofs of the lamps. The four diagonal panels are trimmed along the roof
   slopes of the two neighbouring lamps and continue as a 0.54 m strip between the lamps, ending
   in a bronze V point at 8.4 m over the corner notch of the lantern block.

That is six hinges per arm (root, elbow, two per strut), matching the designer's description.
Folded, the finial tip is at 21.7 m, as published; the casing runs from 8.4 m (diagonal tips) to 20.0 m.

The strut lengths are not published. The hinge heights and inner-arm length are measured off the
drawing; the script then solves the lower-strut pin position so that one rigid linkage passes
through both the open and the folded pose (`kin_design`), and steps it through 49 positions (`kin_solve`).

## Supports, as seen from above

Checked against an aerial photo of open umbrellas (SL Rasch project page): nothing projects past the
fabric edge, and each of the eight main arms forks into two long side arms. In the model the four
middle arms end on the edge midpoints, the four diagonal arms reach the corners through a fold-back
extension, and the 16 passive arms fork off at about 60 % of the way out and end on the remaining
edge points: 24 supports for 24 edge points. Each passive arm swings on one oblique pin.

## Validation and parts list

`python3 validate.py` runs 48 checks and writes `VALIDATION.md`, `PARTS.md` and `parts.json`.
It checks that the linkage closes with rigid parts at every step, that every hardware joint is a
single pin or a straight slide, strut pushing angles, clearances against the mast, lantern block,
roof deck and lamps through the whole motion, headroom, footprint, casing fit, lighting, and the
exported files. It does not check strength: see the top of `VALIDATION.md`.

For a smaller model: `python3 validate.py --scale 0.1` writes the parts list at 1:10 (any scale works),
with each part's size, material, colour and the mesh name that holds its shape in the GLB.

## Known limits

- The linkage is a consistent reconstruction, not the fabrication geometry: the lower-strut pin
  position and the arm lengths (4.10 m inner, 8.31 m outer) are solved or chosen. The arm lengths are
  set so the middle arms end exactly on the fabric edge and the folded arms clear the lantern roof.
- The fold-back corner extension on the diagonal arms is my assumption for how a 36 m diagonal
  packs into a 9.5 m casing; I found no drawing of it.
- The membrane is moved by the arm rig and flattened inside the casing. It is not a cloth
  simulation, so half-open folds are approximate.
- The casing pattern (triple gold chevrons peaking on each panel ridge, fine turquoise stripes)
  follows the photos; the real surface is glass mosaic, here a flat texture. Panel stand-off from
  the arms (about 0.5 m) is set so the casing meets the lantern block; it is not a measured value.
- This is a reconstruction from one section drawing and published photographs,
  not from a survey or the fabrication drawings. Treat the `[P]` items and all
  small-part sizes as approximate (roughly ±10 %).
- The frieze plaques on the real columns carry inscriptions. The model uses an
  abstract geometric band instead of imitating them.
- The capital, frieze and lamp ornament follow the layout seen in the photos, but the exact
  scroll and arabesque line-work is my own drawing in the same style, not a tracing.
- The column-top proportions come from photo ratios tied to the drawing's levels; widths there
  are good to roughly ±10 %.

## Sources

- SL Rasch, Madinah Piazza Shading Project — https://www.sl-rasch.com/en/projects/u-26-piazza/
- Wikipedia, Medina Haram Piazza — https://en.wikipedia.org/wiki/Medina_Haram_Piazza
- Premier Composite Technologies, 25 m umbrellas — https://www.pct.ae/25m-umbrellas
- TensiNet project database — https://www.tensinet.com/index.php/projects-database/projects/3761
- Architect Magazine — https://www.architectmagazine.com/project-gallery/medina-haram-piazza/
- Saudi Press Agency — https://www.spa.gov.sa/en/N2111564
