import { Viewer } from './viewer.js';

const viewer = new Viewer(document.getElementById('viewer'));
const el = (id) => document.getElementById(id);
const els = {};
for (const id of [
  'outputSeg', 'viewSeg', 'drop', 'file', 'fileName', 'dropLabel', 'bottomRow', 'file2', 'file2Name',
  'mirror', 'stlOpts', 'gcodeOpts', 'height', 'double', 'penWidth', 'perimeters', 'fill', 'drawZ',
  'travelZ', 'drawFeed', 'travelFeed', 'boardMargin', 'originX', 'originY', 'boardThickness', 'jig',
  'convert', 'download', 'status', 'statusText', 'dims', 'fit', 'hideTravel', 'legend', 'statsChip',
  'statStrokes', 'statDist',
]) els[id] = el(id);

let output = 'stl';
let result = { blob: null, name: 'board.stl' };

setupSeg(els.outputSeg, 'output', setOutput);
setupSeg(els.viewSeg, 'view', (v, btn) => { if (!btn.disabled) setView(v); });
setupDrop(els.drop, els.file, els.fileName);
setupDrop(els.bottomRow, els.file2, els.file2Name);
els.double.addEventListener('change', () => setOutput(output));
els.hideTravel.addEventListener('change', () => viewer.setTravelVisible(!els.hideTravel.checked));
els.fit.addEventListener('click', () => viewer.fit());
els.convert.addEventListener('click', convert);
els.download.addEventListener('click', () => saveBlob(result.blob, result.name));
els.jig.addEventListener('click', downloadJig);

setOutput('stl');
setView('solid');

function setOutput(value) {
  output = value;
  select(els.outputSeg, 'output', value);
  const gcode = value === 'gcode';
  const dbl = !gcode && els.double.checked;
  els.gcodeOpts.classList.toggle('hidden', !gcode);
  els.stlOpts.classList.toggle('hidden', gcode);
  els.bottomRow.classList.toggle('hidden', !dbl);
  els.dropLabel.textContent = dbl ? '⤓ Top layer (F.Cu)' : '⤓ Drop or click — Gerber / SVG / DXF';
  els.convert.textContent = gcode ? 'Generate G-code' : dbl ? 'Convert both sides' : 'Convert & preview';
  els.download.textContent = gcode ? 'Download .gcode' : dbl ? 'Download ZIP' : 'Download STL';
  if (!gcode) {
    enableToolpaths(false);
    setView('solid');
  }
}

function setView(value) {
  select(els.viewSeg, 'view', value);
  viewer.setMode(value);
  const tp = value === 'toolpaths';
  els.legend.classList.toggle('hidden', !tp);
  els.statsChip.classList.toggle('hidden', !tp);
}

function enableToolpaths(on) {
  els.viewSeg.querySelector('[data-view="toolpaths"]').disabled = !on;
}

function convert() {
  if (output === 'gcode') return convertGcode();
  return els.double.checked ? convertDouble() : convertSingle();
}

async function convertSingle() {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a Gerber, SVG or DXF file first.', 'err');
  await run(async () => {
    const buffer = await postBinary('/api/convert', formWith(file, { height_mm: els.height.value, mirror: bool(els.mirror) }));
    keep(new Blob([buffer], { type: 'model/stl' }), stem(file.name) + '.stl');
    showDims(viewer.showSolid(buffer.slice(0)));
    enableToolpaths(false);
    setView('solid');
    setStatus('Done — slice it in your slicer to pen-plot.', 'ok');
  });
}

async function convertDouble() {
  const top = els.file.files[0];
  const bottom = els.file2.files[0];
  if (!top || !bottom) return setStatus('Choose both the top and bottom layers.', 'err');
  const archive = new FormData();
  archive.append('top', top);
  archive.append('bottom', bottom);
  archive.append('height_mm', els.height.value);
  await run(async () => {
    const [zip, stl] = await Promise.all([
      postBinary('/api/convert-double', archive),
      postBinary('/api/convert', formWith(top, { height_mm: els.height.value })),
    ]);
    keep(new Blob([zip], { type: 'application/zip' }), 'pcb2stl-double-sided.zip');
    showDims(viewer.showSolid(stl));
    enableToolpaths(false);
    setView('solid');
    setStatus('Top + bottom (mirrored) with registration holes.', 'ok');
  });
}

async function convertGcode() {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a Gerber, SVG or DXF file first.', 'err');
  const geom = {
    pen_width_mm: els.penWidth.value, perimeters: els.perimeters.value, fill: bool(els.fill),
    mirror: bool(els.mirror), origin_x_mm: els.originX.value, origin_y_mm: els.originY.value,
    board_margin_mm: els.boardMargin.value,
  };
  const motion = {
    ...geom, draw_z_mm: els.drawZ.value, travel_z_mm: els.travelZ.value,
    draw_feed: els.drawFeed.value, travel_feed: els.travelFeed.value,
  };
  await run(async () => {
    const [text, paths, stl] = await Promise.all([
      postText('/api/gcode', formWith(file, motion)),
      postJson('/api/toolpaths', formWith(file, geom)),
      postBinary('/api/convert', formWith(file, { height_mm: '0.2', mirror: bool(els.mirror) })),
    ]);
    keep(new Blob([text], { type: 'text/plain' }), stem(file.name) + '.gcode');
    showDims(viewer.showSolid(stl));
    viewer.showToolpaths(paths);
    setStats(paths.stats);
    enableToolpaths(true);
    setView('toolpaths');
    setStatus(`G-code ready — ${paths.stats.strokes} strokes.`, 'ok');
  });
}

async function downloadJig() {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a file first.', 'err');
  els.jig.disabled = true;
  setStatus('Building jig…', '');
  try {
    const stl = await postBinary('/api/jig', formWith(file, {
      board_thickness_mm: els.boardThickness.value, board_margin_mm: els.boardMargin.value,
    }));
    saveBlob(new Blob([stl], { type: 'model/stl' }), stem(file.name) + '-jig.stl');
    setStatus('Jig ready — print it, seat the board in the corner at the work origin.', 'ok');
  } catch (err) {
    setStatus(err.message, 'err');
  } finally {
    els.jig.disabled = false;
  }
}

async function run(action) {
  setStatus('Working…', '');
  els.convert.disabled = true;
  els.download.disabled = true;
  try {
    await action();
    els.download.disabled = false;
  } catch (err) {
    setStatus(err.message, 'err');
  } finally {
    els.convert.disabled = false;
  }
}

async function postBinary(url, form) { return (await ok(await fetch(url, { method: 'POST', body: form }))).arrayBuffer(); }
async function postText(url, form) { return (await ok(await fetch(url, { method: 'POST', body: form }))).text(); }
async function postJson(url, form) { return (await ok(await fetch(url, { method: 'POST', body: form }))).json(); }

async function ok(res) {
  if (res.ok) return res;
  const body = await res.json().catch(() => ({ detail: res.statusText }));
  throw new Error(body.detail || res.statusText);
}

function setupSeg(seg, attr, handler) {
  seg.querySelectorAll('.seg-btn').forEach((btn) => btn.addEventListener('click', () => handler(btn.dataset[attr], btn)));
}

function select(seg, attr, value) {
  seg.querySelectorAll('.seg-btn').forEach((b) => b.setAttribute('aria-selected', String(b.dataset[attr] === value)));
}

function setupDrop(zone, input, nameEl) {
  input.addEventListener('change', () => showName(input, nameEl));
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag');
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      showName(input, nameEl);
    }
  });
}

function showName(input, nameEl) {
  const file = input.files[0];
  nameEl.textContent = file ? file.name : '';
  nameEl.classList.toggle('hidden', !file);
}

function formWith(file, fields) {
  const form = new FormData();
  form.append('file', file);
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  return form;
}

function keep(blob, name) { result = { blob, name }; }

function saveBlob(blob, name) {
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function setStats(stats) {
  els.statStrokes.textContent = `${stats.strokes} strokes`;
  els.statDist.textContent = `draw ${(stats.draw_mm / 1000).toFixed(1)} m · travel ${(stats.travel_mm / 1000).toFixed(1)} m`;
}

function showDims(dims) {
  els.dims.textContent = dims ? `${dims.x.toFixed(1)} × ${dims.y.toFixed(1)} × ${dims.z.toFixed(2)} mm` : '';
}

function setStatus(message, kind) {
  els.statusText.textContent = message;
  els.status.className = 'status' + (kind ? ` ${kind}` : '');
}

const bool = (checkbox) => (checkbox.checked ? 'true' : 'false');
const stem = (name) => name.replace(/\.[^.]+$/, '');
