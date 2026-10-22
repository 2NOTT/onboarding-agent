"""本地 JSON 数据读写模块：所有模拟数据的唯一入口。"""
import json
import os
import threading
from typing import Any, Optional

from backend.config import BASE_DIR

DATA_DIR = os.path.join(BASE_DIR, "backend", "data")

_global_lock = threading.Lock()


def _path(name: str) -> str:
    if not name.endswith(".json"):
        name = name + ".json"
    return os.path.join(DATA_DIR, name)


def load(name: str, default: Optional[Any] = None) -> Any:
    """读取 JSON 文件；文件不存在时返回 default。"""
    p = _path(name)
    if not os.path.exists(p):
        return default
    with _global_lock:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)


def save(name: str, data: Any) -> None:
    """原子写回 JSON 文件。"""
    p = _path(name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with _global_lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)


def append(name: str, item: Any) -> None:
    """向 JSON 数组文件追加一条记录（用于执行日志）。"""
    p = _path(name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with _global_lock:
        data = []
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        data.append(item)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
