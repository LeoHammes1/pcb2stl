import { Viewer } from './viewer.js';

const viewer = new Viewer(document.getElementById('viewer'));
const els = {
  file: document.getElementById('file'),
  height: document.getElementById('height'),
  mirror: document.getElementById('mirror'),
  convert: document.getElementById('convert'),
  download: document.getElementById('download'),
  status: document.getElementById('status'),
  dims: document.getElementById('dims'),
};

let stlBlob = null;
let stlName = 'board.stl';

els.convert.addEventListener('click', async () => {
  const file = els.file.files[0];
  if (!file) return setStatus('Choose a Gerber or SVG file first.', true);

  const form = new FormData();
  form.append('file', file);
  form.append('height_mm', els.height.value);
  form.append('mirror', els.mirror.checked ? 'true' : 'false');

  setStatus('Converting…');
  els.convert.disabled = true;
  els.download.disabled = true;
  try {
    const res = await fetch('/api/convert', { method: 'POST', body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || res.statusText);
    }
    const buffer = await res.arrayBuffer();
    stlBlob = new Blob([buffer], { type: 'model/stl' });
    stlName = file.name.replace(/\.[^.]+$/, '') + '.stl';
    const dims = viewer.showSTL(buffer.slice(0));
    els.dims.textContent = `${dims.x.toFixed(1)} × ${dims.y.toFixed(1)} × ${dims.z.toFixed(2)} mm`;
    setStatus('Done — slice it in your slicer to pen-plot.');
    els.download.disabled = false;
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    els.convert.disabled = false;
  }
});

els.download.addEventListener('click', () => {
  if (!stlBlob) return;
  const url = URL.createObjectURL(stlBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = stlName;
  a.click();
  URL.revokeObjectURL(url);
});

function setStatus(message, error = false) {
  els.status.textContent = message;
  els.status.className = error ? 'error' : '';
}
