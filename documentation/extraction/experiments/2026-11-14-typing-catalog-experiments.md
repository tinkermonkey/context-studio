# Typing-stage experiments on `find_then_type` (2026-11-14)

**Question.** Does offering whole class definitions in the typing catalog (instead of their first 260 characters) improve typing? And how noisy is typing?

**Method.** Every take typed the same 570 recorded mentions: find answers were replayed from the committed cassettes, so only typing varied. Claude Haiku 5.5, one take per arm, about $1 in all. Scratch scripts, not committed.

| take | dev typed F1 | holdout typed F1 | gold-named mentions: right / wrong / "none" | other mentions recorded |
|---|---|---|---|---|
| committed recording (260-character definitions) | 0.465 | 0.481 | 122 / 13 / 45 | 195 of 390 |
| same catalog, second take | 0.476 | 0.442 | 120 / 13 / 47 | 203 of 390 |
| whole definitions (catalog 62k to 209k characters) | 0.446 | 0.437 | 116 / 18 / 46 | 201 of 390 |
| "none" rule reworded to answer "none" less often | 0.412 | 0.469 | 135 / 37 / 8 | 273 of 390 |

## Findings

- **Typing noise:** re-typing with nothing changed changes 16.5% of answers (50 of 570 flip between a class and "none"). Typed F1 moved 0.01 on dev and 0.04 on the holdout.
- **Whole definitions: no gain**, slightly worse class choice, and a prompt three times as large. Rejected.
- **"None" is the main typing loss:** typing declines about a quarter of the mentions gold records (45 of 180), consistently. Asked for reasons, the model mostly said the mention was "only a heading or table label here" or "only cited in passing". Each mention is typed from its first occurrence only, which explains the first reason.
- **Rewording the "none" rule is not the fix:** it recovered 37 of those mentions but typed 24 of them wrong and let 78 more non-gold mentions through.
- **Relationships are fragile:** the relate stage ran out of output tokens (then capped at 8,000) on `gitlab_architecture` in two of four takes, and relationship recall on `edit_check` swung between 0.00 and 0.09 across takes.

## Verdict

No change adopted. Untried: typing a mention from all of its occurrences rather than the first. The noise figures seed the refinement loop's provisional margins for `find_then_type`.
