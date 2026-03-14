import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import BrowserContext, Page, Request, Response, sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.account_store import find_account, load_accounts
from auth.ticket_store import (
    iso_now,
    load_ticket_bundle,
    slugify_account_key,
    storage_state_path_for_account_version,
    ticket_path_for_account_version,
)


PLATFORM_URL = "https://ec.95306.cn/platformIndex"
TARGET_COOKIE_KEYS = {"SESSION", "95306-1.6.10-accessToken"}
TARGET_SESSION_KEYS = {
    "95306-outer-refreshToken",
    "95306-outer-resetTime",
    "95306-outer-loginCount",
    "95306-outer-menuList",
}
TARGET_REQUEST_HINTS = (
    "refreshToken",
    "checkUserLoginState",
    "basePermission",
    "queryCwdOrCz",
    "queryUnReadCount",
    "api/",
)
MAX_EVENTS = 200
SUMMARY_DIFF_LIMIT = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace how 95306 updates session/cookie/token state after login.")
    parser.add_argument("--account", help="Account key, name, or id from runtime/95306_accounts.json.")
    parser.add_argument("--version", required=True, help="Ticket version label to use, for example vpn_clean_1.")
    parser.add_argument("--list-accounts", action="store_true", help="List configured accounts and exit.")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode.")
    parser.add_argument("--duration-seconds", type=int, default=90, help="How long to observe after opening platformIndex.")
    parser.add_argument("--poll-seconds", type=float, default=1.0, help="How often to snapshot cookies and storage.")
    args = parser.parse_args()
    if not args.list_accounts and not args.account:
        parser.error("the following arguments are required: --account")
    return args


def trimmed_append(items: List[Dict[str, Any]], item: Dict[str, Any]) -> None:
    items.append(item)
    if len(items) > MAX_EVENTS:
        del items[0 : len(items) - MAX_EVENTS]


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


def extract_target_cookies(cookies: List[Dict[str, Any]]) -> Dict[str, str]:
    result = {}
    for cookie in cookies:
        name = str(cookie.get("name", ""))
        if name in TARGET_COOKIE_KEYS:
            result[name] = str(cookie.get("value", ""))
    return result


def extract_target_cookies_from_ticket(ticket_data: Dict[str, Any]) -> Dict[str, str]:
    cookies = ticket_data.get("cookies", [])
    if not isinstance(cookies, list):
        return {}
    return extract_target_cookies(cookies)


def extract_target_session(session_storage: Dict[str, str]) -> Dict[str, str]:
    return {key: value for key, value in session_storage.items() if key in TARGET_SESSION_KEYS}


def summarize_request(request: Request) -> Dict[str, Any]:
    headers = request.headers
    lowered_url = request.url.lower()
    interesting = any(hint.lower() in lowered_url for hint in TARGET_REQUEST_HINTS)
    auth_headers = {}
    for key, value in headers.items():
        lower_key = str(key).lower()
        if lower_key in {"access_token", "authorization", "cookie"} or "token" in lower_key:
            auth_headers[key] = value
    return {
        "timestamp": iso_now(),
        "url": request.url,
        "method": request.method,
        "resource_type": request.resource_type,
        "interesting": interesting,
        "auth_headers": auth_headers,
    }


def summarize_response(response: Response) -> Dict[str, Any]:
    request = response.request
    headers = response.headers
    lowered_url = response.url.lower()
    interesting = any(hint.lower() in lowered_url for hint in TARGET_REQUEST_HINTS)
    response_headers = {}
    for key, value in headers.items():
        lower_key = str(key).lower()
        if lower_key in {"set-cookie", "authorization"} or "token" in lower_key:
            response_headers[key] = value
    return {
        "timestamp": iso_now(),
        "url": response.url,
        "method": request.method,
        "status": response.status,
        "resource_type": request.resource_type,
        "interesting": interesting,
        "request_auth_headers": summarize_request(request)["auth_headers"],
        "response_auth_headers": response_headers,
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


def install_storage_hooks(context: BrowserContext, storage_events: List[Dict[str, Any]]) -> None:
    context.expose_binding(
        "__codexRefreshStorageChanged",
        lambda _source, event: trimmed_append(storage_events, {"timestamp": iso_now(), **event}),
    )
    context.add_init_script(
        """
        (() => {
            const patch = (storageName) => {
                const store = window[storageName];
                if (!store) return;
                const wrap = (method) => {
                    const original = store[method].bind(store);
                    store[method] = (...args) => {
                        const result = original(...args);
                        window.__codexRefreshStorageChanged({
                            storage: storageName,
                            method,
                            args,
                            href: window.location.href
                        });
                        return result;
                    };
                };
                wrap("setItem");
                wrap("removeItem");
                wrap("clear");
            };
            patch("localStorage");
            patch("sessionStorage");
        })();
        """
    )


def capture_state(context: BrowserContext, page: Page) -> Dict[str, Any]:
    storage = read_storage(page)
    cookies = context.cookies()
    return {
        "timestamp": iso_now(),
        "url": page.url,
        "cookies": extract_target_cookies(cookies),
        "session_storage": extract_target_session(storage["sessionStorage"]),
        "all_session_storage": storage["sessionStorage"],
    }


def diff_maps(previous: Dict[str, str], current: Dict[str, str]) -> Dict[str, Any]:
    previous_keys = set(previous.keys())
    current_keys = set(current.keys())
    changed = {}
    for key in sorted(previous_keys & current_keys):
        if previous[key] != current[key]:
            changed[key] = {"before": previous[key], "after": current[key]}
    return {
        "added": {key: current[key] for key in sorted(current_keys - previous_keys)},
        "removed": {key: previous[key] for key in sorted(previous_keys - current_keys)},
        "changed": changed,
    }


def has_any_diff(diff: Dict[str, Any]) -> bool:
    return bool(diff["added"] or diff["removed"] or diff["changed"])


def summarize_diff_keys(diff: Dict[str, Any]) -> List[str]:
    return sorted(set(diff["added"].keys()) | set(diff["removed"].keys()) | set(diff["changed"].keys()))


def build_compact_diff_summary(state_diffs: List[Dict[str, Any]]) -> Dict[str, Any]:
    impactful = []
    for diff in state_diffs:
        cookie_keys = summarize_diff_keys(diff["cookie_diff"])
        session_keys = summarize_diff_keys(diff["session_storage_diff"])
        non_reset_session_keys = [key for key in session_keys if key != "95306-outer-resetTime"]
        if not cookie_keys and not non_reset_session_keys:
            continue
        impactful.append(
            {
                "timestamp": diff["timestamp"],
                "url": diff["url"],
                "cookie_keys": cookie_keys,
                "session_storage_keys": non_reset_session_keys,
                "recent_requests": diff["recent_requests"],
                "recent_responses": diff["recent_responses"],
            }
        )
        if len(impactful) >= SUMMARY_DIFF_LIMIT:
            break
    return {
        "impactful_diff_count": len(impactful),
        "impactful_diffs": impactful,
        "first_impactful_diff": impactful[0] if impactful else None,
    }


def trace_refresh(account: Dict[str, Any], version: str, browser_name: str, headed: bool, duration_seconds: int, poll_seconds: float) -> Path:
    ticket_path = ticket_path_for_account_version(account["key"], version)
    storage_state_path = storage_state_path_for_account_version(account["key"], version)
    ticket_data = load_ticket_bundle(ticket_path)

    requests_log: List[Dict[str, Any]] = []
    responses_log: List[Dict[str, Any]] = []
    storage_events: List[Dict[str, Any]] = []
    url_changes: List[Dict[str, Any]] = []
    state_diffs: List[Dict[str, Any]] = []
    initial_state = {
        "timestamp": iso_now(),
        "url": "ticket_source",
        "cookies": extract_target_cookies_from_ticket(ticket_data),
        "session_storage": extract_target_session(ticket_data.get("session_storage", {})),
    }

    with sync_playwright() as p:
        browser = getattr(p, browser_name).launch(headless=not headed)
        context = browser.new_context(storage_state=str(storage_state_path))
        inject_session_storage(context, ticket_data.get("session_storage", {}), "https://ec.95306.cn")
        install_storage_hooks(context, storage_events)
        context.on("request", lambda request: trimmed_append(requests_log, summarize_request(request)) if request.url.startswith("http") else None)
        context.on("response", lambda response: trimmed_append(responses_log, summarize_response(response)) if response.url.startswith("http") else None)

        page = context.new_page()
        page.on(
            "framenavigated",
            lambda frame: trimmed_append(url_changes, {"timestamp": iso_now(), "url": frame.url, "event": "navigated"}) if frame == page.main_frame else None,
        )

        page.goto(PLATFORM_URL, wait_until="domcontentloaded")
        time.sleep(2)
        previous = capture_state(context, page)
        bootstrap_cookie_diff = diff_maps(initial_state["cookies"], previous["cookies"])
        bootstrap_session_diff = diff_maps(initial_state["session_storage"], previous["session_storage"])
        if has_any_diff(bootstrap_cookie_diff) or has_any_diff(bootstrap_session_diff):
            state_diffs.append(
                {
                    "timestamp": previous["timestamp"],
                    "url": previous["url"],
                    "phase": "bootstrap_after_navigation",
                    "cookie_diff": bootstrap_cookie_diff,
                    "session_storage_diff": bootstrap_session_diff,
                    "recent_requests": requests_log[-8:],
                    "recent_responses": responses_log[-8:],
                    "recent_storage_events": storage_events[-12:],
                }
            )
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            time.sleep(poll_seconds)
            current = capture_state(context, page)
            cookie_diff = diff_maps(previous["cookies"], current["cookies"])
            session_diff = diff_maps(previous["session_storage"], current["session_storage"])
            if has_any_diff(cookie_diff) or has_any_diff(session_diff):
                state_diffs.append(
                    {
                        "timestamp": current["timestamp"],
                        "url": current["url"],
                        "phase": "polling",
                        "cookie_diff": cookie_diff,
                        "session_storage_diff": session_diff,
                        "recent_requests": requests_log[-5:],
                        "recent_responses": responses_log[-5:],
                        "recent_storage_events": storage_events[-10:],
                    }
                )
            previous = current

        final_state = capture_state(context, page)
        browser.close()

    report = {
        "captured_at": iso_now(),
        "account": {
            "key": account["key"],
            "name": account["name"],
            "id": account["id"],
        },
        "version": version,
        "platform_url": PLATFORM_URL,
        "source_ticket_file": str(ticket_path.resolve()),
        "source_storage_state_file": str(storage_state_path.resolve()),
        "initial_state": initial_state,
        "final_url": final_state["url"],
        "final_cookies": final_state["cookies"],
        "final_session_storage": final_state["session_storage"],
        "compact_summary": build_compact_diff_summary(state_diffs),
        "state_diffs": state_diffs,
        "storage_events": storage_events,
        "requests": requests_log,
        "responses": responses_log,
        "url_changes": url_changes,
    }

    report_path = ROOT_DIR / "runtime" / (
        "95306_refresh_trace_%s_%s.json"
        % (slugify_account_key(account["key"]), slugify_account_key(version))
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main() -> int:
    args = parse_args()
    if args.list_accounts:
        for account in load_accounts():
            print("%s\t%s\t%s" % (account["key"], account["name"], account["id"]))
        return 0

    account = find_account(args.account)
    report_path = trace_refresh(
        account=account,
        version=args.version,
        browser_name=args.browser,
        headed=args.headed,
        duration_seconds=args.duration_seconds,
        poll_seconds=args.poll_seconds,
    )
    print("刷新追踪报告已保存: %s" % report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
