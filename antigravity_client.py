from google import genai
from dotenv import load_dotenv
import requests
import os

load_dotenv()

SERVER_URL = "http://127.0.0.1:8000"

def login(username: str, password: str) -> str:
    response = requests.post(
        f"{SERVER_URL}/login",
        json={
            "username": username,
            "password": password,
        },
    )

    response.raise_for_status()
    return response.json()["access_token"]


username = input("Username: ")
password = input("Password: ")

token = login(username, password)
print("Login successful!")



client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

MCP_SERVER_URL = (
    "https://automobile-toolkit-libs-encourages.trycloudflare.com/mcp"
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
                    "headers": {
                        "Authorization": f"Bearer {token}"
                    },
                }
            ]
        )

        print(f"\nAntigravity: {response.output_text}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
