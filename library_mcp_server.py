#!/usr/bin/env python3
"""
library_mcp_server.py
MCP Server for the AI Smart Library Application.
Exposes two external resources:
  1. SQLite Database: books catalog and circulation loan tracking
  2. Local Filesystem: policy documents, exported reports, and audit logs

Supports:
  - Tools with typed schemas, clear descriptions, and actionable error messages
  - MCP Resources (catalog summary and policy texts)
  - MCP Prompts (guided borrow workflow and circulation audit)
  - Dual transports: stdio (default, strict stdout safety) & streamable-http
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from mcp.server.mcpserver import MCPServer
from ai_library_service import LibraryService, POLICIES_DIR, LOGS_DIR

# -------------------------------------------------------------
# Logging Configuration
# CRITICAL CONSTRAINT: In stdio mode, NEVER print to stdout.
# All logs go to sys.stderr and optionally a log file.
# -------------------------------------------------------------
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SERVER_LOG_FILE = LOGS_DIR / "server.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(str(SERVER_LOG_FILE), encoding="utf-8"),
    ],
)
logger = logging.getLogger("library_mcp_server")

# -------------------------------------------------------------
# Initialize Server & Resources
# -------------------------------------------------------------
mcp = MCPServer("ai-library-server")
service = LibraryService()

logger.info("Initializing AI Library MCP Server with SQLite DB and Local Filesystem resources.")

# =============================================================
# RESOURCE 1: SQLite Catalog & Circulation Tools
# =============================================================

@mcp.tool()
def search_books(query: str = "", author: str = "") -> str:
    """Search the library catalog database for books by title keyword or author name.
    
    Use this tool whenever the user asks to look up a book, find available titles,
    check availability, or get the catalog ID for borrowing or updating.
    
    Args:
        query: Optional title keyword to search for (e.g., 'Dune', 'Code').
        author: Optional author name keyword to filter by (e.g., 'Herbert').
    
    Returns:
        A JSON string containing matching books with id, title, author, and available copies.
    """
    logger.info("Tool called: search_books(query=%r, author=%r)", query, author)
    result = service.search_books(query=query, author=author)
    return json.dumps(result, indent=2)


@mcp.tool()
def add_book(title: str, author: str, copies: int = 1) -> str:
    """Add a new book or replenish available copies of an existing book in the catalog.
    
    Use this tool when adding newly acquired books to the library collection or
    increasing inventory stock of existing titles.
    
    Args:
        title: Title of the book (cannot be empty).
        author: Author's full or primary name (cannot be empty).
        copies: Number of physical copies to add (must be an integer >= 1, defaults to 1).
    
    Returns:
        A JSON string confirming the addition or detailing any validation error.
    """
    logger.info("Tool called: add_book(title=%r, author=%r, copies=%r)", title, author, copies)
    result = service.add_book(title=title, author=author, copies=copies)
    return json.dumps(result, indent=2)


@mcp.tool()
def borrow_book(book_id: int, patron_name: str) -> str:
    """Borrow a copy of a book from the catalog for a specified library patron.
    
    Use this tool when a user or patron requests to check out a book. The tool
    verifies available copies in the database, decrements inventory, and registers
    an active loan record.
    
    Args:
        book_id: The integer catalog ID of the book (from search_books).
        patron_name: The full name or username of the patron checking out the book.
    
    Returns:
        A JSON string detailing loan success, due date rules, or error if unavailable.
    """
    logger.info("Tool called: borrow_book(book_id=%r, patron_name=%r)", book_id, patron_name)
    result = service.borrow_book(book_id=book_id, patron_name=patron_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def return_book(book_id: int, patron_name: str = "") -> str:
    """Return a previously borrowed book back into library inventory.
    
    Use this tool when a patron returns a book. It increases the available
    copy count in the database and marks the active loan record as returned.
    
    Args:
        book_id: The integer catalog ID of the book being returned.
        patron_name: Optional name of the patron returning the book.
    
    Returns:
        A JSON string confirming return and updated available copy count.
    """
    logger.info("Tool called: return_book(book_id=%r, patron_name=%r)", book_id, patron_name)
    result = service.return_book(book_id=book_id, patron_name=patron_name)
    return json.dumps(result, indent=2)


# =============================================================
# RESOURCE 2: Local Filesystem Tools (Policies, Reports, Logs)
# =============================================================

@mcp.tool()
def read_library_policy(topic: str = "general") -> str:
    """Read official library rules and policies stored in local filesystem documents.
    
    Use this tool when users ask about borrowing periods, loan limits, late fines,
    grace periods, or book renewal procedures.
    
    Args:
        topic: The policy topic to read. Valid options are:
               - 'general': standard loan durations (14 days), borrowing limits, cardholder terms.
               - 'fines': overdue rates ($0.25/day), grace periods (2 days), maximum fine caps.
               - 'renewals': renewal eligibility (up to 2 times), restrictions on reserved items.
    
    Returns:
        A JSON string containing the full markdown content of the requested policy.
    """
    logger.info("Tool called: read_library_policy(topic=%r)", topic)
    result = service.read_policy(topic=topic)
    return json.dumps(result, indent=2)


@mcp.tool()
def export_circulation_report(report_title: str = "Daily Circulation Summary") -> str:
    """Generate and write a comprehensive circulation and inventory report to the filesystem.
    
    Use this tool when a librarian or manager requests an inventory summary,
    circulation statistics, active loan status, or an audit file for record-keeping.
    
    Args:
        report_title: A title describing the report (e.g., 'Weekly Inventory Audit').
    
    Returns:
        A JSON string containing report metadata, saved file path, and summary counts.
    """
    logger.info("Tool called: export_circulation_report(report_title=%r)", report_title)
    result = service.export_circulation_report(report_title=report_title)
    return json.dumps(result, indent=2)


@mcp.tool()
def view_audit_logs(limit: int = 10) -> str:
    """Retrieve recent operational audit events from the local audit log file.
    
    Use this tool to inspect recent actions taken within the system, such as book
    checkouts, returns, catalog updates, or report exports.
    
    Args:
        limit: Maximum number of recent log entries to return (default 10, max 50).
    
    Returns:
        A JSON string containing a chronological list of recent audit event records.
    """
    safe_limit = max(1, min(limit, 50))
    logger.info("Tool called: view_audit_logs(limit=%r)", safe_limit)
    result = service.read_audit_logs(limit=safe_limit)
    return json.dumps(result, indent=2)


# =============================================================
# MCP RESOURCES: Static & Dynamic Data Exposures
# =============================================================

@mcp.resource("library://catalog/summary")
def get_catalog_summary_resource() -> str:
    """Live snapshot of library catalog statistics and active loans."""
    logger.info("Resource requested: library://catalog/summary")
    stats = service.get_inventory_summary()
    return json.dumps(stats, indent=2)


@mcp.resource("library://policies/borrowing_rules")
def get_borrowing_rules_resource() -> str:
    """Full text of the general library borrowing policy from local filesystem."""
    logger.info("Resource requested: library://policies/borrowing_rules")
    res = service.read_policy("general")
    return res.get("content", "General policy not found.")


# =============================================================
# MCP PROMPTS: Pre-built LLM Workflows
# =============================================================

@mcp.prompt()
def borrow_workflow_prompt(book_title: str, patron_name: str) -> str:
    """A guided prompt workflow to assist a user in searching, verifying, and borrowing a book."""
    return f"""
You are the AI Smart Library Assistant. Follow these steps to assist {patron_name}:
1. Use the `search_books` tool to look for books matching '{book_title}'.
2. If found with available copies (> 0), use `borrow_book` with the book's catalog ID and patron '{patron_name}'.
3. Use `read_library_policy` with topic='general' to inform the patron about the 14-day loan period and rules.
4. If no copies are available, explain the situation politely and suggest alternative books or topics.
"""


@mcp.prompt()
def circulation_audit_prompt(report_title: str = "End-of-Day Audit") -> str:
    """A guided prompt workflow for librarians to audit recent operations and export a report."""
    return f"""
You are the AI Library Auditor.
1. Call `view_audit_logs` (limit=10) to review the most recent catalog and circulation activities.
2. Call `export_circulation_report` with report_title='{report_title}'.
3. Provide a clear executive summary of catalog health, active checkouts, and the generated report location.
"""


# =============================================================
# Main Entry Point
# =============================================================

def main():
    parser = argparse.ArgumentParser(description="AI Library MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport type: 'stdio' (default) or 'streamable-http'",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for streamable-http")
    parser.add_argument("--port", type=int, default=8000, help="Port for streamable-http")

    args = parser.parse_args()

    if args.transport == "streamable-http":
        logger.info("Starting AI Library MCP Server over Streamable HTTP on %s:%d/mcp", args.host, args.port)
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
        )
    else:
        logger.info("Starting AI Library MCP Server over stdio")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
