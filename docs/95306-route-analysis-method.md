# 95306 Route Analysis Method

## Scope

This document defines a later analysis method for deriving stable route station order from accumulated tracking data.

It is intentionally separate from the current online capture logic.

## Goal

When enough completed tracking data has been accumulated:

1. group shipments by route
2. summarize station appearances for each route group
3. derive the most plausible station order from real historical data
4. use that derived order to supplement and adjust persisted route data

## Grouping Key

Current grouping key:

- origin station
- destination station

Practical group identifier:

```text
<origin_name> -> <destination_name>
```

Example:

```text
高桥镇 -> 海拉尔东
```

## Core Principle

Do not require perfect route order during the first capture stage.

Instead:

- capture route-related data as-is
- retain route arrays with nullable station times
- wait until enough shipments exist in the same route group
- then derive a stable station sequence from the historical set

## Input Data

For one route group, analysis should use all completed shipments that have:

- same origin
- same destination
- destination arrival completed
- sufficiently complete tracking data

Relevant fields:

- top-level route metadata:
  - `origin`
  - `destination`
  - `cargo_name`
  - `transport_mode`
  - `ticketed_at`
  - `departed_at`
  - `final_arrived_at`
- route array:
  - `route_track[*].station_name`
  - `route_track[*].arrived_at`
  - `route_track[*].departed_at`

## Analysis Steps

### 1. Collect route group samples

Select all completed shipments under one route group.

Minimum suggestion:

- only analyze a route after enough samples have accumulated

Initial practical threshold:

- 10+ completed shipments in the same route group

### 2. Count station appearances

For every route group:

- count how often each station appears in `route_track`
- count how often each station has non-null arrival/departure times

This helps separate:

- core fixed route stations
- occasional branch/split/abnormal stations

### 3. Infer station order

Use pairwise precedence from historical shipments:

- if station A appears before station B in most shipments, treat `A < B`

Recommended method:

- build pairwise ordering counts for all station pairs
- rank stations by the strongest consistent ordering across the sample set

This is more stable than trusting any single shipment's `route_track`.

### 4. Build canonical route order

For each route group, generate one canonical station list:

```json
[
  "高桥镇",
  "锦州",
  "大虎山",
  "通辽西",
  "通辽",
  "海拉尔东"
]
```

This canonical route order becomes the reference route for that origin/destination pair.

### 5. Repair and supplement stored route arrays

Once canonical order exists, historical shipment rows can be adjusted:

- insert missing stations into `route_track`
- preserve existing observed arrival/departure times
- leave missing observed times as `null`

Example:

```json
{
  "station_name": "大虎山",
  "arrived_at": null,
  "departed_at": null
}
```

This is acceptable and useful.

### 6. Handle split or abnormal routes separately

Some shipments may be split or rerouted.

Those should not directly redefine the canonical route.

Suggested treatment:

- mark as outlier route variants
- keep original shipment-level route data
- only promote route order into the canonical route when it is stable across the majority sample

## Output Of This Analysis

For each origin/destination group, the analysis should eventually produce:

1. canonical station order
2. station appearance counts
3. likely core route stations
4. possible variant/outlier stations
5. repaired shipment route arrays for easier downstream comparison

## Intended Database Impact Later

This method is intended for a later stage.

Likely later outcomes:

- add a canonical route definition table by origin/destination
- add a route-analysis result table
- backfill shipment route arrays using canonical station order

But this document does not require immediate schema work.
