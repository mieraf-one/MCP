# 📚 AI Library Assistant (Model Context Protocol)

> **Use Case:** An AI-powered library assistant designed for patrons and librarians to search catalog availability, manage book checkouts and returns, and inspect library policies using natural language.

This project implements an end-to-end **Model Context Protocol (MCP)** application consisting of an MCP Server that exposes tools over SQLite and local files, and a custom user-defined MCP Client that connects the server's tools to Google's Gemini LLM.

---

## 📝 Summary Note: Architecture & How Pieces Fit Together

### 1. What Was Built
- **`database/db.py` (Database Layer):** A Python SQLite wrapper managing `library.db` with thread-safe connections, table initialization, and CRUD operations for books and available copies.
- **`server.py` (MCP Server):** A Model Context Protocol server built with `mcp.server.mcpserver.MCPServer`. It exposes six typed tools (five database tools + one local file tool) and one prompt (`find_book_prompt`). Operates cleanly over `stdio` without corrupting stdout.
- **`client.py` (Custom MCP Client):** A user-defined client that launches the server process, connects via `stdio_client`, dynamically queries `session.list_tools()`, maps them to Gemini `FunctionDeclaration` objects, and orchestrates an autonomous multi-turn tool calling loop.
- **`library_policy.txt` (Local Filesystem Resource):** A text document containing official borrowing duration rules, checkout limits, and late fee structures.

### 2. How the Pieces Fit Together

```
 [ User Prompt in Terminal ]
              │
              ▼
    ┌───────────────────┐
    │     client.py     │ <───── (1) Connects via stdio & discovers tools
    └─────────┬─────────┘
              │
              ├───────────────────────────────────┐
              ▼                                   ▼
    ┌───────────────────┐               ┌───────────────────┐
    │ Gemini 3.8 Flash  │               │     server.py     │
    │  (LLM Reasoning)  │               │   (MCP Server)    │
    └─────────┬─────────┘               └─────────┬─────────┘
              │                                   │
              │ (2) Generates Tool Call           │ (3) Executes Tool
              └──────────────────────────────────>│
                                                  ├──────────────┬──────────────┐
                                                  ▼                             ▼
                                        ┌───────────────────┐         ┌───────────────────┐
                                        │  database/db.py   │         │ library_policy.txt│
                                        │ (Resource 1: DB)  │         │ (Resource 2: File)│
                                        └───────────────────┘         └───────────────────┘
```

1. **Discovery:** When `client.py` starts, it initializes an MCP session with `server.py` and inspects all registered tools.
2. **LLM Tool Binding:** The client converts MCP JSON schemas into Gemini function declarations and delivers them with the user's prompt to Gemini.
3. **Execution Loop:** When Gemini decides to call tools (e.g. `search_book` and `read_library_policy`), the client catches the function calls, executes them via `session.call_tool()`, and feeds the results back to Gemini.
4. **Final Response:** Gemini synthesizes the structured tool results into a natural, conversational response for the user.

---

## 🔌 External Resources Used

The application interfaces with **two distinct external resources**:
1. **Resource 1: SQLite Database (`library.db`)**
   - Stores catalog records (`id`, `title`, `author`, `available_copies`).
2. **Resource 2: Local Filesystem (`library_policy.txt`)**
   - Stores official library rules regarding checkout limits (5 books), loan durations (14 days), and overdue fines ($0.25/day).

---

## 🛠️ List of Tools & Example Calls

| Tool Name | Parameters | Description |
|---|---|---|
| `search_book` | `title: str = ""` | Search catalog for books matching a title keyword. |
| `add_book` | `title: str`, `author: str`, `copies: int = 1` | Add a new book or replenish copies in inventory. |
| `update_book` | `id: int`, `copies: int` | Update the available copy count of a book by ID. |
| `borrow_book` | `id: int` | Borrow one available copy of a book by ID. |
| `return_book` | `id: int` | Return a copy of a book to the library by ID. |
| `read_library_policy` | *(None)* | Read loan duration, limits, and fine rules from local disk. |

### Example Tool Calls (JSON-RPC)

#### 1. Search for a Book
```json
{
  "name": "search_book",
  "arguments": {
    "title": "Ethiopia"
  }
}
```
**Example Result:**
```json
[
  {
    "id": 3,
    "title": "Ethiopia",
    "author": "Elyas",
    "available_copies": 7
  }
]
```

#### 2. Borrow a Book
```json
{
  "name": "borrow_book",
  "arguments": {
    "id": 3
  }
}
```
**Example Result:**
`"Book 3 borrowed successfully"`

#### 3. Read Library Policy
```json
{
  "name": "read_library_policy",
  "arguments": {}
}
```
**Example Result:**
`"Library Policies:\n1. Standard loan duration is 14 days.\n2. Patrons may borrow up to 5 books at a time.\n3. Overdue fine is $0.25 per day."`

---

## ⚙️ Setup and Installation

### 1. Prerequisites
- Python 3.10+
- Node.js & `npx` (for testing with the MCP Inspector)

### 2. Virtual Environment & Dependencies
```bash
# Clone the repository
git clone <your-repo-url>
cd ai_library

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required packages
pip install mcp google-genai python-dotenv
```

### 3. Environment Variables
Create a `.env` file in the project directory:
```env
GEMINI_API_KEY="your-google-gemini-api-key"
GEMINI_MODEL="gemini-3.8-flash"
```

---

## 🧪 Testing with MCP Inspector

Test your server tools using the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector python server.py
```

1. Open the inspector URL in your browser.
2. Click **Connect**.
3. Under the **Tools** tab, test `search_book` and `read_library_policy`.
4. Under the **Prompts** tab, test `find_book_prompt`.

---

## 🚀 Running the Application

Run the custom MCP client:

```bash
python client.py
```

### Example Multi-Tool Interaction:

```text
What do you want? "Can you search for the book 'Ethiopia' and also tell me what our library policy is regarding loan periods?"
Calling tool: search_book
Calling tool: read_library_policy

Gemini: I found one book titled "Ethiopia" in our catalog, written by Elyas, with 7 copies currently available.

Regarding our library policy:
* Loan duration: The standard loan period is 14 days.
* Borrowing limit: You may borrow up to 5 books at a time.
* Fines: The overdue fine is $0.25 per day.
```

---

## 🌐 Stretch Goal: Streamable HTTP with Authentication & RBAC (`antigravity_server.py`)

In addition to the standard stdio server, the project implements an advanced **Streamable HTTP MCP Server** (`antigravity_server.py`) with token authentication and role-based permissions, addressing both assignment stretch goals.

### 1. Key Features
- **Transport:** Exposes the MCP endpoint over HTTP (`http://127.0.0.1:8000/mcp`) using `transport="streamable-http"`.
- **Token Authentication:** Implements a custom `LibraryTokenVerifier(TokenVerifier)` and an HTTP POST `/login` endpoint that issues temporary bearer tokens (`TOKEN_LIFETIME = 3600`).
- **Timing-Attack Protection:** Verifies user credentials using `hmac.compare_digest()`.
- **Cryptographic Tokens:** Uses `secrets.token_urlsafe(32)` to generate secure access tokens.

### 2. Role-Based Access Control (RBAC)
Tools are protected with the `require_role(...)` decorator, enforcing two permission tiers:

| Role | Permitted Tools | Description |
|---|---|---|
| **`member`** | `search_book`, `borrow_book`, `return_book` | Patrons can search the catalog, borrow books, and return them. |
| **`librarian`** | `add_book`, `update_book`, + all member tools | Staff members can also acquire new inventory and update copy counts. |

### 3. Running & Testing Streamable HTTP

#### Step 1: Configure Credentials in `.env`
```env
LIBRARY_MEMBER_USERNAME="member_user"
LIBRARY_MEMBER_PASSWORD="member123"
LIBRARY_LIBRARIAN_USERNAME="librarian_admin"
LIBRARY_LIBRARIAN_PASSWORD="librarian123"
```

#### Step 2: Start the HTTP Server
```bash
python antigravity_server.py
```

#### Step 3: Login to obtain a Bearer Token
```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "librarian_admin", "password": "librarian123"}'
```

**Response:**
```json
{
  "access_token": "your_secure_bearer_token_here",
  "token_type": "Bearer",
  "expires_in": 3600,
  "role": "librarian"
}
```

#### Step 4: Connect via MCP Client or Inspector
Provide the Bearer token in the `Authorization: Bearer <token>` header when sending JSON-RPC requests to `http://127.0.0.1:8000/mcp`.

---

## 📂 Project Structure

```
ai_library/
├── database/
│   ├── __init__.py
│   └── db.py               # SQLite database access and schema
├── server.py               # Standard Stdio MCP Server
├── antigravity_server.py   # Streamable HTTP MCP Server (Auth & RBAC)
├── client.py               # Custom MCP Client running Gemini agent loop
├── library.db              # SQLite database storage
├── library_policy.txt      # Local filesystem policy document
├── .env                    # Environment variables (API keys & credentials)
└── README.md               # Project documentation & summary note
```

---

## 🔒 Safety & Standards
- **Stdio Safety:** The server never prints debug text to `stdout`, keeping JSON-RPC framing intact.
- **Secrets:** API keys are loaded via `python-dotenv` from `.env` and kept out of version control.
- **Loop Guards:** The client enforces an iteration limit (`max_iterations = 8`) to prevent runaway loops.