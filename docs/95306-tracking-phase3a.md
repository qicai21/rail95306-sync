# 95306 Tracking Query Baseline

## Scope

This document only covers the website-side ability to query the latest tracking state for one shipment / one car.

Current phase goals:

- make the tracking query callable from the program side
- document the live request and response shape
- provide a minimal CLI entrypoint

Out of scope in this phase:

- server deployment
- OpenClaw runtime integration
- tracking event storage
- database schema redesign
- route-wide status derivation

## Verified Live Interface

Tracking interface confirmed from the live page:

- `POST https://ec.95306.cn/api/scjh/track/qeryYdgjNew`

Tracking page referer pattern:

- `https://ec.95306.cn/ydTrickDu?prams=<encoded_ydid>`

## Request Construction

Live request body uses an encoded `ydid`, not the plain shipment id.

Rule confirmed from both the legacy code path and the current live request:

1. start with the plain shipment id from shipment query result, for example `516322603154358675`
2. Base64-encode the byte string 6 times in a row
3. send the final string as request JSON field `ydid`
4. use the same encoded string in the referer `prams` query, URL-encoding `=`

Verified example:

- plain shipment id: `516322603154358675`
- encoded tracking id:
  - `Vm10a05GVXhTbkpOV0VwT1ZrWndWVll3WkRSVlJteFlaRVZrVDJKR1NsaFdWM2hoVkd4S1ZWSlVTbGRpUmtwVVZrUktSMlJHVWxsYWVqQTk=`

## Reused Foundation

Current tracking query implementation reuses the same verified foundations as shipment query:

- saved ticket file:
  - `runtime/95306_ticket_<account>.json`
- saved storage state file:
  - `runtime/95306_storage_state_<account>.json`
- cookie jar built from saved ticket cookies
- request headers derived from saved `95306-1.6.10-userdo` and `95306-1.6.10-accessToken`
- session writeback through `SessionStateManager.sync_cookie_jar()`

This means tracking query uses the same account/session prerequisites as shipment query and does not introduce a separate login path.

## Response Structure Overview

The live response is already sufficient for programmatic use.

Main top-level fields:

- `data.fsMain`
  - main shipment summary
- `data.gjzt`
  - phase flags such as accepted, loaded, departed, arrived
- `data.gj`
  - tracking event list, newest item first
- `data.dtgjDetailVoList`
  - grouped event text by station
- `data.jlzc`
  - route nodes / predicted passing stations
- `data.yjddsj`
  - estimated arrival time
- `data.yjddlc`
  - remaining distance

## Fields Most Useful In This Phase

Latest status:

- `data.fsMain.ztgj`
  - latest status code
- `data.fsMain.ztgjjc`
  - latest status name
- `data.gj[0]`
  - latest event record when present

Time / place / node / message:

- `data.gj[*].detail`
  - event time
- `data.gj[*].operator`
  - station / node name
- `data.gj[*].tmism`
  - station TMIS code
- `data.gj[*].czdbm`
  - station telegraph code
- `data.gj[*].czdz`
  - location text
- `data.gj[*].message`
  - event description
- `data.gj[*].rptid`
  - report/event kind marker when present

Shipment context:

- `data.fsMain.ydid`
- `data.fsMain.ch`
- `data.fsMain.hph`
- `data.fsMain.hzpm`
- `data.fsMain.fzhzzm`
- `data.fsMain.dzhzzm`
- `data.fsMain.fzyxhz`
- `data.fsMain.dzyxhz`

Timing context:

- `data.yjddsj`
- `data.yjddsj1`
- `data.yjddlc`
- `data.useHour`

## CLI

Entry point:

- `tools/query_95306_tracking.py`

Windows:

```powershell
python .\tools\query_95306_tracking.py --account newts --shipment-id 516322603154358675
```

macOS:

```bash
python3 ./tools/query_95306_tracking.py --account newts --shipment-id 516322603154358675
```

Optional raw output:

```powershell
python .\tools\query_95306_tracking.py --account newts --shipment-id 516322603154358675 --raw
```

## Output Shape

Default output is normalized JSON with these main sections:

- `query_input`
- `shipment`
- `latest_status`
- `tracking_flags`
- `timing`
- `events`
- `route_nodes`
- `raw_response`

This phase intentionally keeps the full live event list and route node list in JSON output without trying to derive final business states.

## Current Boundaries

Done in this phase:

- standalone tracking query ability
- verified `ydid -> 6x Base64` request rule
- normalized one-shot JSON output
- independent CLI entrypoint

Deferred to later phases:

- deciding which tracking fields should become persistent columns
- tracking event storage tables
- route latest-node derivation
- current-line status aggregation
- full downstream business modeling
