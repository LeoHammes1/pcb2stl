import { Viewer } from './viewer.js';

const viewer = new Viewer(document.getElementById('viewer'));
const el = (id) => document.getElementById(id);
const els = {};
for (const id of [
  'format', 'drop', 'file', 'fileName', 'dropLabel', 'bottomRow', 'file2', 'file2Name', 'mirror',
  'stlOpts', 'gcodeOpts', 'boardOpts', 'jigOpts', 'height', 'penWidth', 'perimeters', 'fill',
  'drawZ', 'travelZ', 'drawFeed', 'travelFeed', 'boardMargin', 'originX', 'originY', 'boardThickness',
  'download', 'status', 'statusText', 'dims', 'fit', 'hideTravel', 'legend', 'statsChip',
  'statStrokes', 'statDist',
]) els[id] = el(id);

const NUM = ['height', 'penWidth', 'perimeters', 'drawZ', 'travelZ', 'drawFeed', 'travelFeed', 'boardMargin', 'originX', 'originY', 'boardThickness'];

let seq = 0;
let regenTimer = null;
let pendingFit = false;
let firstFit = false;
let cachedStl = null;

NUM.forEach((id) => els[id].addEventListener('input', () => scheduleRegen(300, false)));
['mirror', 'fill'].forEach((id) => els[id].addEventListener('change', () => scheduleRegen(80, false)));
els.format.addEventListener('change', () => { applyFormat(els.format.value); scheduleRegen(0, true); });
els.hideTravel.addEventListener('change', () => viewer.setTravelVisible(!els.hideTravel.checked));
els.fit.addEventListener('click', () => viewer.fit());
els.download.addEventListener('click', onDownload);
setupDrop(els.drop, els.file, els.fileName);
setupDrop(els.bottomRow, els.file2, els.file2Name);

applyFormat('stl');

function applyFormat(value) {
  const gcode = value === 'gcode';
  const dbl = value === 'double';
  const jig = value === 'jig';
  els.stlOpts.classList.toggle('hidden', gcode || jig);
  els.gcodeOpts.classList.toggle('hidden', !gcode);
  els.boardOpts.classList.toggle('hidden', !(gcode || jig));
  els.jigOpts.classList.toggle('hidden', !jig);
  els.bottomRow.classList.toggle('hidden', !dbl);
  els.dropLabel.textContent = dbl ? '⤓ Top layer (F.Cu)' : '⤓ Drop or click — Gerber / SVG / DXF';
  els.download.textContent = { stl: '⤓ Download .stl', double: '⤓ Download .zip', gcode: '⤓ Download .gcode', jig: '⤓ Download jig .stl' }[value];
}

function scheduleRegen(delay, fit) {
  if (fit) pendingFit = true;
  clearTimeout(regenTimer);
  regenTimer = setTimeout(regen, delay);
}

async function regen() {
  const file = els.file.files[0];
  const fit = pendingFit;
  pendingFit = false;
  if (!file) {
    setStatus('Load a board — Gerber / SVG / DXF', '');
    els.download.disabled = true;
    return;
  }
  const format = els.format.value;
  const mySeq = ++seq;
  setStatus('Previewing…', 'busy');
  els.download.disabled = true;
  viewer.container.classList.add('dim');
  try {
    if (format === 'gcode') {
      const [paths, stl] = await Promise.all([
        postJson('/api/toolpaths', formWith(file, geomFields())),
        postBinary('/api/convert', formWith(file, { height_mm: '0.2', mirror: bool(els.mirror) })),
      ]);
      if (mySeq !== seq) return;
      cachedStl = null;
      const dims = viewer.showSolid(stl);
      viewer.showToolpaths(paths);
      viewer.setMode('toolpaths');
      els.legend.classList.remove('hidden');
      els.statsChip.classList.remove('hidden');
      setStats(paths.stats);
      showDims(dims);
    } else {
      const buffer = await postBinary('/api/convert', formWith(file, { height_mm: els.height.value, mirror: bool(els.mirror) }));
      if (mySeq !== seq) return;
      cachedStl = new Blob([buffer], { type: 'model/stl' });
      const dims = viewer.showSolid(buffer.slice(0));
      viewer.setMode('solid');
      els.legend.classList.add('hidden');
      els.statsChip.classList.add('hidden');
      showDims(dims);
    }
    if (fit || !firstFit) {
      viewer.fit();
      firstFit = true;
    }
    settle(format);
  } catch (err) {
    if (mySeq === seq) {
      setStatus(err.message, 'err');
      els.download.disabled = true;
    }
  } finally {
    if (mySeq === seq) viewer.container.classList.remove('dim');
  }
}

function settle(format) {
  if (format === 'double' && !els.file2.files[0]) {
    setStatus('Add the bottom layer (B.Cu) to export', '');
    els.download.disabled = true;
  } else {
    setStatus('Ready', 'ok');
    els.download.disabled = false;
  }
}

async function onDownload() {
  const file = els.file.files[0];
  if (!file) return;
  const format = els.format.value;
  if (format === 'stl') return saveBlob(cachedStl, stem(file.name) + '.stl');
  if (format === 'double') {
    if (!els.file2.files[0]) return setStatus('Add the bottom layer (B.Cu) first', 'err');
    return buildAndSave('/api/convert-double', archive(), 'pcb2stl-double-sided.zip', 'application/zip', postBinary, 'Writing zip…');
  }
  if (format === 'gcode') {
    return buildAndSave('/api/gcode', formWith(file, motionFields()), stem(file.name) + '.gcode', 'text/plain', postText, 'Writing G-code…');
  }
  return buildAndSave('/api/jig', formWith(file, { board_thickness_mm: els.boardThickness.value, board_margin_mm: els.boardMargin.value }), stem(file.name) + '-jig.stl', 'model/stl', postBinary, 'Building jig…');
}

async function buildAndSave(url, form, name, type, poster, busyMessage) {
  setStatus(busyMessage, 'busy');
  els.download.disabled = true;
  try {
    saveBlob(new Blob([await poster(url, form)], { type }), name);
    setStatus(`Saved ${name}`, 'ok');
  } catch (err) {
    setStatus(err.message, 'err');
  } finally {
    els.download.disabled = false;
  }
}

function geomFields() {
  return {
    pen_width_mm: els.penWidth.value, perimeters: els.perimeters.value, fill: bool(els.fill),
    mirror: bool(els.mirror), origin_x_mm: els.originX.value, origin_y_mm: els.originY.value,
    board_margin_mm: els.boardMargin.value,
  };
}

function motionFields() {
  return {
    ...geomFields(), draw_z_mm: els.drawZ.value, travel_z_mm: els.travelZ.value,
    draw_feed: els.drawFeed.value, travel_feed: els.travelFeed.value,
  };
}

function archive() {
  const form = new FormData();
  form.append('top', els.file.files[0]);
  form.append('bottom', els.file2.files[0]);
  form.append('height_mm', els.height.value);
  return form;
}

async function postBinary(url, form) { return (await ok(await fetch(url, { method: 'POST', body: form }))).arrayBuffer(); }
async function postText(url, form) { return (await ok(await fetch(url, { method: 'POST', body: form }))).text(); }
async function postJson(url, form) { return (await ok(await fetch(url, { method: 'POST', body: form }))).json(); }

async function ok(res) {
  if (res.ok) return res;
  const body = await res.json().catch(() => ({ detail: res.statusText }));
  throw new Error(body.detail || res.statusText);
}

function setupDrop(zone, input, nameEl) {
  input.addEventListener('change', () => { showName(input, nameEl); scheduleRegen(0, true); });
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag');
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      showName(input, nameEl);
      scheduleRegen(0, true);
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
