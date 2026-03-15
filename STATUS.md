# STATUS

## Current State
- The keepalive infrastructure is in a stable baseline state for maintenance.
- Account configuration is local-only and loaded from `runtime/95306_accounts.json`.
- Real accounts are not committed to Git; they are provided to the deploy host out-of-band.
- Ticket initialization is manual-login based:
  - Playwright opens a headed browser
  - openclaw can autofill username and password from the local accounts file
  - the operator completes slider/SMS/login manually
  - the system saves standard ticket and storage files locally
- Startup preflight is implemented and enforced before worker launch.
- The worker can run on the target deployment path: Mac Studio + OpenClaw.

## Stable Workflow
- Configure local accounts in `runtime/95306_accounts.json`
- Initialize tickets per account with `tools/bootstrap_95306_ticket.py`
- Verify readiness with `tools/preflight_95306_worker.py`
- Start the keepalive worker with `tools/run_95306_keepalive.py`
- Refresh or reinitialize tickets when login state expires

## Runtime Guarantees
- Worker only reads standard account-scoped ticket files
- Missing accounts file fails loudly
- Missing ticket/storage state is reported explicitly
- Default mode can run only ready accounts
- Strict mode blocks startup if any configured account is not ready

## Deployment Status
- Windows can be used for development and local checks
- macOS is the intended deploy/runtime environment
- Current operational documentation is maintained in `OPERATION.md`
