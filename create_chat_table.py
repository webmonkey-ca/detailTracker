# create_chat_table.py
import sys
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, OperationalError

# Assuming db_connector.py is in the same directory and defines 'engine'
try:
    from db_connector import engine
except ImportError:
    print("Error: Could not import 'engine' from db_connector.py.")
    print("Ensure db_connector.py is in the same directory and defines the SQLAlchemy engine.")
    sys.exit(1)

# SQL statement to create the chat_messages table
# --- MODIFIED: Changed sender_id and recipient_id to INT to match users.id type ---
SQL_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL, -- Changed to INT
    recipient_id INT NOT NULL, -- Changed to INT
    message_text TEXT NOT NULL,
    stockNumber VARCHAR(200) NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0,

    INDEX idx_sender_recipient (sender_id, recipient_id, is_read),
    INDEX idx_recipient_read (recipient_id, is_read),
    INDEX idx_stockNumber (stockNumber),

    CONSTRAINT fk_chat_sender
        FOREIGN KEY (sender_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_chat_recipient
        FOREIGN KEY (recipient_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);
"""
# --- END MODIFIED ---

def create_chat_table():
    """Connects to the database and attempts to create the chat_messages table."""
    if engine is None:
        print("Error: Database engine is not configured.")
        return

    print("Attempting to connect to the database...")
    try:
        with engine.connect() as connection:
            print("Connection successful.")

            # IMPORTANT: Ensure you have dropped the table manually if previous attempts failed
            # print("Attempting to drop existing chat_messages table (if exists)...")
            # with connection.begin():
            #     connection.execute(text("DROP TABLE IF EXISTS chat_messages;"))
            # print("DROP TABLE IF EXISTS command executed.")

            print("Executing CREATE TABLE statement for chat_messages...")
            # Use transaction context manager for safety
            with connection.begin():
                 connection.execute(text(SQL_CREATE_TABLE))
            print("Successfully executed CREATE TABLE statement (or table already exists).")
            print("Table 'chat_messages' should now exist.")

    except OperationalError as e:
        print(f"\nDatabase Connection Error: Could not connect to the database.")
        print(f"Please check your database server is running and connection details are correct.")
        print(f"Error details: {e}")
    except SQLAlchemyError as e:
        print(f"\nAn error occurred during table creation: {e}")
        print("Please double-check the data type AND storage engine (should be InnoDB) of 'id' in your 'users' table.")
        print("Ensure the 'users' table exists and the column 'id' is indexed (usually as PRIMARY KEY).")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    create_chat_table()
