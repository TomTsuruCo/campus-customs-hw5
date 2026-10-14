"""Append-preserving JSON audit log for agent, delegation, and MCP activity."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"
_WRITE_LOCK = threading.Lock()
_SECRET_WORDS = ("api_key", "authorization", "secret", "password", "access_token", "refresh_token")
_PRIVATE_WORDS = ("requester", "customer_email", "email_address", "phone_number", "street_address")


def _safe(value: Any, *, depth: int = 0) -> Any:
    """Bound audit payload size and redact credential-shaped fields defensively."""
    if depth > 8:
        return "[depth limit]"
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            label = str(key)
            lowered = label.lower()
            if any(word in lowered for word in _SECRET_WORDS) or lowered in _PRIVATE_WORDS:
                result[label] = "[redacted]"
            else:
                result[label] = _safe(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value[:6000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:1000]


def read_recent_events(*, limit: int = 50, ticket_id: int | None = None) -> list[dict[str, Any]]:
    """Return the newest audit records (oldest first) shaped for a dashboard refresh."""
    with _WRITE_LOCK:
        if not AUDIT_PATH.exists():
            return []
        try:
            history = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Audit log is not valid JSON: {AUDIT_PATH}") from exc
    if not isinstance(history, list):
        raise RuntimeError(f"Audit log root must be a JSON array: {AUDIT_PATH}")
    if ticket_id is not None:
        history = [item for item in history if item.get("ticket_id") == ticket_id]
    return [_dashboard_event(item) for item in history[-limit:]]


def _dashboard_event(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten one audit record into who acted, what they said, and which tool they used."""
    kind = item.get("kind", "")
    report = item.get("report") if isinstance(item.get("report"), dict) else None
    event = {
        "event_id": item.get("event_id"),
        "timestamp_utc": item.get("timestamp_utc"),
        "run_id": item.get("run_id"),
        "ticket_id": item.get("ticket_id"),
        "kind": kind,
        "agent": item.get("agent") or item.get("to_agent") or item.get("actor"),
        "from_agent": item.get("from_agent"),
        "tool_name": item.get("tool_name"),
        "tool_arguments": item.get("arguments"),
        "tool_output": item.get("output"),
        "said": report.get("summary") if report else item.get("task"),
        "findings": report.get("findings") if report else None,
        "recommendation": report.get("recommendation") if report else None,
        "recommended_status": report.get("recommended_status") if report else None,
        "human_action_required": report.get("human_action_required") if report else None,
        "usage": item.get("usage") if isinstance(item.get("usage"), dict) else None,
        "error": item.get("error") or item.get("error_type") or item.get("reason"),
        "resolution": item.get("resolution"),
        "resolved_by": item.get("resolved_by"),
    }
    return {key: value for key, value in event.items() if value is not None}


def append_event(event: dict[str, Any]) -> dict[str, Any]:
    """Append one event while preserving the existing JSON-array history."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event_id": str(uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        **_safe(event),
    }
    with _WRITE_LOCK:
        if AUDIT_PATH.exists():
            try:
                history = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Audit log is not valid JSON; refusing to replace it: {AUDIT_PATH}") from exc
            if not isinstance(history, list):
                raise RuntimeError(f"Audit log root must be a JSON array; refusing to replace it: {AUDIT_PATH}")
        else:
            history = []
        history.append(record)
        temporary = AUDIT_PATH.with_name(f"{AUDIT_PATH.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(history, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(AUDIT_PATH)
        finally:
            if temporary.exists():
                temporary.unlink()
    return record
