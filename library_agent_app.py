#!/usr/bin/env python3
"""
library_agent_app.py
End-User AI Library Assistant Application.
Integrates the user-defined Model Context Protocol (MCP) Client and Server
into a complete conversational application powered by LLM tool calling.

Usage:
  Interactive Mode:
    python library_agent_app.py

  Single Query Mode:
    python library_agent_app.py --prompt "Find books on Python and borrow one for John"
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from library_mcp_client import LibraryMCPClient

load_dotenv(find_dotenv(usecwd=True))

# ANSI Color formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_header():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════════╗
║               📚 AI SMART LIBRARY ASSISTANT (MCP APP)                ║
║           Powered by Model Context Protocol & Gemini LLM             ║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
{DIM}Connected Resources: [1] SQLite Database (Catalog & Loans)  [2] Filesystem (Policies & Reports){RESET}
""")


def print_help():
    print(f"""
{BOLD}Available Commands & Examples:{RESET}
  {GREEN}/tools{RESET}             List all tools discovered from the MCP server
  {GREEN}/resources{RESET}         List all resources exposed by the MCP server
  {GREEN}/summary{RESET}           Fetch live catalog summary resource (JSON snapshot)
  {GREEN}/rules{RESET}             Read the official borrowing policy document
  {GREEN}/help{RESET}              Display this help message
  {GREEN}/quit{RESET} or {GREEN}/exit{RESET}      Exit the application

{BOLD}Sample Questions you can ask:{RESET}
  • "What books are currently available in the catalog?"
  • "Add a new book called 'Clean Architecture' by Robert Martin with 3 copies."
  • "Borrow a copy of 'Clean Code' for patron 'David Miller'."
  • "What is our policy on overdue fines and grace periods?"
  • "Export a circulation summary report for today's inventory."
  • "Check the recent audit logs to see today's transactions."
""")


def on_tool_call(tool_name: str, tool_args: dict):
    print(f"\n{YELLOW}⚙  Calling MCP Tool: {BOLD}{tool_name}{RESET}")
    print(f"   {DIM}Arguments: {json.dumps(tool_args)}{RESET}")


def on_tool_result(tool_name: str, tool_output: str, is_error: bool):
    status = f"{MAGENTA}FAILED{RESET}" if is_error else f"{GREEN}SUCCESS{RESET}"
    print(f"   {status} {DIM}({tool_name} returned {len(tool_output)} chars){RESET}")


async def interactive_mode(client: LibraryMCPClient):
    print_header()
    print("Initializing MCP connection and discovering tools...")
    caps = await client.list_capabilities()
    tools = caps["tools"]
    print(f"{GREEN}✔ Connected successfully! Loaded {len(tools)} tools.{RESET}")
    print("Type your message or /help for guidance.\n")

    while True:
        try:
            user_input = input(f"{BOLD}{CYAN}You > {RESET}").strip()
            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ["/quit", "/exit", "quit", "exit", "q"]:
                print(f"{YELLOW}Goodbye! Happy reading! 📖{RESET}")
                break

            if cmd == "/help":
                print_help()
                continue

            if cmd == "/tools":
                print(f"\n{BOLD}Discovered MCP Tools ({len(tools)}):{RESET}")
                for t in tools:
                    print(f"  • {BOLD}{GREEN}{t['name']}{RESET}: {t['description'].splitlines()[0]}")
                print()
                continue

            if cmd == "/resources":
                resources = caps.get("resources", [])
                print(f"\n{BOLD}MCP Server Resources ({len(resources)}):{RESET}")
                for r in resources:
                    print(f"  • {BOLD}{BLUE}{r['uri']}{RESET}: {r.get('name')}")
                print()
                continue

            if cmd == "/summary":
                print(f"\n{BOLD}Reading 'library://catalog/summary'...{RESET}")
                res = await client.read_resource("library://catalog/summary")
                print(f"{GREEN}{res}{RESET}\n")
                continue

            if cmd == "/rules":
                print(f"\n{BOLD}Reading 'library://policies/borrowing_rules'...{RESET}")
                res = await client.read_resource("library://policies/borrowing_rules")
                print(f"{MAGENTA}{res}{RESET}\n")
                continue

            # Run the query through the MCP Agent Loop
            print(f"{DIM}Thinking...{RESET}")
            reply = await client.run_agent(
                user_prompt=user_input,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )
            print(f"\n{BOLD}{GREEN}Assistant >{RESET}\n{reply}\n")

        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Session ended.{RESET}")
            break
        except Exception as e:
            print(f"\n{MAGENTA}Error: {e}{RESET}\n")


async def single_query_mode(client: LibraryMCPClient, prompt: str):
    print(f"{BOLD}Running prompt:{RESET} {prompt}")
    reply = await client.run_agent(
        user_prompt=prompt,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
    )
    print(f"\n{BOLD}{GREEN}Assistant >{RESET}\n{reply}")


def main():
    parser = argparse.ArgumentParser(description="AI Library Assistant MCP Application")
    parser.add_argument("--prompt", type=str, help="Single prompt to execute non-interactively")
    parser.add_argument("--model", type=str, default="gemini-3.8-flash", help="Gemini model name")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose MCP client logs")

    args = parser.parse_args()

    client = LibraryMCPClient(
        model_name=args.model,
        verbose=not args.quiet,
    )

    if args.prompt:
        asyncio.run(single_query_mode(client, args.prompt))
    else:
        asyncio.run(interactive_mode(client))


if __name__ == "__main__":
    main()
