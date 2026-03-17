# Phase 3A Handoff

## Core Fields Confirmed From Real Data

- `ydid`
- `ysfs`
- `ch`
- `czcx`
- `hzpm`
- `hwjs`
- `fhdwmc`
- `shdwmc`
- `fzhzzm`
- `fzyxhz`
- `dzhzzm`
- `dzyxhz`
- `xh`
- `zzl`
- `yf`
- `slrq`
- `zcrq`
- `zpsj`
- `fcsj`
- `dzsj`
- `dzjfrq`
- `xqslh`
- `hph`
- `yjxfh`
- `tyrjzsx`
- `zcdcsj`
- `zcddsj`
- `zckssj`
- `zcwbsj`
- `xcdcsj`
- `xcddsj`
- `xckssj`
- `xcwbsj`
- `ztgjend`
- `ztgjjcend`

## Tables Added

- `query_runs`
  - one collection execution
- `query_run_pages`
  - one row per fetched page
- `raw_api_responses`
  - merged raw response trace
- `shipments`
  - latest current state by `ydid`
- `shipment_snapshots`
  - per-run historical snapshots
- `stations`
  - lightweight station dictionary
- `session_states`
  - current session/token summary mirrored from runtime files

## SQLite File

- `runtime/95306_collection.sqlite3`

## Manual Run

```bash
python3 ./tools/collect_95306_shipments.py --account newts --start-date 2026-03-12 --end-date 2026-03-15 --origin-code 51632 --destination-code 52670
```

## Automatic Run

```bash
python3 ./tools/collect_95306_shipments.py --account newts --start-date 2026-03-12 --end-date 2026-03-15 --origin-code 51632 --destination-code 52670 --loop
```

Default interval:
- 20 minutes

## Current Limits

- only merged `queryCargoSend` raw responses are stored
- tracking child tables are not implemented yet
- job-set configuration for multiple routes is not implemented yet
- `launchd` integration is documented as a next step, not implemented

## Next Suggested Phase

1. Add explicit tracking-event persistence from `qeryYdgjNew`.
2. Move automatic route definitions into a local query-job config file.
3. Add page-level raw response persistence if replay/debugging needs increase.
4. Add `launchd` packaging after the local collector shape is stable.
