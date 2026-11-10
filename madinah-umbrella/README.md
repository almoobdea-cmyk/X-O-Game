# Madinah Piazza umbrella

Parametric CAD model of one convertible umbrella from the piazza of the
Prophet's Mosque in Madinah (SL Rasch "U-26 Piazza"), in the open position.

| File | What it is |
| --- | --- |
| `src/madinah_umbrella.py` | The model source (build123d through `cadgen`) |
| `STEP/madinah_umbrella.step` | Exact CAD geometry, millimetres, Z up |
| `GLB/madinah_umbrella.glb` | Coloured mesh, metres, Y up |

Rebuild:

```bash
uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.23 python src/madinah_umbrella.py
```

## Dimensions

Published figures (SL Rasch project data and Saudi press):

- Canopy 25.5 m x 25.5 m
- Open height 15.3 m (set `OPEN_HEIGHT = 14_400` for the shorter type)
- Folded height 21.7 m
- 4 diagonal, 4 middle and 16 passive arms
- PTFE membrane with blue ornament, GRP cladding with glass mosaic,
  gold-plated brass trim, 4 lighting units per column,
  misting fans with 16 spray outlets

Estimates (no drawings or photos were available when this was built):

- Funnel low point 9.45 m, edge mid-point height 13.9 m
- Arm sections, hinge and strut positions
- Column: 1.3 m shaft, plinth, capital to 8.05 m, panel layout
- Lantern design and 5.0 m mounting height, uplight positions
- The ornament layout is stylised; the real pattern is finer

The arm pivot height and middle arm length were chosen so that the folded
stack comes to about the published 21.7 m.
