from __future__ import annotations

import httpx
from typing import Any
from sqlalchemy import text
from db.session import get_engine
from settings import get_settings
from pydantic import BaseModel, Field
from agent.graph import AnalyticsAgent
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException

settings = get_settings()

app = FastAPI(
    title="AI Engineer Technical Assessment API",
    version="1.0.0",
)

agent = AnalyticsAgent()
history: list[dict[str, Any]] = []

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

class ToolCallRecord(BaseModel):
    tool: str
    input: Any
    output: Any
    error: str | None = None

class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallRecord]
    model: str
    duration_ms: int

class HealthResponse(BaseModel):
    status: str
    ollama: str
    database: str
    mcp: str

class ToolInfo(BaseModel):
    name: str
    description: str

@app.on_event("startup")
async def startup_event() -> None:
    try:
        await agent.startup()
    except Exception as exc:
        print(f"Agent startup failed: {exc}")

@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = await agent.ask(payload.question)

        history.append(
            {
                "question": payload.question,
                "answer": result["answer"],
                "tool_calls": result["tool_calls"],
                "model": result["model"],
                "duration_ms": result["duration_ms"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        del history[:-20]

        return ChatResponse(**result)

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Agent request failed.",
                "message": str(exc),
            },
        )

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ollama_status = await check_ollama()
    database_status = check_database()
    mcp_status = await check_mcp()

    overall = (
        "ok"
        if all(status == "ok" for status in [ollama_status, database_status, mcp_status])
        else "degraded"
    )

    return HealthResponse(
        status=overall,
        ollama=ollama_status,
        database=database_status,
        mcp=mcp_status,
    )


@app.get("/tools", response_model=list[ToolInfo])
async def tools() -> list[ToolInfo]:
    return [ToolInfo(**tool) for tool in agent.list_tools()]

@app.get("/history")
async def get_history() -> list[dict[str, Any]]:
    return list(reversed(history))

async def check_ollama() -> str:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            return "ok" if response.status_code == 200 else "error"
    except Exception:
        return "error"

def check_database() -> str:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"

async def check_mcp() -> str:
    try:
        if agent.list_tools():
            return "ok"

        await agent.startup()

        return "ok" if agent.list_tools() else "error"

    except Exception:
        return "error"