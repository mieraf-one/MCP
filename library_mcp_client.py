"""
library_mcp_client.py
Custom, user-defined Model Context Protocol (MCP) Client.
Connects to the AI Library MCP Server over stdio or Streamable HTTP.
Implements the complete autonomous agent loop:
  1. Spawns / connects to the MCP Server
  2. Discovers and lists available server tools, resources, and prompts
  3. Converts MCP tool schemas into LLM function declarations
  4. Runs the multi-turn agent loop (calling tools and feeding results back to LLM)
  5. Returns the final generated answer to the user
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv
from google import genai
from google.genai import errors, types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Automatically locate .env in current or parent directory
load_dotenv(find_dotenv(usecwd=True))

DEFAULT_SERVER_SCRIPT = str(Path(__file__).resolve().parent / "library_mcp_server.py")
DEFAULT_PYTHON_EXE = sys.executable


class LibraryMCPClient:
    """A robust, user-defined MCP Client managing tool discovery, LLM agent loops, and execution."""

    def __init__(
        self,
        server_script: str = DEFAULT_SERVER_SCRIPT,
        python_exe: str = DEFAULT_PYTHON_EXE,
        model_name: Optional[str] = None,
        verbose: bool = True,
    ):
        self.server_script = server_script
        self.python_exe = python_exe
        self.verbose = verbose
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = (
            model_name
            or os.getenv("GEMINI_MODEL")
            or "gemini-3.1-flash-lite"
        )

        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        else:
            self.gemini_client = None

        self.server_params = StdioServerParameters(
            command=self.python_exe,
            args=[self.server_script],
            env=os.environ.copy(),
        )

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[MCP Client] {msg}")

    async def list_capabilities(self) -> Dict[str, Any]:
        """Connect to the server and inspect available tools, resources, and prompts."""
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_resp = await session.list_tools()
                tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    }
                    for tool in tools_resp.tools
                ]

                # Fetch resources
                try:
                    resources_resp = await session.list_resources()
                    resources = [
                        {"uri": str(r.uri), "name": r.name, "description": r.description}
                        for r in getattr(resources_resp, "resources", [])
                    ]
                except Exception:
                    resources = []

                # Fetch prompts
                try:
                    prompts_resp = await session.list_prompts()
                    prompts = [
                        {"name": p.name, "description": p.description}
                        for p in getattr(prompts_resp, "prompts", [])
                    ]
                except Exception:
                    prompts = []

                return {"tools": tools, "resources": resources, "prompts": prompts}

    async def read_resource(self, uri: str) -> str:
        """Fetch content of a resource exposed by the MCP server."""
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.read_resource(uri)
                output = []
                for content in res.contents:
                    if hasattr(content, "text"):
                        output.append(content.text)
                return "\n".join(output)

    async def run_agent(
        self,
        user_prompt: str,
        on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_tool_result: Optional[Callable[[str, str, bool], None]] = None,
    ) -> str:
        """Run the full autonomous agent loop against the MCP server for a given user prompt."""
        if not self.gemini_client:
            raise ValueError(
                "GEMINI_API_KEY environment variable is missing. "
                "Please configure GEMINI_API_KEY in your .env file."
            )

        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self._log("MCP session initialized with server.")

                # 1. Discover MCP tools
                tools_resp = await session.list_tools()
                available_tools = tools_resp.tools
                self._log(f"Discovered {len(available_tools)} tools from MCP server.")

                # 2. Build Gemini Function Declarations from MCP schemas
                function_declarations = []
                for tool in available_tools:
                    # Clean schema for Gemini API compatibility
                    schema = dict(tool.input_schema or {})
                    # Remove unsupported json schema top-level keywords if needed
                    schema.pop("$schema", None)
                    schema.pop("additionalProperties", None)

                    declaration = types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description or "",
                        parameters=schema,
                    )
                    function_declarations.append(declaration)

                gemini_tools = [types.Tool(function_declarations=function_declarations)]

                # 3. Initialize Conversation Contents
                system_instruction = (
                    "You are the AI Smart Library Assistant. You have access to real-time "
                    "library tools for searching catalog books, checking out/returning copies, "
                    "reading library rules/policies, and exporting circulation reports. "
                    "Always use the appropriate tools to fulfill user requests accurately. "
                    "If a tool reports an error or unavailable copies, inform the user clearly "
                    "and suggest constructive next steps."
                )

                contents = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=f"{system_instruction}\n\nUser Request: {user_prompt}")],
                    )
                ]

                # 4. Agent Loop: query model, execute tool calls, return results until completion
                max_iterations = 8
                iteration = 0

                while iteration < max_iterations:
                    iteration += 1
                    # Resilient call with retries and fallback models
                    candidate_models = [
                        self.model_name,
                        "gemini-3.8-flash",
                        "gemini-flash-latest",
                        "gemini-3.5-flash",
                        "gemini-3.1-pro-preview",
                    ]
                    # Deduplicate while preserving order
                    seen = set()
                    unique_candidates = [m for m in candidate_models if not (m in seen or seen.add(m))]

                    response = None
                    last_err = None

                    for try_model in unique_candidates:
                        for attempt in range(2):
                            try:
                                response = await self.gemini_client.aio.models.generate_content(
                                    model=try_model,
                                    contents=contents,
                                    config=types.GenerateContentConfig(tools=gemini_tools),
                                )
                                self.model_name = try_model  # Stick with working model
                                break
                            except errors.APIError as e:
                                last_err = e
                                if "high demand" in e.message.lower() or "quota" in e.message.lower() or "503" in e.message:
                                    self._log(f"Model {try_model} busy (attempt {attempt+1}): {e.message}. Retrying...")
                                    await asyncio.sleep(1.0)
                                    continue
                                else:
                                    break
                            except Exception as e:
                                last_err = e
                                break
                        if response:
                            break

                    if not response:
                        err_msg = f"LLM API Error during turn {iteration}: {last_err}"
                        self._log(err_msg)
                        return err_msg

                    # If model didn't request any function calls, return final response
                    if not response.function_calls:
                        return response.text or "Completed without text response."

                    # Append model turn containing function call requests
                    contents.append(response.candidates[0].content)

                    # Execute each requested function call through MCP session
                    for func_call in response.function_calls:
                        tool_name = func_call.name
                        tool_args = dict(func_call.args or {})

                        self._log(f"-> Calling tool '{tool_name}' with args {tool_args}")
                        if on_tool_call:
                            on_tool_call(tool_name, tool_args)

                        # Call the tool via MCP session
                        try:
                            mcp_result = await session.call_tool(
                                name=tool_name,
                                arguments=tool_args,
                            )
                            # Extract text content from result
                            text_chunks = []
                            for item in mcp_result.content:
                                if hasattr(item, "text"):
                                    text_chunks.append(item.text)
                            tool_output = "\n".join(text_chunks)
                            is_error = bool(mcp_result.is_error)
                        except Exception as e:
                            tool_output = f"Execution error: {str(e)}"
                            is_error = True

                        self._log(f"<- Tool '{tool_name}' returned (error={is_error}): {tool_output[:120]}...")
                        if on_tool_result:
                            on_tool_result(tool_name, tool_output, is_error)

                        # Return tool execution result to LLM context
                        contents.append(
                            types.Content(
                                parts=[
                                    types.Part.from_function_response(
                                        name=tool_name,
                                        response={
                                            "status": "error" if is_error else "success",
                                            "output": tool_output,
                                        },
                                    )
                                ]
                            )
                        )

                return "Maximum agent reasoning iterations reached."


async def run_cli_interactive():
    """Simple interactive CLI test loop."""
    client = LibraryMCPClient()
    print("==================================================")
    print("       AI Smart Library Assistant (MCP Client)    ")
    print("==================================================")
    print("Connecting to server and discovering tools...")
    caps = await client.list_capabilities()
    print(f"Discovered {len(caps['tools'])} tools:")
    for t in caps["tools"]:
        print(f"  - {t['name']}: {t['description'][:75]}...")

    print("\nType your question/command below (or 'quit' to exit):")
    while True:
        try:
            prompt = input("\nYou: ").strip()
            if not prompt:
                continue
            if prompt.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            response = await client.run_agent(prompt)
            print(f"\nAssistant:\n{response}")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


if __name__ == "__main__":
    asyncio.run(run_cli_interactive())
