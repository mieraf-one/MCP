import os
import time
import secrets
import hmac

from dotenv import load_dotenv
from pydantic import AnyHttpUrl

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp.server.mcpserver import MCPServer
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.transport_security import TransportSecuritySettings

from database.db import Book


load_dotenv()

# --------------------------------------------------
# Configuration
# --------------------------------------------------

HOST = "127.0.0.1"
PORT = 8000

BASE_URL = f"http://{HOST}:{PORT}"
RESOURCE_URL = f"{BASE_URL}/mcp"

TOKEN_LIFETIME = 3600  # One hour

mcp = MCPServer(
    "AI Library",
    token_verifier=None,  # Replaced below after verifier definition.
)

library = Book()

# Active tokens are stored in memory.
# Restarting the server invalidates all tokens.
active_tokens: dict[str, AccessToken] = {}


# --------------------------------------------------
# Authentication: Verify bearer tokens
# --------------------------------------------------

class LibraryTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        access_token = active_tokens.get(token)

        if access_token is None:
            return None

        if access_token.expires_at is not None:
            if access_token.expires_at <= int(time.time()):
                active_tokens.pop(token, None)
                return None

        return access_token


# Configure authentication on the MCP server.
# Both token_verifier and auth must be supplied together.

mcp = MCPServer(
    "AI Library",
    token_verifier=LibraryTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(BASE_URL),
        resource_server_url=AnyHttpUrl(RESOURCE_URL),
        required_scopes=["library:access"],
        validate_token_resource=True,
    ),
)


# --------------------------------------------------
# Authentication: Login and issue access tokens
# --------------------------------------------------

USERS = {
    "member": {
        "username": os.getenv("LIBRARY_MEMBER_USERNAME"),
        "password": os.getenv("LIBRARY_MEMBER_PASSWORD"),
        "role": "member",
    },
    "librarian": {
        "username": os.getenv("LIBRARY_LIBRARIAN_USERNAME"),
        "password": os.getenv("LIBRARY_LIBRARIAN_PASSWORD"),
        "role": "librarian",
    },
}


def verify_credentials(username: str, password: str):
    """Return the user record if credentials are valid."""

    for user in USERS.values():
        stored_username = user["username"]
        stored_password = user["password"]

        if not stored_username or not stored_password:
            continue

        username_matches = hmac.compare_digest(
            username,
            stored_username,
        )

        password_matches = hmac.compare_digest(
            password,
            stored_password,
        )

        if username_matches and password_matches:
            return user

    return None


@mcp.custom_route("/login", methods=["POST"])
async def login(request: Request) -> Response:
    """Authenticate a user and issue a temporary access token."""

    try:
        data = await request.json()

        username = data.get("username")
        password = data.get("password")

        if not isinstance(username, str) or not isinstance(password, str):
            return JSONResponse(
                {"error": "Username and password must be strings."},
                status_code=400,
            )

        user = verify_credentials(username, password)

        if user is None:
            return JSONResponse(
                {"error": "Invalid username or password."},
                status_code=401,
            )

        token = secrets.token_urlsafe(32)
        expires_at = int(time.time()) + TOKEN_LIFETIME

        role_scope = f"role:{user['role']}"

        access_token = AccessToken(
            token=token,
            client_id=username,
            subject=username,
            scopes=["library:access", role_scope],
            expires_at=expires_at,
            resource=RESOURCE_URL,
        )

        active_tokens[token] = access_token

        return JSONResponse({
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": TOKEN_LIFETIME,
            "role": user["role"],
        })

    except (ValueError, TypeError):
        return JSONResponse(
            {"error": "Invalid request body."},
            status_code=400,
        )


# --------------------------------------------------
# Authorization: Check user permissions
# --------------------------------------------------

def require_role(*allowed_roles: str) -> AccessToken:
    """Reject requests from users without the required role."""

    token = get_access_token()

    if token is None:
        raise PermissionError("Authentication required.")

    if "library:access" not in token.scopes:
        raise PermissionError("Library access denied.")

    permitted = any(
        f"role:{role}" in token.scopes
        for role in allowed_roles
    )

    if not permitted:
        raise PermissionError(
            "You do not have permission to perform this operation."
        )

    return token


# --------------------------------------------------
# Library tools
# --------------------------------------------------

@mcp.tool()
def add_book(title: str, author: str, copies: int) -> str:
    """Add a new book. Librarian access required."""

    require_role("librarian")

    new_book = library.add_book(title, author, copies)

    return f"Book '{new_book}' added successfully."


@mcp.tool()
def search_book(title: str) -> list:
    """Search for a book. Members and librarians can search."""

    require_role("member", "librarian")

    return library.search_book(title)


@mcp.tool()
def update_book(id: int, copies: int) -> str:
    """Update available copies. Librarian access required."""

    require_role("librarian")

    return library.update_book(id, copies)


@mcp.tool()
def borrow_book(id: int) -> str:
    """Borrow a book. Members and librarians can borrow."""

    require_role("member", "librarian")

    return library.borrow_book(id)


@mcp.tool()
def return_book(id: int) -> str:
    """Return a book. Members and librarians can return."""

    require_role("member", "librarian")

    return library.return_book(id)


# --------------------------------------------------
# Start Streamable HTTP server
# --------------------------------------------------

if __name__ == "__main__":
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )

    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        transport_security=security,
    )