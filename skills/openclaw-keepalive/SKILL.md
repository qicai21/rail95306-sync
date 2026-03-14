---
name: openclaw-keepalive
description: Use when you need to operate the 95306 keepalive worker in this repository: start it, verify whether it is still online, stop it, or pull the latest GitHub code and restart it.
---

# Openclaw Keepalive

This skill controls the 95306 keepalive worker in this repo.

Use it when the user asks things like:

- start the keepalive worker
- check whether it is still online
- stop the running keepalive worker
- pull latest code from GitHub and restart it
- verify whether the worker is still healthy after running for some time

## Project Root

Run all commands from:

`D:\projects\rail95306-sync`

On macOS, use the cloned repository path instead of the Windows path. The workflow is the same.

## Single Entry Point

Always prefer this manager script instead of rebuilding commands manually:

- [tools/manage_95306_keepalive.py](/D:/projects/rail95306-sync/tools/manage_95306_keepalive.py)

Supported actions:

- `start`
- `status`
- `stop`
- `update-restart`

The manager script is cross-platform:

- Windows: uses `tasklist` / `taskkill`
- macOS and Linux: uses PID checks plus `kill`

## Commands

Start the worker:

```powershell
python .\tools\manage_95306_keepalive.py start
```

Check whether it is still online:

```powershell
python .\tools\manage_95306_keepalive.py status
```

Stop the worker:

```powershell
python .\tools\manage_95306_keepalive.py stop
```

Pull latest GitHub code and restart:

```powershell
python .\tools\manage_95306_keepalive.py update-restart
```

## What "Online" Means

Treat the worker as online only if both are true:

1. `status` returns `"running": true`
2. The last event in [runtime/95306_keepalive.log](/D:/projects/rail95306-sync/runtime/95306_keepalive.log) is not a failure-stop event

Important:

- The keepalive loop itself is designed to stop immediately on account failure.
- A stopped worker is not healthy, even if old logs still exist.

## Logs and Evidence

Primary worker health log:

- [runtime/95306_keepalive.log](/D:/projects/rail95306-sync/runtime/95306_keepalive.log)

Manager stdout/stderr log:

- [runtime/95306_keepalive_runner.log](/D:/projects/rail95306-sync/runtime/95306_keepalive_runner.log)

Failure screenshots:

- [runtime/screenshots](/D:/projects/rail95306-sync/runtime/screenshots)

## Account Config

The worker expects:

- `runtime/95306_accounts.json`

The file format is:

```json
{
  "accounts": [
    {
      "key": "newts",
      "name": "新铁晟",
      "id": "5035440021",
      "pwd": "your-password"
    }
  ]
}
```

Do not invent a different mapping format.

If the file is missing on another machine, copy the structure from:

- [config_examples/95306_accounts.example.json](/D:/projects/rail95306-sync/config_examples/95306_accounts.example.json)

Important:

- `runtime/` is ignored by Git
- cloned machines will not automatically have live account secrets or live ticket files
- if `runtime/95306_accounts.json` or ticket files are missing, report that clearly instead of pretending the worker can start

When asked whether it is still online, report:

- whether the process is running
- the last heartbeat event time
- whether the last event is `cycle_completed` or a failure-stop event
- screenshot path if the worker stopped because of failure

## Worker Behavior

The managed worker is:

- [tools/run_95306_keepalive.py](/D:/projects/rail95306-sync/tools/run_95306_keepalive.py)

Its current behavior:

- checks `newts` and `cy-steel`
- heartbeat interval is 10 minutes
- for each account, opens Playwright with the latest saved ticket
- considers the account healthy if it still lands on `platformIndex`
- if any account fails, logs the time, captures a screenshot, and exits immediately

## Update-Restart Workflow

When the user asks to update and restart:

1. Run `update-restart`
2. Confirm `git pull --ff-only` succeeded
3. Confirm a new PID is recorded
4. Run `status`
5. Report whether the worker is back online

If pull fails, do not claim success.

## Do Not

- Do not manually delete runtime files unless the user explicitly asks
- Do not invent health state from stale logs alone
- Do not run multiple keepalive worker instances in parallel
- Do not bypass the manager script unless it is broken and you clearly say so
