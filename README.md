# knowledge-actions

Shared browser-test infrastructure for projects owned by `ngocnhanvo`.

- Central runner: `.github/workflows/playwright.yml` (reusable `workflow_call`).
- Caller repositories retain **their own** domains, GitHub Actions secrets, and test schedules.
- Browser image: Playwright Chromium already baked into Microsoft's Docker image; no browser installation in each test.
- Browser tests use read-only workflows by default. Never deploy, run Astro build or modify WordPress.
- Rules: https://github.com/ngocnhanvo/knowledge (branch `main`).

A calling repository must explicitly pass each secret required by its selected suite. Do not use `secrets: inherit` or copy actual secrets into this repository.
