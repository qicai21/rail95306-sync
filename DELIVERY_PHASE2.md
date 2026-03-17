# DELIVERY PHASE 2

## Final Baseline

Phase 2 formally adopts the current live-page shipment-query scheme as the working baseline.

This means:

- station lookup is based on the current live request to `queryZms`
- shipment list lookup is based on the current live request to `queryCargoSend`
- pagination is based on the current live response fields `total / pages / pageSize`
- the latest verified request payload and response structure are the source of truth for this phase

## What Is No Longer Blocking

The old query implementation is no longer the primary decision baseline.

Its useful conclusions have been extracted into the current docs and query modules.

It no longer blocks Phase 2 delivery decisions and does not need to stay in the active repository tree.

## Delivered In This Phase

- a runnable shipment-query PoC
- automatic station resolution before shipment query
- local station cache
- automatic pagination merge
- verified request and response documentation
- field dictionaries and status dictionaries

## Current Phase Result

The current scheme can already:

- resolve station names into `tmism`
- query shipment data against the live page API
- follow all pages automatically
- merge the full result set into one response
- return normalized summary rows and raw pagination metadata

## Code Responsibilities

- `query95306/shipment_query.py`
  - reusable query client and core query logic
- `tools/query_95306_station.py`
  - station lookup operator entrypoint
- `tools/query_95306_shipment.py`
  - shipment query operator entrypoint

## Next Integration Direction

The next stage should integrate this query result path with keepalive session maintenance, because business queries may also update `SESSION` through response cookies.
