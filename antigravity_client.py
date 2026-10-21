from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

MCP_SERVER_URL = (
    "https://reactions-seal-dealt-revelation.trycloudflare.com/mcp"
)


def main():
    question = input("What do you want? ")

    try:
        response = client.interactions.create(
            agent=os.getenv('ANTIGRAVITY_MODEL'),
            input=question,
            environment="remote",
            tools=[
                {
                    "type": "mcp_server",
                    "name": "ai_library",
                    "url": MCP_SERVER_URL,
                }
            ],
        )

        print(f"\nAntigravity: {response.output_text}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()