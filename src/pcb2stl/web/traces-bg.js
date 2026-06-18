// Animated PCB-trace backdrop for the side panel.
//
// Faint copper routing — orthogonal traces (H / V) with 45° chamfered corners,
// vias and ring pads — with signal pulses that flow along a trace and light its
// pads/vias as they pass. The look is a routed board, not a star field.
//
// CSP-safe: same-origin ES module, no inline script, no external resources.

const panel = document.getElementById('panel');
const canvas = document.getElementById('traceBg');
const ctx = canvas && canvas.getContext('2d');

if (panel && canvas && ctx) {
  const COPPER = '245, 165, 36';        // --accent, as "r, g, b"
  const SPARK = '255, 222, 160';        // hot head of a pulse
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const SPACING = 28;                   // routing grid pitch (px)
  const CHAMFER = SPACING * 0.32;       // 45° corner cut
  const TRACE_AREA = 6000;              // ~one trace per this many px²
  const MAX_PULSES = 3;                 // concurrent signals
  const PULSE_PX = 2.2;                 // head speed, px/frame
  const TRAIL = 7;                      // pulse tail length, in segments

  let traces = [];   // { pts:[{x,y}], pads:[{x,y}], vias:[{x,y}] }
  let pulses = [];   // { tr, seg, t }
  let cssW = 0, cssH = 0, dpr = 1, raf = null;

  const ri = (n) => (Math.random() * n) | 0;
  const dist = (a, b) => Math.hypot(b.x - a.x, b.y - a.y);

  // One routed trace: a Manhattan walk on the grid, corners cut to 45°.
  function makeTrace(cols, rows) {
    let c = ri(cols), r = ri(rows);
    const way = [{ c, r }];
    let d = [{ dc: 1, dr: 0 }, { dc: -1, dr: 0 }, { dc: 0, dr: 1 }, { dc: 0, dr: -1 }][ri(4)];
    const corners = 3 + ri(6);

    for (let i = 0; i < corners; i++) {
      const run = 1 + ri(3);
      const nc = Math.max(0, Math.min(cols - 1, c + d.dc * run));
      const nr = Math.max(0, Math.min(rows - 1, r + d.dr * run));
      if (nc === c && nr === r) break;            // hit a wall
      way.push({ c: nc, r: nr });
      c = nc; r = nr;
      // turn 90° onto a perpendicular axis
      d = d.dc !== 0
        ? { dc: 0, dr: Math.random() < 0.5 ? 1 : -1 }
        : { dc: Math.random() < 0.5 ? 1 : -1, dr: 0 };
    }
    if (way.length < 2) return null;

    const P = (w) => ({ x: w.c * SPACING, y: w.r * SPACING });
    const pts = [];
    for (let i = 0; i < way.length; i++) {
      const cur = P(way[i]);
      if (i === 0 || i === way.length - 1) { pts.push(cur); continue; }
      const prev = P(way[i - 1]), next = P(way[i + 1]);
      const inx = Math.sign(cur.x - prev.x), iny = Math.sign(cur.y - prev.y);
      const outx = Math.sign(next.x - cur.x), outy = Math.sign(next.y - cur.y);
      pts.push({ x: cur.x - inx * CHAMFER, y: cur.y - iny * CHAMFER });
      pts.push({ x: cur.x + outx * CHAMFER, y: cur.y + outy * CHAMFER });
    }

    const pads = [pts[0], pts[pts.length - 1]];
    const vias = [];
    for (let i = 1; i < way.length - 1; i++) {
      if (Math.random() < 0.35) vias.push(P(way[i]));
    }
    return { pts, pads, vias };
  }

  function build() {
    cssW = panel.clientWidth;
    cssH = panel.clientHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.round(cssW * dpr));
    canvas.height = Math.max(1, Math.round(cssH * dpr));
    canvas.style.width = cssW + 'px';
    canvas.style.height = cssH + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cols = Math.max(2, Math.ceil(cssW / SPACING));
    const rows = Math.max(2, Math.ceil(cssH / SPACING));
    const count = Math.round((cssW * cssH) / TRACE_AREA);

    traces = [];
    for (let i = 0; i < count; i++) {
      const t = makeTrace(cols, rows);
      if (t) traces.push(t);
    }
    pulses = [];
    canvas.style.transform = `translateY(${panel.scrollTop}px)`;
  }

  function drawStatic() {
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.shadowBlur = 0;

    // traces
    ctx.strokeStyle = `rgba(${COPPER}, 0.07)`;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    for (const tr of traces) {
      const p = tr.pts;
      ctx.moveTo(p[0].x, p[0].y);
      for (let i = 1; i < p.length; i++) ctx.lineTo(p[i].x, p[i].y);
    }
    ctx.stroke();

    // vias (filled)
    ctx.fillStyle = `rgba(${COPPER}, 0.08)`;
    for (const tr of traces) {
      for (const v of tr.vias) {
        ctx.beginPath();
        ctx.arc(v.x, v.y, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    // end pads (ring)
    ctx.strokeStyle = `rgba(${COPPER}, 0.09)`;
    ctx.lineWidth = 1;
    for (const tr of traces) {
      for (const pad of tr.pads) {
        ctx.beginPath();
        ctx.arc(pad.x, pad.y, 2.6, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  function dotGlow(n, intensity, rad) {
    if (intensity <= 0.04) return;
    ctx.shadowBlur = 9 * intensity;
    ctx.shadowColor = `rgba(${COPPER}, ${0.7 * intensity})`;
    ctx.fillStyle = `rgba(${COPPER}, ${0.6 * intensity})`;
    ctx.beginPath();
    ctx.arc(n.x, n.y, rad, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawPulse(p) {
    const pts = p.tr.pts;
    const a = pts[p.seg], b = pts[p.seg + 1];
    const hx = a.x + (b.x - a.x) * p.t;
    const hy = a.y + (b.y - a.y) * p.t;

    ctx.save();
    ctx.lineCap = 'round';
    for (let k = 0; k < TRAIL; k++) {
      const s = p.seg - k;
      if (s < 0) break;
      const p0 = pts[s];
      const x1 = k === 0 ? hx : pts[s + 1].x;
      const y1 = k === 0 ? hy : pts[s + 1].y;
      const fade = Math.max(0, 1 - k / TRAIL);
      ctx.strokeStyle = `rgba(${COPPER}, ${0.34 * fade})`;
      ctx.lineWidth = 1.8;
      ctx.shadowBlur = 8 * fade;
      ctx.shadowColor = `rgba(${COPPER}, ${0.5 * fade})`;
      ctx.beginPath();
      ctx.moveTo(p0.x, p0.y);
      ctx.lineTo(x1, y1);
      ctx.stroke();
    }

    // pads / vias on this trace light up as the head reaches them
    const head = { x: hx, y: hy };
    for (const v of p.tr.vias) dotGlow(v, 1 - Math.min(1, dist(head, v) / 26), 1.8);
    for (const pad of p.tr.pads) dotGlow(pad, 1 - Math.min(1, dist(head, pad) / 30), 2.8);

    // bright head bead
    ctx.shadowBlur = 11;
    ctx.shadowColor = `rgba(${COPPER}, 0.9)`;
    ctx.fillStyle = `rgba(${SPARK}, 0.95)`;
    ctx.beginPath();
    ctx.arc(hx, hy, 1.7, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function frame() {
    ctx.clearRect(0, 0, cssW, cssH);
    drawStatic();

    if (traces.length && pulses.length < MAX_PULSES && Math.random() > 0.97) {
      const tr = traces[ri(traces.length)];
      if (tr.pts.length >= 2) pulses.push({ tr, seg: 0, t: 0 });
    }

    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i];
      const a = p.tr.pts[p.seg], b = p.tr.pts[p.seg + 1];
      p.t += PULSE_PX / Math.max(1, dist(a, b));   // constant px speed
      while (p.t >= 1) {
        p.t -= 1; p.seg++;
        if (p.seg >= p.tr.pts.length - 1) break;
      }
      if (p.seg >= p.tr.pts.length - 1) { pulses.splice(i, 1); continue; }
      drawPulse(p);
    }

    raf = requestAnimationFrame(frame);
  }

  let resizeTimer = null;
  const ro = new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { build(); if (reduced) drawStatic(); }, 120);
  });
  ro.observe(panel);

  panel.addEventListener('scroll', () => {
    canvas.style.transform = `translateY(${panel.scrollTop}px)`;
  }, { passive: true });

  build();
  if (reduced) drawStatic();
  else raf = requestAnimationFrame(frame);
}
