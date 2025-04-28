# database.py
import sqlite3
import os
import datetime

# --- Configuration ---
DATABASE_DIR = 'data'
DATABASE_NAME = 'detail_shop.db'
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)
PHOTOS_DIR = os.path.join(DATABASE_DIR, 'photos')

# --- Directory Setup ---
def ensure_data_dirs():
    """Ensures data and photos directories exist."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)

# --- Database Connection ---
def get_db_connection():
    """Establishes and returns a database connection."""
    ensure_data_dirs()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return conn

# --- Database Initialization ---
def initialize_database():
    """Creates database tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Users & Employees ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'employee'))
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id INTEGER UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # --- Customers & Units ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS units (
            unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            make TEXT,
            model TEXT,
            year INTEGER,
            vin TEXT UNIQUE,
            license_plate TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
    ''')

    # --- Services ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            service_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            base_price REAL DEFAULT 0.0,
            estimated_duration_minutes INTEGER DEFAULT 0
        )
    ''')

    # --- Jobs / Bookings ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            booking_date TEXT,
            assigned_employee_id INTEGER,
            status TEXT NOT NULL CHECK(status IN ('booked', 'quoted', 'check_in', 'in_progress', 'completed', 'cancelled')) DEFAULT 'booked',
            check_in_notes TEXT,
            check_out_notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES units (unit_id),
            FOREIGN KEY (assigned_employee_id) REFERENCES employees (employee_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_services (
            job_service_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            quoted_price REAL,
            FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services (service_id)
        )
    ''')

    # --- Time Tracking ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_minutes INTEGER,
            FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        )
    ''')

    # --- Photos ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            description TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES units (unit_id)
        )
    ''')

    # --- Purchase Orders ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            po_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier TEXT,
            order_date TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT CHECK(status IN ('draft', 'ordered', 'received', 'cancelled')) DEFAULT 'draft',
            notes TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS po_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0.0,
            FOREIGN KEY (po_id) REFERENCES purchase_orders (po_id) ON DELETE CASCADE
        )
    ''')

    # --- Add initial admin user if none exists ---
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        try:
            from utils import hash_password # Import here to avoid circular dependency issues at module level
            hashed_pw = hash_password('admin') # Default password 'admin'
            cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                           ('admin', hashed_pw, 'admin'))
            print("Created default admin user (username: admin, password: admin)")
        except ImportError:
             print("Warning: Could not import hash_password from utils during initial DB setup.")
        except Exception as e:
            print(f"Error creating default admin user: {e}")


    conn.commit()
    conn.close()
    print("Database initialized.")

# === CRUD Operations ===

# --- User Operations ---
def add_user(username, password_hash, role):
    """Adds a new user to the database."""
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                     (username, password_hash, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"Error: Username '{username}' already exists.")
        return False
    except Exception as e:
        print(f"Database error adding user: {e}")
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    """Retrieves user details by username."""
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return user # Returns a Row object or None
    except Exception as e:
        print(f"Database error getting user: {e}")
        return None
    finally:
        conn.close()

# --- Service Operations ---
def add_service(name, description, base_price, duration):
    """Adds a new service."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO services (name, description, base_price, estimated_duration_minutes)
            VALUES (?, ?, ?, ?)
        """, (name, description, base_price, duration))
        conn.commit()
        return cursor.lastrowid # Return the ID of the newly inserted service
    except sqlite3.IntegrityError:
        print(f"Error: Service name '{name}' likely already exists.")
        return None
    except Exception as e:
        print(f"Database error adding service: {e}")
        return None
    finally:
        conn.close()

def get_all_services():
    """Retrieves all services from the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT service_id, name, description, base_price, estimated_duration_minutes FROM services ORDER BY name")
        services = cursor.fetchall()
        return services # List of Row objects
    except Exception as e:
        print(f"Database error getting services: {e}")
        return []
    finally:
        conn.close()

def delete_service(service_id):
    """Deletes a service by its ID."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Check if service is used in job_services? Optional, or handle via FK constraints/UI logic
        cursor.execute("DELETE FROM services WHERE service_id = ?", (service_id,))
        conn.commit()
        return cursor.rowcount > 0 # Return True if a row was deleted
    except Exception as e:
        print(f"Database error deleting service: {e}")
        return False
    finally:
        conn.close()


# --- Job Operations ---
def get_jobs_overview(limit=100):
    """Retrieves a summary of recent jobs."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Join with units and customers for more info, potentially employees too
        cursor.execute("""
            SELECT
                j.job_id,
                j.status,
                j.booking_date,
                u.make,
                u.model,
                u.license_plate,
                c.name as customer_name,
                e.name as employee_name
            FROM jobs j
            LEFT JOIN units u ON j.unit_id = u.unit_id
            LEFT JOIN customers c ON u.customer_id = c.customer_id
            LEFT JOIN employees e ON j.assigned_employee_id = e.employee_id
            ORDER BY j.created_at DESC
            LIMIT ?
        """, (limit,))
        jobs = cursor.fetchall()
        return jobs
    except Exception as e:
        print(f"Database error getting jobs overview: {e}")
        return []
    finally:
        conn.close()

# --- Placeholder for other CRUD functions ---
# def add_customer(...)
# def get_customer(...)
# def add_unit(...)
# def get_unit(...)
# def add_employee(...)
# def get_employee(...)
# def create_job(...)
# def update_job_status(...)
# def assign_employee_to_job(...)
# def add_service_to_job(...)
# def start_time_log(...)
# def end_time_log(...)
# def get_time_logs_for_job(...)
# def add_photo(...)
# def get_photos_for_job(...)
# def create_po(...)
# def add_po_item(...)
# def get_po(...)
# ... etc ...

