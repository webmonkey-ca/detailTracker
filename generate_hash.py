# generate_hash.py
import hashlib
import os

def hash_password(password):
    """Hashes the password using SHA-256 with a salt (matches utils.py)."""
    salt = os.urandom(16) # Generate a random salt
    # Use the same iteration count as in utils.py (100000)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    # Store salt and hash together, separated by ':'
    return salt.hex() + ':' + pwd_hash.hex()

# --- Set the password you want to hash ---
password_to_hash = "Murray11"

# --- Generate and print the hash ---
hashed_output = hash_password(password_to_hash)
print(f"Password: {password_to_hash}")
print(f"Hashed Output (salt:hash): {hashed_output}")
print("\nCopy the Hashed Output string above to insert into your database.")
