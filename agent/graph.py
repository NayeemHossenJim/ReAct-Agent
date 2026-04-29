from __future__ import annotations

import json
import time
from typing import Any, Literal, TypedDict
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from settings import get_settings

SYSTEM_PROMPT = """You are an internal analytics assistant.

You can answer questions about a PostgreSQL database containing products and orders.

Database facts:
- The products table has product records.
- The orders table has order records.
- Use tools instead of guessing.

Rules:
1. Use tools when the question requires database data, schema details, current time, or date math.
2. Never invent database values.
3. Prefer list_tables and describe_table if you do not know the schema.
4. Use query_database only for safe SELECT queries.
5. Give a short, clear final answer.
6. When numbers are calculated, explain the calculation briefly.
7. If a tool returns an error, explain the error clearly.
"""

class ToolTraceItem(TypedDict):
    tool: str
    input: Any
    output: Any
    error: str | None

class AgentState(TypedDict):
    messages: list[BaseMessage]
    iterations: int
    tool_calls: list[ToolTraceItem]

class AnalyticsAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_name = self.settings.ollama_model
        self.tools = []
        self.tools_by_name = {}
        self.graph = None
        self.llm_with_tools = None

    async def startup(self) -> None:
        client = MultiServerMCPClient(
            {
                "analytics": {
                    "url": self.settings.mcp_server_url,
                    "transport": "streamable_http",
                }
            }
        )

        self.tools = await client.get_tools()
        self.tools_by_name = {tool.name: tool for tool in self.tools}

        llm = ChatOllama(
            model=self.settings.ollama_model,
            base_url=self.settings.ollama_base_url,
            temperature=0,
        )

        self.llm_with_tools = llm.bind_tools(self.tools)
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("reason", self._reason)
        workflow.add_node("act", self._act)

        workflow.set_entry_point("reason")

        workflow.add_conditional_edges(
            "reason",
            self._should_continue,
            {
                "act": "act",
                "end": END,
            },
        )

        workflow.add_edge("act", "reason")

        return workflow.compile()

    async def _reason(self, state: AgentState) -> AgentState:
        if self.llm_with_tools is None:
            raise RuntimeError("Agent was not started. Call startup() first.")

        response = await self.llm_with_tools.ainvoke(state["messages"])

        return {
            **state,
            "messages": [*state["messages"], response],
            "iterations": state["iterations"] + 1,
        }

    async def _act(self, state: AgentState) -> AgentState:
        last_message = state["messages"][-1]

        if not isinstance(last_message, AIMessage):
            return state

        new_messages: list[BaseMessage] = []
        new_traces: list[ToolTraceItem] = []

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call["id"]

            tool = self.tools_by_name.get(tool_name)

            if tool is None:
                output = {
                    "ok": False,
                    "error": f"Unknown tool: {tool_name}",
                }
            else:
                try:
                    output = await tool.ainvoke(tool_args)
                except Exception as exc:
                    output = {
                        "ok": False,
                        "error": str(exc),
                    }

            new_traces.append(
                {
                    "tool": tool_name,
                    "input": tool_args,
                    "output": output,
                    "error": output.get("error") if isinstance(output, dict) else None,
                }
            )

            new_messages.append(
                ToolMessage(
                    content=json.dumps(output, default=str),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )

        return {
            **state,
            "messages": [*state["messages"], *new_messages],
            "tool_calls": [*state["tool_calls"], *new_traces],
        }

    def _should_continue(self, state: AgentState) -> Literal["act", "end"]:
        if state["iterations"] >= 10:
            return "end"

        last_message = state["messages"][-1]

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "act"

        return "end"

    async def ask(self, question: str) -> dict[str, Any]:
        if self.graph is None:
            raise RuntimeError("Agent was not started. Call startup() first.")

        start = time.perf_counter()

        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=question),
            ],
            "iterations": 0,
            "tool_calls": [],
        }

        final_state = await self.graph.ainvoke(initial_state)

        duration_ms = int((time.perf_counter() - start) * 1000)

        answer = self._extract_answer(final_state["messages"])

        return {
            "answer": answer,
            "tool_calls": final_state["tool_calls"],
            "model": self.model_name,
            "duration_ms": duration_ms,
        }

    def _extract_answer(self, messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                if isinstance(message.content, str):
                    return message.content
                return str(message.content)

        return "I could not produce an answer."

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {
                "name": tool.name,
                "description": getattr(tool, "description", "") or "",
            }
            for tool in self.tools
        ]