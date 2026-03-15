# OPERATION

## Overview
- Real account data lives in `runtime/95306_accounts.json`
- Real ticket/runtime files stay local and do not go into Git
- Standard runtime files:
  - `runtime/95306_ticket_<account>.json`
  - `runtime/95306_storage_state_<account>.json`

## 1. Configure Local Accounts
From the repo root:

```bash
mkdir -p runtime
cp config_examples/95306_accounts.example.json runtime/95306_accounts.json
```

Edit `runtime/95306_accounts.json` with the real account values:
- `key`
- `name`
- `id`
- `pwd`

If `runtime/95306_accounts.json` is missing, the scripts must stop and ask the operator to provide it through Telegram or another local channel. Real credentials must not be committed to Git.

## 2. Initialize One Account Ticket
macOS:

```bash
python3 ./tools/bootstrap_95306_ticket.py --account newts
```

Windows:

```powershell
python .\tools\bootstrap_95306_ticket.py --account newts
```

Expected flow:
- the script opens a headed Playwright browser
- if the local accounts file exists, username/password are autofilled
- the operator manually completes slider/SMS/login
- after login succeeds, the script saves:
  - `runtime/95306_ticket_newts.json`
  - `runtime/95306_storage_state_newts.json`

## 3. Check Ticket Status
macOS:

```bash
python3 ./tools/preflight_95306_worker.py --status
```

Windows:

```powershell
python .\tools\preflight_95306_worker.py --status
```

This reports:
- configured accounts
- ready accounts
- accounts missing ticket/storage state
- whether startup would pass in default or strict mode

## 4. Start Worker
macOS:

```bash
python3 ./tools/run_95306_keepalive.py
```

Strict mode:

```bash
python3 ./tools/run_95306_keepalive.py --strict
```

Behavior:
- startup runs preflight first
- default mode starts only ready accounts
- strict mode blocks if any configured account is not ready
- no silent fail is allowed

## 5. Background Worker Management
macOS:

```bash
python3 ./tools/manage_95306_keepalive.py start
python3 ./tools/manage_95306_keepalive.py status
python3 ./tools/manage_95306_keepalive.py stop
python3 ./tools/manage_95306_keepalive.py update-restart
```

## 6. When a Ticket Expires
If preflight or worker reports the account is no longer usable:

1. Check current status:
```bash
python3 ./tools/preflight_95306_worker.py --status
```

2. If the saved login state is invalid, reinitialize that account:
```bash
python3 ./tools/bootstrap_95306_ticket.py --account newts
```

3. If you only need to refresh an already valid ticket bundle, use:
```bash
python3 ./tools/refresh_95306_ticket.py --account newts
```

4. Re-run preflight:
```bash
python3 ./tools/preflight_95306_worker.py
```

5. Start or restart the worker:
```bash
python3 ./tools/run_95306_keepalive.py
```

## 7. Release Baseline
- Stable maintenance tag: `v0.1-keepalive-stable`
- This tag marks the baseline where the keepalive infrastructure, local accounts flow, manual ticket initialization, preflight check, and Mac Studio + OpenClaw worker path are considered stable
