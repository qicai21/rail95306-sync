# STATUS

## Current Stage
- Phase 2 baseline is now the current 95306 shipment-query scheme based on the latest live page and request structure.
- This phase no longer uses the old query path as the decision baseline.
- The keepalive, ticket bootstrap, account storage, and worker preflight baseline remain unchanged.

## Completed In Phase 2
- Shipment station lookup is confirmed on the live page through `POST /api/zd/vizm/queryZms`.
- Shipment list query is confirmed on the live page through `POST /api/scjh/wayBillQuery/queryCargoSend`.
- The minimal shipment-query PoC is implemented and runnable locally.
- Query flow now supports automatic pagination and page merge based on `total / pages / pageSize`.
- Station lookup and shipment lookup are split into separate entry points.
- Confirmed station results are cached locally in the query dictionary file to avoid repeated station lookups against the server.
- The query docs, field dictionaries, and session notes have been written down as the current stage baseline.

## Verified Query Examples
- `高桥镇(51632) -> 马林(52670)`, `2026-03-12` to `2026-03-15`
  - total `120`
  - pages `3`
  - merged counts `50 + 50 + 20`
- `高桥镇(51632) -> 马林(52670)`, `2026-03-13` to `2026-03-14`
  - total `41`
  - pages `1`
  - merged count `41`

## Current Runtime Notes
- Query requests require a valid saved login state:
  - `runtime/95306_ticket_<account>.json`
  - `runtime/95306_storage_state_<account>.json`
- Business query responses may also refresh `SESSION` through `Set-Cookie`.
- This session-refresh behavior is recorded and should be considered in the next keepalive integration stage.

## Not Finished Yet
- Query-driven session refresh has not yet been integrated back into the keepalive worker.
- No scheduled or worker-driven shipment pull loop exists yet.
- No stable export/write pipeline exists yet for saving merged shipment results to files or downstream systems.
- The station dictionary is still partial and grows as new stations are queried.
- The current query tools are still CLI-focused and not yet wrapped as a higher-level operator workflow.

## Deployment Status
- Windows remains usable for development and local verification.
- macOS remains the intended deploy/runtime environment.
- Keepalive operations remain documented in `OPERATION.md`.
- Query operations for this phase are documented in `QUERY.md`.
