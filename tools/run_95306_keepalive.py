import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.account_store import find_account
from auth.keepalive_95306 import DEFAULT_HEARTBEAT_SECONDS, run_keepalive_loop
from auth.preflight_95306 import build_preflight_report, format_preflight_summary, write_preflight_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the 95306 keepalive worker after a startup preflight check.")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode. Default is headless for servers.")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="Max wait time for each account check.")
    parser.add_argument("--heartbeat-seconds", type=int, default=DEFAULT_HEARTBEAT_SECONDS, help="Heartbeat interval. Default is 600 seconds.")
    parser.add_argument("--strict", action="store_true", help="Fail startup if any configured account is not fully initialized.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_preflight_report(strict=args.strict)
    report_path = write_preflight_report(report)
    print(format_preflight_summary(report))
    print("preflight report: %s" % report_path)
    if report["status"] != "ok":
        return 1

    accounts = [find_account(account_info["key"]) for account_info in report["runnable_accounts"]]
    print("Starting keepalive loop for: %s" % ", ".join(account["key"] for account in accounts))
    print("Heartbeat interval: %s seconds" % args.heartbeat_seconds)
    return run_keepalive_loop(
        accounts=accounts,
        browser_name=args.browser,
        headed=args.headed,
        heartbeat_seconds=args.heartbeat_seconds,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
