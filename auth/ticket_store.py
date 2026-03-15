import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
TICKET_PATH = RUNTIME_DIR / "95306_ticket.json"
STORAGE_STATE_PATH = RUNTIME_DIR / "95306_storage_state.json"

TOKEN_FIELD_PATTERN = re.compile(
    r"(authorization|token|access[_-]?token|refresh[_-]?token|session)",
    re.IGNORECASE,
)


def ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def normalize_headers(headers: Optional[dict[str, str]]) -> dict[str, str]:
    if not headers:
        return {}
    return {str(k).lower(): str(v) for k, v in headers.items()}


def sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value


def extract_auth_candidates(mapping: Optional[dict[str, Any]]) -> dict[str, Any]:
    mapping = mapping or {}
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        if TOKEN_FIELD_PATTERN.search(str(key)):
            result[str(key)] = sanitize_value(value)
    return result


def extract_cookie_tokens(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    session_candidates = []
    for cookie in cookies:
        name = str(cookie.get("name", ""))
        value = cookie.get("value")
        lower_name = name.lower()
        if lower_name == "session":
            extracted["session_cookie"] = value
        if "access" in lower_name and "token" in lower_name:
            extracted[name] = value
        if "refresh" in lower_name and "token" in lower_name:
            extracted[name] = value
        if "session" in lower_name:
            session_candidates.append({"name": name, "value": value})
    if session_candidates:
        extracted["session_related_cookies"] = session_candidates
    return extracted


def filter_auth_headers(headers: Optional[dict[str, str]]) -> dict[str, str]:
    headers = normalize_headers(headers)
    kept = {}
    for key, value in headers.items():
        if TOKEN_FIELD_PATTERN.search(key) or key in {"cookie", "set-cookie"}:
            kept[key] = value
    return kept


def build_auth_summary(ticket_data: dict[str, Any]) -> dict[str, Any]:
    cookies = ticket_data.get("cookies", [])
    local_storage = ticket_data.get("local_storage", {})
    session_storage = ticket_data.get("session_storage", {})
    observed_requests = ticket_data.get("observed_requests", [])
    observed_responses = ticket_data.get("observed_responses", [])

    summary = {
        "captured_at": ticket_data.get("captured_at", iso_now()),
        "current_url": ticket_data.get("current_url"),
        "user_agent": ticket_data.get("user_agent"),
        "suspected_login_signals": deepcopy(ticket_data.get("login_signals", {})),
        "cookies": {
            "count": len(cookies),
            "auth_candidates": extract_cookie_tokens(cookies),
        },
        "storage": {
            "local_storage_auth_candidates": extract_auth_candidates(local_storage),
            "session_storage_auth_candidates": extract_auth_candidates(session_storage),
        },
        "important_request_headers": [],
        "important_response_headers": [],
        "identified_tokens": {},
        "key_api_calls": [],
    }

    identified_tokens = {}
    identified_tokens.update(summary["cookies"]["auth_candidates"])
    identified_tokens.update(extract_auth_candidates(local_storage))
    identified_tokens.update(extract_auth_candidates(session_storage))

    for request in observed_requests:
        auth_headers = filter_auth_headers(request.get("headers"))
        if auth_headers:
            summary["important_request_headers"].append(
                {
                    "url": request.get("url"),
                    "method": request.get("method"),
                    "headers": auth_headers,
                }
            )
            identified_tokens.update(auth_headers)

    for response in observed_responses:
        auth_headers = filter_auth_headers(response.get("headers"))
        if auth_headers:
            summary["important_response_headers"].append(
                {
                    "url": response.get("url"),
                    "status": response.get("status"),
                    "headers": auth_headers,
                }
            )
        if response.get("auth_related"):
            summary["key_api_calls"].append(
                {
                    "url": response.get("url"),
                    "method": response.get("method"),
                    "status": response.get("status"),
                    "request_headers": filter_auth_headers(response.get("request_headers")),
                    "response_headers": auth_headers,
                }
            )

    summary["identified_tokens"] = identified_tokens
    return summary


def save_json(path: Path, payload: dict[str, Any]) -> Path:
    ensure_runtime_dir()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_storage_state(storage_state: dict[str, Any], path: Optional[Path] = None) -> Path:
    return save_json(path or STORAGE_STATE_PATH, storage_state)


def save_ticket_bundle(ticket_data: dict[str, Any], path: Optional[Path] = None) -> Path:
    payload = deepcopy(ticket_data)
    payload["auth_summary"] = build_auth_summary(payload)
    return save_json(path or TICKET_PATH, payload)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_ticket_bundle(path: Path) -> dict[str, Any]:
    return load_json(path)


def load_storage_state(path: Path) -> dict[str, Any]:
    return load_json(path)


def slugify_account_key(account_key: str) -> str:
    cleaned = []
    for char in account_key.strip():
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("_")
    text = "".join(cleaned).strip("_")
    return text or "default"


def ticket_path_for_account(account_key: str) -> Path:
    return RUNTIME_DIR / f"95306_ticket_{slugify_account_key(account_key)}.json"


def storage_state_path_for_account(account_key: str) -> Path:
    return RUNTIME_DIR / f"95306_storage_state_{slugify_account_key(account_key)}.json"


def preflight_report_path() -> Path:
    return RUNTIME_DIR / "95306_preflight_report.json"


def validation_report_path_for_account(account_key: str) -> Path:
    return RUNTIME_DIR / f"95306_ticket_validation_{slugify_account_key(account_key)}.json"


def ticket_path_for_account_version(account_key: str, version: str) -> Path:
    return RUNTIME_DIR / f"95306_ticket_{slugify_account_key(account_key)}_{slugify_account_key(version)}.json"


def storage_state_path_for_account_version(account_key: str, version: str) -> Path:
    return RUNTIME_DIR / f"95306_storage_state_{slugify_account_key(account_key)}_{slugify_account_key(version)}.json"


def diff_report_path_for_account(account_key: str, left_version: str, right_version: str) -> Path:
    return RUNTIME_DIR / (
        f"95306_ticket_diff_{slugify_account_key(account_key)}_"
        f"{slugify_account_key(left_version)}_vs_{slugify_account_key(right_version)}.json"
    )


def heartbeat_report_path_for_account(account_key: str) -> Path:
    return RUNTIME_DIR / f"95306_ticket_heartbeat_{slugify_account_key(account_key)}.json"


def heartbeat_report_path_for_account_version(account_key: str, version: str) -> Path:
    return RUNTIME_DIR / (
        f"95306_ticket_heartbeat_{slugify_account_key(account_key)}_{slugify_account_key(version)}.json"
    )
