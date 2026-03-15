# rail95306-sync Agent Notes

## Local secrets and accounts
- Real account data lives in `runtime/95306_accounts.json`.
- `runtime/95306_accounts.json` is never committed to Git.
- The deploy-side operator sends the real `accounts.json` to openclaw through Telegram or another out-of-band channel.
- If `runtime/95306_accounts.json` exists, use it directly and allow login autofill from `id` and `pwd`.
- If `runtime/95306_accounts.json` is missing, stop with a clear error and ask the operator to provide it. Do not ask them to commit credentials to Git.

## Ticket files
- Worker flows only use the standard account-scoped filenames:
  - `runtime/95306_ticket_<account>.json`
  - `runtime/95306_storage_state_<account>.json`
- Do not introduce temporary worker-facing suffixes such as `run1` or `run2`.
- Real ticket files and runtime reports stay local and must not be committed.

## Startup policy
- Always run a preflight check before starting the worker.
- Preflight must fail loudly when the accounts file is missing, malformed, or when no runnable account is available.
- In default mode, worker may run only the accounts that have completed initialization.
- In strict mode, any missing account ticket must block startup.

## Platform assumptions
- Development and ad hoc verification may happen on Windows.
- Deployment and normal operation target macOS.
- Keep command examples and runtime assumptions compatible with macOS shell usage; do not hardcode Windows-only behavior into the main workflow.
