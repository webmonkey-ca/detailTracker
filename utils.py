# utils.py
import hashlib
import os
import shutil
import datetime
from PIL import Image, ImageTk # For displaying images in Tkinter
import tkinter as tk
from tkinter import filedialog, messagebox
import database # Import database to access PHOTOS_DIR etc.

# --- Security ---
def hash_password(password):
    """Hashes the password using SHA-256 with a salt."""
    salt = os.urandom(16) # Generate a random salt
    # Use a high iteration count (e.g., 100000 or more)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    # Store salt and hash together, separated by a character (e.g., ':')
    return salt.hex() + ':' + pwd_hash.hex()

def verify_password(stored_password_hash, provided_password):
    """Verifies a provided password against the stored hash."""
    if not stored_password_hash or ':' not in stored_password_hash:
        # Handle cases where the stored hash is missing or invalid
        print("Warning: Invalid stored password hash format.")
        return False
    try:
        salt_hex, hash_hex = stored_password_hash.split(':', 1)
        salt = bytes.fromhex(salt_hex)
        # Use the same parameters (hash type, salt, iterations) as when hashing
        provided_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        # Compare the generated hash with the stored hash
        return provided_hash.hex() == hash_hex
    except (ValueError, TypeError) as e:
        # Handle potential errors during hex decoding or hashing
        print(f"Error verifying password: {e}")
        return False

# --- File Handling for Photos ---
def save_checkin_photo(job_id, unit_id, source_file_path):
    """Copies a selected photo to the designated storage area for a unit/job
       and returns the relative path stored in the database."""
    if not source_file_path or not os.path.exists(source_file_path):
        print("Error: Source file path is invalid or does not exist.")
        return None

    try:
        # Ensure the base photos directory exists
        database.ensure_data_dirs() # Ensures database.PHOTOS_DIR exists

        # Create a subdirectory for the specific unit if it doesn't exist
        unit_photo_dir = os.path.join(database.PHOTOS_DIR, f"unit_{unit_id}")
        os.makedirs(unit_photo_dir, exist_ok=True)

        # Create a unique filename to avoid collisions
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        _, file_extension = os.path.splitext(source_file_path)
        if not file_extension: file_extension = '.jpg' # Provide a default extension

        # Make filename more descriptive
        filename = f"job_{job_id}_unit_{unit_id}_{timestamp}{file_extension}"
        destination_path = os.path.join(unit_photo_dir, filename)

        # Copy the file
        shutil.copy2(source_file_path, destination_path) # copy2 preserves metadata

        # Return the relative path from the main data directory for storage
        # Example: 'photos/unit_123/job_45_unit_123_20250421_....jpg'
        relative_path = os.path.relpath(destination_path, database.DATABASE_DIR)
        print(f"Photo saved to: {destination_path}")
        print(f"Relative path for DB: {relative_path}")
        return relative_path.replace('\\', '/') # Ensure forward slashes for consistency

    except Exception as e:
        print(f"Error saving photo: {e}")
        messagebox.showerror("Photo Error", f"Could not save photo: {e}")
        return None

def get_absolute_photo_path(relative_path):
    """Converts a relative photo path (from DB) to an absolute path."""
    if not relative_path:
        return None
    # Assuming relative_path is relative to DATABASE_DIR
    return os.path.join(database.DATABASE_DIR, relative_path)


# --- Tkinter Image Loading Helper ---
def load_image_for_tkinter(path, size=(100, 100)):
    """Loads an image from an absolute path, resizes if needed,
       and returns a PhotoImage object suitable for Tkinter.
       Returns a placeholder if loading fails."""
    try:
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Image path not found: {path}")

        img = Image.open(path)
        img.thumbnail(size, Image.Resampling.LANCZOS) # High-quality downscaling
        return ImageTk.PhotoImage(img)
    except FileNotFoundError:
         print(f"Error loading image: File not found at {path}")
    except Exception as e:
        print(f"Error loading image {path}: {e}")

    # Return a placeholder image if loading failed
    try:
        placeholder = Image.new('RGB', size, color = '#CCCCCC') # Light grey placeholder
        # Optional: Add text to placeholder
        # from PIL import ImageDraw
        # draw = ImageDraw.Draw(placeholder)
        # draw.text((5, 5), "No Image", fill='#000000')
        return ImageTk.PhotoImage(placeholder)
    except Exception as pe:
        print(f"Error creating placeholder image: {pe}")
        return None # Should not happen, but fallback

# --- Simple Dialogs ---
def ask_for_file(parent, title="Select File", filetypes=None):
    """Shows a file dialog and returns the selected filepath."""
    if filetypes is None:
        filetypes=[("All Files", "*.*")]
    filepath = filedialog.askopenfilename(
        parent=parent,
        title=title,
        filetypes=filetypes
    )
    return filepath # Returns the full path or an empty string if cancelled

# --- Data Validation ---
def validate_price(price_str):
    """Attempts to convert string to float price, returns float or None."""
    try:
        price = float(price_str)
        if price >= 0:
            return price
        else:
            return None # Price cannot be negative
    except (ValueError, TypeError):
        return None

def validate_duration(duration_str):
    """Attempts to convert string to integer duration, returns int or None."""
    try:
        duration = int(duration_str)
        if duration >= 0:
            return duration
        else:
            return None # Duration cannot be negative
    except (ValueError, TypeError):
        return None

