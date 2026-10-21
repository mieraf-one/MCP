import sqlite3
from contextlib import contextmanager



@contextmanager
def session():
    conn = sqlite3.connect("library.db")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_table():
    with session() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                available_copies INTEGER NOT NULL DEFAULT 1
            )
        """)


class Book:     
    def __init__(self):
        create_table()


    def add_book(self, title: str, author: str, copies: int) -> str:
        if copies < 1:
            return "Error: copies can not be negative."

        with session() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO books(title, author, available_copies)
                VALUES (?, ?, ?)
                """,
                (title, author, copies)
            )


            return title


    def search_book(self, title: str) -> list:
        with session() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM books WHERE title LIKE ?",
                    (f"%{title}%",)
            )

            
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'author': row[2],
                    'available_copies': row[3]
                } 
                for row in cursor.fetchall()
            ]


    def update_book(self, id: int, copies: int) -> str:
        if copies < 1:
            return "Error: copies can not be negative"
        
        with session() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE books SET available_copies = ? WHERE id = ?",
                (copies, id)
            )

            if cursor.rowcount == 0:
                return f"Book with ID {id} not found."

            return f"Updated book {id}: available copies = {copies}."


    def borrow_book(self, id: int) -> str:
        with session() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE books SET available_copies = available_copies - 1
                WHERE id = ? AND available_copies > 0
                """,
                (id,)
            )

            if cursor.rowcount == 0:
                return f"Book not found or no copies left."

            return f"Book {id} borrowed successfully"


    def return_book(self, id: int) -> str:
            with session() as conn:
                cursor = conn.cursor()
    
                cursor.execute(
                    """
                    UPDATE books SET available_copies = available_copies + 1
                    WHERE id = ?
                    """,
                    (id,)
                )
    
                if cursor.rowcount == 0:
                    return f"Book not found."
    
                return f"Book {id} returned successfully"



if __name__ == '__main__':
    create_table()
    print('Database created.')