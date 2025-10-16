#!/usr/bin/env python
"""
Simple script to create admin user using direct SQLite
"""
import sqlite3
import uuid
from datetime import datetime
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from app.core.security import get_password_hash

def create_admin():
    conn = sqlite3.connect('airport_mgmt.db')
    cursor = conn.cursor()
    
    # Check if admin exists
    cursor.execute("SELECT * FROM users WHERE username = ?", ('admin',))
    if cursor.fetchone():
        print("Admin user already exists")
        conn.close()
        return
    
    # Create admin user
    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO users (
            id, username, email, first_name, last_name, 
            hashed_password, is_active, is_superuser, role,
            created_at, updated_at, mfa_enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        'admin',
        'admin@example.com', 
        'Admin',
        'User',
        get_password_hash('admin123'),
        1,  # is_active
        1,  # is_superuser
        'SUPER_ADMIN',
        now,
        now,
        0  # mfa_enabled
    ))
    
    conn.commit()
    conn.close()
    
    print("Admin user created successfully!")
    print("Username: admin")
    print("Password: admin123")
    print("\nPLEASE CHANGE THE PASSWORD AFTER FIRST LOGIN!")

if __name__ == "__main__":
    create_admin()