import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, Request, Response, sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.account_store import find_account, load_accounts
from auth.ticket_store import ensure_runtime_dir, iso_now, load_ticket_bundle, storage_state_path_for_account, ticket_path_for_account


PLATFORM_URL = "https://ec.95306.cn/platformIndex"
GOODS_QUERY_URL = "https://ec.95306.cn/loading/goodsQuery"
DEFAULT_HINTS = (
    "/api/",
    "wayBillQuery",
    "track/",
    "goodsQuery",
    "goodsQueryHistory",
    "platformIndex",
    "ydTrickDu",
)
MAX_EVENTS = 500
MAX_BODY_CHARS = 200000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a headed 95306 browser with the saved session and capture query-related network traffic."
    )
    parser.add_argument("--account", required=True, help="Account key from runtime/95306_accounts.json.")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument("--entry-url", default=GOODS_QUERY_URL, help="Page to open first. Defaults to goodsQuery.")
    parser.add_argument(
        "--hint",
        action="append",
        dest="hints",
        default=[],
        help="Additional URL substring to mark requests/responses as interesting. Can be repeated.",
    )
    parser.add_argument(
        "--label",
        default="manual",
        help="Short label included in the runtime report filename, for example round1 or by-ydid.",
    )
    return parser.parse_args()


def trimmed_append(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    items.append(item)
    if len(items) > MAX_EVENTS:
        del items[0 : len(items) - MAX_EVENTS]


def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_json_loads(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def truncate_text(text: str | None, limit: int = MAX_BODY_CHARS) -> str | None:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."


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


def inject_session_storage(context: BrowserContext, session_storage: dict[str, str], target_origin: str) -> None:
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


def install_dom_hooks(context: BrowserContext, event_log: list[dict[str, Any]], suggestion_log: list[dict[str, Any]]) -> None:
    def on_dom_event(_source, event: dict[str, Any]) -> None:
        trimmed_append(event_log, {"timestamp": iso_now(), **event})

    def on_suggestion_event(_source, event: dict[str, Any]) -> None:
        trimmed_append(suggestion_log, {"timestamp": iso_now(), **event})

    context.expose_binding("__codexObserveDomEvent", on_dom_event)
    context.expose_binding("__codexObserveSuggestionEvent", on_suggestion_event)
    context.add_init_script(
        """
        (() => {
            const textOf = (el) => (el && (el.innerText || el.textContent || '') || '').trim();
            const attrText = (el) => [
                el && el.tagName,
                el && el.id,
                el && el.className,
                el && el.getAttribute && el.getAttribute('placeholder'),
                el && el.getAttribute && el.getAttribute('aria-label'),
                el && el.getAttribute && el.getAttribute('name')
            ].filter(Boolean).join(' | ');

            const logEvent = (type, extra) => {
                window.__codexObserveDomEvent({
                    type,
                    href: window.location.href,
                    ...extra
                });
            };

            document.addEventListener('input', (event) => {
                const el = event.target;
                if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) return;
                logEvent('input', {
                    value: el.value,
                    meta: attrText(el)
                });
            }, true);

            document.addEventListener('change', (event) => {
                const el = event.target;
                if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement)) return;
                logEvent('change', {
                    value: el.value,
                    meta: attrText(el)
                });
            }, true);

            document.addEventListener('click', (event) => {
                const el = event.target;
                if (!(el instanceof Element)) return;
                const text = textOf(el).slice(0, 120);
                if (!text && !(el instanceof HTMLInputElement)) return;
                logEvent('click', {
                    text,
                    meta: attrText(el)
                });
            }, true);

            let lastSuggestionSnapshot = '';
            const collectCandidates = () => {
                const selectors = [
                    '.el-select-dropdown__item',
                    '.el-autocomplete-suggestion li',
                    '.el-scrollbar__view li',
                    '[role="option"]',
                    'li'
                ];
                const seen = new Set();
                const items = [];
                selectors.forEach((selector) => {
                    document.querySelectorAll(selector).forEach((el) => {
                        const text = textOf(el);
                        if (!text) return;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') return;
                        const key = selector + '::' + text;
                        if (seen.has(key)) return;
                        seen.add(key);
                        items.push({
                            selector,
                            text
                        });
                    });
                });
                return items.slice(0, 50);
            };

            const emitCandidates = (reason) => {
                const items = collectCandidates();
                const serialized = JSON.stringify(items);
                if (serialized === lastSuggestionSnapshot) return;
                lastSuggestionSnapshot = serialized;
                window.__codexObserveSuggestionEvent({
                    reason,
                    href: window.location.href,
                    items
                });
            };

            const observer = new MutationObserver(() => emitCandidates('mutation'));
            observer.observe(document.documentElement, {
                childList: true,
                subtree: true,
                characterData: true,
                attributes: true
            });

            window.addEventListener('load', () => emitCandidates('load'));
            document.addEventListener('input', () => {
                window.setTimeout(() => emitCandidates('input'), 50);
                window.setTimeout(() => emitCandidates('input-delayed'), 300);
            }, true);
        })();
        """
    )


def is_interesting(url: str, resource_type: str, hints: tuple[str, ...]) -> bool:
    lowered = url.lower()
    if resource_type in {"xhr", "fetch", "document"}:
        return any(hint.lower() in lowered for hint in hints)
    return False


def summarize_request(request: Request, hints: tuple[str, ...]) -> dict[str, Any]:
    post_data = request.post_data
    return {
        "timestamp": iso_now(),
        "url": request.url,
        "method": request.method,
        "resource_type": request.resource_type,
        "interesting": is_interesting(request.url, request.resource_type, hints),
        "headers": request.headers,
        "post_data": truncate_text(post_data),
        "post_json": safe_json_loads(post_data),
    }


def summarize_response(response: Response, hints: tuple[str, ...]) -> dict[str, Any]:
    body_text = None
    if is_interesting(response.url, response.request.resource_type, hints):
        try:
            body_text = response.text()
        except Exception:
            body_text = None
    return {
        "timestamp": iso_now(),
        "url": response.url,
        "method": response.request.method,
        "status": response.status,
        "resource_type": response.request.resource_type,
        "interesting": is_interesting(response.url, response.request.resource_type, hints),
        "request_headers": response.request.headers,
        "response_headers": response.headers,
        "request_post_data": truncate_text(response.request.post_data),
        "request_post_json": safe_json_loads(response.request.post_data),
        "response_text": truncate_text(body_text),
        "response_json": safe_json_loads(body_text),
    }


def wait_until_pages_closed(context: BrowserContext) -> None:
    while True:
        live_pages = [page for page in context.pages if not page.is_closed()]
        if not live_pages:
            return
        time.sleep(0.5)


def main() -> int:
    args = parse_args()
    account = find_account(args.account)
    ticket_path = ticket_path_for_account(account["key"])
    storage_state_path = storage_state_path_for_account(account["key"])
    ticket_data = load_ticket_bundle(ticket_path)
    hints = tuple(dict.fromkeys(DEFAULT_HINTS + tuple(args.hints)))

    ensure_runtime_dir()
    requests_log: list[dict[str, Any]] = []
    responses_log: list[dict[str, Any]] = []
    url_changes: list[dict[str, Any]] = []
    dom_events: list[dict[str, Any]] = []
    suggestion_events: list[dict[str, Any]] = []
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    temp_report_path = ROOT_DIR / "runtime" / f"95306_query_observation_{account['key']}_{args.label}_{timestamp}.partial.json"

    def current_payload() -> dict[str, Any]:
        return {
            "captured_at": iso_now(),
            "account": {
                "key": account["key"],
                "name": account["name"],
                "id": account["id"],
            },
            "entry_url": args.entry_url,
            "hints": list(hints),
            "ticket_file": str(ticket_path.resolve()),
            "storage_state_file": str(storage_state_path.resolve()),
            "local_storage": ticket_data.get("local_storage", {}),
            "session_storage": ticket_data.get("session_storage", {}),
            "requests": requests_log,
            "responses": responses_log,
            "url_changes": url_changes,
            "dom_events": dom_events,
            "suggestion_events": suggestion_events,
        }

    def persist_partial() -> None:
        write_snapshot(temp_report_path, current_payload())

    with sync_playwright() as p:
        browser = getattr(p, args.browser).launch(headless=False)
        context = browser.new_context(storage_state=str(storage_state_path))
        inject_session_storage(context, ticket_data.get("session_storage", {}), "https://ec.95306.cn")
        install_dom_hooks(context, dom_events, suggestion_events)
        context.on(
            "request",
            lambda request: (
                trimmed_append(requests_log, summarize_request(request, hints)),
                persist_partial(),
            )
            if request.url.startswith("http")
            else None,
        )
        context.on(
            "response",
            lambda response: (
                trimmed_append(responses_log, summarize_response(response, hints)),
                persist_partial(),
            )
            if response.url.startswith("http")
            else None,
        )

        page = context.new_page()
        page.on(
            "framenavigated",
            lambda frame: (
                trimmed_append(
                    url_changes,
                    {"timestamp": iso_now(), "url": frame.url, "event": "navigated"},
                ),
                persist_partial(),
            )
            if frame == page.main_frame
            else None,
        )
        persist_partial()
        page.goto(args.entry_url, wait_until="domcontentloaded")
        print(f"浏览器已打开: {args.entry_url}")
        print("请手动执行查询；查询完成后直接关闭浏览器窗口，脚本会自动保存录包结果。")
        wait_until_pages_closed(context)
        browser.close()

    report_path = ROOT_DIR / "runtime" / f"95306_query_observation_{account['key']}_{args.label}_{timestamp}.json"
    write_snapshot(report_path, current_payload())
    print(f"录包结果已保存: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
