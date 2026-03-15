import json
from pathlib import Path
from typing import Any

from .account_store import (
    ACCOUNTS_PATH,
    ACCOUNT_REQUIRED_FIELDS,
    account_file_missing_message,
    load_accounts,
)
from .ticket_store import (
    ensure_runtime_dir,
    load_storage_state,
    load_ticket_bundle,
    preflight_report_path,
    storage_state_path_for_account,
    ticket_path_for_account,
)

REQUIRED_TICKET_FIELDS = (
    "account",
    "captured_at",
    "cookies",
    "local_storage",
    "session_storage",
    "storage_state_file",
)


def _account_identity(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": account.get("key"),
        "name": account.get("name"),
        "id": account.get("id"),
    }


def _missing_fields(mapping: dict[str, Any], required_fields: tuple[str, ...]) -> list[str]:
    missing = []
    for field in required_fields:
        value = mapping.get(field)
        if value in (None, ""):
            missing.append(field)
    return missing


def _ticket_status_for_account(account: dict[str, Any]) -> dict[str, Any]:
    ticket_path = ticket_path_for_account(str(account["key"]))
    storage_path = storage_state_path_for_account(str(account["key"]))
    status = {
        "account": _account_identity(account),
        "ticket_path": str(ticket_path.resolve()),
        "storage_state_path": str(storage_path.resolve()),
        "state": "missing_ticket",
        "errors": [],
        "warnings": [],
        "ticket_captured_at": None,
        "runnable": False,
    }

    if not ticket_path.exists():
        status["errors"].append("Missing ticket file.")
        return status

    if not storage_path.exists():
        status["state"] = "missing_storage_state"
        status["errors"].append("Missing storage state file.")
        return status

    try:
        ticket_data = load_ticket_bundle(ticket_path)
    except Exception as exc:
        status["state"] = "invalid_ticket"
        status["errors"].append(f"Unable to read ticket file: {exc}")
        return status

    missing_ticket_fields = _missing_fields(ticket_data, REQUIRED_TICKET_FIELDS)
    if missing_ticket_fields:
        status["state"] = "invalid_ticket"
        status["errors"].append(
            "Ticket file is missing required fields: %s." % ", ".join(missing_ticket_fields)
        )
        return status

    try:
        load_storage_state(storage_path)
    except Exception as exc:
        status["state"] = "invalid_storage_state"
        status["errors"].append(f"Unable to read storage state file: {exc}")
        return status

    stored_storage_path = Path(str(ticket_data["storage_state_file"]))
    if stored_storage_path.resolve() != storage_path.resolve():
        status["warnings"].append(
            "Ticket metadata points to a different storage_state_file; worker will use the standard path."
        )

    ticket_account = ticket_data.get("account", {})
    if str(ticket_account.get("key", "")) != str(account["key"]):
        status["warnings"].append("Ticket account key does not match the configured account key.")

    status["state"] = "ready"
    status["runnable"] = True
    status["ticket_captured_at"] = ticket_data.get("captured_at")
    return status


def build_preflight_report(strict: bool = False) -> dict[str, Any]:
    report = {
        "accounts_file": str(ACCOUNTS_PATH.resolve()),
        "strict": strict,
        "status": "failed",
        "errors": [],
        "warnings": [],
        "configured_accounts": [],
        "account_statuses": [],
        "runnable_accounts": [],
        "missing_accounts": [],
    }

    if not ACCOUNTS_PATH.exists():
        report["errors"].append(account_file_missing_message(ACCOUNTS_PATH))
        return report

    try:
        accounts = load_accounts()
    except Exception as exc:
        report["errors"].append(str(exc))
        return report

    report["configured_accounts"] = [_account_identity(account) for account in accounts]

    malformed_accounts = []
    for account in accounts:
        missing_fields = _missing_fields(account, ACCOUNT_REQUIRED_FIELDS)
        if missing_fields:
            malformed_accounts.append(
                {
                    "account": _account_identity(account),
                    "missing_fields": missing_fields,
                }
            )
    if malformed_accounts:
        for item in malformed_accounts:
            report["errors"].append(
                "Configured account [%s] is missing required fields: %s."
                % (item["account"].get("key") or "unknown", ", ".join(item["missing_fields"]))
            )
        return report

    statuses = [_ticket_status_for_account(account) for account in accounts]
    report["account_statuses"] = statuses
    report["runnable_accounts"] = [item["account"] for item in statuses if item["runnable"]]
    report["missing_accounts"] = [item["account"] for item in statuses if not item["runnable"]]

    for status in statuses:
        for warning in status["warnings"]:
            report["warnings"].append("%s: %s" % (status["account"]["key"], warning))

    blocking_states = [item for item in statuses if not item["runnable"]]
    if strict and blocking_states:
        for status in blocking_states:
            for error in status["errors"]:
                report["errors"].append("%s: %s" % (status["account"]["key"], error))
        return report

    if not report["runnable_accounts"]:
        if blocking_states:
            for status in blocking_states:
                for error in status["errors"]:
                    report["errors"].append("%s: %s" % (status["account"]["key"], error))
        report["errors"].append("No runnable accounts are available. Initialize at least one account ticket before starting the worker.")
        return report

    if blocking_states and not strict:
        for status in blocking_states:
            joined = "; ".join(status["errors"]) if status["errors"] else "not initialized"
            report["warnings"].append("%s: %s" % (status["account"]["key"], joined))

    report["status"] = "ok"
    return report


def write_preflight_report(report: dict[str, Any]) -> Path:
    ensure_runtime_dir()
    path = preflight_report_path()
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def format_preflight_summary(report: dict[str, Any]) -> str:
    lines = [
        "95306 preflight",
        "accounts file: %s" % report["accounts_file"],
        "strict mode: %s" % ("on" if report.get("strict") else "off"),
        "status: %s" % report["status"],
    ]
    runnable = ", ".join(item["key"] for item in report.get("runnable_accounts", [])) or "(none)"
    lines.append("runnable accounts: %s" % runnable)

    for item in report.get("account_statuses", []):
        account = item["account"]
        captured_at = item.get("ticket_captured_at") or "-"
        lines.append(
            "[%s] %s | ticket=%s | captured_at=%s"
            % (account["key"], item["state"], "yes" if item["runnable"] else "no", captured_at)
        )

    if report.get("warnings"):
        lines.append("warnings:")
        lines.extend("- %s" % warning for warning in report["warnings"])

    if report.get("errors"):
        lines.append("errors:")
        lines.extend("- %s" % error for error in report["errors"])

    return "\n".join(lines)
