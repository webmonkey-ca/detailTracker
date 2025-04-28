# db_connector.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from .env file
# Make sure you have a .env file with your DB credentials
load_dotenv()

# --- Database Configuration (Load from Environment Variables) ---
# Defaults to 'mysql' as confirmed by user
DB_TYPE = os.getenv('DB_TYPE', 'mysql')
DB_DRIVER_MAP = { # Map DB type to common SQLAlchemy driver names
    'mysql': 'mysqlconnector', # Uses mysql-connector-python library
    'postgresql': 'psycopg2',
    'mssql': 'pyodbc'
    # Add other mappings as needed
}
# Gets 'mysqlconnector' by default if DB_TYPE is 'mysql' and DB_DRIVER isn't set
DB_DRIVER = os.getenv('DB_DRIVER') or DB_DRIVER_MAP.get(DB_TYPE)

# --- These MUST be set in your .env file ---
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
# -------------------------------------------

DB_HOST = os.getenv('DB_HOST', '192.168.0.7') # Your IP from the request
DB_PORT = os.getenv('DB_PORT','3306') # Optional, defaults vary (e.g., 3306 for MySQL)

# --- Validate Essential Credentials ---
if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_DRIVER]):
    print("CRITICAL: Database connection details (USER, PASSWORD, NAME) missing from environment variables (.env file).")
    print("Please ensure DB_USER, DB_PASSWORD, and DB_NAME are set.")
    # Raise an error or set engine/SessionLocal to None to indicate failure
    engine = None
    SessionLocal = None
    # exit() # Or prevent app startup
else:
    try:
        # Encode password for connection string safety
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

        # --- Construct Database URI ---
        # This section correctly handles the 'mysql' case based on DB_TYPE
        if DB_TYPE == 'mssql':
             # Example for SQL Server with pyodbc (requires driver name)
             ODBC_DRIVER = os.getenv('ODBC_DRIVER', '{ODBC Driver 17 for SQL Server}')
             DATABASE_URI = f"mssql+pyodbc://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT or '1433'}/{DB_NAME}?driver={ODBC_DRIVER}"
        elif DB_TYPE == 'postgresql':
             DATABASE_URI = f"postgresql+{DB_DRIVER}://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT or '5432'}/{DB_NAME}"
        elif DB_TYPE == 'mysql':
             # Uses the mysqlconnector driver by default
             # Assumes default port 3306 if DB_PORT is not set
             DATABASE_URI = f"mysql+{DB_DRIVER}://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT or '3306'}/{DB_NAME}"
        else:
             raise ValueError(f"Unsupported DB_TYPE in environment: {DB_TYPE}")

        print(f"Attempting to connect to: {DB_TYPE} database '{DB_NAME}' at {DB_HOST}")

        # --- Create SQLAlchemy Engine ---
        # echo=True shows SQL statements (useful for debugging, disable in production)
        # pool_pre_ping=True helps manage connections that might go stale
        engine = create_engine(
            DATABASE_URI,
            echo=False,
            pool_pre_ping=True
        )

        # --- Create Session Maker ---
        # This creates a factory for producing database session objects
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # --- Test Connection (Optional but Recommended) ---
        # This will raise an error if connection fails
        with engine.connect() as connection:
            print(f"Successfully connected to database '{DB_NAME}' at {DB_HOST}!")

    except ImportError:
        # Specific error if mysql-connector-python is missing
        print(f"CRITICAL: Database driver '{DB_DRIVER}' for {DB_TYPE} not installed.")
        print("Try: pip install SQLAlchemy mysql-connector-python")
        engine = None
        SessionLocal = None
    except ValueError as ve:
         print(f"CRITICAL: Configuration Error - {ve}")
         engine = None
         SessionLocal = None
    except SQLAlchemyError as db_err:
        # Catches general SQLAlchemy errors, including authentication failures
        print(f"CRITICAL: Failed to connect to database '{DB_NAME}' at {DB_HOST}. Check credentials and DB status.")
        print(f"SQLAlchemy Error: {db_err}")
        engine = None
        SessionLocal = None
    except Exception as e:
        print(f"CRITICAL: An unexpected error occurred during database setup: {e}")
        engine = None
        SessionLocal = None

# --- Function to get a DB session (optional, can be used as a dependency) ---
def get_db_session():
    """Provides a database session."""
    if not SessionLocal:
        # Optionally raise an error or return None if connection failed during setup
        raise ConnectionError("Database connection not established during setup.")
        # return None
    db = SessionLocal()
    try:
        yield db # Yield the session for use in a 'with' block or route
    finally:
        db.close() # Ensure session is closed

# You can now import 'engine' or 'SessionLocal' or 'get_db_session'
# into your app.py file to interact with the database.
