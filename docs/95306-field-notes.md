# 95306 Field Notes

## Scope

This file is a working field-note document for 95306 query and tracking responses.

Purpose:

- collect field meanings in one place
- separate confirmed meanings from current guesses
- give future iterations a stable place to add evidence

Status markers used in this document:

- `confirmed`
  - directly supported by live request/response, code behavior, or existing docs
- `inferred`
  - strong current interpretation, but still worth later verification
- `unknown`
  - field exists, but meaning is not yet stable enough

## 1. Cross-Cutting Identity And Station Fields

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `ydid` | 运单号 / 当前业务主键 | confirmed | 当前 query 和 tracking 都围绕它展开 |
| `czydid` | 运单号同义字段 / 冗余字段 | inferred | 现有代码把它作为 `ydid` 缺失时的回退 |
| `fztmism` | 发站 TMIS 编码 | confirmed | shipment 查询与 tracking `fsMain` 均出现 |
| `fzhzzm` | 发站站名 | confirmed | |
| `dztmism` | 到站 TMIS 编码 | confirmed | |
| `dzhzzm` | 到站站名 | confirmed | |
| `fzyxhz` | 发站专用线/货场名称 | inferred | tracking `fsMain` 中常见 |
| `dzyxhz` | 到站专用线/货场名称 | inferred | tracking `fsMain` 中常见 |
| `tmism` | 站点 TMIS 编码 | confirmed | 见 tracking `gj[*]` |
| `dbm` | 电报码 | confirmed | 见站点查询结果 |
| `czdbm` | 车站电报码 | inferred | tracking 事件中的站点报码 |
| `hzzm` | 站名 | confirmed | 见站点查询结果 |
| `pym` | 拼音码 | confirmed | 见站点查询结果 |
| `ljdm` | 路局代码 | confirmed | 见站点查询结果 |
| `ljqc` | 路局全称 | confirmed | 见站点查询结果 |
| `ljjc` | 路局简称 | confirmed | 见站点查询结果 |
| `cwd` | 车务段或归属编码 | inferred | 站点查询结果字段，当前还未用于业务判断 |
| `dzm` | 地区/局代码 | inferred | 站点查询结果字段 |
| `hyzdmc` | 货运站点归属名称 | inferred | 站点查询结果字段 |
| `csbm` | 城市编码 | inferred | 站点查询结果字段 |

## 2. Shipment Query Fields

These fields mainly come from `queryCargoSend`.

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `ysfs` | 运输方式代码 | confirmed | 当前文档已确认 `1=整车`、`3=集装箱` |
| `hzpm` | 货种/货物品名 | confirmed | |
| `pm` | 品名代码 | inferred | 在请求里可作为过滤字段 |
| `ch` | 车号 | confirmed | |
| `hph` | 货票号 | confirmed | 用户补充确认 |
| `xh` | 箱号 | confirmed | 只有运输方式是集装箱时才会有，且通常成组出现 |
| `hwjs` | 件数 | inferred | 现有 projection 中作为 cargo_count |
| `zzl` | 重量 / 标载重量 | inferred | Phase 3A 中按标载重量理解 |
| `yf` | 运费 | inferred | |
| `zfje` | 支付金额 | inferred | 字典已有，尚未深入验证 |
| `fhdwmc` | 发货单位名称 | confirmed | |
| `shdwmc` | 收货单位名称 | confirmed | |
| `xqslh` | 需求受理号 | confirmed | 请车/运输需求提报时生成；一批 `ydid` 可对应同一个 `xqslh` |
| `yjxfh` | 运价项目号 | inferred | 当前保留，不做业务解释扩展 |
| `ifdzyd` | 是否电子运单 | inferred | 查询请求过滤字段 |
| `zffs` | 支付方式 | inferred | 查询请求过滤字段/结果字段 |
| `zfzt` | 支付状态 | inferred | 查询请求过滤字段/结果字段 |
| `ydztgj` | 运单状态轨迹过滤值 | inferred | 查询请求字段 |
| `ztgjend` | 当前状态码 | confirmed | shipment 列表中的状态码 |
| `ztgjjcend` | 当前状态中文 | confirmed | shipment 列表中的状态中文 |

## 3. Timeline Fields From Shipment Query

These are currently used as a coarse latest-update fallback.

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `slrq` | 受理时间 | inferred | parsing 中映射为 `accepted_at` |
| `zcrq` | 装车/发运日期 | inferred | 现有文档里有时写“发运日期”，tracking 中更像发车所属日期 |
| `zpsj` | 制票时间 | inferred | Phase 3A 已按制票时间理解 |
| `fcsj` | 发车时间 | confirmed | |
| `dzsj` | 到站时间 | confirmed | `queryCargoSend` 中该字段有值即表示已到站，到站时间以此为准 |
| `dzjfrq` | 交付时间 | confirmed | |
| `zcddsj` | 装车到位时间 | inferred | 仅见于优先级列表，待补证据 |
| `zckssj` | 装车开始时间 | inferred | |
| `zcwbsj` | 装车完毕时间 | inferred | |
| `zcdcsj` | 装车出场/出线时间 | inferred | 结合 tracking 文案推测 |
| `xcddsj` | 卸车到位时间 | inferred | |
| `xckssj` | 卸车开始时间 | inferred | |
| `xcwbsj` | 卸车完毕时间 | inferred | |
| `xcdcsj` | 卸车出场时间 | inferred | |

## 4. Tracking Response Structure

Tracking API response:

- top level: `msg`, `returnCode`, `data`
- `data.fsMain`
  - 主运单/车辆上下文
- `data.gjzt`
  - 节点布尔状态
- `data.gj`
  - 轨迹事件列表，当前观察为最新在前
- `data.dtgjDetailVoList`
  - 按站聚合的动态轨迹
- `data.jlzc`
  - 预计经由站/线路节点
- `data.yjddsj`
  - 预计到达时间

## 5. Tracking Core Fields

### 5.1 `data.fsMain`

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `ydid` | 运单号 | confirmed | 与 shipment `ydid` 对应 |
| `ysfs` | 运输方式代码 | confirmed | 与 shipment 保持一致 |
| `fztmism` | 发站 TMIS | confirmed | |
| `fzhzzm` | 发站站名 | confirmed | |
| `fzyx` | 发站货运相关编码 | unknown | 当前只保留原字段 |
| `fzyxhz` | 发站专用线/货场名称 | inferred | |
| `dztmism` | 到站 TMIS | confirmed | |
| `dzhzzm` | 到站站名 | confirmed | |
| `dzyx` | 到站货运相关编码 | unknown | 当前只保留原字段 |
| `dzyxhz` | 到站专用线/货场名称 | inferred | |
| `fhdwmc` | 发货单位名称 | confirmed | |
| `shdwmc` | 收货单位名称 | confirmed | |
| `hzpm` | 货物品名 | confirmed | |
| `zcrq` | 发车所属日期/发运日期 | inferred | 样例值为 `20260316` |
| `hph` | 箱号/货票标识 | inferred | 当前程序命名为 `container_no` |
| `ztgj` | tracking 主状态码 | confirmed | 样例 `40` |
| `ztgjjc` | tracking 主状态中文 | confirmed | 样例 `已发车` |
| `ch` | 车号 | confirmed | 样例 `1585686` |
| `xqslh` | 需求受理号 | inferred | 与 shipment 一致 |
| `fcsj` | 发车时间 | inferred | 在样例中为空，不代表字段无效 |
| `dzsj` | 到站时间 | confirmed | 到站判定最终以 shipment/queryCargoSend 返回值为准 |
| `dzjfrq` | 交付时间 | inferred | |

### 5.2 `data.gjzt`

This object appears to represent stage flags.

| Field | Possible Meaning | Status | Notes |
| --- | --- | --- | --- |
| `iftb` | 已填报/已提报 | inferred | 结合事件“需求信息填报”推测 |
| `ifsl` | 已受理 | inferred | |
| `ifzc` | 已装车 | inferred | |
| `ifdc` | 已带出 | confirmed | 货车车列由牵引机头机车带出当前装货道线 |
| `ifzp` | 已制票 | inferred | |
| `iffc` | 已发车 | inferred | |
| `ifzt` | 已在途某阶段 | unknown | 当前不强行解释 |
| `ifdd` | 已到达 | inferred | |
| `ifxc` | 已卸车 | inferred | |
| `ifybjfsx` | 已办交付手续 | confirmed | 用户补充确认 |
| `ifjf` | 已交付 | inferred | |

### 5.3 `data.gj[*]`

This is the most important tracking event list for current use.

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `operator` | 当前事件对应站点/节点名 | confirmed | |
| `message` | 当前事件文案 | confirmed | 最适合直接展示 |
| `detail` | 事件时间 | confirmed | |
| `czdz` | 站点地理位置描述 | inferred | 一般到区县级 |
| `tmism` | 事件站点 TMIS | confirmed | |
| `czdbm` | 事件站点电报码 | inferred | |
| `rptid` | report-id 缩写，事件类别标识 | confirmed | `LCDD=列车到达`，`LCCF=列车出发` |

### 5.4 `data.dtgjDetailVoList[*]`

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `operator` | 聚合站点名 | inferred | |
| `message` | 按站拼接后的事件串 | inferred | 当前展示价值有，但程序优先级低于 `gj` |
| `detail` | 该站最近事件时间 | inferred | |
| `czdz` | 站点位置 | inferred | |
| `yjddsj` | 该节点的预计到达时间 | inferred | 常为空 |

### 5.5 `data.jlzc[*]`

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `operator` | 线路节点/车站名 | inferred | 线路途经点 |
| `message` | 节点附加说明 | unknown | 当前样例为空 |
| `detail` | 节点时间 | unknown | 当前样例为空 |
| `czdz` | 节点地理位置 | inferred | |
| `yjddsj` | 该节点预计到达时间 | inferred | 终点节点上更有值 |

## 6. Tracking Timing Fields

| Field | Meaning | Status | Notes |
| --- | --- | --- | --- |
| `yjddsj` | 预计到达时间 | confirmed | 样例 `2026年03月18日 07时` |
| `yjddsj1` | 备用/补充预计到达时间 | unknown | 当前样例为空 |
| `yjddlc` | 剩余里程 | inferred | 样例 `1303`，推测公里 |
| `useHour` | 已用时/耗时小时数 | unknown | 当前样例为 `0`，还不稳定 |

## 7. Current Program-Side Usage

These are the fields currently most suitable for direct use without over-modeling.

### 7.1 Latest tracking status

Latest train/shipment status should be represented by the current normalized `latest_status` object.

Business interpretation confirmed by the user:

- `status_name = 已发车` means the car/shipment is already `在途`

- `data.fsMain.ztgj`
- `data.fsMain.ztgjjc`
- `data.gj[0].detail`
- `data.gj[0].message`
- `data.gj[0].operator`
- `data.gj[0].tmism`
- `data.gj[0].czdbm`
- `data.gj[0].czdz`
- `data.gj[0].rptid`

### 7.2 Shipment context

- `data.fsMain.ydid`
- `data.fsMain.ch`
- `data.fsMain.hph`
- `data.fsMain.hzpm`
- `data.fsMain.fzhzzm`
- `data.fsMain.dzhzzm`
- `data.fsMain.fzyxhz`
- `data.fsMain.dzyxhz`
- `data.fsMain.fhdwmc`
- `data.fsMain.shdwmc`

### 7.3 Keep-as-raw for now

- `data.gjzt`
- `data.dtgjDetailVoList`
- `data.jlzc`
- `data.yjddsj1`
- `data.useHour`
- `fsMain` 里未确认含义的各类编码字段

## 8. Open Questions

These are good candidates for your next补充:

1. `hph` 到底更适合解释为货票号、箱号，还是场景相关字段。
2. `zcrq` 在 shipment 和 tracking 中是否统一应解释为发运日期，还是装车日期。
3. `gjzt` 各布尔字段的精确定义，尤其是 `iftb`、`ifdc`、`ifzt`、`ifybjfsx`。
4. `jlzc` 是否是“全线路预计节点表”，以及节点时间为空时的业务规则。
5. `fzyx`、`dzyx` 这类编码字段的准确业务名。

## 9. User-Confirmed Future Use Rules

These are downstream usage rules confirmed by the user, but not yet implemented in the current phase.

1. Tracking capture should only start after the shipment/car status reaches `已制单`.
2. Tracking data should later be processed into two outputs:
   - a dedicated vehicle tracking table
   - latest tracking summary written back to the main shipment/car table
3. Dedicated vehicle tracking table should focus on:
   - 发站
   - 到站
   - 货物
   - 发车时间
   - 在途各站到达时间
   - 在途各站发出时间
   - 最终到站时间
4. Main shipment/car table should later store a current readable status summary, for example:
   - `在途（最近报告的车站情况：2026-3-15 17:30 到达通辽西站）`
5. A new grouping field is needed later to mark multiple cars as one train group for query/display use.
6. Train group id format is confirmed as:
   - `收货人拼音简称 + "_" + yymm + "_" + 当月该流向第几列(三位数)`
   - example:
     - `YTTY_2603_004`
   - sample meaning:
     - `云铜铜业`
     - `2026-03`
     - `当月该流向第 4 列`
7. Train groups may split during transit. Example:
   - initial group: `53` cars from 高桥镇
   - later split at 锦州 into `30` cars and `23` cars
   - split handling still needs a concrete suffix rule in a later phase
8. Other tracking data outside the above use cases is currently not needed.

## 10. Main Table Current Status Summary Rules

The main shipment/car table should later generate one readable current-status summary from tracking data.

Confirmed rules:

1. Only start tracking capture after the shipment status reaches `已制单`.
2. Use normalized `latest_status` as the direct source of the summary sentence.
3. Status wording rules:
   - arrival event => `到达`
   - departure event => `在途`
   - delivered event => `已交付`
4. `status_name = 已发车` should be treated as `在途`.
5. Recommended summary pattern:
   - `在途（最近报告：2026-03-16 07:31 到达锦州站）`
   - actual wording can later be normalized from `latest_event_time + latest_event_message`

## 11. Minimum Vehicle Tracking Table Fields

Confirmed minimum field set for the later dedicated vehicle tracking table:

- 发站
- 到站
- 货物
- 发车时间
- 各站到达时间
- 各站发出时间
- 最终到站时间
- 列号

## 12. Value Assessment For `gjzt` And `rptid`

Current recommendation:

- `gjzt`
  - low immediate value
  - keep raw for debugging/reference
  - do not prioritize in downstream modeling unless a specific flag proves necessary
- `rptid`
  - medium value
  - worth retaining because it may help distinguish arrival/departure event kinds when event text is inconsistent
  - still not part of the minimum business summary unless later evidence proves it stable and useful

## 13. Revised Tracking Capture Rules

These revised rules supersede the earlier broad tracking-retention idea:

1. only start tracking capture after shipment status reaches `已制单`
2. stop active tracking capture after destination arrival
3. before destination arrival, tracking is mainly used to update the latest shipment status
4. only retain completed destination-arrived tracking data in the database for later route analysis and comparison

## 14. Revised Persisted Tracking Shape

Confirmed preferred target shape:

- one shipment per row
- one route array stored as JSON-like structure

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

Each route item should contain:

- `station_name`
- `arrived_at`
- `departed_at`

Important rule:

- keep route stations even when `arrived_at = null` and `departed_at = null`
- reason: some passing stations are not stop points, but the route path itself is still valuable for later analysis
