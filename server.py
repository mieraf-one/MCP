import json
from pathlib import Path
from mcp.server.mcpserver import MCPServer
from database.db import Book


mcp = MCPServer("AI Library Search")
library = Book()


POLICY_FILE = Path(__file__).resolve().parent / 'library_policy.txt'


# Create a policy file if it doesn't exist
if not POLICY_FILE.exists():
    POLICY_FILE.write_text(
        "Library Policies:\n"
        "1. Standard loan duration is 14 days.\n"
        "2. Patrons may borrow up to 5 books at a time.\n"
        "3. Overdue fine is $0.25 per day.\n"
    )

@mcp.tool()
def read_library_policy() -> str:
    """Read official library rules, loan durations, borrowing limits, and overdue fines from local files."""
    return POLICY_FILE.read_text(encoding='utf-8')


@mcp.tool()
def add_book(title: str, author: str, copies: int = 1) -> str:
    """Add a book to the library catalog. Both title and author are required. 
    If the user has not provided an author, do NOT guess or call this tool—ask the user for the author first."""
    new_book = library.add_book(title, author, copies)
    return f"Book '{new_book}' added successfully."



@mcp.tool()
def search_book(title: str) -> list:
    """Search the catalog for books with titles containing the provided text."""
    results = library.search_book(title)

    if not results:
        return json.dumps({
            "status": "not_found",
            "message": f"No books found matching '{title}'.",
            "recovery_hint": "Try searching with an empty string to view all available titles."
        })

    return json.dumps(results, indent=2)


@mcp.tool()
def update_book(id: int, copies: int) -> str:
    """Set the available copy count for a book by its catalog ID."""
    return library.update_book(id, copies)


@mcp.tool()
def borrow_book(id: int) -> str:
    """Borrow one available copy of a book by its catalog ID."""
    return library.borrow_book(id)


@mcp.tool()
def return_book(id: int) -> str:
    """Return one copy of a book to the library using its catalog ID."""
    return library.return_book(id)


# =======================================
#               PROMPT  
# =======================================
@mcp.prompt()
def find_book_prompt(title: str) -> str:
    """Create a prompt to help find a book in the library."""
    return f"""
    Find the book titled '{title}' in the library.
    Use the search_book tool to search for it.
    Explain whether the book is available.
    """

if __name__ == "__main__":
    # mcp.run(host="0.0.0.0", port=4000, transport='streamable-http')
    mcp.run()