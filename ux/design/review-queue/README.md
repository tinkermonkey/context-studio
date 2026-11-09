# Review queue design

Board sources for the review queue (#1359), decision states (#1431) and tiered apply (#1411), saved from the Claude design canvas https://claude.ai/artifact/31U3Gn9bUXzRQihDwdcGy9 on 2026-11-09.

| Board | File |
|---|---|
| 1 · Proposals list | `Main.dc.html` |
| 2 · Proposal detail and decisions | `Detail.dc.html` |
| 3 · Accept with edit | `Edit.dc.html` |
| 4 · Apply results and revert | `Results.dc.html` |
| 5 · Where proposals appear elsewhere | `Elsewhere.dc.html` |
| 6 · Tiered apply | `Tiered.dc.html` |

`canvas.json` holds the board layout. The boards render inside the design canvas runtime, which supplies `support.js` and the Heimdall bundle under `ds/heimdall/`; they don't open on their own from this folder. Each board's sample data and interactions are in its `<script type="text/x-dc">` block, and every `HeimdallDesignSystem_*.X` tag maps to the `@tinkermonkey/heimdall-ui` component `X`.
