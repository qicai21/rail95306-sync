# QUERY

## Purpose

This document is the Phase 2 operator guide for the current 95306 shipment-query baseline.

This query path is independent from keepalive bootstrap and worker startup.
It reuses the saved login state, station lookup, and automatic pagination logic that have already been verified on the live page.

## Preconditions

Before running shipment queries, these conditions must already be true:

- `runtime/95306_accounts.json` exists locally
- the target account has a valid saved ticket file:
  - `runtime/95306_ticket_<account>.json`
- the target account has a valid saved storage state file:
  - `runtime/95306_storage_state_<account>.json`
- the account can still access 95306 business pages

If login state has expired, reinitialize the ticket first with:

Windows:
```powershell
python .\tools\bootstrap_95306_ticket.py --account newts --yes
```

macOS:
```bash
python3 ./tools/bootstrap_95306_ticket.py --account newts --yes
```

## Related Code Entrypoints

- `query95306/shipment_query.py`
  - core query client
  - station lookup
  - shipment query payload construction
  - automatic pagination merge
  - optional tracking detail query
- `tools/query_95306_station.py`
  - standalone station lookup CLI
- `tools/query_95306_shipment.py`
  - standalone shipment lookup CLI
- `tools/query_95306_tracking.py`
  - standalone single-shipment tracking CLI
- `docs/95306-tracking-phase3a.md`
  - tracking request and response baseline

## Station Lookup

Use this when you want to resolve station names or abbreviations into `tmism`.

Windows:
```powershell
python .\tools\query_95306_station.py --account newts --keyword gqz --exact-name 高桥镇
```

Output JSON includes:

- `keyword`
- `http_status`
- `return_code`
- `count`
- `stations`
- `selected` when `--exact-name` is provided

The tool first checks the local station cache in `docs/95306-query-dictionaries.json`.
If the station already exists in cache, it does not query the server again.

## Shipment Query

You can query by TMIS code directly or by station name/keyword.

### By station name

Windows:
```powershell
python .\tools\query_95306_shipment.py --account newts --start-date 2026-01-11 --end-date 2026-02-01 --origin-keyword gqz --origin-name 高桥镇 --destination-keyword xtz --destination-name 新台子
```

### By TMIS code

Windows:
```powershell
python .\tools\query_95306_shipment.py --account newts --start-date 2026-03-12 --end-date 2026-03-15 --origin-code 51632 --destination-code 52670
```

## Shipment Query Parameters

- `--account`
  - account key from `runtime/95306_accounts.json`
- `--start-date`
  - query start date, format `YYYY-MM-DD`
- `--end-date`
  - query end date, format `YYYY-MM-DD`
- `--origin-code`
  - origin `tmism`
- `--destination-code`
  - destination `tmism`
- `--origin-keyword`
  - station lookup keyword, such as `gqz`
- `--destination-keyword`
  - station lookup keyword, such as `xtz`
- `--origin-name`
  - exact origin station name, such as `高桥镇`
- `--destination-name`
  - exact destination station name, such as `新台子`
- `--shipment-id`
  - optional exact waybill filter
- `--page-size`
  - current default is `50`, matching the live page
- `--limit`
  - number of normalized shipment rows printed in `shipments`
- `--skip-track`
  - skip the optional `qeryYdgjNew` tracking request
- `--single-page`
  - disable auto-pagination and only request one page

## Tracking Query

Tracking query is now available as a standalone one-shot tool for one shipment id.

Windows:

```powershell
python .\tools\query_95306_tracking.py --account newts --shipment-id 516322603154358675
```

Preconditions are the same as shipment query:

- valid `runtime/95306_ticket_<account>.json`
- valid `runtime/95306_storage_state_<account>.json`
- usable account session on 95306

If the server returns `invalid_token`, refresh the ticket first:

```powershell
python .\tools\refresh_95306_ticket.py --account newts
```

## Output JSON Structure

The shipment query output includes at least:

- `query_input`
- `shipment_id`
- `origin`
- `destination`
- `shipment_status`
- `last_update_time`
- `shipments`
- `raw_response`
- `mapping_notes`
- `station_resolution` when station lookup was used

## How To Read `page_summaries`

`raw_response.page_summaries` lists each requested page and what was returned:

```json
[
  {
    "page_num": 1,
    "page_size": 50,
    "result_count": 50,
    "total": 120,
    "pages": 3
  },
  {
    "page_num": 2,
    "page_size": 50,
    "result_count": 50,
    "total": 120,
    "pages": 3
  },
  {
    "page_num": 3,
    "page_size": 50,
    "result_count": 20,
    "total": 120,
    "pages": 3
  }
]
```

## How To Tell Whether All Pages Were Pulled

The result set is complete when:

- the number of page summaries equals `pages`
- the sum of all `result_count` values equals `total`
- the merged `raw_response.result_count` equals `total`

If `pages` is `1`, a single request is enough.
If `pages` is greater than `1`, the tool follows all pages automatically unless `--single-page` is set.

## Verified Example

Command:

```powershell
python .\tools\query_95306_shipment.py --account newts --start-date 2026-03-12 --end-date 2026-03-15 --origin-code 51632 --destination-code 52670 --limit 2 --skip-track
```

Verified result:

- `高桥镇 -> 马林`
- `total = 120`
- merged pages:
  - page 1 = `50`
  - page 2 = `50`
  - page 3 = `20`

## Session Note

`queryCargoSend` may return a new `SESSION` cookie in the response.
That means shipment queries themselves can refresh session state and should be treated as a valid session-update source in the next keepalive integration stage.
