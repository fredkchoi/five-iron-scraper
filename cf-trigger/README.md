# cf-trigger

A tiny Cloudflare Worker that fires a GitHub `repository_dispatch` event on a cron schedule. Part of [five-iron-scraper](../README.md) — replaces GitHub Actions' built-in `schedule:` cron, which is routinely delayed 25–55min and occasionally dropped entirely on small repos (fatal for a job that must fire at midnight ET).

## How it works

Cloudflare cron fires at `0 3 * * *` (03:00 UTC, = 11:00pm EDT / 10:00pm EST) → the Worker `POST`s to `https://api.github.com/repos/<owner>/<repo>/dispatches` with `{"event_type": "midnight-booker"}` → the target workflow (configured with `on: repository_dispatch`) runs.

## Setup

1. **Create a fine-grained GitHub PAT** at https://github.com/settings/personal-access-tokens/new
   - Repository access: only your `five-iron-scraper` fork
   - Repository permissions: `Contents: Read and write`, `Metadata: Read-only`
   - (Note: `repository_dispatch` requires `Contents: write` despite the endpoint living under `/dispatches` — GitHub's docs are misleading on this.)
2. **Edit `wrangler.jsonc`** — set `GITHUB_REPO` to your fork's `owner/repo`.
3. **Store the PAT as a Worker secret**:
   ```bash
   npx wrangler secret put GITHUB_TOKEN
   ```
4. **Deploy**:
   ```bash
   npx wrangler deploy
   ```

## Verify

```bash
# Manually trigger the Worker:
npx wrangler triggers cron --cron "0 3 * * *"
# Then check the target repo:
gh run list --workflow=midnight-booker.yml --limit 3
```

You should see a new run with `event = repository_dispatch`.
