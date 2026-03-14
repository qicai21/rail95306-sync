import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib import error, request

from .ticket_store import (
    heartbeat_report_path_for_account,
    heartbeat_report_path_for_account_version,
    iso_now,
    load_storage_state,
    load_ticket_bundle,
    save_json,
    save_storage_state,
    save_ticket_bundle,
    storage_state_path_for_account,
    storage_state_path_for_account_version,
    ticket_path_for_account,
    ticket_path_for_account_version,
)


WHITE_LIST_URL = "https://ec.95306.cn/api/yhzx/user/queryWhiteListStatus"
REFRESH_TOKEN_URL = "https://ec.95306.cn/api/zuul/refreshToken"


class HeartbeatRefreshError(RuntimeError):
    def __init__(self, message: str, report_path: Path):
        super().__init__(message)
        self.report_path = report_path


def _cookies_to_map(cookies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for cookie in cookies:
        name = str(cookie.get("name", ""))
        if name:
            result[name] = deepcopy(cookie)
    return result


def _extract_cookie_header(cookies: dict[str, dict[str, Any]]) -> str:
    parts = []
    for name in ("95306-1.6.10-userdo", "95306-1.6.10-accessToken", "SESSION"):
        cookie = cookies.get(name)
        if cookie and cookie.get("value") is not None:
            parts.append(f"{name}={cookie['value']}")
    return "; ".join(parts)


def _request_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30) as response:
            return {
                "status_code": response.status,
                "headers": dict(response.headers.items()),
                "body": response.read().decode("utf-8", errors="replace"),
            }
    except error.HTTPError as exc:
        return {
            "status_code": exc.code,
            "headers": dict(exc.headers.items()),
            "body": exc.read().decode("utf-8", errors="replace"),
        }


def _extract_session_value(set_cookie: str | None) -> str | None:
    if not set_cookie:
        return None
    for part in set_cookie.split(";"):
        text = part.strip()
        if text.startswith("SESSION="):
            return text.split("=", 1)[1]
    return None


def _get_header(headers: dict[str, str], name: str) -> str | None:
    lowered_name = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered_name:
            return value
    return None


def _build_base_headers(ticket_data: dict[str, Any], cookies: dict[str, dict[str, Any]]) -> dict[str, str]:
    account = ticket_data["account"]
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Origin": "https://ec.95306.cn",
        "User-Agent": ticket_data["user_agent"],
        "bureauDm": "02",
        "bureauId": "T00",
        "channel": "P",
        "type": "outer",
        "unitId": account["id"][:7],
        "userId": account["id"],
        "userType": "OUTUNIT",
        "Cookie": _extract_cookie_header(cookies),
    }


def _update_cookie_value(cookie_map: dict[str, dict[str, Any]], name: str, value: str) -> None:
    existing = cookie_map.get(name)
    if existing:
        existing["value"] = value
        return
    cookie_map[name] = {
        "name": name,
        "value": value,
        "domain": "ec.95306.cn",
        "path": "/",
        "httpOnly": name == "SESSION",
        "secure": True,
        "sameSite": "Lax",
    }


def _sorted_cookies(cookie_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [cookie_map[name] for name in sorted(cookie_map.keys())]


def refresh_ticket(account_key: str, version: str | None = None) -> dict[str, Any]:
    ticket_path = ticket_path_for_account_version(account_key, version) if version else ticket_path_for_account(account_key)
    storage_state_path = (
        storage_state_path_for_account_version(account_key, version) if version else storage_state_path_for_account(account_key)
    )
    report_path = (
        heartbeat_report_path_for_account_version(account_key, version)
        if version
        else heartbeat_report_path_for_account(account_key)
    )

    ticket_data = load_ticket_bundle(ticket_path)
    storage_state = load_storage_state(storage_state_path)
    cookie_map = _cookies_to_map(ticket_data.get("cookies", []))
    session_storage = deepcopy(ticket_data.get("session_storage", {}))
    base_headers = _build_base_headers(ticket_data, cookie_map)

    current_access_token = cookie_map["95306-1.6.10-accessToken"]["value"]
    current_refresh_token = session_storage["95306-outer-refreshToken"]

    white_headers = dict(base_headers)
    white_headers["Referer"] = "https://ec.95306.cn/login"
    white_response = _request_json(
        WHITE_LIST_URL,
        {"userId": ticket_data["account"]["id"]},
        white_headers,
    )

    report = {
        "refreshed_at": iso_now(),
        "account": ticket_data["account"],
        "version": version,
        "ticket_file": str(ticket_path.resolve()),
        "storage_state_file": str(storage_state_path.resolve()),
        "success": False,
        "changes": {},
        "white_list_status": {
            "status_code": white_response.get("status_code"),
            "set_cookie": _get_header(white_response.get("headers", {}), "Set-Cookie"),
            "body": white_response.get("body"),
        },
        "refresh_token": None,
    }

    if white_response["status_code"] != 200:
        save_json(report_path, report)
        raise HeartbeatRefreshError(
            f"queryWhiteListStatus failed: {white_response['status_code']} {white_response['body']}",
            report_path,
        )

    next_session_value = _extract_session_value(_get_header(white_response["headers"], "Set-Cookie"))
    if not next_session_value:
        save_json(report_path, report)
        raise HeartbeatRefreshError("queryWhiteListStatus did not return a new SESSION cookie", report_path)

    refresh_cookie_map = deepcopy(cookie_map)
    _update_cookie_value(refresh_cookie_map, "SESSION", next_session_value)

    refresh_headers = _build_base_headers(ticket_data, refresh_cookie_map)
    refresh_headers["Referer"] = "https://ec.95306.cn/platformIndex"
    refresh_headers["access_token"] = current_access_token
    refresh_response = _request_json(
        REFRESH_TOKEN_URL,
        {"extData": {"grant_type": "refresh_token", "refresh_token": current_refresh_token}},
        refresh_headers,
    )
    report["refresh_token"] = {
        "status_code": refresh_response.get("status_code"),
        "set_cookie": _get_header(refresh_response.get("headers", {}), "Set-Cookie"),
        "body": refresh_response.get("body"),
    }

    if refresh_response["status_code"] != 200:
        save_json(report_path, report)
        raise HeartbeatRefreshError(
            f"refreshToken failed: {refresh_response['status_code']} {refresh_response['body']}",
            report_path,
        )

    refresh_payload = json.loads(refresh_response["body"])
    refresh_data = refresh_payload.get("data") or {}
    next_access_token = refresh_data.get("accessToken")
    next_refresh_token = refresh_data.get("refreshToken")
    if not next_access_token or not next_refresh_token:
        save_json(report_path, report)
        raise HeartbeatRefreshError(
            f"refreshToken response missing token fields: {refresh_response['body']}",
            report_path,
        )

    final_cookie_map = deepcopy(refresh_cookie_map)
    _update_cookie_value(final_cookie_map, "95306-1.6.10-accessToken", next_access_token)

    updated_ticket = deepcopy(ticket_data)
    updated_ticket["captured_at"] = iso_now()
    updated_ticket["current_url"] = "https://ec.95306.cn/platformIndex"
    updated_ticket["cookies"] = _sorted_cookies(final_cookie_map)
    updated_ticket.setdefault("session_storage", {})
    updated_ticket["session_storage"]["95306-outer-refreshToken"] = next_refresh_token
    updated_ticket["last_heartbeat"] = {
        "at": iso_now(),
        "session_changed": next_session_value != cookie_map["SESSION"]["value"],
        "access_token_changed": next_access_token != current_access_token,
        "refresh_token_changed": next_refresh_token != current_refresh_token,
        "white_list_status": white_response["status_code"],
        "refresh_status": refresh_response["status_code"],
    }

    updated_storage_state = deepcopy(storage_state)
    updated_storage_state["cookies"] = updated_ticket["cookies"]

    save_ticket_bundle(updated_ticket, ticket_path)
    save_storage_state(updated_storage_state, storage_state_path)

    report["success"] = True
    report["changes"] = {
        "session": {
            "before": cookie_map["SESSION"]["value"],
            "after": next_session_value,
        },
        "access_token": {
            "before": current_access_token,
            "after": next_access_token,
        },
        "refresh_token": {
            "before": current_refresh_token,
            "after": next_refresh_token,
        },
    }
    save_json(report_path, report)
    return {
        "ticket_path": ticket_path,
        "storage_state_path": storage_state_path,
        "report_path": report_path,
        "report": report,
    }
