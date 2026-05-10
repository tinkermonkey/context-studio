# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ontology-management/full-crud-chain.spec.ts >> Ontology Management Full CRUD Chain >> should complete full CRUD chain: taxonomy → scheme → classes → property → relationship → delete → undo
- Location: e2e/tests/ontology-management/full-crud-chain.spec.ts:16:3

# Error details

```
Error: browserType.launch: Executable doesn't exist at /home/orchestrator/.cache/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     npx playwright install                                 ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝
```