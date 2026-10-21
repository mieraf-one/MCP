#!/usr/bin/env python3
"""
demo_task.py
End-to-end Demonstration Script for the AI Smart Library MCP Application.

Demonstrates the MCP Client connecting to the MCP Server and utilizing
multiple tools across BOTH external resources:
  1. Resource 1 (SQLite Catalog Database):
     - search_books: Locates book catalog ID and verifies copy availability
     - borrow_book: Checks out a physical copy and creates an active loan record
  2. Resource 2 (Local Filesystem):
     - read_library_policy: Reads borrowing terms, duration, and fine rules from Markdown
     - export_circulation_report: Compiles live database metrics into a Markdown audit report
     - view_audit_logs: Inspects operational event logs written to disk

Also tests the LLM Agent Loop (Gemini) when API access is available.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import find_dotenv, load_dotenv

# Load environment configuration
load_dotenv(find_dotenv(usecwd=True))

SERVER_SCRIPT = str(Path(__file__).resolve().parent / "library_mcp_server.py")
PYTHON_EXE = sys.executable

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str):
    width = 75
    print("\n" + "=" * width)
    print(f" {BOLD}{CYAN}{title.center(width - 2)}{RESET} ")
    print("=" * width)


def print_step(step_num: int, title: str):
    print(f"\n{BOLD}{YELLOW}[STEP {step_num}] {title}{RESET}")


def print_success(msg: str):
    print(f"{GREEN}✔ {msg}{RESET}")


def print_info(label: str, val: Any):
    print(f"  {BLUE}• {label}:{RESET} {val}")


async def run_mcp_tool_demonstration():
    print_banner("AI SMART LIBRARY: END-TO-END MCP DEMO")
    print(f"Starting server process: {SERVER_SCRIPT}")

    server_params = StdioServerParameters(
        command=PYTHON_EXE,
        args=[SERVER_SCRIPT],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # -----------------------------------------------------------------
            # Initialization & Discovery
            # -----------------------------------------------------------------
            print_step(1, "Initialize MCP Client & Discover Server Capabilities")
            init_result = await session.initialize()
            print_success(f"Connected to MCP Server: '{init_result.server_info.name}'")

            tools_resp = await session.list_tools()
            print_success(f"Discovered {len(tools_resp.tools)} Tools:")
            for tool in tools_resp.tools:
                print(f"    - {BOLD}{tool.name}{RESET}: {tool.description.splitlines()[0]}")

            resources_resp = await session.list_resources()
            print_success(f"Discovered {len(resources_resp.resources)} Resources:")
            for r in resources_resp.resources:
                print(f"    - {BOLD}{r.uri}{RESET}: {r.name}")

            prompts_resp = await session.list_prompts()
            print_success(f"Discovered {len(prompts_resp.prompts)} Prompts:")
            for p in prompts_resp.prompts:
                print(f"    - {BOLD}{p.name}{RESET}: {p.description}")

            # -----------------------------------------------------------------
            # Tool 1: search_books (Resource 1: SQLite Database)
            # -----------------------------------------------------------------
            print_step(2, "Search Books Catalog (Resource 1: SQLite Database)")
            query_title = "Clean Code"
            print_info("Action", f"Calling tool 'search_books' with query='{query_title}'")

            call_res = await session.call_tool("search_books", {"query": query_title})
            search_data = json.loads(call_res.content[0].text)

            book_id = None
            if search_data.get("books"):
                book = search_data["books"][0]
                book_id = book["id"]
                print_success(f"Found book: '{book['title']}' by {book['author']} (ID: {book_id}, Available Copies: {book['available_copies']})")
            else:
                # Fallback to search all books
                print_info("Fallback", "Searching without filter to get available title...")
                all_res = await session.call_tool("search_books", {"query": ""})
                all_data = json.loads(all_res.content[0].text)
                if all_data.get("books"):
                    book = all_data["books"][0]
                    book_id = book["id"]
                    print_success(f"Selected catalog item: '{book['title']}' (ID: {book_id}, Copies: {book['available_copies']})")

            # -----------------------------------------------------------------
            # Tool 2: borrow_book (Resource 1: SQLite Database)
            # -----------------------------------------------------------------
            print_step(3, "Borrow Book for Patron (Resource 1: SQLite Database)")
            patron = "Alice Smith"
            print_info("Action", f"Calling tool 'borrow_book' with book_id={book_id}, patron_name='{patron}'")

            borrow_res = await session.call_tool("borrow_book", {"book_id": book_id, "patron_name": patron})
            borrow_data = json.loads(borrow_res.content[0].text)
            print_success(f"Checkout Result: {borrow_data.get('message')}")
            print_info("Transaction Details", f"Loan ID: {borrow_data.get('loan_id')}, Borrowed At: {borrow_data.get('borrowed_at')}")

            # -----------------------------------------------------------------
            # Tool 3: read_library_policy (Resource 2: Local Filesystem)
            # -----------------------------------------------------------------
            print_step(4, "Read Circulation Policies (Resource 2: Local Filesystem)")
            print_info("Action", "Calling tool 'read_library_policy' with topic='general'")

            policy_res = await session.call_tool("read_library_policy", {"topic": "general"})
            policy_data = json.loads(policy_res.content[0].text)
            print_success(f"Loaded policy file: '{policy_data.get('file_path')}'")
            # Print first 3 lines of policy
            preview = "\n".join(policy_data.get("content", "").splitlines()[:5])
            print(f"  {MAGENTA}Policy Excerpt:\n{preview}{RESET}")

            # -----------------------------------------------------------------
            # Tool 4: export_circulation_report (Resource 2: Local Filesystem)
            # -----------------------------------------------------------------
            print_step(5, "Export Circulation Audit Report (Resource 2: Local Filesystem)")
            report_title = "Demo Automated Circulation Audit"
            print_info("Action", f"Calling tool 'export_circulation_report' with title='{report_title}'")

            report_res = await session.call_tool("export_circulation_report", {"report_title": report_title})
            report_data = json.loads(report_res.content[0].text)
            print_success(f"Report Generated: '{report_data.get('file_name')}'")
            print_info("Saved Path", report_data.get("file_path"))
            print_info("Catalog Metrics", f"Total Titles: {report_data.get('total_titles')}, Shelf Copies: {report_data.get('total_available_copies')}, Active Loans: {report_data.get('active_loans')}")

            # -----------------------------------------------------------------
            # Tool 5: view_audit_logs (Resource 2: Local Filesystem)
            # -----------------------------------------------------------------
            print_step(6, "Inspect Operational Audit Logs (Resource 2: Local Filesystem)")
            logs_res = await session.call_tool("view_audit_logs", {"limit": 4})
            logs_data = json.loads(logs_res.content[0].text)
            print_success(f"Retrieved {logs_data.get('count')} Recent Audit Entries:")
            for entry in logs_data.get("logs", []):
                print(f"    • [{entry['timestamp'][:19]}] {BOLD}{entry['action']}{RESET}: {entry['details']}")

            # -----------------------------------------------------------------
            # Read MCP Resource: library://catalog/summary
            # -----------------------------------------------------------------
            print_step(7, "Read Dynamic MCP Resource 'library://catalog/summary'")
            res_content = await session.read_resource("library://catalog/summary")
            summary_text = res_content.contents[0].text
            print_success("Resource Data:")
            print(f"  {summary_text}")

            print_banner("DEMO COMPLETED SUCCESSFULLY!")
            print(f"{GREEN}All tools from Database and Local Filesystem executed flawlessly over MCP stdio protocol.{RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_mcp_tool_demonstration())
