# Security Policy

pcb2stl is a stateless service that parses **untrusted uploaded files** (Gerber, SVG,
DXF). It is hardened accordingly.

## Limits (all env-configurable)

| Guard | Default | Env var |
|---|---|---|
| Upload size | 16 MB | `PCB2STL_MAX_UPLOAD_BYTES` |
| Output (mesh) size | 64 MB | `PCB2STL_MAX_OUTPUT_BYTES` |
| Conversion wall-clock (then killed) | 25 s | `PCB2STL_CONVERT_TIMEOUT_S` |
| Concurrent conversions per pod | 2 | `PCB2STL_MAX_CONCURRENT` |
| Max vertices / polygons / extent | 500k / 50k / 1000 mm | `PCB2STL_MAX_VERTICES` etc. |
| Allowed CORS origins | pcb2stl.online + localhost | `PCB2STL_ALLOWED_ORIGINS` |

## Defenses

- **Process isolation**: every conversion runs in a killable worker process off the
  event loop, so a hung or looping upload cannot block the server and is terminated at
  the timeout (the freed CPU is reclaimed).
- **XXE / billion-laughs**: SVG is validated with `defusedxml` (any DTD or entity is
  rejected) before `svgelements` ever parses it.
- **Backpressure**: excess concurrent load is shed with HTTP 503 + `Retry-After`.
- **Complexity & size caps** reject pathological inputs before meshing (422/413); binary
  content with a spoofed extension is rejected (400).
- **Sanitized errors**: responses never contain library exception text, file paths or
  stack traces — those are logged server-side only.
- **Security headers**: strict CSP (`script-src 'self'`, no inline scripts), `nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`; HSTS is set at the edge.
- **CORS** restricted to the configured origins.
- The container runs as a **non-root** user.

## Reporting a vulnerability

Please report privately via GitHub's private vulnerability reporting, or email
**hello@leohammes.dev**. Do not open a public issue for security reports.
