import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.account_store import find_account, load_accounts
from auth.heartbeat_95306 import HeartbeatRefreshError, refresh_ticket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh 95306 SESSION/accessToken/refreshToken using direct API calls.")
    parser.add_argument("--account", help="Account key, name, or id from runtime/95306_accounts.json.")
    parser.add_argument("--version", help="Optional versioned ticket label to refresh in place.")
    parser.add_argument("--list-accounts", action="store_true", help="List configured accounts and exit.")
    args = parser.parse_args()
    if not args.list_accounts and not args.account:
        parser.error("the following arguments are required: --account")
    return args


def main() -> int:
    args = parse_args()
    if args.list_accounts:
        for account in load_accounts():
            print("%s\t%s\t%s" % (account["key"], account["name"], account["id"]))
        return 0

    account = find_account(args.account)
    try:
        result = refresh_ticket(account["key"], version=args.version)
    except HeartbeatRefreshError as exc:
        print("账号 [%s] 的门票刷新失败: %s" % (account["name"], exc))
        print("失败报告已保存: %s" % exc.report_path)
        return 1
    print("账号 [%s] 的门票已刷新: %s" % (account["name"], result["ticket_path"]))
    print("账号 [%s] 的 storage_state 已同步: %s" % (account["name"], result["storage_state_path"]))
    print("刷新报告已保存: %s" % result["report_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
