import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, Request, Response, TimeoutError, sync_playwright

from .session_state import SessionStateManager
from .ticket_store import (
    ensure_runtime_dir,
    iso_now,
    load_ticket_bundle,
    save_json,
    storage_state_path_for_account,
    ticket_path_for_account,
)


PLATFORM_URL = "https://ec.95306.cn/platformIndex"
LOGIN_URL = "https://ec.95306.cn/login"
SUCCESS_HINTS = ("/platformindex",)
LOGIN_HINTS = ("/login",)
API_HINTS = ("api/", "basePermission", "queryUnReadCount", "queryCwdOrCz")
MAX_EVENTS = 60
DEFAULT_ACCOUNTS = ("newts", "cy-steel")
DEFAULT_HEARTBEAT_SECONDS = 600


def _trimmed_append(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    items.append(item)
    if len(items) > MAX_EVENTS:
        del items[0 : len(items) - MAX_EVENTS]


def _summarize_request(request: Request) -> dict[str, Any]:
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


def _summarize_response(response: Response) -> dict[str, Any]:
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


def _attach_network_listeners(context: BrowserContext, requests_log: list[dict[str, Any]], responses_log: list[dict[str, Any]]) -> None:
    context.on("request", lambda request: _trimmed_append(requests_log, _summarize_request(request)) if request.url.startswith("http") else None)
    context.on("response", lambda response: _trimmed_append(responses_log, _summarize_response(response)) if response.url.startswith("http") else None)


def _read_storage(page: Page) -> dict[str, dict[str, str]]:
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


def _capture_snapshot(context: BrowserContext, page: Page) -> dict[str, Any]:
    storage = _read_storage(page)
    return {
        "captured_at": iso_now(),
        "current_url": page.url,
        "title": page.title(),
        "cookies": context.cookies(),
        "local_storage": storage["localStorage"],
        "session_storage": storage["sessionStorage"],
    }


def _inject_session_storage(context: BrowserContext, session_storage: dict[str, str], target_origin: str) -> None:
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


def _detect_validation_signals(snapshot: dict[str, Any], requests_log: list[dict[str, Any]], responses_log: list[dict[str, Any]], url_changes: list[dict[str, Any]]) -> dict[str, Any]:
    current_url = snapshot["current_url"]
    lowered_url = current_url.lower()
    session_cookie_present = any(cookie.get("name") == "SESSION" for cookie in snapshot["cookies"])
    storage_has_refresh = any("refresh" in key.lower() for key in snapshot["session_storage"].keys())
    storage_has_user = any("user" in key.lower() for key in snapshot["local_storage"].keys())
    landed_on_platform = any(hint in lowered_url for hint in SUCCESS_HINTS)
    redirected_to_login = any(hint in lowered_url for hint in LOGIN_HINTS)
    touched_platform = any("/platformindex" in item["url"].lower() for item in url_changes)
    business_api_success = any(item["auth_related"] and str(item.get("status", "")) == "200" for item in responses_log)
    auth_request_count = len([item for item in requests_log if item["auth_related"]])

    return {
        "landed_on_platform": landed_on_platform,
        "redirected_to_login": redirected_to_login,
        "touched_platform": touched_platform,
        "business_api_success": business_api_success,
        "session_cookie_present": session_cookie_present,
        "storage_has_refresh": storage_has_refresh,
        "storage_has_user": storage_has_user,
        "auth_request_count": auth_request_count,
    }


def _is_ticket_valid(signals: dict[str, Any]) -> bool:
    return signals["landed_on_platform"] and not signals["redirected_to_login"]


def _screenshots_dir() -> Path:
    path = ensure_runtime_dir() / "screenshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_path() -> Path:
    return ensure_runtime_dir() / "95306_keepalive.log"


def _append_log(event: dict[str, Any]) -> None:
    line = json.dumps(event, ensure_ascii=False)
    _log_path().open("a", encoding="utf-8").write(line + "\n")


def run_keepalive_check(account: dict[str, Any], browser_name: str = "chromium", headed: bool = False, timeout_seconds: int = 30) -> dict[str, Any]:
    ticket_path = ticket_path_for_account(account["key"])
    storage_state_file = storage_state_path_for_account(account["key"])
    ticket_data = load_ticket_bundle(ticket_path)
    session_manager = SessionStateManager(account["key"])

    requests_log: list[dict[str, Any]] = []
    responses_log: list[dict[str, Any]] = []
    url_changes: list[dict[str, Any]] = []
    screenshot_path: str | None = None
    check_started_at = iso_now()

    with sync_playwright() as p:
        browser = getattr(p, browser_name).launch(headless=not headed)
        context = browser.new_context(storage_state=str(storage_state_file))
        _inject_session_storage(context, ticket_data.get("session_storage", {}), "https://ec.95306.cn")
        _attach_network_listeners(context, requests_log, responses_log)
        page = context.new_page()
        page.on(
            "framenavigated",
            lambda frame: _trimmed_append(url_changes, {"timestamp": iso_now(), "url": frame.url, "event": "navigated"}) if frame == page.main_frame else None,
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

        snapshot = _capture_snapshot(context, page)
        signals = _detect_validation_signals(snapshot, requests_log, responses_log, url_changes)
        is_valid = _is_ticket_valid(signals)

        if is_valid:
            updated_ticket = deepcopy(ticket_data)
            updated_ticket["captured_at"] = iso_now()
            updated_ticket["current_url"] = snapshot["current_url"]
            updated_ticket["cookies"] = snapshot["cookies"]
            updated_ticket["local_storage"] = snapshot["local_storage"]
            updated_ticket["session_storage"] = snapshot["session_storage"]
            updated_ticket["last_keepalive_check"] = {
                "check_started_at": check_started_at,
                "check_finished_at": iso_now(),
                "result": "ok",
            }
            updated_storage_state = context.storage_state()
            session_manager.save_bundle(updated_ticket, updated_storage_state, source="keepalive")
        else:
            screenshot_file = _screenshots_dir() / f"{account['key']}_{int(time.time())}.png"
            page.screenshot(path=str(screenshot_file), full_page=True)
            screenshot_path = str(screenshot_file.resolve())

        browser.close()

    result = {
        "heartbeat_at": iso_now(),
        "account": {
            "key": account["key"],
            "name": account["name"],
            "id": account["id"],
        },
        "check_started_at": check_started_at,
        "check_finished_at": iso_now(),
        "is_valid": is_valid,
        "current_url": snapshot["current_url"],
        "signals": signals,
        "ticket_file": str(ticket_path.resolve()),
        "storage_state_file": str(storage_state_file.resolve()),
        "screenshot_path": screenshot_path,
        "recent_requests": requests_log[-10:],
        "recent_responses": responses_log[-10:],
    }
    _append_log(result)
    return result


def run_keepalive_loop(accounts: list[dict[str, Any]], browser_name: str = "chromium", headed: bool = False, heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS, timeout_seconds: int = 30) -> int:
    while True:
        cycle_started_at = iso_now()
        _append_log(
            {
                "event": "cycle_started",
                "heartbeat_at": cycle_started_at,
                "accounts": [account["key"] for account in accounts],
                "heartbeat_seconds": heartbeat_seconds,
            }
        )
        for account in accounts:
            result = run_keepalive_check(
                account=account,
                browser_name=browser_name,
                headed=headed,
                timeout_seconds=timeout_seconds,
            )
            if not result["is_valid"]:
                _append_log(
                    {
                        "event": "stopped_on_failure",
                        "heartbeat_at": iso_now(),
                        "account": account["key"],
                        "current_url": result["current_url"],
                        "screenshot_path": result["screenshot_path"],
                    }
                )
                return 1
        _append_log(
            {
                "event": "cycle_completed",
                "heartbeat_at": iso_now(),
                "accounts": [account["key"] for account in accounts],
            }
        )
        time.sleep(heartbeat_seconds)
