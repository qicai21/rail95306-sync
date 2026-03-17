# Rail Freight Process

## Purpose

This document records the current business-level baseline for railway freight shipment flow.

It is intended for:

- AI or agent business analysis
- domain modeling
- field interpretation
- future workflow design

It is not an operator command guide and is intentionally kept separate from implementation and runtime documents.

## Main Flow

Current baseline main flow:

`需求提报 -> 需求受理 -> 车辆到位 -> 开始装车 -> 需求订车成功 -> 装车完成 -> 制单完成 -> 发站发出 -> 车辆在途[发站 -> 中间站... -> 到站] -> 到达目的站 -> 卸车完成 -> 办理交付 -> 确认收货 -> 交付完成`

For the sampled shipment `高桥镇 -> 林西`, the observed flow is:

`需求提报 -> 需求受理 -> 车辆到位 -> 开始装车 -> 需求订车成功 -> 装车完成 -> 制单完成 -> 发站发出 -> 车辆在途[高桥镇 -> 锦州 -> 彰武 -> 通辽 -> 哲里木 -> 大板 -> 林西] -> 到达目的站 -> 卸车完成 -> 办理交付 -> 确认收货 -> 交付完成`

## Node Definitions

### 1. 需求提报

Business meaning:

- shipper submits the transport demand
- this is the start of the business chain

Typical tracking text:

- `【...】提出需求。`

### 2. 需求受理

Business meaning:

- system or railway side accepts the demand
- the demand enters executable status

Typical tracking text:

- `需求受理通过。`

Typical field:

- `slrq`

### 3. 车辆到位

Business meaning:

- vehicle is positioned and ready for loading at the origin side

Typical tracking text:

- `您的车辆已到位，车号为...。`

Typical field:

- `zcddsj`

### 4. 开始装车

Business meaning:

- loading operation starts

Typical tracking text:

- `货物已开始装车。`

Typical field:

- `zckssj`

### 5. 需求订车成功

Business meaning:

- car booking or dispatch arrangement is confirmed

Typical tracking text:

- `需求订车成功。`

### 6. 装车完成

Business meaning:

- origin loading operation is completed

Typical tracking text:

- `货物已完成装车。`

Typical field:

- `zcwbsj`

### 7. 制单完成

Business meaning:

- shipment document or waybill preparation is completed

Typical tracking text:

- `您的货物已完成制单。`

Typical field:

- `zpsj`

### 8. 发站发出

Business meaning:

- shipment leaves the origin station and enters line-haul transport

Typical tracking text:

- `货物离开...站。`

Typical field:

- `fcsj`

### 9. 车辆在途

Business meaning:

- shipment is moving across intermediate stations on the route
- actual traveled station sequence should be derived from tracking events

Suggested representation:

- `车辆在途[站点1 -> 站点2 -> ... -> 站点N]`

Primary data source:

- `gj`

Auxiliary grouped source:

- `dtgjDetailVoList`

### 10. 到达目的站

Business meaning:

- shipment arrives at the destination station

Typical tracking text:

- `货物到达...站。`

Typical field:

- `dzsj`

### 11. 卸车完成

Business meaning:

- unloading at the destination side is completed

Typical tracking text:

- `货物已卸车完毕。`

Typical field:

- `xcwbsj`

### 12. 办理交付

Business meaning:

- delivery procedures are handled on the destination side before final close-out

Typical tracking text:

- `已办交付手续。`

### 13. 确认收货

Business meaning:

- consignee side confirms receipt

Typical tracking text:

- `确认收货，实际领货人为...。`

Typical status:

- `确认收货`

### 14. 交付完成

Business meaning:

- the shipment is fully delivered and the business flow closes

Typical tracking text:

- `货物已交付完毕。`

Typical field:

- `dzjfrq`

## Field Mapping Baseline

Current field interpretation baseline confirmed by sample comparison:

- `ydid`
  - unique shipment id
- `xqslh`
  - demand or request batch id, not the unique shipment id
- `slrq`
  - demand accepted time
- `zcddsj`
  - vehicle ready / loading-side inbound time
- `zckssj`
  - loading started
- `zcwbsj`
  - loading completed
- `zpsj`
  - ticket or waybill document completed
- `fcsj`
  - departed origin station
- `dzsj`
  - arrived destination station
- `xcwbsj`
  - unloading completed
- `dzjfrq`
  - final delivery completed

Fields that still need more cross-sample confirmation:

- `xcdcsj`
- `xcddsj`
- `xckssj`
- `zcdcsj`

## Route Extraction Baseline

For future AI or agent analysis, the recommended route extraction method is:

1. read `gj`
2. sort by event time ascending
3. extract station from `operator`
4. keep station metadata from:
   - `tmism`
   - `czdbm`
   - `czdz`
5. remove adjacent duplicate stations
6. build the route string:
   - `车辆在途[站点1 -> 站点2 -> ...]`

## Station Dictionary Baseline

Tracking events can directly expand the station dictionary.

Useful source fields from `gj`:

- `operator`: station name
- `tmism`: station TMIS code
- `czdbm`: station telegraph code
- `czdz`: station address

This means the station dictionary does not have to rely only on separate online station lookup APIs.

## Sample Reference

Current baseline sample:

- route: `高桥镇 -> 林西`
- shipment id: `202602TY3158540038`
- route path observed from tracking:
  - `高桥镇 -> 锦州 -> 彰武 -> 通辽 -> 哲里木 -> 大板 -> 林西`

Related sample analysis:

- [95306-gj-sample-analysis.md](/D:/projects/rail95306-sync/docs/95306-gj-sample-analysis.md)
