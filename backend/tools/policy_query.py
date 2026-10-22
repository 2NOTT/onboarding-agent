"""Tool: query_policies 查询制度知识库。

支持关键词/类型/版本检索，优先返回当前生效版本。
"""
from typing import Any, Dict, List

from backend.tools.util import load_policies

CONTENT_MAX_LEN = 1500


def _sort_key(p: Dict[str, Any]):
    # 生效版本优先，其次按生效日期倒序（最新优先）
    return (0 if p.get("status") == "active" else 1, p.get("effective_date", ""), p.get("version", ""))


async def run(params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    keyword = (params.get("keyword") or "").strip()
    policy_type = (params.get("policy_type") or "").strip().lower()
    version = (params.get("version") or "").strip()
    include_deprecated = bool(params.get("include_deprecated", False))

    policies: List[Dict[str, Any]] = load_policies()
    result = []
    for p in policies:
        if not include_deprecated and p.get("status") != "active":
            continue
        if policy_type and p.get("type") != policy_type:
            continue
        if version and p.get("version") != version:
            continue
        if keyword:
            hay = " ".join([
                p.get("name", ""), p.get("summary", ""), p.get("content", ""),
                " ".join(p.get("keywords", [])),
            ])
            if keyword not in hay:
                continue
        result.append(p)

    result.sort(key=_sort_key)
    items = []
    for p in result:
        content = p.get("content", "")
        truncated = len(content) > CONTENT_MAX_LEN
        items.append({
            "policy_id": p.get("policy_id"),
            "name": p.get("name"),
            "type": p.get("type"),
            "type_label": p.get("type_label"),
            "version": p.get("version"),
            "effective_date": p.get("effective_date"),
            "status": p.get("status"),
            "scope": p.get("scope"),
            "summary": p.get("summary"),
            "content": content[:CONTENT_MAX_LEN] + ("…（正文已截断）" if truncated else ""),
            "keywords": p.get("keywords", []),
        })

    return {
        "filter": {
            "keyword": keyword, "policy_type": policy_type,
            "version": version, "include_deprecated": include_deprecated,
        },
        "count": len(items),
        "policies": items,
    }
