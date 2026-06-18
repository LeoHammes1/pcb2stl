import { Viewer } from './viewer.js';

const viewer = new Viewer(document.getElementById('viewer'));
const el = (id) => document.getElementById(id);
const els = {
  output: el('output'),
  file: el('file'),
  file2: el('file2'),
  fileLabel: el('fileLabel'),
  bottomRow: el('bottomRow'),
  stlOpts: el('stlOpts'),
  gcodeOpts: el('gcodeOpts'),
  height: el('height'),
  double: el('double'),
  mirror: el('mirror'),
  penWidth: el('penWidth'),
  perimeters: el('perimeters'),
  drawZ: el('drawZ'),
  travelZ: el('travelZ'),
  drawFeed: el('drawFeed'),
  travelFeed: el('travelFeed'),
  boardMargin: el('boardMargin'),
  originX: el('originX'),
  originY: el('originY'),
  boardThickness: el('boardThickness'),
  jig: el('jig'),
  convert: el('convert'),
  download: el('download'),
  status: el('status'),
  dims: el('dims'),
};

let resultBlob = null;
let resultName = 'board.stl';

els.output.addEventListener('change', refreshMode);
els.double.addEventListener('change', refreshMode);
els.convert.addEventListener('click', () => MODES[mode()]());
els.download.addEventListener('click', () => saveBlob(resultBlob, resultName));
els.jig.addEventListener('click', downloadJig);

function mode() {
  if (els.output.value === 'gcode') return 'gcode';
  return els.double.checked ? 'double' : 'single';
}

function refreshMode() {
  const gcode = els.output.value === 'gcode';
  const dbl = !gcode && els.double.checked;
  els.gcodeOpts.style.display = gcode ? 'block' : 'none';
  els.stlOpts.style.display = gcode ? 'none' : 'block';
  els.bottomRow.style.display = dbl ? 'block' : 'none';
  els.fileLabel.textContent = dbl ? 'Top layer (F.Cu)' : 'Gerber, SVG or DXF file';
  els.convert.textContent = gcode ? 'Generate G-code' : dbl ? 'Convert both sides' : 'Convert & preview';
  els.download.textContent = gcode ? 'Download .gcode' : dbl ? 'Download ZIP' : 'Download STL';
}

const MODES = { single: convertSingle, double: convertDouble, gcode: convertGcode };

async function convertSingle() {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a Gerber, SVG or DXF file first.', true);
  const form = formWith(file, { height_mm: els.height.value, mirror: bool(els.mirror) });
  await run(async () => {
    const buffer = await postBinary('/api/convert', form);
    keep(new Blob([buffer], { type: 'model/stl' }), stem(file.name) + '.stl');
    showDims(viewer.showSTL(buffer.slice(0)));
    setStatus('Done — slice it in your slicer to pen-plot.');
  });
}

async function convertDouble() {
  const top = els.file.files[0];
  const bottom = els.file2.files[0];
  if (!top || !bottom) return setStatus('Choose both the top and bottom layers.', true);
  const archive = new FormData();
  archive.append('top', top);
  archive.append('bottom', bottom);
  archive.append('height_mm', els.height.value);
  await run(async () => {
    const [zip, topStl] = await Promise.all([
      postBinary('/api/convert-double', archive),
      postBinary('/api/convert', formWith(top, { height_mm: els.height.value })),
    ]);
    keep(new Blob([zip], { type: 'application/zip' }), 'pcb2stl-double-sided.zip');
    showDims(viewer.showSTL(topStl));
    setStatus('Top + bottom (mirrored) with registration holes. Preview shows the top.');
  });
}

async function convertGcode() {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a Gerber, SVG or DXF file first.', true);
  const form = formWith(file, {
    pen_width_mm: els.penWidth.value,
    perimeters: els.perimeters.value,
    mirror: bool(els.mirror),
    draw_z_mm: els.drawZ.value,
    travel_z_mm: els.travelZ.value,
    draw_feed: els.drawFeed.value,
    travel_feed: els.travelFeed.value,
    origin_x_mm: els.originX.value,
    origin_y_mm: els.originY.value,
    board_margin_mm: els.boardMargin.value,
  });
  const preview = formWith(file, { height_mm: '0.2', mirror: bool(els.mirror) });
  await run(async () => {
    const [text, stl] = await Promise.all([
      postText('/api/gcode', form),
      postBinary('/api/convert', preview),
    ]);
    keep(new Blob([text], { type: 'text/plain' }), stem(file.name) + '.gcode');
    showDims(viewer.showSTL(stl));
    const stats = (text.match(/;\s*(strokes [^\n]*)/) || [])[1] || `${text.split('\n').length} lines`;
    setStatus(`G-code ready — ${stats}. Preview shows the copper to be drawn.`);
  });
}

function formWith(file, fields) {
  const form = new FormData();
  form.append('file', file);
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  return form;
}

async function run(action) {
  setStatus('Working…');
  els.convert.disabled = true;
  els.download.disabled = true;
  try {
    await action();
    els.download.disabled = false;
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    els.convert.disabled = false;
  }
}

async function postBinary(url, form) {
  return (await ok(await fetch(url, { method: 'POST', body: form }))).arrayBuffer();
}

async function postText(url, form) {
  return (await ok(await fetch(url, { method: 'POST', body: form }))).text();
}

async function ok(res) {
  if (res.ok) return res;
  const body = await res.json().catch(() => ({ detail: res.statusText }));
  throw new Error(body.detail || res.statusText);
}

function keep(blob, name) {
  resultBlob = blob;
  resultName = name;
}

async function downloadJig() {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a file first.', true);
  const form = formWith(file, {
    board_thickness_mm: els.boardThickness.value,
    board_margin_mm: els.boardMargin.value,
  });
  els.jig.disabled = true;
  setStatus('Building jig…');
  try {
    const stl = await postBinary('/api/jig', form);
    saveBlob(new Blob([stl], { type: 'model/stl' }), stem(file.name) + '-jig.stl');
    setStatus('Jig ready — print it, fix it at the work origin, seat the board in the corner.');
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    els.jig.disabled = false;
  }
}

function saveBlob(blob, name) {
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function showDims(dims) {
  els.dims.textContent = `${dims.x.toFixed(1)} × ${dims.y.toFixed(1)} × ${dims.z.toFixed(2)} mm`;
}

const bool = (checkbox) => (checkbox.checked ? 'true' : 'false');
const stem = (name) => name.replace(/\.[^.]+$/, '');

function setStatus(message, error = false) {
  els.status.textContent = message;
  els.status.className = error ? 'error' : '';
}
