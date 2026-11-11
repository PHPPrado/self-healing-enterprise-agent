"""FastAPI entrypoint for the self-healing enterprise agent."""

from __future__ import annotations

import json as _json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.adapters.cloud_adapter import get_cloud_adapter
from app.config import settings
from app.core.self_healing_engine import SelfHealingAgentEngine
from app.schemas.agent_response import AgentExecutionResponse, HealthResponse

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return _json.dumps(payload)


logging.basicConfig(level=logging.INFO)
for _h in logging.root.handlers:
    _h.setFormatter(_JsonFormatter())
logger = logging.getLogger("self-healing-agent")


class ExecuteRequest(BaseModel):
    user_goal: str = Field(..., min_length=3, description="Natural language instruction")
    tool_name: str = Field(default="create_purchase_order", description="Target enterprise tool")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting self-healing agent (provider=%s)", settings.cloud_provider.value)
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    adapter = get_cloud_adapter()
    ok = await adapter.health_check()
    if not ok:
        raise HTTPException(status_code=503, detail="Cloud adapter unhealthy")
    return HealthResponse(
        status="ok",
        cloud_provider=settings.cloud_provider.value,
        llm_mode="mock" if settings.is_mock_llm else "remote",
    )


@app.post("/api/v1/agent/execute", response_model=AgentExecutionResponse)
async def execute(request: ExecuteRequest) -> AgentExecutionResponse:
    engine = SelfHealingAgentEngine()
    result = await engine.execute(user_goal=request.user_goal, tool_name=request.tool_name)
    return AgentExecutionResponse(**result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
