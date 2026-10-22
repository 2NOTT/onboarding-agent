"""应用入口：python -m backend.main  或  uvicorn backend.main:app"""
import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import BASE_DIR, settings
from backend.routers import agent, logs, skills, tools

app = FastAPI(
    title="企业入职助手 · Plan + Skill 可配置执行平台",
    description="本地 JSON 模拟数据的入职助手 MVP：Planner 生成计划，Executor 按 步骤调用 Skill 与 Tool，最终回复经合规风控审核。",
    version="0.1.0",
)

app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(tools.router, prefix="/api", tags=["tools"])
app.include_router(logs.router, prefix="/api", tags=["logs"])

# 前端静态资源（放在 API 路由之后挂载）
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    print(f"Server running at http://localhost:{settings.PORT}  (mock_mode={settings.mock_mode})")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=settings.PORT, reload=False)
