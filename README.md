# pcb2stl

Convert a PCB copper layer (**Gerber**, **SVG** or **DXF**) into a watertight **STL**
you can slice in any FDM slicer and "print" with a pen — to draw etch-resist directly
onto copper-clad board (3D-printer pen plotter, then etch).

Two outputs: a clean **STL** to slice yourself, or **G-code straight for a pen
plotter** — perimeters plus fill, pen up/down on Z, with no extrusion, heating or
fan commands. Use the slicer when you want its tuning; skip it when you just want
to draw.

## Quick start

```sh
docker compose up --build      # then open http://localhost:8000
# or
docker build -t pcb2stl . && docker run -p 8000:8000 pcb2stl
```

Open the browser UI, drop a Gerber/SVG/DXF, set the layer height (≈ your pen width),
optionally mirror, preview in 3D, and download the STL.

For a **two-layer board**, tick *Double-sided* and add the bottom layer: you get a ZIP
with `top.stl` and a mirrored `bottom.stl`, both carrying two ring registration
fiducials in the margins. Drill those, pin the board, and flip — the sides stay aligned.

## How it works

```
Gerber / SVG / DXF ─► 2D polygons (mm) ─► union ─► manifold extrude (1 layer) ─► STL
```

- **Gerber** is flattened with `gerbonara`, **SVG** with `svgelements`, **DXF** with
  `ezdxf` (closed shapes become copper, width-carrying polylines become traces).
- Overlapping copper is unioned with `shapely`; pads/traces become one clean region.
- `manifold3d` extrudes it to a guaranteed-watertight solid; `trimesh` writes the STL.

Internally the geometry is a format-agnostic polygon model, so adding an input format
is just adding a parser — nothing else changes.

## Slicer settings for pen plotting

- **Layer height = STL height** (set in the UI) so the model slices to a single pass.
- **Extrusion/line width = your pen width** so each trace is covered in one stroke.
- **Z-hop on travel** to lift the pen between strokes (or use a spring-loaded pen mount).
- Strip extrusion (`E`) in a post-processor, or ignore it on a pen toolhead.

## Direct G-code (no slicer)

Pick *G-code* as the output to drive a 3D-printer pen mod (e.g. an Ender 3 V2 with
the extruder removed) directly. pcb2stl fills each copper region with concentric
perimeters and a zig-zag, and emits Marlin G-code that only moves X/Y and lifts the
pen on Z — no `E`, no `M104/M109`, no fan.

- Set **pen width** to your marker, **draw Z** to where the pen meets the board, and
  **travel Z** to a safe lift height. Calibrate draw Z against your bed.
- The pen is raised/lowered with Z (works for a fixed or spring-loaded mount). Homing
  (`G28`) runs first, so the board origin must match the printer's.
- Targets Marlin (Ender-class). Bambu printers are locked down and need their own
  toolchain, so plain G-code is not guaranteed there.

### Placing the board

The toolpaths start at a fixed **work origin** (default X10 Y10) with the copper inset
by the **board margin**. To seat the physical board there repeatably, download the
**placement jig** — an STL sized to your board — print it, fix it on the bed with its
inner corner at the work origin, and butt the board into the L. Cut the board to the
copper extent plus that margin on each side so it fills the jig.

## Local development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn pcb2stl.api:app --reload
```

## Status & limits

- Pads are solid (drill after etching).
- SVG without a physical size, and DXF without `$INSUNITS`, are read as millimetres.
- Double-sided alignment is by drilled registration holes; there is no copper-fill
  drill output yet.

## License

MIT — see `LICENSE`.
