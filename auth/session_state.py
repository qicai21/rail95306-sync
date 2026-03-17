import os
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from .ticket_store import (
    iso_now,
    load_storage_state,
    load_ticket_bundle,
    save_storage_state,
    save_ticket_bundle,
    storage_state_path_for_account,
    ticket_path_for_account,
)


LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.1


def _cookie_to_dict(cookie: Any) -> dict[str, Any]:
    return {
        "name": str(cookie.name),
        "value": str(cookie.value),
        "domain": str(cookie.domain or "ec.95306.cn"),
        "path": str(cookie.path or "/"),
        "secure": bool(cookie.secure),
        "expires": cookie.expires,
        "httpOnly": "HttpOnly" in getattr(cookie, "_rest", {}),
    }


def _cookie_map(cookies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cookie in cookies:
        name = str(cookie.get("name", "")).strip()
        if name:
            result[name] = deepcopy(cookie)
    return result


def _sorted_cookies(cookie_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [cookie_map[name] for name in sorted(cookie_map.keys())]


class _FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def acquire(self, timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> None:
        deadline = time.time() + timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self.fd, str(os.getpid()).encode("ascii", errors="ignore"))
                return
            except FileExistsError:
                if time.time() >= deadline:
                    raise TimeoutError(f"Timed out waiting for lock: {self.path}")
                time.sleep(LOCK_POLL_SECONDS)

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class SessionStateManager:
    def __init__(self, account_key: str):
        self.account_key = account_key
        self.ticket_path = ticket_path_for_account(account_key)
        self.storage_state_path = storage_state_path_for_account(account_key)
        self.lock_path = self.ticket_path.with_suffix(".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        lock = _FileLock(self.lock_path)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def read_current_summary(self) -> dict[str, Any]:
        ticket_data = load_ticket_bundle(self.ticket_path)
        cookie_map = _cookie_map(ticket_data.get("cookies", []))
        session_storage = ticket_data.get("session_storage", {})
        return {
            "account_key": self.account_key,
            "ticket_file": str(self.ticket_path.resolve()),
            "storage_state_file": str(self.storage_state_path.resolve()),
            "session_cookie_value": cookie_map.get("SESSION", {}).get("value"),
            "access_token_value": cookie_map.get("95306-1.6.10-accessToken", {}).get("value"),
            "refresh_token_value": session_storage.get("95306-outer-refreshToken"),
            "updated_at": ticket_data.get("captured_at"),
            "last_session_sync": ticket_data.get("last_session_sync"),
        }

    def save_bundle(self, ticket_data: dict[str, Any], storage_state: dict[str, Any], source: str) -> None:
        with self._locked():
            updated_ticket = deepcopy(ticket_data)
            updated_ticket["captured_at"] = iso_now()
            updated_ticket["last_session_sync"] = {
                "at": iso_now(),
                "source": source,
            }
            updated_storage_state = deepcopy(storage_state)
            if "cookies" not in updated_storage_state:
                updated_storage_state["cookies"] = updated_ticket.get("cookies", [])
            save_ticket_bundle(updated_ticket, self.ticket_path)
            save_storage_state(updated_storage_state, self.storage_state_path)

    def sync_cookie_jar(self, cookie_jar: Any, current_url: str | None, source: str) -> bool:
        jar_cookies = [_cookie_to_dict(cookie) for cookie in cookie_jar]
        if not jar_cookies:
            return False

        with self._locked():
            ticket_data = load_ticket_bundle(self.ticket_path)
            storage_state = load_storage_state(self.storage_state_path)
            stored_cookie_map = _cookie_map(ticket_data.get("cookies", []))
            changed = False

            for cookie in jar_cookies:
                name = cookie["name"]
                if stored_cookie_map.get(name) != cookie:
                    stored_cookie_map[name] = cookie
                    changed = True

            if not changed:
                return False

            updated_ticket = deepcopy(ticket_data)
            updated_ticket["cookies"] = _sorted_cookies(stored_cookie_map)
            updated_ticket["captured_at"] = iso_now()
            if current_url:
                updated_ticket["current_url"] = current_url
            updated_ticket["last_session_sync"] = {
                "at": iso_now(),
                "source": source,
                "changed_fields": ["cookies"],
            }

            updated_storage_state = deepcopy(storage_state)
            updated_storage_state["cookies"] = updated_ticket["cookies"]

            save_ticket_bundle(updated_ticket, self.ticket_path)
            save_storage_state(updated_storage_state, self.storage_state_path)
            return True
