# OPERATION

## 使用前确认
按下面的顺序操作，不要把真实账号、密码、票据文件提交到 Git。

本地敏感文件只放在 `runtime/` 下：
- `runtime/95306_accounts.json`
- `runtime/95306_ticket_<account>.json`
- `runtime/95306_storage_state_<account>.json`

## 1. 第一次本地配置 accounts
1. 进入仓库根目录。
2. 创建 `runtime` 目录。
3. 复制示例文件为本地真实配置文件。

macOS:
```bash
mkdir -p runtime
cp config_examples/95306_accounts.example.json runtime/95306_accounts.json
```

Windows:
```powershell
New-Item -ItemType Directory -Force runtime
Copy-Item config_examples\95306_accounts.example.json runtime\95306_accounts.json
```

4. 编辑 `runtime/95306_accounts.json`。
5. 只填写你自己的真实账户信息，不要填写到仓库里的 example 文件。
6. 每个账户保留这些字段：
   - `key`
   - `name`
   - `id`
   - `pwd`
7. 通过本地文件或 Telegram 单独下发真实 `accounts.json`，不要通过 Git 同步。

## 2. 初始化某个账户票据
1. 确认 `runtime/95306_accounts.json` 已存在。
2. 执行初始化命令。
3. 等待 Playwright 打开有头浏览器。
4. 让程序自动填入账号名和密码。
5. 手动完成滑块、短信验证码和登录确认。
6. 等待脚本自动保存票据文件。

macOS:
```bash
python3 ./tools/bootstrap_95306_ticket.py --account newts
```

Windows:
```powershell
python .\tools\bootstrap_95306_ticket.py --account newts
```

执行成功后，检查是否生成：
- `runtime/95306_ticket_newts.json`
- `runtime/95306_storage_state_newts.json`

把 `newts` 替换成你自己的账户 `key`。

## 3. 检查票据状态
1. 执行状态检查命令。
2. 查看哪些账户已经初始化。
3. 查看哪些账户缺少票据或 storage state。
4. 在启动 worker 之前先看这一步结果。

macOS:
```bash
python3 ./tools/preflight_95306_worker.py --status
```

Windows:
```powershell
python .\tools\preflight_95306_worker.py --status
```

如果你要做严格检查，执行：

macOS:
```bash
python3 ./tools/preflight_95306_worker.py --strict
```

Windows:
```powershell
python .\tools\preflight_95306_worker.py --strict
```

## 4. 启动 worker
1. 先确认 preflight 已通过。
2. 执行 worker 启动命令。
3. 默认模式下，只运行已经完成初始化的账户。
4. 如果你要求全部账户都齐全，再使用 `--strict`。

macOS:
```bash
python3 ./tools/run_95306_keepalive.py
```

macOS 严格模式:
```bash
python3 ./tools/run_95306_keepalive.py --strict
```

Windows:
```powershell
python .\tools\run_95306_keepalive.py
```

如果你要用后台管理命令，执行：

macOS:
```bash
python3 ./tools/manage_95306_keepalive.py start
python3 ./tools/manage_95306_keepalive.py status
python3 ./tools/manage_95306_keepalive.py stop
python3 ./tools/manage_95306_keepalive.py update-restart
```

## 5. 某个账户票据失效后的更新步骤
1. 先检查当前票据状态。
2. 确认是哪一个账户失效。
3. 优先尝试重新初始化该账户票据。
4. 初始化完成后重新执行 preflight。
5. 再重新启动 worker。

先检查状态：

macOS:
```bash
python3 ./tools/preflight_95306_worker.py --status
```

重新初始化某个账户：

macOS:
```bash
python3 ./tools/bootstrap_95306_ticket.py --account newts
```

如果票据仍然可用，只是需要刷新一次，执行：

macOS:
```bash
python3 ./tools/refresh_95306_ticket.py --account newts
```

重新检查：

macOS:
```bash
python3 ./tools/preflight_95306_worker.py
```

重新启动：

macOS:
```bash
python3 ./tools/run_95306_keepalive.py
```

## 6. 常见报错及处理方式
### 报错：`Account file not found`
按下面处理：
1. 检查 `runtime/95306_accounts.json` 是否存在。
2. 如果不存在，重新放置本地真实 accounts 文件。
3. 不要把真实 accounts 提交到 Git。
4. 如果是 OpenClaw 部署机缺文件，就把 `accounts.json` 通过 Telegram 单独发过去。

### 报错：某个账户 `Missing ticket file`
按下面处理：
1. 说明这个账户还没有完成初始化。
2. 执行该账户的初始化命令：
```bash
python3 ./tools/bootstrap_95306_ticket.py --account <account_key>
```
3. 初始化完成后重新执行：
```bash
python3 ./tools/preflight_95306_worker.py --status
```

### 报错：`Missing storage state file`
按下面处理：
1. 说明票据文件和 storage state 不完整。
2. 直接重新初始化该账户票据，不要手工补文件。
3. 执行：
```bash
python3 ./tools/bootstrap_95306_ticket.py --account <account_key>
```

### 报错：strict 模式下 preflight 失败
按下面处理：
1. 先看 preflight 输出里是哪一个账户未就绪。
2. 如果你允许部分账户运行，不要加 `--strict`。
3. 如果你要求全部账户都运行，就先把缺失账户全部初始化完，再启动 worker。

### 报错：登录后仍未生成标准票据文件
按下面处理：
1. 检查登录是否真的进入了已登录页面。
2. 重新执行初始化命令。
3. 手动完成滑块和短信验证，不要提前关闭浏览器。
4. 确认最终生成的是标准文件名，而不是临时文件名。

## 7. 维护基线
当前稳定维护标签：
- `v0.1-keepalive-stable`

把这份文档当作你本人在 Mac Studio / OpenClaw 上的实际操作手册使用。
