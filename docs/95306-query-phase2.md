# 95306 货物发运动态查询 Phase 2

## 目标

本阶段只做独立的 `95306` 货物发运动态查询能力，不改动已经稳定的登录 keepalive、账户配置、本地票据保存和初始化流程。

## 旧项目查询资源位置

- 旧查询主实现：`browser.py`
- 旧请求构造和字典：`header_configs.py`
- 旧测试样例和字段样本：`browser_tests.py`、`functional_tests.py`
- 历史真实页面追踪：`runtime/95306_refresh_trace_newts_vpn_clean_1.json`
- 当前登录态与票据：`runtime/95306_ticket_newts.json`、`runtime/95306_storage_state_newts.json`

## 旧逻辑梳理结果

### 旧 API

- `POST http://ec.95306.cn/api/scjh/wayBillQuery/queryCargoSend`
  - 发送查询主接口
- `POST http://ec.95306.cn/api/scjh/wayBillQuery/queryCargoArrival`
  - 到达查询主接口
- `POST https://ec.95306.cn/api/scjh/track/qeryYdgjNew`
  - 运单追踪接口
- `POST https://ec.95306.cn/api/yhzx/user/queryWhiteListStatus`
  - 登录态白名单刷新
- `POST https://ec.95306.cn/api/zuul/refreshToken`
  - 访问令牌刷新

### 旧核心参数

发送查询旧 payload 的关键字段在 `header_configs.py` 里是：

- `zcqsrq` / `zcjzrq`
  - 装车日期范围
- `fztmism` / `dztmism`
  - 发站 / 到站 TMIS 编码
- `pm`
  - 品名或旧业务代码，旧发送逻辑固定为 `1160001`
- `ydid`
  - 运单标识
- `pageSize` / `pageNum`
  - 分页

旧代码内置的站点映射：

- `新台子 -> 53918`
- `得胜台 -> 53924`
- `虎石台 -> 53900`
- `all -> ""`

### 旧响应字段

旧测试样本和真实返回都表明 `queryCargoSend` 的核心字段长期稳定，包含：

- `ydid`
- `fzhzzm` / `dzhzzm`
- `fztmism` / `dztmism`
- `fcsj`
- `ztgjend` / `ztgjjcend`
- `ch`
- `hph`
- `zcdcsj` / `dzsj` / `dzjfrq`

追踪接口 `qeryYdgjNew` 的核心结构：

- `data.fsMain`
  - 运单主信息
- `data.gjzt`
  - 阶段布尔状态
- `data.gj`
  - 追踪事件列表，通常倒序，首条即最新事件

### 旧调用顺序

旧项目的查询链路是：

1. 依赖已登录状态，带 `SESSION + 95306-1.6.10-accessToken`
2. 组装发送或到达查询 payload
3. 调 `queryCargoSend` / `queryCargoArrival`
4. 取结果中的 `ydid`
5. 将 `ydid` 连续做 6 次 Base64 编码
6. 调 `qeryYdgjNew` 获取追踪详情

### 可直接复用的部分

- `queryCargoSend` 仍是发送数据主接口
- `qeryYdgjNew` 仍是追踪主接口
- `ydid` 六次 Base64 编码规则仍然有效
- `ztgjend` / `ztgjjcend` 等核心响应字段仍可复用
- 旧站点 TMIS 编码映射仍可用

### 需要重点核验的部分

- 页面初始化是否增加了配套接口
- 默认查询 payload 是否新增字段
- 默认分页大小是否变化
- 状态字典是否仍以旧编码为主

## 本次真实核验

核验日期：`2026-03-15`

核验方式：

1. 复用现有 `newts` 票据和 `storage_state`
2. 用 Playwright 打开 `https://ec.95306.cn/loading/goodsQuery`
3. 点击页面“查询”
4. 记录真实 XHR 请求和响应
5. 再进入 `https://ec.95306.cn/ydTrickDu?prams=...`
6. 记录追踪请求和响应
7. 再用独立 HTTP 调用回放旧 payload，验证兼容性

### 当前页面新增或更显式依赖的接口

- `POST https://ec.95306.cn/api/zd/vizm/queryZms`
  - 车站联想查询，返回站名、TMIS、路局信息
- `POST https://ec.95306.cn/api/scjh/wayBillQuery/initCargoSend`
  - 页面初始化，返回状态字典、日期范围等
- `POST https://ec.95306.cn/api/scjh/wayBillQuery/queryCountsForMysend`
  - 汇总统计
- `POST https://ec.95306.cn/api/scjh/wayBillQuery/queryCargoSend`
  - 明细列表

### 当前页面默认发送 payload

当前页面在 `goodsQuery` 上点“查询”后，发送的是：

```json
{
  "zcqsrq": "2026-03-12",
  "zcjzrq": "2026-03-15",
  "fj": "",
  "dj": "",
  "pageSize": 50,
  "pageNum": 1,
  "ifhnjghw": "",
  "fxbj": ""
}
```

省略了空字符串字段之外，和旧版相比最明显的新点是：

- 增加 `fj`
- 增加 `dj`
- 增加 `ifhnjghw`
- 增加 `fxbj`
- 默认 `pageSize` 变为 `50`

### 当前追踪 payload

`qeryYdgjNew` 仍然是：

```json
{
  "ydid": "<运单号做 6 次 Base64 后的字符串>"
}
```

## 新旧对比结论

### 仍可用

- 旧 `queryCargoSend`
- 旧 `qeryYdgjNew`
- 旧 `fztmism` / `dztmism` 过滤思路
- 旧 `pm=1160001` 的发送查询思路
- 旧站点 TMIS 映射
- 旧 `ydid -> 6 次 Base64 -> 追踪` 逻辑

### 已变化

- 页面先通过 `queryZms` 解析站名输入，再把选中的 `tmism` 回填给 `fztmism` / `dztmism`
- 页面流程新增 `initCargoSend`
- 页面流程新增 `queryCountsForMysend`
- 页面默认请求体新增 `fj`、`dj`、`ifhnjghw`、`fxbj`
- 页面默认分页从旧代码的 `100` 变为 `50`
- 业务查询响应可能返回新的 `SESSION` Cookie，说明查询本身也会续命会话

### 兼容性结论

- 直接回放旧 payload 仍返回 `200 OK`
- 旧 `fztmism=51632`、`dztmism=53918`、`pm=1160001` 仍可正确过滤
- 旧追踪编码规则无变化
- 因此本阶段保留旧查询思路，只把新增页面初始化接口和差异记录到文档中，不强行改写主查询链路

## 本次实现

新增独立模块：

- `query95306/shipment_query.py`
  - 封装车站查询、发送查询、分页抓全和追踪查询
- `tools/query_95306_station.py`
  - 独立车站查询工具
- `tools/query_95306_shipment.py`
  - 支持先查站再查发运数据的最小可运行 PoC 命令行
- `docs/95306-query-dictionaries.json`
  - 已确认状态码、站点、字段解释和会话备注

实现原则：

- 不复写 keepalive
- 不改账户配置
- 不改票据保存
- 不改初始化流程
- 查询逻辑和 keepalive 逻辑分离
- 优先沿用旧 payload 和旧查询顺序

## 最小查询 PoC

示例命令：

```powershell
python .\tools\query_95306_station.py --account newts --keyword gqz --exact-name 高桥镇
python .\tools\query_95306_shipment.py --account newts --start-date 2026-01-11 --end-date 2026-02-01 --origin-keyword gqz --origin-name 高桥镇 --destination-keyword xtz --destination-name 新台子
```

输出 JSON 至少包含：

- `query_input`
- `shipment_id`
- `origin`
- `destination`
- `shipment_status`
- `last_update_time`
- `raw_response`
- `mapping_notes`

默认行为：

- 若提供站名或检索词，先调用 `queryZms` 解析车站 `tmism`
- 默认自动按 `pages` 翻页，抓完整个结果集
- 若有结果，则对首条记录追加一次 `qeryYdgjNew` 查询
- 默认只输出前 `10` 条归一化结果，完整总数在 `raw_response.total` 中体现

## Keepalive 备注

- `queryCargoSend`
  - 业务查询成功响应可能带 `Set-Cookie: SESSION=...`
- 这说明业务查询本身也是 `SESSION` 更新来源
- 后续整合 keepalive 时，除了纯心跳接口外，还要允许查询模块回写最新 `SESSION`

## 后续扩展建议

- 批量查询
  - 在独立模块外层循环多个查询条件，不改底层 client
- 多账户查询
  - 直接按账号切换票据文件实例化多个 `ShipmentQueryClient`
- 定时拉取
  - 将当前 PoC 封装为 worker 任务，但仍与 keepalive 解耦
- 字典补全
  - 可以继续从 `initCargoSend`、页面脚本和历史 trace 补充更完整的状态字典、局站字典和字段解释
