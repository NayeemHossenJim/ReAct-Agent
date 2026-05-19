# AI Engineer Technical Assessment

Production-oriented AI backend service built for the Backend & AI Engineering Track assessment.

This project exposes an AI assistant API that can answer natural-language analytics questions by using:

- FastAPI for the HTTP API
- LangGraph for agent orchestration
- LangChain for model and tool integration
- MCP for tool serving
- Ollama for local LLM inference
- Qwen2.5 3B as the local language model
- PostgreSQL for structured analytics data

All AI inference runs locally through Ollama. No external LLM APIs are used.

---

## Architecture

```text
User
 ↓
FastAPI API
 ↓
LangGraph ReAct Agent
 ↓
Qwen2.5 3B via Ollama
 ↓
MCP Tool Server
 ↓
PostgreSQL Database
````

---

## Project Structure

```text
.
├── main.py
├── mcp_server.py
├── settings.py
├── requirements.txt
├── .env.example
├── README.md
├── agent/
│   ├── __init__.py
│   └── graph.py
└── db/
    ├── __init__.py
    ├── session.py
    └── schema.sql
```

---

## Requirements

Install the following before running the project:

* Python 3.11+
* Docker
* Ollama
* Git

---

## 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_NAME>
```

---

## 2. Create Python Virtual Environment

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

The `.env` file should contain:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b

DATABASE_URL=postgresql://assess:assess@localhost:5432/analytics

MCP_SERVER_URL=http://localhost:8001/mcp
```

---

## 5. Start Ollama

Pull the required local model:

```bash
ollama pull qwen2.5:3b
```

Start the Ollama server:

```bash
ollama serve
```

Ollama should now be running at:

```text
http://localhost:11434
```

You can verify it with:

```bash
curl http://localhost:11434/api/tags
```

---

## 6. Start PostgreSQL

Start a PostgreSQL 16 container:

```bash
docker run --name pg-assess \
  -e POSTGRES_USER=assess \
  -e POSTGRES_PASSWORD=assess \
  -e POSTGRES_DB=analytics \
  -p 5432:5432 \
  -d postgres:16
```

If the container already exists, start it with:

```bash
docker start pg-assess
```

---

## 7. Run the Database Seed Script

The seed script creates the required `products` and `orders` tables and inserts sample data.

```bash
docker cp db/schema.sql pg-assess:/schema.sql
docker exec -it pg-assess psql -U assess -d analytics -f /schema.sql
```

Verify that the tables were created:

```bash
docker exec -it pg-assess psql -U assess -d analytics -c "\dt"
```

Expected tables:

```text
orders
products
```

Verify the seed data:

```bash
docker exec -it pg-assess psql -U assess -d analytics -c "SELECT COUNT(*) FROM orders;"
docker exec -it pg-assess psql -U assess -d analytics -c "SELECT COUNT(*) FROM products;"
```

Both should return `5`.

---

## 8. Start the MCP Server

Open a new terminal and activate the virtual environment.


### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
python mcp_server.py
```

The MCP server runs at:

```text
http://localhost:8001/mcp
```

The server may not return a normal browser response because MCP Streamable HTTP expects specific headers. This is normal.

---

## 9. Start the FastAPI Server

Open another terminal and activate the virtual environment.

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

If Windows blocks `uvicorn.exe`, use `python -m uvicorn` as shown above.

FastAPI will run at:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

---

## Service Startup Order

Start services in this order:

```text
1. Ollama
2. PostgreSQL
3. MCP server
4. FastAPI server
```

---

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

Example response:

```json
{
  "status": "ok",
  "ollama": "ok",
  "database": "ok",
  "mcp": "ok"
}
```

---

### List Registered Tools

```bash
curl http://localhost:8000/tools
```

This returns the MCP tools currently available to the agent.

Expected tools:

```text
query_database
get_current_time
date_diff
list_tables
describe_table
```

---

### Chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"How many pending orders do we have?"}'
```

Example response:

```json
{
  "answer": "There is 1 pending order.",
  "tool_calls": [
    {
      "tool": "query_database",
      "input": {
        "sql": "SELECT COUNT(*) AS pending_orders FROM orders WHERE status = 'pending';"
      },
      "output": {
        "ok": true,
        "row_count": 1,
        "rows": [
          {
            "pending_orders": 1
          }
        ]
      },
      "error": null
    }
  ],
  "model": "qwen2.5:3b",
  "duration_ms": 1240
}
```

---

### Chat History

```bash
curl http://localhost:8000/history
```

Returns the last 20 chat interactions stored in memory.

Persistence across restarts is not required.

---

## Required Assessment Scenario Tests

### Scenario A — Direct Database Query

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"List all products in the Electronics category with their prices."}'
```

Expected result:

```text
Wireless Keyboard - 49.99
USB-C Hub - 34.99
```

---

### Scenario B — Time-Aware Query

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"How many days ago was the most recent completed order placed?"}'
```

Expected behavior:

* The agent queries the `orders` table.
* The agent uses `get_current_time` or `date_diff`.
* The response explains how long ago the most recent completed order was placed.

---

### Scenario C — Schema Discovery

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What tables are available and what columns does the orders table have?"}'
```

Expected behavior:

* The agent calls `list_tables`.
* The agent calls `describe_table`.
* The response summarizes the available tables and the `orders` columns.

---

### Scenario D — Multi-Step Reasoning

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the total revenue from completed orders, and what percentage of all orders does that represent?"}'
```

Expected result based on seed data:

```text
Completed orders generated 134.97 in revenue and represent 40% of all orders.
```

Calculation:

```text
Completed revenue = 99.98 + 34.99 = 134.97
Completed orders = 2
Total orders = 5
Percentage = 2 / 5 * 100 = 40%
```

---

## MCP Tools

The MCP server exposes the following tools:

### `query_database`

Executes one read-only PostgreSQL `SELECT` query and returns results as JSON objects.

Non-SELECT statements are rejected.

Rejected examples:

```sql
DROP TABLE products;
DELETE FROM orders;
UPDATE products SET price = 0;
```

---

### `get_current_time`

Returns:

* Current UTC timestamp
* Day of week
* Human-readable phrase such as `afternoon on a Wednesday`

---

### `date_diff`

Accepts two ISO-8601 date strings and returns the difference in:

* Days
* Hours
* Minutes
* Total minutes

---

### `list_tables`

Returns all user-created tables in the connected PostgreSQL database.

---

### `describe_table`

Returns schema details for a specific table:

* Column name
* Data type
* Nullable flag

---

## Error Handling

The application returns structured JSON errors for:

* Invalid requests
* Agent failures
* Database query failures
* Missing or unavailable services
* Invalid date input
* Unsafe SQL statements
* Unknown table names

The API avoids exposing raw stack traces to clients.

---

## Troubleshooting

### `/health` shows `mcp: error`

Make sure the MCP server is running:

```bash
python mcp_server.py
```

Then restart FastAPI.

Startup order matters:

```text
1. Ollama
2. PostgreSQL
3. MCP server
4. FastAPI
```

---

### `/health` shows `database: ok`, but queries say tables do not exist

The database is running, but the seed script was not applied.

Run:

```bash
docker cp db/schema.sql pg-assess:/schema.sql
docker exec -it pg-assess psql -U assess -d analytics -f /schema.sql
```

Then restart the MCP and FastAPI servers.

---

### Windows blocks `uvicorn.exe`

Run Uvicorn as a Python module:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

If reload causes issues:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### PowerShell `curl` gives an MCP event-stream error

PowerShell aliases `curl` to `Invoke-WebRequest`.

The MCP endpoint expects Streamable HTTP requests and may reject simple browser-style requests.

This is normal if the FastAPI `/tools` endpoint successfully lists the tools.

Use this to verify MCP integration:

```bash
curl http://localhost:8000/tools
```

---

## Development Notes

The agent uses a ReAct-style LangGraph loop with:

```text
reason
act
should_continue
```

The loop is capped at 10 iterations to prevent infinite cycles.

Each `/chat` response includes a structured `tool_calls` trace showing:

* Tool name
* Tool input
* Tool output
* Tool error, if any

---


## Bonus Features

No bonus features implemented.
