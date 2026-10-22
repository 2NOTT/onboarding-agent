"""执行日志模块：每次用户提问的完整执行轨迹持久化到 execution_logs.json。"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.services import json_store

LOG_FILE = "execution_logs"


def new_log_id() -> str:
    return f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


def save_execution(result: Dict[str, Any]) -> None:
    entry = dict(result)
    entry.setdefault("log_id", new_log_id())
    entry.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    json_store.append(LOG_FILE, entry)


def list_logs(limit: int = 100) -> List[Dict[str, Any]]:
    logs = json_store.load(LOG_FILE, []) or []
    summaries = []
    for log in reversed(logs[-limit:]):
        summaries.append({
            "log_id": log.get("log_id"),
            "created_at": log.get("created_at"),
            "employee_id": log.get("employee_id"),
            "employee_name": (log.get("employee") or {}).get("name"),
            "question": log.get("question"),
            "risk_level": (log.get("risk_result") or {}).get("risk_level"),
            "passed": (log.get("risk_result") or {}).get("passed"),
            "mock_mode": log.get("mock_mode"),
            "planner_engine": log.get("planner_engine"),
            "step_count": len(log.get("steps") or []),
            "duration_ms": log.get("duration_ms"),
        })
    return summaries


def get_log(log_id: str) -> Optional[Dict[str, Any]]:
    for log in json_store.load(LOG_FILE, []) or []:
        if log.get("log_id") == log_id:
            return log
    return None
