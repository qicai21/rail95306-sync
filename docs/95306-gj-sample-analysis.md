# 95306 `gj` Sample Analysis

## Sample

This sample uses one real shipment on the route:

- origin: `高桥镇` (`51632`, `GZD`)
- destination: `林西` (`13192`, `LXC`)
- shipment id: `202602TY3158540038`
- request date scope used to locate the shipment: `2026-03-11`

Important correction:

- `202602TY3158540038` is `ydid`, not `xqslh`
- the matching `xqslh` for this shipment is `202602TY315854`

Raw sample files saved under `runtime/`:

- `phase4_waybill_202602TY3158540038.json`
- `phase4_tracking_202602TY3158540038.json`
- `phase4_summary_202602TY3158540038.json`
- `phase4_focus_202602TY3158540038.json`

## Core Comparison

Waybill core fields confirmed from this sample:

```json
{
  "ydid": "202602TY3158540038",
  "xqslh": "202602TY315854",
  "fztmism": "51632",
  "fzhzzm": "高桥镇",
  "fzyxhz": "锦州高天铁路有限责任公司专用铁路",
  "dztmism": "13192",
  "dzhzzm": "林西",
  "dzyxhz": "铁路货场",
  "fhdwmc": "锦州新铁晟港口物流有限公司",
  "shdwmc": "锦州新铁晟港口物流有限公司",
  "hzpm": "铜精矿",
  "zzl": "70.00",
  "ysfs": "1",
  "ch": "1754444",
  "hph": "GZDZW0461092",
  "slrq": "2026-03-10 10:08:08",
  "zpsj": "2026-03-10 21:38:21",
  "fcsj": "2026-03-11 02:56:00",
  "dzsj": "2026-03-13 20:44:00",
  "dzjfrq": "2026-03-14 17:46:56",
  "zcddsj": "2026-03-10 12:20:00",
  "zckssj": "2026-03-10 12:30:47",
  "zcwbsj": "2026-03-10 21:30:47",
  "xcddsj": "2026-03-13 23:10:42",
  "xcdcsj": "2026-03-14 03:35:47",
  "xcwbsj": "2026-03-14 03:30:52",
  "ztgjend": "85",
  "ztgjjcend": "确认收货"
}
```

Tracking structures returned by `qeryYdgjNew` for this sample:

- `gj`: 23 event rows
- `dtgjDetailVoList`: 7 station-level grouped rows
- `jlzc`: 0 rows in this sample

## Field Interpretation Updates

Confirmed from the waybill and tracking time alignment:

- `ydid`
  - single shipment primary key
- `xqslh`
  - demand/request batch id, not the unique shipment id
- `slrq`
  - accepted time
  - aligned with `2026-03-10 10:08:08 需求受理通过`
- `zcddsj`
  - loading-side vehicle ready / inbound time
  - aligned with `2026-03-10 12:20:00 您的车辆已到位`
- `zckssj`
  - loading started
  - aligned with `2026-03-10 12:30:47 货物已开始装车`
- `zcwbsj`
  - loading completed
  - aligned with `2026-03-10 21:30:47 货物已完成装车`
- `zpsj`
  - ticket/document completed
  - aligned with `2026-03-10 21:38:21 您的货物已完成制单`
- `fcsj`
  - departed origin station
  - aligned with `2026-03-11 02:56:00 货物离开高桥镇站`
- `dzsj`
  - arrived destination station
  - aligned with `2026-03-13 20:44:00 货物到达林西站`
- `xcwbsj`
  - unloading completed
  - aligned with `2026-03-14 03:30:52 货物已卸车完毕`
- `dzjfrq`
  - delivery completed
  - aligned with `2026-03-14 17:46:56 货物已交付完毕`

Fields still not fully fixed from one sample:

- `xcddsj`
- `xcdcsj`
- `xckssj`

These need more samples before a final label is locked, because the current sample does not expose explicit `gj` messages with the same names.

## Station Dictionary Rule From `gj`

Each `gj` row can be used to grow the station dictionary directly.

Useful fields:

- `operator` -> station name
- `tmism` -> station TMIS code
- `czdbm` -> station telegraph code
- `czdz` -> station address

This sample adds or confirms:

- `高桥镇` `51632` `GZD` `辽宁省 葫芦岛市 连山区`
- `锦州` `51650` `JZD` `辽宁省 锦州市 凌河区`
- `彰武` `53291` `ZWD` `辽宁省 阜新市 彰武县`
- `通辽` `53363` `TLD` `内蒙古自治区 通辽市 科尔沁区`
- `哲里木` `13230` `ZLC` `内蒙古自治区 通辽市 科尔沁区`
- `大板` `13198` `DBC` `内蒙古自治区 赤峰市 巴林右旗`
- `林西` `13192` `LXC` `内蒙古自治区 赤峰市 林西县`

## Route Extraction Rule From `gj`

Use `gj` as the default source for actual traveled station order.

Algorithm:

1. sort `gj` by `detail` ascending
2. read station from `operator`
3. keep `tmism`, `czdbm`, `czdz` with the station
4. remove adjacent duplicate stations
5. save the result as the actual route path for this shipment

The route path for this sample is:

`高桥镇 -> 锦州 -> 彰武 -> 通辽 -> 哲里木 -> 大板 -> 林西`

Suggested fallback order for future route extraction:

1. if `jlzc` is present and stable enough for the route, use it as auxiliary context
2. always keep `gj` as the source of truth for actual observed station sequence
3. save `dtgjDetailVoList` as grouped station summary for operator-facing display

## `dtgjDetailVoList` Usage

`dtgjDetailVoList` is useful as a grouped station summary view:

- the origin grouped row explains the loading-side lifecycle
- the destination grouped row explains the unloading and delivery-side lifecycle
- intermediate grouped rows can be empty in `message`, but still provide station stop boundaries

For this sample:

- origin grouped row: `高桥镇`
  - demand submitted
  - accepted
  - vehicle ready
  - loading started
  - booking success
  - loading completed
  - ticket completed
  - departed origin
- destination grouped row: `林西`
  - arrived destination
  - unloading completed
  - delivery procedure handled
  - receipt confirmed
  - delivery completed
