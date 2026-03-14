import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import BrowserContext, Page, Request, Response, TimeoutError, sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.account_store import find_account, load_accounts
from auth.ticket_store import (
    iso_now,
    load_ticket_bundle,
    storage_state_path_for_account_version,
    ticket_path_for_account_version,
    validation_report_path_for_account,
)


PLATFORM_URL = "https://ec.95306.cn/platformIndex"
LOGIN_URL = "https://ec.95306.cn/login"
SUCCESS_HINTS = ("/platformindex",)
LOGIN_HINTS = ("/login",)
API_HINTS = ("api/", "basePermission", "queryUnReadCount", "queryCwdOrCz")
MAX_EVENTS = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate whether a saved 95306 ticket can still open platformIndex.")
    parser.add_argument("--account", help="Account key, name, or id from runtime/95306_accounts.json.")
    parser.add_argument("--version", help="Optional ticket version label, for example run1 or vpn_clean_1.")
    parser.add_argument("--list-accounts", action="store_true", help="List configured accounts and exit.")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode.")
    parser.add_argument("--timeout-seconds", type=int, default=25, help="Max wait time for the validation page flow.")
    parser.add_argument("--hold-seconds", type=int, default=0, help="Keep the browser open for N seconds after validation.")
    args = parser.parse_args()
    if not args.list_accounts and not args.account:
        parser.error("the following arguments are required: --account")
    return args


def trimmed_append(items: List[Dict[str, Any]], item: Dict[str, Any]) -> None:
    items.append(item)
    if len(items) > MAX_EVENTS:
        del items[0 : len(items) - MAX_EVENTS]


def summarize_request(request: Request) -> Dict[str, Any]:
    headers = request.headers
    lowered_url = request.url.lower()
    auth_related = any(hint.lower() in lowered_url for hint in API_HINTS) or "access_token" in headers or "cookie" in headers
    return {
        "timestamp": iso_now(),
        "url": request.url,
        "method": request.method,
        "resource_type": request.resource_type,
        "headers": headers,
        "auth_related": auth_related,
    }


def summarize_response(response: Response) -> Dict[str, Any]:
    request = response.request
    headers = response.headers
    lowered_url = response.url.lower()
    auth_related = any(hint.lower() in lowered_url for hint in API_HINTS) or "set-cookie" in headers
    return {
        "timestamp": iso_now(),
        "url": response.url,
        "method": request.method,
        "status": response.status,
        "resource_type": request.resource_type,
        "request_headers": request.headers,
        "response_headers": headers,
        "auth_related": auth_related,
    }


def attach_network_listeners(context: BrowserContext, requests_log: List[Dict[str, Any]], responses_log: List[Dict[str, Any]]) -> None:
    context.on("request", lambda request: trimmed_append(requests_log, summarize_request(request)) if request.url.startswith("http") else None)
    context.on("response", lambda response: trimmed_append(responses_log, summarize_response(response)) if response.url.startswith("http") else None)


def read_storage(page: Page) -> Dict[str, Dict[str, str]]:
    return page.evaluate(
        """() => {
            const read = (store) => {
                const result = {};
                for (let i = 0; i < store.length; i += 1) {
                    const key = store.key(i);
                    result[key] = store.getItem(key);
                }
                return result;
            };
            return {
                localStorage: read(window.localStorage),
                sessionStorage: read(window.sessionStorage),
            };
        }"""
    )


def capture_snapshot(context: BrowserContext, page: Page) -> Dict[str, Any]:
    storage = read_storage(page)
    return {
        "captured_at": iso_now(),
        "current_url": page.url,
        "title": page.title(),
        "cookies": context.cookies(),
        "local_storage": storage["localStorage"],
        "session_storage": storage["sessionStorage"],
    }


def inject_session_storage(context: BrowserContext, session_storage: Dict[str, str], target_origin: str) -> None:
    payload = json.dumps(session_storage, ensure_ascii=False)
    origin = json.dumps(target_origin, ensure_ascii=False)
    context.add_init_script(
        """
        (() => {
            const sessionStorageData = %s;
            const expectedOrigin = %s;
            if (window.location.origin !== expectedOrigin) {
                return;
            }
            Object.keys(sessionStorageData || {}).forEach((key) => {
                window.sessionStorage.setItem(key, sessionStorageData[key]);
            });
        })();
        """
        % (payload, origin)
    )


def detect_validation_signals(snapshot: Dict[str, Any], requests_log: List[Dict[str, Any]], responses_log: List[Dict[str, Any]], url_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    current_url = snapshot["current_url"]
    lowered_url = current_url.lower()
    request_urls = [item["url"].lower() for item in requests_log]
    response_urls = [item["url"].lower() for item in responses_log]
    session_cookie_present = any(cookie.get("name") == "SESSION" for cookie in snapshot["cookies"])
    storage_has_refresh = any("refresh" in key.lower() for key in snapshot["session_storage"].keys())
    storage_has_user = any("user" in key.lower() for key in snapshot["local_storage"].keys())
    landed_on_platform = any(hint in lowered_url for hint in SUCCESS_HINTS)
    redirected_to_login = any(hint in lowered_url for hint in LOGIN_HINTS)
    touched_platform = any("/platformindex" in item["url"].lower() for item in url_changes)
    business_api_success = any(
        item["auth_related"] and str(item.get("status", "")) == "200"
        for item in responses_log
    )
    auth_request_count = len([item for item in requests_log if item["auth_related"]])

    score = sum(
        [
            1 if landed_on_platform else 0,
            1 if touched_platform else 0,
            1 if business_api_success else 0,
            1 if session_cookie_present else 0,
            1 if storage_has_refresh else 0,
            1 if storage_has_user else 0,
            1 if auth_request_count >= 2 else 0,
            -2 if redirected_to_login else 0,
        ]
    )

    return {
        "score": score,
        "landed_on_platform": landed_on_platform,
        "redirected_to_login": redirected_to_login,
        "touched_platform": touched_platform,
        "business_api_success": business_api_success,
        "session_cookie_present": session_cookie_present,
        "storage_has_refresh": storage_has_refresh,
        "storage_has_user": storage_has_user,
        "auth_request_count": auth_request_count,
        "request_urls": request_urls[-10:],
        "response_urls": response_urls[-10:],
    }


def is_ticket_valid(signals: Dict[str, Any]) -> bool:
    return (
        signals["landed_on_platform"]
        and not signals["redirected_to_login"]
        and signals["session_cookie_present"]
        and (signals["business_api_success"] or signals["auth_request_count"] >= 2)
    )


def validate_ticket(account: Dict[str, Any], browser_name: str, headed: bool, timeout_seconds: int, hold_seconds: int, version: Optional[str] = None) -> Tuple[Path, Dict[str, Any]]:
    if version:
        ticket_path = ticket_path_for_account_version(account["key"], version)
        storage_state_file = storage_state_path_for_account_version(account["key"], version)
    else:
        ticket_path = ROOT_DIR / "runtime" / ("95306_ticket_%s.json" % account["key"])
        storage_state_file = None

    ticket_data = load_ticket_bundle(ticket_path)
    if storage_state_file is None:
        storage_state_file = Path(ticket_data["storage_state_file"])
    if not storage_state_file.exists():
        raise FileNotFoundError("Storage state file not found: %s" % storage_state_file)

    requests_log: List[Dict[str, Any]] = []
    responses_log: List[Dict[str, Any]] = []
    url_changes: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = getattr(p, browser_name).launch(headless=not headed)
        context = browser.new_context(storage_state=str(storage_state_file))
        inject_session_storage(context, ticket_data.get("session_storage", {}), "https://ec.95306.cn")
        attach_network_listeners(context, requests_log, responses_log)
        page = context.new_page()
        page.on(
            "framenavigated",
            lambda frame: trimmed_append(url_changes, {"timestamp": iso_now(), "url": frame.url, "event": "navigated"}) if frame == page.main_frame else None,
        )

        page.goto(PLATFORM_URL, wait_until="domcontentloaded")
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                page.wait_for_load_state("networkidle", timeout=2000)
            except TimeoutError:
                pass
            if page.url.lower().startswith(LOGIN_URL):
                break
            if page.url.lower().startswith(PLATFORM_URL.lower()) and len(responses_log) >= 3:
                break

        snapshot = capture_snapshot(context, page)
        signals = detect_validation_signals(snapshot, requests_log, responses_log, url_changes)
        result = {
            "validated_at": iso_now(),
            "account": {
                "key": account["key"],
                "name": account["name"],
                "id": account["id"],
            },
            "platform_url": PLATFORM_URL,
            "source_ticket_file": str(ticket_path.resolve()),
            "source_storage_state_file": str(storage_state_file.resolve()),
            "current_url": snapshot["current_url"],
            "title": snapshot["title"],
            "cookies": snapshot["cookies"],
            "local_storage": snapshot["local_storage"],
            "session_storage": snapshot["session_storage"],
            "signals": signals,
            "is_valid": is_ticket_valid(signals),
            "observed_requests": requests_log,
            "observed_responses": responses_log,
            "url_changes": url_changes,
        }
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        browser.close()

    report_path = validation_report_path_for_account(account["key"])
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path, result


def main() -> int:
    args = parse_args()
    if args.list_accounts:
        for account in load_accounts():
            print("%s\t%s\t%s" % (account["key"], account["name"], account["id"]))
        return 0

    account = find_account(args.account)
    report_path, result = validate_ticket(
        account=account,
        browser_name=args.browser,
        headed=args.headed,
        timeout_seconds=args.timeout_seconds,
        hold_seconds=args.hold_seconds,
        version=args.version,
    )
    print("账号 [%s] 的门票验证报告已保存: %s" % (account["name"], report_path))
    print("验证结论: %s" % ("有效" if result["is_valid"] else "无效"))
    print("最终 URL: %s" % result["current_url"])
    return 0 if result["is_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
