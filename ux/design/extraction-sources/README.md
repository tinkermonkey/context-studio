# Extraction on sources design

Board sources for running extraction on files, uploads and web pages (#1449), saved from the Claude design canvas https://claude.ai/artifact/9SimMhNvzc7hSFcY6qyMT7 on 2026-11-10. The build is tracked in #1450 and #1451.

| Board | File |
|---|---|
| 1 · Sources: add a file, a web page or text | `Main.dc.html` |
| 2 · Start an extraction, follow it, hand off to review | `Extract.dc.html` |
| 3 · Review an extraction proposal beside its passage | `Review.dc.html` |
| 4 · Provenance on an applied entity | `Provenance.dc.html` |
| 5 · One contract for the UI, REST and MCP | `Contract.dc.html` |

`canvas.json` holds the board layout. The boards render inside the design canvas runtime, which supplies `support.js` and the Heimdall bundle under `ds/heimdall/`; they don't open on their own from this folder. Each board's sample data and interactions are in its `<script type="text/x-dc">` block, and every `HeimdallDesignSystem_*.X` tag maps to the `@tinkermonkey/heimdall-ui` component `X`. Board 2's `startAt` tweak opens it on the configure, running or done state.
