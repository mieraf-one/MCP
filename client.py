import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types, errors
from dotenv import load_dotenv
import os

load_dotenv()



server_parameters = StdioServerParameters(
    command='python',
    args=['server.py']
)


gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))



async def main():
    async with stdio_client(server_parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()

            functions = [
                types.FunctionDeclaration(
                    name=tool.name,
                    parameters=tool.input_schema,
                    description=tool.description
                ) 
                for tool in tools.tools
            ]

            question = input('What do you want?')

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=question)],
                )
            ]

            try:
                response = gemini.models.generate_content(
                    model=os.getenv('GEMINI_MODEL'),
    
                    contents=contents,
    
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(function_declarations=functions)]
                    )
                )
            except errors.APIError as e:
                print(f"GEMINI API ERROR: {e.message}")
                return

            

            if not response.function_calls:
                print(response.text)
                return


            while response.function_calls:
                contents.append(response.candidates[0].content)

                for function_call in response.function_calls:
                    print(f"Calling tool: {function_call.name}")

                    try:
                        result = await session.call_tool(
                            name=function_call.name,
                            arguments=dict(function_call.args or {})
                        )

                        tool_result = ""

                        for content in result.content:
                            if hasattr(content, "text"):
                                tool_result += content.text

                        is_error = result.is_error
                    except Exception as e:
                        print(f"Actual error: {repr(e)}")
                        tool_result = f"Tool execution failed: {e}"
                        is_error = True


                    contents.append(
                        types.Content(
                            parts=[
                                types.Part.from_function_response(
                                    name=function_call.name,
                                    response={"error" if is_error else "response": tool_result}
                                )
                            ]
                        )
                    )

                try:
                    response = gemini.models.generate_content(
                        model=os.getenv('GEMINI_MODEL'),
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(function_declarations=functions)]
                        )
                    )
                except errors.APIError as e:
                    print(f"GEMINI API ERROR: {e.message}")
                    return

            print(f'Gemini: {response.text}')



if __name__ == "__main__":
    asyncio.run(main())