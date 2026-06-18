# pcb2stl

Convert a PCB copper layer (**Gerber** or **SVG**) into a watertight **STL** you can
slice in any FDM slicer and "print" with a pen — to draw etch-resist directly onto
copper-clad board (3D-printer pen plotter, then etch).

The slicer stays yours: its line-width, infill and travel settings give you full
control over how the pen fills traces and pads. pcb2stl only does the part the
slicer can't — turning copper artwork into a clean, manifold solid.

## Quick start

```sh
docker compose up --build      # then open http://localhost:8000
# or
docker build -t pcb2stl . && docker run -p 8000:8000 pcb2stl
```

Open the browser UI, drop a Gerber/SVG, set the layer height (≈ your pen width),
optionally mirror, preview in 3D, and download the STL.

## How it works

```
Gerber / SVG ─► 2D polygons (mm) ─► union ─► manifold extrude (1 layer) ─► STL
```

- **Gerber** is flattened with `gerbonara`, **SVG** with `svgelements` (curves sampled).
- Overlapping copper is unioned with `shapely`; pads/traces become one clean region.
- `manifold3d` extrudes it to a guaranteed-watertight solid; `trimesh` writes the STL.

Internally the geometry is a format-agnostic polygon model, so adding an input format
is just adding a parser — nothing else changes.

## Slicer settings for pen plotting

- **Layer height = STL height** (set in the UI) so the model slices to a single pass.
- **Extrusion/line width = your pen width** so each trace is covered in one stroke.
- **Z-hop on travel** to lift the pen between strokes (or use a spring-loaded pen mount).
- Strip extrusion (`E`) in a post-processor, or ignore it on a pen toolhead.

## Local development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn pcb2stl.api:app --reload
```

## Status & limits

- Single copper layer. Pads are solid (drill after etching).
- SVG must declare a physical size (mm); KiCad plots do.
- Double-sided registration and DXF input are not implemented yet.

## License

MIT — see `LICENSE`.
