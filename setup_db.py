#!/usr/bin/env python3
"""
Ulwazi Setup
One-time initialization of the SQLite database
"""

import sqlite3
from pathlib import Path

# Configuration - must match ulwazi.py
DB_FILE = Path('/mnt/ssd/Applications/ulwazi/ulwazi.db')

def setup_database():
    """Create the database and tables"""
    
    # Ensure the directory exists
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating database at: {DB_FILE}")
    
    # Create database and tables
    conn = sqlite3.connect(DB_FILE)

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # Table: ksbs
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ksbs (
            standard    TEXT NOT NULL,
            code        TEXT NOT NULL,
            category    TEXT CHECK(category IN ('Knowledge', 'Skill', 'Behaviour')),
            description TEXT,
            PRIMARY KEY (standard, code)
        )
    ''')

    # Table: module_ksbs
    conn.execute('''
        CREATE TABLE IF NOT EXISTS module_ksbs (
            standard      TEXT NOT NULL,
            ksb_code      TEXT NOT NULL,
            phase         TEXT CHECK(phase IN ('Discover', 'Module')),
            module_number INTEGER,
            PRIMARY KEY (standard, ksb_code, phase, module_number),
            FOREIGN KEY (standard, ksb_code) REFERENCES ksbs(standard, code)
                ON DELETE CASCADE
        )
    ''')

    # Table: session_ksbs
    conn.execute('''
        CREATE TABLE IF NOT EXISTS session_ksbs (
            standard       TEXT NOT NULL,
            ksb_code       TEXT NOT NULL,
            module_number  INTEGER NOT NULL,
            day_number     INTEGER NOT NULL,
            session_number INTEGER NOT NULL,
            notes TEXT,
            PRIMARY KEY (standard, ksb_code, module_number, day_number, session_number),
            FOREIGN KEY (standard, ksb_code) REFERENCES ksbs(standard, code)
                ON DELETE CASCADE
        )
    ''')

    # Table: content
    conn.execute('''
    ''')

    conn.commit()
    conn.close()
    
    print("✓ Database created successfully!")
    print("✓ Table 'ksbs' created")
    print("✓ Table 'module_ksbs' created")
    print("✓ Table 'session_ksbs' created")
    print(f"✓ Database location: {DB_FILE}")
    print("\nYou can now use ulwazi commands:")
    print("  ulwazi course DE5")
    print("  ulwazi ksb K2 --add 'Description here'")
    print("  ulwazi coverage -m 2 -d 1")

if __name__ == '__main__':
    setup_database()

