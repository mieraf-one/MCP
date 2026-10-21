"""
ai_library_service.py
Service layer handling two external resources for the AI Library MCP Application:
  1. Resource 1: SQLite Database (Catalog & Circulation tracking)
  2. Resource 2: Local Filesystem (Policy documents, exported reports, audit logs)
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "library.db"
DATA_DIR = BASE_DIR / "data"
POLICIES_DIR = DATA_DIR / "policies"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
AUDIT_LOG_FILE = LOGS_DIR / "audit.log"


class LibraryService:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._ensure_directories()
        self._init_database()
        self._seed_default_books_if_empty()

    def _ensure_directories(self) -> None:
        """Create necessary data subdirectories if they do not exist."""
        POLICIES_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """Ensure books and borrow_records tables exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Compatible with existing books table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    available_copies INTEGER NOT NULL DEFAULT 1
                )
            """)
            # Circulation tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS borrow_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    patron_name TEXT NOT NULL,
                    borrowed_at TEXT NOT NULL,
                    returned_at TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    FOREIGN KEY (book_id) REFERENCES books (id)
                )
            """)
            conn.commit()

    def _seed_default_books_if_empty(self) -> None:
        """Seed a few standard books if the catalog is completely empty."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM books")
            count = cursor.fetchone()[0]
            if count == 0:
                sample_books = [
                    ("Dune", "Frank Herbert", 4),
                    ("Clean Code", "Robert C. Martin", 3),
                    ("1984", "George Orwell", 5),
                    ("Designing Data-Intensive Applications", "Martin Kleppmann", 2),
                    ("The Hobbit", "J.R.R. Tolkien", 4),
                    ("To Kill a Mockingbird", "Harper Lee", 3),
                ]
                cursor.executemany(
                    "INSERT INTO books (title, author, available_copies) VALUES (?, ?, ?)",
                    sample_books
                )
                conn.commit()

    # ==========================================================
    # RESOURCE 1: SQLite Catalog & Circulation Tools
    # ==========================================================

    def search_books(self, query: str = "", author: str = "") -> Dict[str, Any]:
        """
        Search catalog books matching a title keyword and/or author.
        Returns matching records or guidance if none found.
        """
        try:
            query = (query or "").strip()
            author = (author or "").strip()

            sql = "SELECT id, title, author, available_copies FROM books WHERE 1=1"
            params: List[Any] = []

            if query:
                sql += " AND title LIKE ?"
                params.append(f"%{query}%")
            if author:
                sql += " AND author LIKE ?"
                params.append(f"%{author}%")

            sql += " ORDER BY title ASC"

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                results = [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "author": row["author"],
                        "available_copies": row["available_copies"],
                    }
                    for row in rows
                ]

            self.log_event("SEARCH_BOOKS", f"query='{query}', author='{author}', matches={len(results)}")

            if not results:
                return {
                    "success": True,
                    "count": 0,
                    "books": [],
                    "message": f"No books found matching title '{query}' and author '{author}'.",
                    "recovery_hint": "Try a broader title keyword or list all books by leaving query blank.",
                }

            return {
                "success": True,
                "count": len(results),
                "books": results,
                "message": f"Found {len(results)} matching book(s).",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Database query failed: {str(e)}",
                "recovery_hint": "Ensure the database connection is intact and query strings are valid text.",
            }

    def add_book(self, title: str, author: str, copies: int = 1) -> Dict[str, Any]:
        """
        Add a new title or increase copies of an existing title.
        """
        try:
            title = (title or "").strip()
            author = (author or "").strip()
            if not title:
                return {"success": False, "error": "Title cannot be empty.", "recovery_hint": "Provide a non-empty book title."}
            if not author:
                return {"success": False, "error": "Author cannot be empty.", "recovery_hint": "Provide a valid author name."}
            if copies < 1:
                return {"success": False, "error": f"Invalid copies: {copies}. Must be at least 1.", "recovery_hint": "Set copies to an integer >= 1."}

            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Check if exact title and author already exists
                cursor.execute("SELECT id, available_copies FROM books WHERE LOWER(title) = LOWER(?) AND LOWER(author) = LOWER(?)", (title, author))
                existing = cursor.fetchone()

                if existing:
                    book_id = existing["id"]
                    new_total = existing["available_copies"] + copies
                    cursor.execute("UPDATE books SET available_copies = ? WHERE id = ?", (new_total, book_id))
                    conn.commit()
                    msg = f"Increased copies for '{title}' (ID {book_id}) by {copies}. Total available: {new_total}."
                else:
                    cursor.execute("INSERT INTO books (title, author, available_copies) VALUES (?, ?, ?)", (title, author, copies))
                    book_id = cursor.lastrowid
                    conn.commit()
                    msg = f"Added '{title}' by {author} (ID {book_id}) with {copies} copy/copies."

            self.log_event("ADD_BOOK", f"id={book_id}, title='{title}', copies={copies}")
            return {"success": True, "book_id": book_id, "title": title, "author": author, "message": msg}
        except Exception as e:
            return {"success": False, "error": f"Failed to add book: {str(e)}", "recovery_hint": "Verify input types and database status."}

    def borrow_book(self, book_id: int, patron_name: str) -> Dict[str, Any]:
        """
        Borrow a copy of a book for a specified patron.
        Decrements available_copies and inserts a record in borrow_records.
        """
        try:
            patron_name = (patron_name or "").strip()
            if not patron_name:
                return {"success": False, "error": "patron_name cannot be empty.", "recovery_hint": "Provide borrower's name."}
            if not isinstance(book_id, int) or book_id <= 0:
                return {"success": False, "error": f"Invalid book_id: {book_id}.", "recovery_hint": "Provide a positive integer catalog ID (use search_books to find ID)."}

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, author, available_copies FROM books WHERE id = ?", (book_id,))
                book = cursor.fetchone()

                if not book:
                    return {
                        "success": False,
                        "error": f"No book exists with catalog ID {book_id}.",
                        "recovery_hint": "Use search_books to find the correct book ID first.",
                    }

                if book["available_copies"] <= 0:
                    return {
                        "success": False,
                        "error": f"Book '{book['title']}' (ID {book_id}) has 0 copies available.",
                        "recovery_hint": "The book is currently checked out. Suggest another title or check back later.",
                    }

                # Decrement copy
                cursor.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (book_id,))

                # Record transaction
                now_str = datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO borrow_records (book_id, patron_name, borrowed_at, status) VALUES (?, ?, ?, 'ACTIVE')",
                    (book_id, patron_name, now_str)
                )
                loan_id = cursor.lastrowid
                conn.commit()

            self.log_event("BORROW_BOOK", f"loan_id={loan_id}, book_id={book_id}, title='{book['title']}', patron='{patron_name}'")
            return {
                "success": True,
                "loan_id": loan_id,
                "book_id": book_id,
                "title": book["title"],
                "author": book["author"],
                "patron_name": patron_name,
                "borrowed_at": now_str,
                "message": f"Successfully checked out '{book['title']}' to patron '{patron_name}'. Remaining copies: {book['available_copies'] - 1}.",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to borrow book: {str(e)}", "recovery_hint": "Ensure book_id is numeric and DB is accessible."}

    def return_book(self, book_id: int, patron_name: str = "") -> Dict[str, Any]:
        """
        Return a copy of a book, incrementing available copies and marking active loan as RETURNED.
        """
        try:
            if not isinstance(book_id, int) or book_id <= 0:
                return {"success": False, "error": f"Invalid book_id: {book_id}.", "recovery_hint": "Provide a valid positive integer ID."}

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, author, available_copies FROM books WHERE id = ?", (book_id,))
                book = cursor.fetchone()

                if not book:
                    return {"success": False, "error": f"Book with ID {book_id} not found.", "recovery_hint": "Verify book ID using search_books."}

                # Find active loan if patron is provided, else closest active loan
                if patron_name:
                    cursor.execute(
                        "SELECT id FROM borrow_records WHERE book_id = ? AND LOWER(patron_name) = LOWER(?) AND status = 'ACTIVE' LIMIT 1",
                        (book_id, patron_name.strip())
                    )
                else:
                    cursor.execute(
                        "SELECT id FROM borrow_records WHERE book_id = ? AND status = 'ACTIVE' LIMIT 1",
                        (book_id,)
                    )
                loan = cursor.fetchone()

                now_str = datetime.now().isoformat()
                if loan:
                    cursor.execute(
                        "UPDATE borrow_records SET status = 'RETURNED', returned_at = ? WHERE id = ?",
                        (now_str, loan["id"])
                    )

                cursor.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (book_id,))
                conn.commit()

            self.log_event("RETURN_BOOK", f"book_id={book_id}, title='{book['title']}', patron='{patron_name or 'unspecified'}'")
            return {
                "success": True,
                "book_id": book_id,
                "title": book["title"],
                "new_available_copies": book["available_copies"] + 1,
                "message": f"Successfully returned '{book['title']}' (ID {book_id}). Available copies now: {book['available_copies'] + 1}.",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to return book: {str(e)}", "recovery_hint": "Check database integrity."}

    def get_inventory_summary(self) -> Dict[str, Any]:
        """
        Get aggregated statistics of the library catalog and circulation.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) AS total_titles, SUM(available_copies) AS total_available FROM books")
                row = cursor.fetchone()
                total_titles = row["total_titles"] or 0
                total_available = row["total_available"] or 0

                cursor.execute("SELECT COUNT(*) AS active_loans FROM borrow_records WHERE status = 'ACTIVE'")
                active_loans = cursor.fetchone()["active_loans"] or 0

            return {
                "success": True,
                "total_titles": total_titles,
                "total_available_copies": total_available,
                "active_loans": active_loans,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==========================================================
    # RESOURCE 2: Local Filesystem Storage (Policies, Reports, Logs)
    # ==========================================================

    def read_policy(self, topic: str = "general") -> Dict[str, Any]:
        """
        Read library policy markdown from local filesystem.
        Supported topics: 'general', 'fines', 'renewals'.
        """
        try:
            topic_clean = (topic or "general").strip().lower()
            policy_file = POLICIES_DIR / f"{topic_clean}.md"

            if not policy_file.exists():
                available = [f.stem for f in POLICIES_DIR.glob("*.md")]
                return {
                    "success": False,
                    "error": f"Policy topic '{topic}' not found on disk.",
                    "available_topics": available,
                    "recovery_hint": f"Choose from available policy topics: {', '.join(available)}.",
                }

            content = policy_file.read_text(encoding="utf-8")
            self.log_event("READ_POLICY", f"topic='{topic_clean}'")
            return {
                "success": True,
                "topic": topic_clean,
                "file_path": str(policy_file),
                "content": content,
            }
        except Exception as e:
            return {"success": False, "error": f"Error reading policy file: {str(e)}"}

    def export_circulation_report(self, report_title: str = "Daily Circulation Summary") -> Dict[str, Any]:
        """
        Export a comprehensive circulation summary report to a local markdown file.
        Includes catalog status, active loans, and timestamp.
        """
        try:
            timestamp = datetime.now()
            slug = timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"circulation_report_{slug}.md"
            report_file = REPORTS_DIR / filename

            # Fetch DB metrics
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, author, available_copies FROM books ORDER BY title ASC")
                books = [dict(row) for row in cursor.fetchall()]

                cursor.execute("""
                    SELECT b.title, r.patron_name, r.borrowed_at
                    FROM borrow_records r
                    JOIN books b ON r.book_id = b.id
                    WHERE r.status = 'ACTIVE'
                    ORDER BY r.borrowed_at DESC
                """)
                active_loans = [dict(row) for row in cursor.fetchall()]

            total_titles = len(books)
            total_copies = sum(b["available_copies"] for b in books)

            # Generate Markdown report
            lines = [
                f"# {report_title}",
                f"*Generated on: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}*",
                "",
                "## 1. Executive Summary",
                f"- **Total Catalog Titles:** {total_titles}",
                f"- **Total Available Copies On Shelf:** {total_copies}",
                f"- **Active Book Loans:** {len(active_loans)}",
                "",
                "## 2. Active Loans",
            ]

            if not active_loans:
                lines.append("_No books currently on loan._")
            else:
                lines.append("| Book Title | Patron | Checkout Date |")
                lines.append("|---|---|---|")
                for loan in active_loans:
                    lines.append(f"| {loan['title']} | {loan['patron_name']} | {loan['borrowed_at'][:19]} |")

            lines.extend([
                "",
                "## 3. Current Catalog Inventory",
                "| ID | Title | Author | Available Copies |",
                "|---|---|---|---|",
            ])
            for b in books:
                lines.append(f"| {b['id']} | {b['title']} | {b['author']} | {b['available_copies']} |")

            report_content = "\n".join(lines) + "\n"
            report_file.write_text(report_content, encoding="utf-8")

            self.log_event("EXPORT_REPORT", f"file='{report_file.name}', titles={total_titles}, active_loans={len(active_loans)}")

            return {
                "success": True,
                "file_name": report_file.name,
                "file_path": str(report_file),
                "total_titles": total_titles,
                "total_available_copies": total_copies,
                "active_loans": len(active_loans),
                "message": f"Successfully exported circulation report to {report_file.name}.",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to export circulation report: {str(e)}"}

    def log_event(self, action: str, details: str, status: str = "SUCCESS") -> None:
        """
        Append a structured audit log entry to the local audit log file.
        """
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "status": status,
                "details": details,
            }
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def read_audit_logs(self, limit: int = 10) -> Dict[str, Any]:
        """
        Read the most recent N entries from the local audit log file.
        """
        try:
            if not AUDIT_LOG_FILE.exists():
                return {"success": True, "count": 0, "logs": [], "message": "No audit logs recorded yet."}

            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            recent = lines[-limit:]
            parsed = [json.loads(line) for line in reversed(recent)]

            return {
                "success": True,
                "count": len(parsed),
                "logs": parsed,
                "file_path": str(AUDIT_LOG_FILE),
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to read audit logs: {str(e)}"}
