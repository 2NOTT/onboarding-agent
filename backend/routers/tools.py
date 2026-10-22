"""Tool 管理接口：列表 / 详情。"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core import tool_registry

router = APIRouter()


class ToolUpdateRequest(BaseModel):
    enabled: Optional[bool] = None


@router.get("/tools")
def list_tools():
    return tool_registry.load_tools()


@router.get("/tools/{tool_name}")
def get_tool(tool_name: str):
    tool = tool_registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"未找到 Tool {tool_name}")
    return tool


@router.put("/tools/{tool_name}")
def update_tool(tool_name: str, req: ToolUpdateRequest):
    """MVP 仅支持启用/禁用 Tool。"""
    tools = tool_registry.load_tools()
    for t in tools:
        if t.get("name") == tool_name:
            if req.enabled is not None:
                t["enabled"] = bool(req.enabled)
            from backend.services import json_store
            json_store.save("tools", {"tools": tools})
            return t
    raise HTTPException(status_code=404, detail=f"未找到 Tool {tool_name}")
