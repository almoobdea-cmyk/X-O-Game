---
name: image-to-3d
description: >
  من صورة الى 3D — يستقبل اسم أو وصف منتج/مبنى/مجسّم فقط، ثم يبحث عن صوره
  ومقاساته، يحلّلها هندسياً، ويبني له نموذجاً ثلاثي الأبعاد تفاعلياً دقيقاً
  مع جدول المقاسات. Takes only the name or description of an object (product,
  building, monument, tool), researches reference photos and dimensions,
  measures them like an engineer, and builds an accurate interactive 3D model
  with a dimension schedule. Use when the user says «من صورة الى 3D»،
  «سوّ لي مجسم»، «حوّله ثري دي»، "image to 3D", "model this in 3D", or names an
  object and asks for a precise 3D version of it.
argument-hint: "<اسم أو وصف المنتج>"
---

# من صورة الى 3D

The user gives a name or a description, nothing else. Do the research, the
measuring and the modelling yourself, and do not come back with questions
unless the name is ambiguous between clearly different objects. Reply in the
user's language.

The deliverable is one self-contained HTML page: an orbitable Three.js model
on top, the measured schedule and the method underneath, published as an
Artifact. `references/green-dome-example.html` is a complete finished example
(the Green Dome in Madinah); copy its scaffold rather than starting from zero.

## 1. Research

Run these together:

- Web search for published dimensions, in English and in the object's own
  language (Arabic names find Arabic sources). Note which numbers are for the
  thing itself and which are for a neighbour or an earlier version; sources
  mix them up.
- Reference photos. Any photo the user attached counts as a reference and is
  usually the most relevant one. Then find more: you need at least one sharp,
  high-resolution, near-orthographic view (telephoto, side-on), plus oblique
  views for depth and for parts hidden in the main one.

Cloud sandboxes block most image hosts. Check reachability before planning
around a source. Wikimedia Commons is usually reachable: read the category
page HTML for `File:` names and download through
`https://commons.wikimedia.org/wiki/Special:FilePath/<name>?width=1600` with
a descriptive User-Agent, a few seconds apart, retrying on 429. Its API is
often rate-limited when the pages are not. Put downloads in their own folder
in the scratchpad.

## 2. Look closely

View every reference at full size, then crop and upscale the parts that carry
detail (edges, joints, ornaments, openings, the top, the base) and view the
crops. Most of the model's quality comes from this step: counts, mouldings
and small features are invisible at overview scale.

Write down, per part: shape, how it joins its neighbours, how many times it
repeats, colour and finish.

## 3. Measure like an engineer

- **Profile.** For anything with a silhouette against a clean background,
  trace the edge in code (PIL + numpy: classify pixels by colour, take the
  first and last hit per row every ~10 px). Use the cleaner side when one is
  in shadow. This gives the true curve; do not assume a hemisphere, a
  cylinder or a circle.
- **Counts.** Count repeats in a crop. For a faceted ring, the facet width at
  the centre over the full width gives sin(π/N). Cross-check counts against
  each other (features per facet × facets).
- **Scale.** Prefer a published dimension. Without one, anchor on something
  of known size in the photo (ladder rungs ≈ 0.28 m, a door, a brick, a
  person, a standard fitting) and say so.
- **Cross-check** the result against any published number, and state the
  expected error separately for ratios and for absolute size.

Never present an estimate as a surveyed figure.

## 4. Build

Follow the example file's structure:

- Three.js r128 from cdnjs (`.../three.js/r128/three.min.js`), the UMD build.
  r128 has no colour management: convert every material colour with
  `convertSRGBToLinear()` once after building, set `outputEncoding` to sRGB,
  skip tone mapping, and keep light intensities near 1 total. Skipping this
  makes every colour look washed out.
- One block of named constants at the top for every measured level and
  radius, in metres (or mm for small products), so the schedule and the model
  cannot drift apart.
- Revolved parts from the traced profile (`LatheGeometry` through a
  Catmull-Rom curve). Faceted parts as low-segment cylinders with flat
  shading. Repeated ornaments as one geometry placed around a ring. Openings
  as a raised frame plus a darker inset panel. Fine surface pattern as a
  canvas texture.
- The example's own orbit camera (drag, wheel, pinch), named view presets,
  turntable, sun slider, dimension overlay, and optional context. Expose
  `window.__model = {setView, setAuto}` for the test script.
- The page text: a schedule table bottom to top, a short "how the numbers
  were derived" section, and a note listing every modelled assumption.

Load the `artifact-design` guidance (or the Artifact quickstart) before
writing the page, and follow its contract.

## 5. Check against the photos

`npm i three@0.128.0` in the scratchpad, then
`node scripts/shot.js <page> <three.min.js> <outDir> <views…>`. View the
renders next to the reference crops and fix what differs: silhouette first,
then proportions of each band, then colour, then details. Add a view that
matches the camera position of the best reference photo. Two or three rounds
is normal. Finish with the full-page desktop and phone screenshots.

## 6. Deliver

Publish the page as an Artifact and give the link. In the reply: the schedule
table, how the scale was fixed and its error, the cross-check, the list of
assumptions and which parts are least certain, and the sources as links.
Say plainly what you rendered and checked and what you did not.
