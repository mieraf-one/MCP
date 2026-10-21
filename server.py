from mcp.server.mcpserver import MCPServer
from database.db import Book


mcp = MCPServer("AI Library Search")
library = Book()


@mcp.tool()
def add_book(title: str, author: str, copies: int) -> str:
    """Add a book to the library catalog with its title, author, and available copy count."""
    new_book = library.add_book(title, author, copies)
    return f"Book '{new_book}' added successfully."



@mcp.tool()
def search_book(title: str) -> list:
    """Search the catalog for books with titles containing the provided text."""
    return library.search_book(title)


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