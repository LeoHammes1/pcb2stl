import { Viewer } from './viewer.js';

const viewer = new Viewer(document.getElementById('viewer'));
const els = {
  file: document.getElementById('file'),
  file2: document.getElementById('file2'),
  fileLabel: document.getElementById('fileLabel'),
  bottomRow: document.getElementById('bottomRow'),
  mirrorRow: document.getElementById('mirrorRow'),
  height: document.getElementById('height'),
  mirror: document.getElementById('mirror'),
  double: document.getElementById('double'),
  convert: document.getElementById('convert'),
  download: document.getElementById('download'),
  status: document.getElementById('status'),
  dims: document.getElementById('dims'),
};

let resultBlob = null;
let resultName = 'board.stl';

els.double.addEventListener('change', () => {
  const on = els.double.checked;
  els.bottomRow.style.display = on ? 'block' : 'none';
  els.mirrorRow.style.display = on ? 'none' : 'flex';
  els.fileLabel.textContent = on ? 'Top layer (F.Cu)' : 'Gerber, SVG or DXF file';
  els.convert.textContent = on ? 'Convert both sides' : 'Convert & preview';
  els.download.textContent = on ? 'Download ZIP' : 'Download STL';
});

els.convert.addEventListener('click', () => (els.double.checked ? convertDouble() : convertSingle()));

async function convertSingle() {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a Gerber, SVG or DXF file first.', true);

  const form = new FormData();
  form.append('file', file);
  form.append('height_mm', els.height.value);
  form.append('mirror', els.mirror.checked ? 'true' : 'false');

  await run(async () => {
    const buffer = await postBinary('/api/convert', form);
    resultBlob = new Blob([buffer], { type: 'model/stl' });
    resultName = stem(file.name) + '.stl';
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

  const preview = new FormData();
  preview.append('file', top);
  preview.append('height_mm', els.height.value);

  await run(async () => {
    const [zip, topStl] = await Promise.all([
      postBinary('/api/convert-double', archive),
      postBinary('/api/convert', preview),
    ]);
    resultBlob = new Blob([zip], { type: 'application/zip' });
    resultName = 'pcb2stl-double-sided.zip';
    showDims(viewer.showSTL(topStl));
    setStatus('Top + bottom (mirrored) generated with registration holes. Preview shows the top.');
  });
}

async function run(action) {
  setStatus('Converting…');
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
  const res = await fetch(url, { method: 'POST', body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.arrayBuffer();
}

els.download.addEventListener('click', () => {
  if (!resultBlob) return;
  const url = URL.createObjectURL(resultBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = resultName;
  a.click();
  URL.revokeObjectURL(url);
});

function showDims(dims) {
  els.dims.textContent = `${dims.x.toFixed(1)} × ${dims.y.toFixed(1)} × ${dims.z.toFixed(2)} mm`;
}

function stem(name) {
  return name.replace(/\.[^.]+$/, '');
}

function setStatus(message, error = false) {
  els.status.textContent = message;
  els.status.className = error ? 'error' : '';
}
