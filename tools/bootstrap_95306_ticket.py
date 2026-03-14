import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, Request, Response, TimeoutError, sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.account_store import find_account, load_accounts
from auth.ticket_store import (
    ensure_runtime_dir,
    iso_now,
    save_storage_state,
    save_ticket_bundle,
    storage_state_path_for_account,
    storage_state_path_for_account_version,
    ticket_path_for_account,
    ticket_path_for_account_version,
)


LOGIN_URL = "https://ec.95306.cn/login"
API_HINTS = (
    "api/",
    "zuul/",
    "queryWhiteListStatus",
    "refreshToken",
    "login",
    "wayBillQuery",
    "track/",
)
LOGIN_SUCCESS_HINTS = (
    "/platformindex",
    "/index",
    "/home",
    "/loading/",
    "/deliveryService/",
    "/ydTrickDu",
)
MAX_EVENT_COUNT = 80


@dataclass
class ObservationState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    responses: list[dict[str, Any]] = field(default_factory=list)
    storage_events: list[dict[str, Any]] = field(default_factory=list)
    url_changes: list[dict[str, Any]] = field(default_factory=list)
    initial_url: str | None = None
    initial_cookies: list[dict[str, Any]] = field(default_factory=list)
    initial_local_storage: dict[str, str] = field(default_factory=dict)
    initial_session_storage: dict[str, str] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture 95306 initial login ticket with a headed Playwright browser.")
    parser.add_argument("--timeout-minutes", type=int, default=15, help="Maximum time to wait for manual login.")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="Polling interval while waiting for login.")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument("--account", help="Account key, name, or id from runtime/95306_accounts.json.")
    parser.add_argument("--version", help="Optional capture label, for example run1 or 20260314a.")
    parser.add_argument("--no-autofill", action="store_true", help="Do not auto-fill username and password.")
    parser.add_argument("--yes", action="store_true", help="Auto-confirm capture once login success is detected.")
    parser.add_argument("--list-accounts", action="store_true", help="List configured accounts and exit.")
    args = parser.parse_args()
    if not args.list_accounts and not args.account:
        parser.error("the following arguments are required: --account")
    return args


def read_storage(page: Page) -> dict[str, dict[str, str]]:
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


def summarize_request(request: Request) -> dict[str, Any]:
    headers = request.headers
    return {
        "timestamp": iso_now(),
        "url": request.url,
        "method": request.method,
        "resource_type": request.resource_type,
        "headers": headers,
        "auth_related": is_auth_related(request.url, headers),
    }


def summarize_response(response: Response) -> dict[str, Any]:
    headers = response.headers
    request = response.request
    return {
        "timestamp": iso_now(),
        "url": response.url,
        "status": response.status,
        "method": request.method,
        "resource_type": request.resource_type,
        "headers": headers,
        "request_headers": request.headers,
        "auth_related": is_auth_related(response.url, headers) or is_auth_related(response.url, request.headers),
    }


def is_auth_related(url: str, headers: dict[str, str] | None) -> bool:
    headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    lowered = url.lower()
    if any(hint.lower() in lowered for hint in API_HINTS):
        return True
    return any(key in headers for key in ("authorization", "access_token", "cookie", "set-cookie", "token"))


def trimmed_append(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    items.append(item)
    if len(items) > MAX_EVENT_COUNT:
        del items[0 : len(items) - MAX_EVENT_COUNT]


def attach_network_listeners(context: BrowserContext, state: ObservationState) -> None:
    def on_request(request: Request) -> None:
        if request.url.startswith("http"):
            trimmed_append(state.requests, summarize_request(request))

    def on_response(response: Response) -> None:
        if response.url.startswith("http"):
            trimmed_append(state.responses, summarize_response(response))

    context.on("request", on_request)
    context.on("response", on_response)


def collect_page_snapshot(context: BrowserContext, page: Page) -> dict[str, Any]:
    storage = read_storage(page)
    return {
        "url": page.url,
        "cookies": context.cookies(),
        "local_storage": storage["localStorage"],
        "session_storage": storage["sessionStorage"],
    }


def compute_storage_delta(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    before_keys = set(before)
    after_keys = set(after)
    changed = [key for key in before_keys & after_keys if before[key] != after[key]]
    return {
        "added": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "changed": sorted(changed),
    }


def compute_cookie_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    def key_fn(cookie: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(cookie.get("name", "")),
            str(cookie.get("domain", "")),
            str(cookie.get("path", "")),
        )

    before_map = {key_fn(cookie): cookie.get("value") for cookie in before}
    after_map = {key_fn(cookie): cookie.get("value") for cookie in after}
    changed = [key[0] for key in before_map.keys() & after_map.keys() if before_map[key] != after_map[key]]
    return {
        "count_before": len(before),
        "count_after": len(after),
        "added": sorted(key[0] for key in after_map.keys() - before_map.keys()),
        "removed": sorted(key[0] for key in before_map.keys() - after_map.keys()),
        "changed": sorted(changed),
    }


def detect_success_signals(state: ObservationState, snapshot: dict[str, Any]) -> dict[str, Any]:
    current_url = snapshot["url"]
    cookie_delta = compute_cookie_delta(state.initial_cookies, snapshot["cookies"])
    local_storage_delta = compute_storage_delta(state.initial_local_storage, snapshot["local_storage"])
    session_storage_delta = compute_storage_delta(state.initial_session_storage, snapshot["session_storage"])

    url_changed = bool(state.initial_url and current_url != state.initial_url)
    url_matches_logged_in = any(hint in current_url.lower() for hint in LOGIN_SUCCESS_HINTS)
    auth_requests = [item for item in state.requests if item.get("auth_related")]
    auth_responses = [item for item in state.responses if item.get("auth_related")]
    has_business_api = any("/api/" in item.get("url", "").lower() for item in auth_responses)
    cookie_growth = cookie_delta["count_after"] > cookie_delta["count_before"]
    extracted_names = {cookie.get("name", "").lower() for cookie in snapshot["cookies"]}
    has_session_cookie = "session" in extracted_names
    storage_has_token = any(
        "token" in key.lower() or "session" in key.lower()
        for key in list(snapshot["local_storage"].keys()) + list(snapshot["session_storage"].keys())
    )

    score = sum(
        [
            1 if url_changed else 0,
            1 if url_matches_logged_in else 0,
            1 if has_business_api else 0,
            1 if cookie_growth else 0,
            1 if has_session_cookie else 0,
            1 if storage_has_token else 0,
            1 if len(auth_requests) >= 3 else 0,
        ]
    )

    return {
        "score": score,
        "url_changed": url_changed,
        "url_matches_logged_in": url_matches_logged_in,
        "has_business_api": has_business_api,
        "cookie_growth": cookie_growth,
        "has_session_cookie": has_session_cookie,
        "storage_has_token": storage_has_token,
        "auth_request_count": len(auth_requests),
        "auth_response_count": len(auth_responses),
        "cookie_delta": cookie_delta,
        "local_storage_delta": local_storage_delta,
        "session_storage_delta": session_storage_delta,
    }


def is_probably_logged_in(signals: dict[str, Any]) -> bool:
    strong_combo = signals["url_changed"] and (signals["has_business_api"] or signals["has_session_cookie"])
    storage_combo = signals["storage_has_token"] and signals["cookie_growth"]
    return signals["score"] >= 3 and (strong_combo or storage_combo or signals["url_matches_logged_in"])


def prompt_for_confirmation(auto_confirm: bool = False) -> bool:
    if auto_confirm:
        return True
    while True:
        answer = input("检测到疑似登录成功。确认采集当前认证状态吗？[y/n]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False


def maybe_autofill_login_form(page: Page, account: dict[str, Any]) -> bool:
    script = """
    ({ username, password }) => {
        const visible = (el) => !!el && el.offsetParent !== null;
        const textInputs = Array.from(document.querySelectorAll('input'))
            .filter((el) => visible(el) && !el.disabled);

        const findUserInput = () => {
            const predicates = [
                (el) => /user|account|login|name|用户名|账号/i.test(
                    [el.name, el.id, el.placeholder, el.getAttribute('aria-label')].filter(Boolean).join(' ')
                ),
                (el) => (el.type || '').toLowerCase() === 'text',
            ];
            for (const predicate of predicates) {
                const target = textInputs.find(predicate);
                if (target) return target;
            }
            return null;
        };

        const findPasswordInput = () => {
            return textInputs.find((el) => (el.type || '').toLowerCase() === 'password') || null;
        };

        const userInput = findUserInput();
        const passwordInput = findPasswordInput();
        if (!userInput || !passwordInput) {
            return { ok: false, reason: 'login inputs not found' };
        }

        const assign = (element, value) => {
            element.focus();
            element.value = '';
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.value = value;
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.blur();
        };

        assign(userInput, username);
        assign(passwordInput, password);
        return {
            ok: true,
            userSelector: userInput.name || userInput.id || userInput.placeholder || 'unknown',
            passwordSelector: passwordInput.name || passwordInput.id || passwordInput.placeholder || 'unknown',
        };
    }
    """
    result = page.evaluate(script, {"username": account["id"], "password": account["pwd"]})
    return bool(result.get("ok"))


def wait_for_manual_login(context: BrowserContext, page: Page, state: ObservationState, timeout_minutes: int, poll_seconds: float, auto_confirm: bool = False) -> dict[str, Any]:
    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        snapshot = collect_page_snapshot(context, page)
        signals = detect_success_signals(state, snapshot)
        if is_probably_logged_in(signals):
            print(json.dumps({"login_signals": signals, "current_url": snapshot["url"]}, ensure_ascii=False, indent=2))
            if prompt_for_confirmation(auto_confirm=auto_confirm):
                return {"snapshot": snapshot, "signals": signals}
            print("继续等待，你可以在浏览器中继续操作，之后再次确认。")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out after {timeout_minutes} minutes while waiting for manual login.")


def write_storage_state(context: BrowserContext) -> Path:
    ensure_runtime_dir()
    storage_state = context.storage_state()
    return save_storage_state(storage_state)


def build_ticket_payload(account: dict[str, Any], page: Page, state: ObservationState, final_snapshot: dict[str, Any], signals: dict[str, Any], storage_path: Path) -> dict[str, Any]:
    return {
        "captured_at": iso_now(),
        "account": {
            "key": account["key"],
            "name": account["name"],
            "id": account["id"],
        },
        "login_url": LOGIN_URL,
        "current_url": final_snapshot["url"],
        "user_agent": page.evaluate("() => navigator.userAgent"),
        "cookies": final_snapshot["cookies"],
        "local_storage": final_snapshot["local_storage"],
        "session_storage": final_snapshot["session_storage"],
        "storage_state_file": str(storage_path.resolve()),
        "login_signals": signals,
        "observed_requests": state.requests,
        "observed_responses": state.responses,
        "storage_events": state.storage_events,
        "url_changes": state.url_changes,
    }


def bootstrap_ticket(account: dict[str, Any], timeout_minutes: int, poll_seconds: float, browser_name: str, no_autofill: bool, version: str = None, auto_confirm: bool = False) -> tuple[Path, Path]:
    with sync_playwright() as p:
        browser_launcher = getattr(p, browser_name)
        browser = browser_launcher.launch(headless=False)
        context = browser.new_context()
        state = ObservationState()
        attach_network_listeners(context, state)

        context.expose_binding(
            "__codexStorageChanged",
            lambda _source, event: trimmed_append(state.storage_events, {"timestamp": iso_now(), **event}),
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
                            window.__codexStorageChanged({
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
        page = context.new_page()
        page.on("framenavigated", lambda frame: state.url_changes.append({"timestamp": iso_now(), "url": frame.url, "event": "navigated"}) if frame == page.main_frame else None)

        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except TimeoutError:
            pass

        initial_snapshot = collect_page_snapshot(context, page)
        state.initial_url = initial_snapshot["url"]
        state.initial_cookies = initial_snapshot["cookies"]
        state.initial_local_storage = initial_snapshot["local_storage"]
        state.initial_session_storage = initial_snapshot["session_storage"]
        state.url_changes.append({"timestamp": iso_now(), "url": page.url, "event": "initial"})

        autofilled = False
        if not no_autofill:
            try:
                autofilled = maybe_autofill_login_form(page, account)
            except Exception:
                autofilled = False

        if autofilled:
            print(f"浏览器已打开，账号 [{account['name']}] 的用户名和密码已自动填入。请手动完成滑块和短信验证。")
        else:
            print(f"浏览器已打开，请为账号 [{account['name']}] 手动完成登录。脚本不会处理滑块和短信验证。")
        result = wait_for_manual_login(context, page, state, timeout_minutes, poll_seconds, auto_confirm=auto_confirm)
        result["snapshot"]["url"] = page.url

        if version:
            storage_path = storage_state_path_for_account_version(account["key"], version)
            ticket_path = ticket_path_for_account_version(account["key"], version)
        else:
            storage_path = storage_state_path_for_account(account["key"])
            ticket_path = ticket_path_for_account(account["key"])
        save_storage_state(context.storage_state(), storage_path)
        ticket_payload = build_ticket_payload(account, page, state, result["snapshot"], result["signals"], storage_path)
        save_ticket_bundle(ticket_payload, ticket_path)
        browser.close()
        return ticket_path, storage_path


def main() -> int:
    args = parse_args()
    if args.list_accounts:
        for account in load_accounts():
            print(f"{account['key']}\t{account['name']}\t{account['id']}")
        return 0

    account = find_account(args.account)
    try:
        ticket_path, storage_path = bootstrap_ticket(
            account=account,
            timeout_minutes=args.timeout_minutes,
            poll_seconds=args.poll_seconds,
            browser_name=args.browser,
            no_autofill=args.no_autofill,
            version=args.version,
            auto_confirm=args.yes,
        )
    except TimeoutError as exc:
        print(str(exc))
        return 1

    print(f"账号 [{account['name']}] 的认证摘要已保存: {ticket_path}")
    print(f"账号 [{account['name']}] 的 Playwright storage_state 已保存: {storage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
