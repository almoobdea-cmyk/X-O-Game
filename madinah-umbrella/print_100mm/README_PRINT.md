# Printable miniature, 100 mm, for a 0.4 mm nozzle

Scale 1:256. Assembled size 100 x 100 x 70.8 mm (100 mm is the fabric square, side to side;
corner to corner it is 141 mm). Open position, low variant.

This is a purpose-built print design, not the display model shrunk: each piece is one watertight
solid and the smallest wall is 0.9 mm. Made by `python3 print_model.py` (`--size 150` for other sizes).

| File | What | Size (mm) | How to place it |
|---|---|---|---|
| `canopy.stl` | Fabric, arms and mast | 100 x 100 x 20.9 | As supplied: upside down, arm tops flat on the bed, mast pointing up |
| `column.stl` | Base, shaft, capital, lantern with 4 lamps | 10.5 x 10.5 x 38.9 | As supplied: standing on its base |
| `cap.stl` | Small upper canopy, crown and finial | 25.7 x 25.7 x 13.8 | As supplied: flat base on the bed |
| `assembled_preview_do_not_print.stl` | The three pieces together, to look at | 100 x 100 x 70.8 | Not for printing |

## How the fabric was made printable

- The fabric is a 1.0 mm shell with the real funnel shape and the six scallops per side.
- The 8 main arms and 16 side arms are ribs on top of it, ending on the 24 edge points. On the real
  umbrella cables hang the fabric below the arms; here each rib is a solid fin down to the fabric,
  which is what holds the shell up while printing.
- The 24 seams and the ring of 24 diamonds are raised 0.3 mm on the underside.
- Left out because they are below 0.4 mm at this scale: struts, hinges, carving, lamp glass.
- The arm ribs are flat and level so the canopy can sit on the bed; the real arms rise about 2 mm
  (at this scale) toward the mast.

## Settings

- Layer height 0.16 to 0.2 mm, 3 walls, 15 % infill (most of it prints solid anyway).
- Supports: none needed for `column` and `cap`. `canopy` is designed to print without supports: the
  shell is bridged between the ribs, spans up to 16 mm. If your printer sags on bridges, turn on
  supports "build plate only"; they will sit on the top side, between the ribs.
- Brim: 5 mm on `column` (it is 39 mm tall on a 7 mm foot) and on `canopy`.
- Print slowly with full part cooling for the column shaft (3.5 mm thick) and the finial (0.9 mm tip).

## Assembly

1. Push the mast pin of the canopy into the hole on top of the column (2.7 mm pin, 0.18 mm clearance
   all round). A drop of glue fixes it.
2. Glue the cap on the centre of the canopy, its eight star points over the eight main ribs.
