# 📚 AI Smart Library Assistant: Model Context Protocol (MCP)

> **Use Case:** An intelligent conversational AI agent designed for library members and librarians to search catalog availability, manage book loans and returns, inspect official borrowing and fee policies, and generate automated administrative inventory reports.

This project delivers a complete, production-grade **Model Context Protocol (MCP)** implementation end to end, featuring an MCP Server exposing multiple external resources as typed tools, a user-defined custom MCP Client with an autonomous multi-turn LLM agent loop, an interactive CLI application, and automated verification suites.

---

## 🏛 Architecture Overview

```
 ┌──────────────────────────────────────────────────────────────┐
 │                     User / Client Shell                      │
 │      (library_agent_app.py  /  demo_task.py  /  REPL)        │
 └──────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │             Custom MCP Client (library_mcp_client.py)        │
 │  • Initializes stdio / HTTP ClientSession                    │
 │  • Discovers Server Tools, Resources, and Prompts            │
 │  • Maps MCP Schemas to LLM Function Declarations             │
 │  • Orchestrates Autonomous Multi-Turn Reasoning Loop         │
 └──────────────┬───────────────────────────────▲───────────────┘
                │ JSON-RPC (stdio / HTTP)       │ Function Responses
                ▼                               │
 ┌──────────────────────────────────────────────────────────────┐
 │             MCP Server (library_mcp_server.py)               │
 │  • Pure Stdio (stdout strictly reserved for JSON-RPC framing)│
 │  • Stderr & File logging for debugging and audit safety       │
 │  • Exposes 7 typed tools, 2 live resources, 2 prompt templates│
 └──────────────┬───────────────────────────────┬───────────────┘
                │                               │
                ▼                               ▼
 ┌──────────────────────────────┐ ┌──────────────────────────────┐
 │ Resource 1: SQLite Database  │ │ Resource 2: Local Filesystem │
 │ • Catalog Table (books)      │ │ • Policy Docs (Markdown)     │
 │ • Loan Records Table         │ │ • Exported Circulation Rpts  │
 │ • Real-time Inventory Counts │ │ • Structured Audit Event Log │
 └──────────────────────────────┘ └──────────────────────────────┘
```

---

## 🔌 External Resources

The application connects to **two distinct external resources**:

1. **Resource 1: SQLite Catalog & Circulation Database (`library.db`)**
   - **Catalog Table (`books`)**: Maintains book IDs, titles, authors, and available copies.
   - **Circulation Table (`borrow_records`)**: Tracks active and returned loans with patron names, checkout timestamps, and loan status.
   - **Live In-Memory Aggregations**: Computes real-time catalog statistics, active loan ratios, and copy counts.

2. **Resource 2: Local Filesystem Storage (`data/`)**
   - **Policy Documents (`data/policies/*.md`)**: Official guidelines for `general` borrowing rules (14-day checkout, 5-book limit), `fines` ($0.25/day overdue penalty, grace periods), and `renewals` (2-time limit).
   - **Exported Reports (`data/reports/*.md`)**: Auto-generated Markdown circulation audit reports capturing inventory summaries and active borrower records.
   - **Operational Audit Log (`data/logs/audit.log`)**: Append-only JSON-lines record of every library action for compliance and activity tracking.

---

## 🛠 MCP Tools Specification

All tools feature **typed schemas**, comprehensive docstrings, and **actionable error recovery hints** returned directly in results so the LLM can self-correct when an invalid ID or out-of-stock item is encountered.

### 1. Catalog & Circulation Tools (Resource 1: Database)

| Tool Name | Parameters | Description |
|---|---|---|
| `search_books` | `query: str = ""` (title keyword)<br>`author: str = ""` (author keyword) | Search the catalog database by title or author. Returns book IDs, titles, authors, and available copy counts. |
| `add_book` | `title: str` (non-empty)<br>`author: str` (non-empty)<br>`copies: int = 1` (>= 1) | Add a new book title or replenish available copies of an existing title in the catalog. |
| `borrow_book` | `book_id: int` (catalog ID)<br>`patron_name: str` (borrower name) | Check out a book copy for a patron. Decrements available copies and registers an active loan. |
| `return_book` | `book_id: int` (catalog ID)<br>`patron_name: str = ""` | Return a borrowed book into inventory, increasing shelf copies and closing active loans. |

### 2. Filesystem & Documentation Tools (Resource 2: Filesystem)

| Tool Name | Parameters | Description |
|---|---|---|
| `read_library_policy` | `topic: str = "general"`<br>(Options: `'general'`, `'fines'`, `'renewals'`) | Reads Markdown policy documents from the local filesystem. Provides borrowing rules, fee schedules, or renewal limits. |
| `export_circulation_report` | `report_title: str = "Daily Circulation Summary"` | Compiles current database metrics and writes a timestamped Markdown report into `data/reports/`. |
| `view_audit_logs` | `limit: int = 10` (max 50) | Reads the most recent chronological audit events from `data/logs/audit.log`. |

---

## 🌟 Stretch Goals Implemented

- ✅ **Dual Transport Support:** Runs over standard `stdio` (default) or **Streamable HTTP** (`--transport streamable-http --port 8000`).
- ✅ **MCP Resources:**
  - `library://catalog/summary`: Live JSON snapshot of total titles, total shelf copies, and active checkouts.
  - `library://policies/borrowing_rules`: Full text of official library circulation policies.
- ✅ **MCP Prompts:**
  - `borrow_workflow_prompt`: Guided multi-step prompt for searching, policy validation, and borrowing.
  - `circulation_audit_prompt`: Administrative workflow for auditing system logs and exporting reports.
- ✅ **Custom User-Defined MCP Client (`library_mcp_client.py`):**
  - Fully written from scratch using Python `mcp` SDK.
  - Dynamic discovery via `session.list_tools()`.
  - Native multi-turn autonomous agent loop with Gemini API (`google-genai`).
  - Automatic model fallback and retry resilience.

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.10+
- Node.js & `npx` (optional, for MCP Inspector)

### 2. Environment Setup
Clone the repository and activate your virtual environment:

```bash
cd ai_library
source ../.venv/bin/activate
```

Create or verify your `.env` file in the project or parent directory:
```env
GEMINI_API_KEY="your-gemini-api-key-here"
GEMINI_MODEL="gemini-3.8-flash"
```

### 3. Install Dependencies
```bash
pip install mcp mcp-types google-genai python-dotenv starlette uvicorn
```

---

## 🧪 Testing with MCP Inspector

Before connecting custom clients, verify the MCP Server using the official `@modelcontextprotocol/inspector`:

```bash
npx @modelcontextprotocol/inspector /home/ela/Documents/codeProjects/icog/Trainings/training-6/.venv/bin/python library_mcp_server.py
```

The inspector UI allows you to interactively:
1. View all 7 registered tools with their input JSON schemas.
2. Execute tool calls (e.g. `search_books` or `read_library_policy`) and inspect JSON responses.
3. Inspect exposed resources (`library://catalog/summary`).
4. Trigger prompts (`borrow_workflow_prompt`).

---

## 💻 Running the Application

### 1. Interactive AI Assistant (REPL)
Launch the interactive assistant shell:
```bash
python library_agent_app.py
```

Interactive commands:
- Type natural questions: *"Can you find Dune and check out a copy for Alice?"*
- `/tools`: List all tools loaded dynamically from the MCP server.
- `/resources`: List available MCP resources.
- `/summary`: Read live catalog summary resource snapshot.
- `/rules`: Read library borrowing guidelines.
- `/help`: Show command help.
- `/quit`: Exit.

### 2. Single Command-Line Query
Execute a single instruction directly through the agent loop:
```bash
python library_agent_app.py --prompt "What is our policy on overdue fines, and export a circulation report."
```

### 3. Automated End-to-End Demo Script
Run the automated verification demo testing all tools and resources:
```bash
python demo_task.py
```

**Demo Execution Workflow:**
1. Connects to `library_mcp_server.py` over MCP `stdio`.
2. Discovers tools, resources, and prompt definitions.
3. Searches catalog database for book availability (Resource 1: DB).
4. Borrows a copy for patron 'Alice Smith' (Resource 1: DB).
5. Reads borrowing rules and grace periods from disk (Resource 2: Filesystem).
6. Exports a circulation markdown audit report to `data/reports/` (Resource 2: Filesystem).
7. Reads recent audit trail logs (Resource 2: Filesystem).
8. Reads dynamic MCP resource `library://catalog/summary`.

---

## 📂 Project Structure

```
ai_library/
├── ai_library_service.py      # Core service handling SQLite DB and local filesystem resources
├── library_mcp_server.py      # Stdio & Streamable HTTP MCP Server with tools, resources, prompts
├── library_mcp_client.py      # Custom MCP Client & multi-turn LLM agent loop
├── library_agent_app.py       # Interactive CLI end-user AI library application
├── demo_task.py               # Automated end-to-end demonstration script
├── library.db                 # SQLite database file (books & borrow_records)
├── data/
│   ├── policies/              # Policy markdown files (general.md, fines.md, renewals.md)
│   ├── reports/               # Auto-generated circulation reports
│   └── logs/                  # Audit log (audit.log) & server logs
├── README.md                  # Comprehensive project documentation
└── SUMMARY.md                 # Architecture summary note
```

---

## 🔒 Safety & Standards
- **Zero Stdout Contamination:** In stdio mode, Python standard logging is restricted to `sys.stderr` and disk log files. Stdout is exclusively reserved for JSON-RPC protocol framing.
- **Secret Protection:** API keys and credentials are read strictly from `.env` and environment variables; never hardcoded or printed to stdout.
- **Actionable Error Feedback:** Exceptions and validation failures return informative error structures with recovery suggestions so the AI agent can self-heal.
