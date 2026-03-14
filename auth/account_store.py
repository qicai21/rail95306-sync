import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
ACCOUNTS_PATH = RUNTIME_DIR / "95306_accounts.json"


def ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR


def load_accounts(path: Path | None = None) -> list[dict[str, Any]]:
    file_path = path or ACCOUNTS_PATH
    if not file_path.exists():
        raise FileNotFoundError(f"Account file not found: {file_path}")
    data = json.loads(file_path.read_text(encoding="utf-8"))
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list) or not accounts:
        raise ValueError(f"No accounts found in: {file_path}")
    return accounts


def find_account(account_key: str, path: Path | None = None) -> dict[str, Any]:
    accounts = load_accounts(path)
    for account in accounts:
        if account.get("key") == account_key:
            return account
        if account.get("name") == account_key:
            return account
        if account.get("id") == account_key:
            return account
    raise KeyError(f"Account not found: {account_key}")


def save_accounts(accounts: list[dict[str, Any]], path: Path | None = None) -> Path:
    ensure_runtime_dir()
    file_path = path or ACCOUNTS_PATH
    payload = {"accounts": accounts}
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_path
