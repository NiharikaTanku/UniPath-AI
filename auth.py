import sqlite3
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    """Returns a SHA-256 hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(email, password):
    """
    Creates a new user. 
    Returns True if successful, False if email already exists or error occurs.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        hashed_pw = hash_password(password)
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Database error: {e}")
        return False

def verify_user(email, password):
    """
    Verifies user credentials.
    Returns True if valid, False otherwise.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hashed_pw))
    user = cursor.fetchone()
    conn.close()
    return user is not None
