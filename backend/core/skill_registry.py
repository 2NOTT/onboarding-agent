"""Skill 注册与加载机制。

- Skill 元数据（名称、描述、Prompt、模型参数、启用状态）保存在 skills.json。
- 每次访问都从文件重新读取，保证后台保存后前台立即生效。
- Skill 执行体 = Prompt（来自配置） + 大模型调用；Mock 模式下回退到本地规则实现。
"""
from typing import Any, Dict, List, Optional

from backend.services import json_store

SKILL_TYPES = [
    "question_structuring",
    "task_decision",
    "process_explainer",
    "policy_qa",
    "communication",
    "compliance_check",
]


def load_skills() -> List[Dict[str, Any]]:
    return json_store.load("skills", {}).get("skills", [])


def list_enabled() -> List[Dict[str, Any]]:
    return [s for s in load_skills() if s.get("enabled", False)]


def get(skill_id: str) -> Optional[Dict[str, Any]]:
    for s in load_skills():
        if s.get("skill_id") == skill_id:
            return s
    return None


def get_by_type(skill_type: str) -> Optional[Dict[str, Any]]:
    for s in load_skills():
        if s.get("type") == skill_type:
            return s
    return None


def is_enabled(skill_id: str) -> bool:
    s = get(skill_id)
    return bool(s) and bool(s.get("enabled", False))


VALID_MODEL_PARAMS = {"model", "temperature", "max_tokens"}


def update(skill_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新 Skill 配置并持久化。返回更新后的 Skill；不存在返回 None。"""
    data = json_store.load("skills", {})
    skills = data.get("skills", [])
    for s in skills:
        if s.get("skill_id") == skill_id:
            if "name" in patch:
                name = (patch.get("name") or "").strip()
                if not name:
                    raise ValueError("Skill 名称不能为空")
                s["name"] = name
            if "description" in patch:
                s["description"] = (patch.get("description") or "").strip()
            if "prompt" in patch:
                prompt = patch.get("prompt") or ""
                if not prompt.strip():
                    raise ValueError("Skill Prompt 不能为空")
                s["prompt"] = prompt
            if "enabled" in patch:
                s["enabled"] = bool(patch["enabled"])
            if "model_params" in patch:
                mp = patch.get("model_params") or {}
                current = s.get("model_params", {})
                merged = {k: current.get(k) for k in VALID_MODEL_PARAMS}
                if "model" in mp:
                    merged["model"] = (mp.get("model") or "").strip()
                if "temperature" in mp and mp["temperature"] is not None:
                    temp = float(mp["temperature"])
                    if not (0 <= temp <= 2):
                        raise ValueError("temperature 取值范围为 0-2")
                    merged["temperature"] = temp
                if "max_tokens" in mp and mp["max_tokens"] is not None:
                    mt = int(mp["max_tokens"])
                    if not (64 <= mt <= 8192):
                        raise ValueError("max_tokens 取值范围为 64-8192")
                    merged["max_tokens"] = mt
                s["model_params"] = merged
            json_store.save("skills", data)
            return s
    return None


def save_last_test(skill_id: str, test: Dict[str, Any]) -> None:
    data = json_store.load("skills", {})
    for s in data.get("skills", []):
        if s.get("skill_id") == skill_id:
            s["last_test"] = test
            json_store.save("skills", data)
            return
