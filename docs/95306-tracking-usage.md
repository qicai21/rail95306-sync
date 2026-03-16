# 95306 Tracking Usage Rules

## Scope

This document defines how the current tracking response should be used by the program side.

It does not define deployment, storage schema migration, or worker rollout.

## Current Objective

Use one tracking response for two downstream purposes only:

1. generate a readable current status summary for the main shipment/car table
2. extract the minimum useful data for a dedicated vehicle tracking table

Everything else should stay raw or be deferred.

## Start Condition

Tracking capture should only start after the shipment/car status reaches:

- `已制单`

## Current Status Summary Rules

Program input source:

- normalized `latest_status`

Current latest-status fields:

- `status_code`
- `status_name`
- `latest_event_time`
- `latest_event_message`
- `latest_event_station`
- `latest_event_station_tmis`
- `latest_event_station_dbm`
- `latest_event_location`
- `latest_event_report_id`

### Status Mapping

Current summary status should be derived with this priority:

1. if latest event text contains `交付`, summary status = `已交付`
2. if latest event is destination arrival, summary status = `到达`
3. if shipment has departed from origin and has not yet arrived at destination, summary status = `在途`
4. if `status_name = 已发车`, summary status = `在途`
5. intermediate arrival at a non-destination station still counts as `在途`
6. otherwise fall back to `status_name`

Confirmed `rptid` meanings:

- `LCDD`
  - 列车到达
- `LCCF`
  - 列车出发

### Summary Sentence Format

Recommended format:

```text
<派生状态>（最近报告：<latest_event_time> <latest_event_message>）
```

Examples:

```text
在途（最近报告：2026-03-16 05:52:00 货物离开高桥镇站。）
在途（最近报告：2026-03-16 07:31:00 货物到达锦州站。）
已交付（最近报告：2026-03-18 09:30:00 货物已交付。）
```

## Minimum Vehicle Tracking Table Content

Only the following fields are currently considered necessary:

- 发站
- 到站
- 货物
- 发车时间
- 各站到达时间
- 各站发出时间
- 最终到站时间
- 列号

### Recommended Source Mapping

| Target Meaning | Suggested Source |
| --- | --- |
| 发站 | `data.fsMain.fzhzzm` |
| 到站 | `data.fsMain.dzhzzm` |
| 货物 | `data.fsMain.hzpm` |
| 发车时间 | `data.fsMain.fcsj` if present, otherwise first departure-like event from `data.gj` |
| 各站到达时间 | events with `rptid = LCDD` |
| 各站发出时间 | events with `rptid = LCCF` |
| 最终到站时间 | destination-arrival event, or `data.fsMain.dzsj` when reliable |
| 列号 | later-generated grouping field |

## Train Group Id Rule

Later train-group id format is confirmed as:

```text
收货人拼音简称 + "_" + yymm + "_" + 当月该流向第几列(三位数)
```

Example:

```text
YTTY_2603_004
```

Meaning:

- `YTTY`
  - 收货人拼音简称，例如 云铜铜业
- `2603`
  - `2026-03`
- `004`
  - 当月该流向第 4 列

## Split Handling

Train groups may split after departure.

Example:

- 53 cars depart together from 高桥镇
- they split at 锦州 into 30 cars and 23 cars

Current conclusion:

- split scenarios are real and must be modeled later
- exact suffix naming rule for split groups is still pending

## Low-Priority Fields

These fields are not primary for the current business output:

- `data.gjzt`
- `data.dtgjDetailVoList`
- `data.jlzc`
- `data.useHour`
- `data.yjddsj1`

Current handling:

- keep raw for reference
- do not prioritize in the next implementation step

## Current Implementation Note

The normalized tracking output may expose:

- `latest_status`
- `derived_status`
- `current_status_summary`

These are meant to make the later main-table update rule explicit before any storage redesign is done.

## Revised Capture And Persistence Rules

The following rules supersede the earlier broad persistence idea:

1. only start tracking capture after shipment status reaches `已制单`
2. stop active tracking capture after destination arrival
3. before destination arrival, tracking is mainly used to update the latest shipment status
4. only retain completed destination-arrived tracking data in the database for later route analysis

## Revised Persisted Shape

The later persisted structure should be one shipment per row, with one route array kept as JSON-like data.

Suggested shape:

```json
{
  "id": 1,
  "shipment_id": "516322603154358675",
  "car_no": "1585686",
  "origin": "高桥镇",
  "destination": "海拉尔东",
  "cargo_name": "锌精矿",
  "transport_mode": "集装箱",
  "train_group_id": "YTTY_2603_004",
  "ticketed_at": "2026-03-15 21:27:57",
  "departed_at": "2026-03-16 05:52:00",
  "final_arrived_at": null,
  "route_track": [
    {
      "station_name": "锦州",
      "arrived_at": "2026-03-16 07:31:00",
      "departed_at": null
    },
    {
      "station_name": "大虎山",
      "arrived_at": null,
      "departed_at": null
    },
    {
      "station_name": "通辽西",
      "arrived_at": null,
      "departed_at": null
    }
  ]
}
```

Required top-level fields:

- `id`
- `shipment_id`
- `car_no`
- `origin`
- `destination`
- `cargo_name`
- `transport_mode`
- `train_group_id`
- `ticketed_at`
- `departed_at`
- `final_arrived_at`
- `route_track`

Arrival confirmation rule:

- destination arrival should be confirmed by shipment query field `dzsj`
- if `queryCargoSend.dzsj` has a value, the shipment is considered arrived
- `final_arrived_at` should use that `dzsj` value as the final arrival time

Route item fields:

- `station_name`
- `arrived_at`
- `departed_at`

Why null route times must be kept:

- some passing stations are not actual stop points
- the route path is still valuable for later travel-time and route-planning analysis
- later comparison needs a relatively complete station sequence, not only observed stop events

## Open TODO

Future optimization idea confirmed by the user:

- between shipment query and tracking query, add an intermediate table
- this intermediate table should at least store:
  - `ydid`
  - train/group info (`列名` / `车次信息`)
- tracking download should be scheduled from that intermediate table instead of directly scanning every shipment repeatedly
- for the same train group, one shared tracking record may be enough
- later add a `car_count` attribute for the train group
- later plan a smarter “train in-transit status update” workflow, because full-scan tracking is wasteful

Current rule about station order:

- do not over-fit or over-correct `route_track` station order in the current capture stage
- current `route_track` may contain incomplete or imperfect station ordering
- stable station order should be derived later from accumulated historical data, grouped by origin/destination
