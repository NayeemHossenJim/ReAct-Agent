from __future__ import annotations
from typing import Any
from decimal import Decimal
from settings import get_settings
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, inspect, text

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

mcp = FastMCP("analytics-tools")

def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, datetime):
        return value.isoformat()

    return value

def _is_safe_select(sql: str) -> bool:
    cleaned = sql.strip().lower()

    if not cleaned.startswith("select"):
        return False

    dangerous_words = {
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "truncate",
        "create",
        "grant",
        "revoke",
        "copy",
        "execute",
        "call",
    }

    if ";" in cleaned.rstrip(";"):
        return False

    tokens = set(cleaned.replace(";", " ").split())

    return not bool(tokens.intersection(dangerous_words))

@mcp.tool()
def query_database(sql: str) -> dict[str, Any]:
    """
    Execute one read-only PostgreSQL SELECT query and return rows as JSON objects.
    Use this for questions about products, orders, totals, counts, categories, prices, stock, statuses, or timestamps.
    Only SELECT statements are allowed. Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or multiple statements.
    """
    if not sql or not sql.strip():
        return {
            "ok": False,
            "error": "SQL query is required.",
            "rows": [],
        }

    if not _is_safe_select(sql):
        return {
            "ok": False,
            "error": "Only one read-only SELECT statement is allowed.",
            "rows": [],
        }

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [
                {key: _json_safe(value) for key, value in row._mapping.items()}
                for row in result
            ]

        return {
            "ok": True,
            "row_count": len(rows),
            "rows": rows,
        }

    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "error": f"Database query failed: {str(exc)}",
            "rows": [],
        }

@mcp.tool()
def get_current_time() -> dict[str, Any]:
    """
    Return the current UTC timestamp, day of week, and a simple human-readable time phrase.
    Use this when the user asks about current time, today, now, how many days ago, or time-aware reasoning.
    """
    now = datetime.now(timezone.utc)

    hour = now.hour

    if 5 <= hour < 12:
        part_of_day = "morning"
    elif 12 <= hour < 17:
        part_of_day = "afternoon"
    elif 17 <= hour < 21:
        part_of_day = "evening"
    else:
        part_of_day = "night"

    day = now.strftime("%A")

    return {
        "ok": True,
        "utc_timestamp": now.isoformat(),
        "day_of_week": day,
        "human_readable": f"{part_of_day} on a {day}",
    }

@mcp.tool()
def date_diff(date_a: str, date_b: str) -> dict[str, Any]:
    """
    Accept two ISO-8601 date strings and return the absolute difference in days, hours, and minutes.
    Use this to calculate elapsed time between an order timestamp and the current timestamp.
    """
    try:
        parsed_a = datetime.fromisoformat(date_a.replace("Z", "+00:00"))
        parsed_b = datetime.fromisoformat(date_b.replace("Z", "+00:00"))
    except Exception:
        return {
            "ok": False,
            "error": "Both date_a and date_b must be valid ISO-8601 date strings.",
        }

    delta = abs(parsed_b - parsed_a)
    total_minutes = int(delta.total_seconds() // 60)

    days = total_minutes // (24 * 60)
    remaining_minutes = total_minutes % (24 * 60)
    hours = remaining_minutes // 60
    minutes = remaining_minutes % 60

    return {
        "ok": True,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "total_minutes": total_minutes,
    }

@mcp.tool()
def list_tables() -> dict[str, Any]:
    """
    Return all user-created table names in the connected PostgreSQL database.
    Use this before answering questions about available database schema or unknown tables.
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema="public")

        return {
            "ok": True,
            "tables": tables,
        }

    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "error": f"Could not list tables: {str(exc)}",
            "tables": [],
        }

@mcp.tool()
def describe_table(table_name: str) -> dict[str, Any]:
    """
    Return column names, data types, and nullable flags for a specific PostgreSQL table.
    Use this to understand the schema of products, orders, or any table returned by list_tables.
    """
    if not table_name or not table_name.strip():
        return {
            "ok": False,
            "error": "table_name is required.",
            "columns": [],
        }

    try:
        inspector = inspect(engine)
        available_tables = inspector.get_table_names(schema="public")

        if table_name not in available_tables:
            return {
                "ok": False,
                "error": f"Table '{table_name}' does not exist.",
                "columns": [],
            }

        columns = inspector.get_columns(table_name, schema="public")

        return {
            "ok": True,
            "table": table_name,
            "columns": [
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": bool(column["nullable"]),
                }
                for column in columns
            ],
        }

    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "error": f"Could not describe table: {str(exc)}",
            "columns": [],
        }

if __name__ == "__main__":
    mcp.run()