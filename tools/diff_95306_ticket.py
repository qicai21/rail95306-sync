import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.account_store import find_account, load_accounts
from auth.ticket_store import diff_report_path_for_account, load_ticket_bundle, ticket_path_for_account_version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diff two captured 95306 ticket bundles for the same account.")
    parser.add_argument("--account", help="Account key, name, or id from runtime/95306_accounts.json.")
    parser.add_argument("--left", help="Left ticket version label, for example run1.")
    parser.add_argument("--right", help="Right ticket version label, for example run2.")
    parser.add_argument("--list-accounts", action="store_true", help="List configured accounts and exit.")
    args = parser.parse_args()
    if not args.list_accounts:
        missing = [name for name in ("account", "left", "right") if not getattr(args, name)]
        if missing:
            parser.error("the following arguments are required: %s" % ", ".join("--" + name for name in missing))
    return args


def cookie_map(cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {str(item.get("name", "")): item.get("value") for item in cookies}


def diff_mapping(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    left_keys = set(left.keys())
    right_keys = set(right.keys())
    changed = {}
    for key in sorted(left_keys & right_keys):
        if left[key] != right[key]:
            changed[key] = {"left": left[key], "right": right[key]}
    return {
        "added": {key: right[key] for key in sorted(right_keys - left_keys)},
        "removed": {key: left[key] for key in sorted(left_keys - right_keys)},
        "changed": changed,
    }


def summarize_request_headers(ticket: Dict[str, Any]) -> Dict[str, Any]:
    summary = ticket.get("auth_summary", {})
    result = {}
    for item in summary.get("important_request_headers", []):
        url = item.get("url")
        headers = item.get("headers", {})
        if url and headers:
            result[url] = headers
    return result


def build_diff_report(account: Dict[str, Any], left_version: str, right_version: str) -> Path:
    left_path = ticket_path_for_account_version(account["key"], left_version)
    right_path = ticket_path_for_account_version(account["key"], right_version)
    left = load_ticket_bundle(left_path)
    right = load_ticket_bundle(right_path)

    left_cookies = cookie_map(left.get("cookies", []))
    right_cookies = cookie_map(right.get("cookies", []))
    left_local = left.get("local_storage", {})
    right_local = right.get("local_storage", {})
    left_session = left.get("session_storage", {})
    right_session = right.get("session_storage", {})
    left_tokens = left.get("auth_summary", {}).get("identified_tokens", {})
    right_tokens = right.get("auth_summary", {}).get("identified_tokens", {})
    left_headers = summarize_request_headers(left)
    right_headers = summarize_request_headers(right)

    report = {
        "account": {
            "key": account["key"],
            "name": account["name"],
            "id": account["id"],
        },
        "left_version": left_version,
        "right_version": right_version,
        "left_file": str(left_path.resolve()),
        "right_file": str(right_path.resolve()),
        "diff": {
            "cookies": diff_mapping(left_cookies, right_cookies),
            "local_storage": diff_mapping(left_local, right_local),
            "session_storage": diff_mapping(left_session, right_session),
            "identified_tokens": diff_mapping(left_tokens, right_tokens),
            "important_request_headers": diff_mapping(left_headers, right_headers),
        },
    }

    report_path = diff_report_path_for_account(account["key"], left_version, right_version)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main() -> int:
    args = parse_args()
    if args.list_accounts:
        for account in load_accounts():
            print("%s\t%s\t%s" % (account["key"], account["name"], account["id"]))
        return 0

    account = find_account(args.account)
    report_path = build_diff_report(account, args.left, args.right)
    print("差异报告已保存: %s" % report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
