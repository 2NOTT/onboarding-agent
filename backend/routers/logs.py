"""执行日志接口。"""
from fastapi import APIRouter, HTTPException

from backend.core import logger

router = APIRouter()


@router.get("/logs")
def list_logs(limit: int = 100):
    return logger.list_logs(limit=limit)


@router.get("/logs/{log_id}")
def get_log(log_id: str):
    log = logger.get_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail=f"未找到执行日志 {log_id}")
    return log
