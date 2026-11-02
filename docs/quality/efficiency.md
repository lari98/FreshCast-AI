# Efficiency report (v0.3.0)

Goal: less network traffic, less processor load and fewer wake-ups (so a cooler, quieter computer and less
battery use), without losing reliability or security. Measured in a 2-core Linux container on the synthetic demo
data. Watts and temperatures were **not** measured (no power meter); processor time, request counts and
wake-ups are used as honest proxies.

## What changed and what it measured

| Area | Before (v0.2.0) | After (v0.3.0) | Measured effect |
|---|---|---|---|
| Static server compression | gzip computed again on every request | Brotli and gzip computed once per file, kept in memory | 200 requests for the main script: 1,475 ms CPU before, 0.04 ms after |
| First page load (12 files) | 234,548 B (gzip) | 217,405 B (Brotli) | 7 % less than before, 76 % less than uncompressed (911,857 B) |
| Reload | about 23,326 B re-downloaded (no ETag) | ETag, answer 304 | 0 B of body on an unchanged reload |
| Update check | every 60 s, also in hidden tabs, offline and after errors | every 5 min, only in a visible tab and online, back-off after errors (x2, max 30 min) | 60 requests/h before; 12/h visible, 4/h in energy-saving mode, 0/h hidden |
| Upload analysis threads | 2 threads | 1 thread by default (`FRESHCAST_THREADS` to raise) | same wall time (1.56 s), CPU 1.45 s instead of 2.98 s (half) |
| Same upload again | trained again | answered from a small in-memory cache | 1.56 s and 1.45 s CPU become 0.02 s |
| Parallel uploads | unlimited | at most 2 at once, others get 503 with Retry-After | bounded CPU and memory under load |
| API responses | uncompressed | gzip above 1 KB | answers shrink roughly 5x for JSON |
| Run script | rescanned every 2 s, normal priority | every 10 s, below-normal priority, no telemetry | fewer wake-ups; builds no longer compete with your other programs (not tested on Windows here) |
| Energy-saving mode | none | setting, also on by default when the browser requests "data saver" | 25 instead of 100 table rows per page, update check every 15 min |

Idle behaviour: the static server has no timers and no file watching, so an idle server uses no processor time.

## Reliability and security additions

- A rendering error in one tab shows a calm message with retry; other tabs keep working (the error text is not shown, it could echo uploaded content).
- Damaged or hostile saved settings (invalid JSON, wrong types) are ignored and the dashboard starts with defaults.
- Static server: health check `/healthz`, header and request time limits (slow clients cannot hold connections), URL length limit (414), CSP header with `frame-ancestors 'none'`, Permissions-Policy, COOP and CORP, clean shutdown on SIGINT and SIGTERM.
- API: readiness probe `/health/ready` (checks the database), load gate, cache keyed by a content hash (never written to disk, no cross-user leakage because the same bytes are needed to hit an entry).
- New tests: `tests/efficiency.test.tsx` (12), `apps/api/tests/test_efficiency.py` (7), 2 more static-server tests, 1 more core test.

## Limits (honest)

- Temperature and power draw were not measured; fewer wake-ups and less CPU time lower both but I cannot give numbers.
- Page weight is dominated by the React and Next.js runtime (about 3/4 of the JavaScript); splitting tabs into separate files was tested as a design option but would save little (tabs are a small part) and was not done.
- The PowerShell changes could not be run here (no Windows). They are small; check `.\scripts\run-dashboard.ps1` starts as before.
- Cache and gate are per process; several API workers each have their own.
