# 95306 Local Deployment Workflow

## Overview
- Real credentials are local-only and live at `runtime/95306_accounts.json`.
- The real `accounts.json` is not committed to Git. Send it to the deploy host through Telegram or another out-of-band channel.
- Worker startup only uses the standard files:
  - `runtime/95306_ticket_<account>.json`
  - `runtime/95306_storage_state_<account>.json`
- Start the worker only after `preflight` passes.

## macOS Deployment
### 1. Install dependencies
```bash
cd /path/to/rail95306-sync
python3 -m pip install playwright
python3 -m playwright install chromium
```

### 2. Prepare the local accounts file
```bash
mkdir -p runtime
cp config_examples/95306_accounts.example.json runtime/95306_accounts.json
```

- Replace the example values with the real account data you send to openclaw through Telegram.
- If `runtime/95306_accounts.json` is missing, openclaw must stop and ask you for the file.

### 3. Initialize one account
```bash
python3 ./tools/bootstrap_95306_ticket.py --account newts
```

- The script opens a headed Playwright browser.
- If `runtime/95306_accounts.json` exists, it auto-fills `id` and `pwd`.
- You manually finish slider/SMS/login.
- On success it saves:
  - `runtime/95306_ticket_newts.json`
  - `runtime/95306_storage_state_newts.json`

### 4. Check ticket/account status
```bash
python3 ./tools/preflight_95306_worker.py --status
```

### 5. Run startup preflight
```bash
python3 ./tools/preflight_95306_worker.py
python3 ./tools/preflight_95306_worker.py --strict
```

### 6. Start the worker
```bash
python3 ./tools/run_95306_keepalive.py
python3 ./tools/run_95306_keepalive.py --strict
```

### 7. Background management
```bash
python3 ./tools/manage_95306_keepalive.py start
python3 ./tools/manage_95306_keepalive.py status
python3 ./tools/manage_95306_keepalive.py stop
python3 ./tools/manage_95306_keepalive.py update-restart
```

## Win11 Development Notes
- Development and local verification can happen on Windows.
- The deployed target remains macOS, so keep the real runtime flow aligned with the macOS commands above.
- You can run local checks with:
```powershell
python .\tools\preflight_95306_worker.py --status
python .\tools\run_95306_keepalive.py --strict
```

## Failure policy
- Missing `runtime/95306_accounts.json`: fail with a clear message telling the operator to provide it out-of-band.
- Missing ticket/storage state for one account:
  - default mode: list the account as not ready and run only ready accounts
  - `--strict`: block startup
- Missing tickets for all accounts: block startup
