# knowledge-actions — shared Playwright

Reusable **GitHub Actions + Chromium/Playwright** browser checks for the `ngocnhanvo` projects.

## Structure

- `.github/workflows/playwright.yml`: reusable workflow using `workflow_call`.
- `tests/run.mjs`: centralized browser test suites (`smoke`, `wordpress-site-health`).
- `package.json`: pinned Playwright version matching the browser image.
- Domain URLs, permitted hostnames, and secrets are held by each project's `-actions` repository, **not here**.

## Calling it from your project

The project Actions repository defines a small workflow job:

```yaml
jobs:
  browser:
    uses: ngocnhanvo/knowledge-actions/.github/workflows/playwright.yml@main
    with:
      site_url: https://example.com
      expected_hostname: example.com
      suite: smoke
```

For WordPress Site Health only, set `suite: wordpress-site-health`, point `site_url` and `expected_hostname` at **that project's WordPress admin domain**, and explicitly pass:

```yaml
    secrets:
      WP_ADMIN_USERNAME: ${{ secrets.WP_ADMIN_USERNAME }}
      WP_ADMIN_PASSWORD: ${{ secrets.WP_ADMIN_PASSWORD }}
```

The optional `disallowed_db_name` input compares the Site Health database name against one reference; output shows **PASS/FAIL only**, never the actual DB name, password, cookies, HTML, or screenshots. The comparison reference must be independently verified before interpreting the result as proof of complete database isolation.

## Browser setup, speed, and safety

The workflow uses Microsoft's `mcr.microsoft.com/playwright:v1.64.0-noble`, which **already includes Chromium and its OS dependencies**. Only the small Playwright npm package is installed during a run; npm downloads are cached per caller repository. GitHub-hosted runners are ephemeral, so a new run may still pull the container image. To eliminate that startup cost, use a trusted self-hosted runner with a warmed image instead.

- The approved suite list is finite; no arbitrary shell, JavaScript or remote URL is accepted as a test action.
- HTTPS and exact host verification are mandatory. Off-origin redirects cause failure.
- Read-only tests only: no WordPress database/config edits, deploy, FTP uploads or Astro build.
- Pass explicit secrets, never `secrets: inherit`. Public logs never contain runtime database names.
- Anyone allowed to edit this **public** central repository can change code executed with caller secrets. Restrict write permissions, review modifications carefully, and consider pinning a full commit SHA or protected release tag for high-trust callers. `@main` intentionally consumes updates as soon as they are merged.
- For testing sensitive admin sites, carefully verify GitHub Actions permissions and security review before enabling.

Shared working rules: https://github.com/ngocnhanvo/knowledge (branch main).
