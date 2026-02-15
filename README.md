# TrainingPeaks CLI

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

Command-line interface for TrainingPeaks workout management, analysis, upload, and export.

## Status

This project is in alpha. Core workflows are implemented and usable.

## What It Does

- Login/logout with session cookie caching
- Fetch workouts with date/sport/type/TSS filters
- Get or delete a workout by ID
- Upload workouts from JSON, YAML, stdin, or quick CLI flags
- Analyze weekly summaries, zones, and training patterns
- Export workouts to CSV, iCal, and minimal TCX
- Return machine-readable output via `--json`

## Requirements

- Python `3.10+`
- A TrainingPeaks account
- Playwright Chromium for browser-based login

## Install

### 1. Clone and install

```bash
git clone https://github.com/exhibiton/trainingpeaks-cli.git
cd trainingpeaks-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[browser]"
playwright install chromium
```

### 2. Verify install

```bash
tp-cli --version
tp-cli --help
```

If `tp-cli` is not on your PATH, use:

```bash
python3 -m tp_cli --help
```

CLI entrypoints are `tp` and `tp-cli`.

## New User Setup (Step-by-Step)

### 1. Provide credentials

The simplest setup is environment variables:

```bash
export TP_USERNAME="you@example.com"
export TP_PASSWORD="your-password"
```

### 2. Login and cache session

```bash
tp-cli login
```

On first login, the CLI uses Playwright to sign in and stores cookies locally.

### 3. Confirm it works with a small fetch

```bash
tp-cli fetch --last-days 7 --format json --json
```

If successful, you should get a JSON payload with `workouts`, `summary`, and `exports`.

### 4. Run a normal fetch for local files

```bash
tp-cli fetch --last-days 30 --format both
```

This creates export files in your output directory (default: `./workouts`).

## Typical Workflow

### Fetch workouts

```bash
tp-cli fetch --last-days 30 --sport run --format both
tp-cli fetch --start-date 2026-01-01 --end-date 2026-01-31 --type threshold
```

### Get one workout

```bash
tp-cli get 123456789 --format markdown
tp-cli --json get 123456789
```

### Upload workouts

Quick single workout:

```bash
tp-cli upload --date 2026-02-15 --sport run --title "Easy Run 45min" --dry-run
tp-cli upload --date 2026-02-15 --sport run --title "Easy Run 45min"
```

From file:

```bash
tp-cli upload --file workout.yaml
```

From stdin:

```bash
cat workout.json | tp-cli upload --stdin
```

### Delete workout

```bash
tp-cli delete 123456789
tp-cli delete 123456789 --force
```

### Analyze training

```bash
tp-cli analyze weekly --last-weeks 8
tp-cli analyze zones --last-weeks 8 --sport run
tp-cli analyze patterns --last-weeks 8 --multi-sport --injury-risk
```

### Export workouts

```bash
tp-cli export --format csv --last-weeks 4
tp-cli export --format ical --this-month
tp-cli export --format tcx --last-days 14
```

## Command Summary

```bash
tp-cli login
tp-cli logout
tp-cli fetch [options]
tp-cli get WORKOUT_ID [--format json|markdown|raw]
tp-cli upload [options]
tp-cli delete WORKOUT_ID [--force]
tp-cli export [options]
tp-cli analyze weekly [options]
tp-cli analyze zones [options]
tp-cli analyze patterns [options]
```

Use `tp-cli --help` and `tp-cli <command> --help` for full options.

## Global Output Flags

- `--json`: JSON output where available
- `--plain`: plain output (no Rich formatting/tables)
- `--config PATH`: custom config file

`--json` and `--plain` cannot be used together.

## Upload Input Schema (Example)

`upload` accepts `--file`/`--stdin` with JSON or YAML.

```json
{
  "date": "2026-02-15",
  "sport": "run",
  "title": "Threshold Intervals",
  "description": "6x3min hard / 2min easy",
  "steps": [
    { "type": "warmup", "duration": "15:00", "target": "70% TP" },
    {
      "type": "interval",
      "reps": 6,
      "on": "3:00",
      "off": "2:00",
      "on_target": "95-100% TP",
      "off_target": "70% TP"
    },
    { "type": "cooldown", "duration": "10:00", "target": "65% TP" }
  ]
}
```

## Configuration

Default config path:

- `~/.config/tp/config.toml`

Legacy fallback path:

- `~/.tp-cli/config.json`

Useful environment variables:

- `TP_CONFIG_FILE`
- `TP_DATA_DIR`
- `TP_OUTPUT_DIR`
- `TP_COOKIE_STORE`
- `TP_USERNAME`
- `TP_PASSWORD`

Example `~/.config/tp/config.toml`:

```toml
[auth]
use_1password = false
cookie_store = "~/.local/share/tp/cookies.json"

[export]
default_directory = "./workouts"
include_index = true

[zones]
easy_max = 75
lt1_max = 93
lt2_max = 100

[api]
rate_limit_delay = 1.0
max_retries = 3
timeout_seconds = 30
```

### Optional 1Password setup

You can configure credential/cookie lookup from 1Password:

```toml
[auth]
use_1password = true
op_vault = "Your Vault"
op_cookie_document = "tp-cookies"
op_username_ref = "op://vault/item/username"
op_password_ref = "op://vault/item/password"
```

If you use a service account token, set `OP_SERVICE_ACCOUNT_TOKEN` in your environment.

## Files Created by the CLI

- Cookie cache: `~/.local/share/tp/cookies.json` (default; configurable)
- Fetch exports (default): `./workouts`
- Raw fetch dump (when `--raw`): `./workouts/raw/all_workouts.json`
- CSV export (default): `./workouts/workouts.csv`
- iCal export (default): `./workouts/training.ics`
- TCX export directory: `./workouts/tcx`

## Troubleshooting

### `Playwright is not installed`

Install browser extras and Chromium:

```bash
pip install -e ".[browser]"
playwright install chromium
```

### `Missing credentials`

Set `TP_USERNAME` and `TP_PASSWORD`, or pass `--username/--password` to `tp-cli login`.

### Login/session issues

Force a fresh login:

```bash
tp-cli login --force
```

Clear local cookies:

```bash
tp-cli logout
```

### `--json` and `--plain` conflict

Use only one output mode at a time.

## Current Limitations

- FIT export is not implemented yet.
- TCX export is metadata-only (minimal placeholder format).
- Login currently depends on browser automation via Playwright.

## Development

```bash
pip install -e ".[dev,browser]"
playwright install chromium
pytest
```

## Contributing

Issues and pull requests are welcome.

## License

MIT. See `LICENSE`.
