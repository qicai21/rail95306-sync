# rail95306-sync

95306 认证抓取、验证、刷新追踪与心跳保活实验仓库。

当前仓库重点不在完整业务查询，而在把 95306 的登录态从“手工登录一次”收敛成“可保存、可验证、可刷新、可多账户复用”的认证链路。

## 当前状态

已经实现的能力：

- 首次登录门票抓取
  - 使用 Playwright headed 模式打开 `https://ec.95306.cn/login`
  - 可按账户自动填写用户名和密码
  - 由人工完成滑块和短信验证
  - 登录后采集 `cookies`、`localStorage`、`sessionStorage`、关键请求/响应摘要

- 门票有效性验证
  - 使用已保存门票重新打开 `https://ec.95306.cn/platformIndex`
  - 可验证门票是否还能维持登录

- 登录态刷新追踪
  - 观察页面运行期间 `SESSION`、`accessToken`、`refreshToken`、`resetTime` 的变化
  - 对比页面操作前后的认证状态差异

- 纯接口心跳保活原型
  - 调用 `queryWhiteListStatus` 刷新 `SESSION`
  - 调用 `refreshToken` 刷新 `accessToken + refreshToken`
  - 成功时回写本地门票，失败时生成诊断报告

## 目录

- [auth](/D:/projects/rail95306-sync/auth)
  - 账户配置、门票存储、心跳保活逻辑

- [tools](/D:/projects/rail95306-sync/tools)
  - 首次抓取、门票验证、差异分析、刷新追踪、纯接口刷新脚本

- [runtime](/D:/projects/rail95306-sync/runtime)
  - 本地运行产物
  - 账户配置、门票文件、验证报告、刷新追踪报告都在这里
  - 该目录已加入 `.gitignore`

- [query95306](/D:/projects/rail95306-sync/query95306)
  - 旧版接口调用实现
  - 目前主要作为历史逻辑参考

## 核心脚本

- [tools/bootstrap_95306_ticket.py](/D:/projects/rail95306-sync/tools/bootstrap_95306_ticket.py)
  - 首次登录门票抓取器

- [tools/validate_95306_ticket.py](/D:/projects/rail95306-sync/tools/validate_95306_ticket.py)
  - 已保存门票的有效性验证器

- [tools/diff_95306_ticket.py](/D:/projects/rail95306-sync/tools/diff_95306_ticket.py)
  - 两份门票差异分析

- [tools/trace_95306_refresh.py](/D:/projects/rail95306-sync/tools/trace_95306_refresh.py)
  - 页面运行期间的刷新来源追踪

- [tools/refresh_95306_ticket.py](/D:/projects/rail95306-sync/tools/refresh_95306_ticket.py)
  - 纯接口心跳保活入口

## 快速开始

### 1. 安装依赖

目前浏览器抓取和验证依赖 Playwright：

```powershell
cd D:\projects\rail95306-sync
python -m pip install playwright
python -m playwright install chromium
```

纯接口心跳脚本使用 Python 标准库，不额外依赖 `requests`。

### 2. 查看账户

```powershell
python .\tools\bootstrap_95306_ticket.py --list-accounts
```

账户文件位置：

- [config_examples/95306_accounts.example.json](/D:/projects/rail95306-sync/config_examples/95306_accounts.example.json)

### 3. 首次登录抓票

例如抓取 `newts`：

```powershell
python .\tools\bootstrap_95306_ticket.py --account newts --version run1
```

流程：

- 脚本打开 95306 登录页
- 自动填写账号密码
- 人工完成滑块和短信验证
- 登录成功后确认保存当前门票

输出：

- `runtime/95306_ticket_<account>_<version>.json`
- `runtime/95306_storage_state_<account>_<version>.json`

### 4. 验证门票是否可复用

```powershell
python .\tools\validate_95306_ticket.py --account newts --version run1 --headed
```

### 5. 追踪页面操作时的刷新行为

```powershell
python .\tools\trace_95306_refresh.py --account newts --version run1 --headed --duration-seconds 300
```

### 6. 纯接口刷新门票

```powershell
python .\tools\refresh_95306_ticket.py --account newts --version run1
```

如果刷新成功，会回写：

- 对应的 `ticket` 文件
- 对应的 `storage_state` 文件

并生成报告：

- `runtime/95306_ticket_heartbeat_<account>_<version>.json`

## 当前已知结论

基于当前实验，95306 登录态里最值得关注的字段是：

- `SESSION`
- `95306-1.6.10-accessToken`
- `95306-outer-refreshToken`
- `95306-outer-resetTime`

目前已验证：

- `queryWhiteListStatus` 仍然可以返回新的 `SESSION`
- `refreshToken` 接口仍然可以刷新 `accessToken + refreshToken`
- `refreshToken` 是轮换型的一次性票据，旧值不能重复使用
- 页面业务操作会频繁刷新 `SESSION`
- `resetTime` 会持续递减，表现为前端倒计时/心跳信号

## 当前边界

本仓库当前还没有完成这些内容：

- 最终版多账户心跳调度器
- 完整业务查询模块重构
- openclaw / agent skill 封装
- 全量字段字典整理

## 同步

GitHub 仓库：

- [qicai21/rail95306-sync](https://github.com/qicai21/rail95306-sync)

Mac Studio 同步：

```bash
git clone https://github.com/qicai21/rail95306-sync.git
```
