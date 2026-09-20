# Release Rat

[![CI](https://github.com/silascroe/release-rat/actions/workflows/ci.yml/badge.svg)](https://github.com/silascroe/release-rat/actions/workflows/ci.yml)

Release Rat is a small self-hosted GitHub release monitor. Give it a list of repositories and it will poll for new releases, decide which ones are worth your attention, summarize the useful ones in plain English, remember what it has already processed, and send reports to Discord or a local log.

It is deliberately boring infrastructure: Python 3.11+, SQLite, the GitHub REST API, and no runtime third-party Python dependencies.

> Experimental project. Maintained as interest permits.

## What it does

- Watches any number of public GitHub repositories.
- Ignores drafts and optionally includes prereleases.
- Seeds existing releases silently on first run so you do not get flooded with old notifications.
- Supports explicit backfill when you *do* want to process that seeded history.
- Uses an optional OpenAI-compatible model to judge significance and write summaries.
- Falls back to deterministic heuristics when no model is configured or the model fails.
- Persists state in SQLite so restarts do not reprocess everything.
- Prevents overlapping local polls from double-processing releases.
- Sends interesting releases to Discord when configured; otherwise writes JSON Lines locally.
- Recovers saved judgments across delivery failures and interruptions.

## Quick start

Clone the repository and edit `config.json`:

```bash
git clone https://github.com/silascroe/release-rat.git
cd release-rat
```

Add repositories as `owner/name` values:

```json
{
  "repositories": ["python/cpython", "astral-sh/uv"],
  "poll_interval_seconds": 3600,
  "include_prereleases": false,
  "bootstrap_mode": "seed",
  "state_path": "state.db",
  "local_log_path": "release-log.jsonl",
  "discord_webhook_env": "DISCORD_WEBHOOK_URL",
  "github_token_env": "GITHUB_TOKEN",
  "llm": {
    "enabled": true,
    "base_url_env": "OPENAI_BASE_URL",
    "api_key_env": "OPENAI_API_KEY",
    "model_env": "RELEASE_RAT_MODEL",
    "default_base_url": "https://api.openai.com/v1",
    "default_model": "gpt-5-mini"
  }
}
```

Run it directly from the checkout:

```bash
python -m release_rat --once
```

Or install the local package to get the `release-rat` command:

```bash
python -m pip install .
release-rat --once
```

`--once` is the default, so `python -m release_rat` and `release-rat` also perform one normal poll.

## Credentials and delivery

All secrets are optional and come from environment variables. Do not put them in `config.json`.

```bash
export GITHUB_TOKEN="..."
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export RELEASE_RAT_MODEL="gpt-5-mini"
export DISCORD_WEBHOOK_URL="..."
```

- `GITHUB_TOKEN` raises GitHub API limits. Public repositories work without it.
- `OPENAI_API_KEY` enables model-assisted significance decisions and summaries. Without it, Release Rat uses its heuristic judge.
- `OPENAI_BASE_URL` and `RELEASE_RAT_MODEL` let you point the judge at another OpenAI-compatible endpoint/model.
- `DISCORD_WEBHOOK_URL` enables Discord delivery. Without it, reports go to `release-log.jsonl`.

The environment-variable names themselves can be changed in `config.json`.

## First run and backfill

The first successful **normal** poll for a repository records the releases already present without reporting them. This is deliberate: adding a project with years of releases should not dump its history into your notifications.

```bash
release-rat --once
```

To process those seeded releases explicitly:

```bash
release-rat --backfill
```

Subsequent normal polls process only releases that appeared after the baseline.

## Running continuously

Foreground watch mode:

```bash
release-rat --watch
```

It polls every `poll_interval_seconds` and prints a summary after each run.

For Linux servers, example systemd units are included in `examples/`. Replace `/opt/release-rat` with your installation path, create `/etc/release-rat.env` if you use environment variables, then:

```bash
sudo cp examples/release-rat.service /etc/systemd/system/
sudo cp examples/release-rat.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now release-rat.timer
```

On Windows, create a Task Scheduler task that runs `python -m release_rat --once` (or `release-rat --once`) from the project directory on your desired cadence.

## Reliability notes

Release Rat stores release state and saved judgments in SQLite. A delivery failure does not force the release through judgment again, and failed judgments remain retryable. One repository failing does not stop the others from being checked.

Only one poll may own a given state database at a time. Overlapping invocations skip work rather than risk duplicate processing. Keep the state database on a local filesystem with functioning SQLite locks, and use the same state path for every worker that should coordinate.

There is one unavoidable exactly-once caveat: if Discord accepts a report and the process dies before Release Rat commits the delivery marker, that report can be sent again after recovery. External webhook delivery cannot be made perfectly atomic from the client side.

For the implementation details, see [docs/architecture.md](docs/architecture.md).

## Testing

The test suite uses temporary directories and fake HTTP clients; it does not require GitHub, Discord, or model credentials.

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).

---

Built as a small experiment in agent-assisted software development.
