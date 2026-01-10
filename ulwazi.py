#!/usr/bin/env python3
"""
Ulwazi - KSB Mapping Tool for Apprenticeship Training
"""

import click
import sqlite3
import json
from pathlib import Path

# Configuration
CONFIG_DIR = Path.home() / '.ulwazi'
CONFIG_FILE = CONFIG_DIR / 'config.json'
DB_FILE = Path('/mnt/ssd/Applications/ulwazi/ulwazi.db')


def ensure_config_dir():
    """Ensure config directory exists"""
    CONFIG_DIR.mkdir(exist_ok=True)


def load_config():
    """Load current configuration"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save configuration"""
    ensure_config_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_current_course():
    """Get the currently set course"""
    config = load_config()
    return config.get('current_course')


def init_database():
    """Initialise the SQLite database"""
    if not DB_FILE.exists():
        click.echo("Database not found. Run 'python setup_db.py' first.")
        exit(1)
    return


def get_db_connection():
    """Get database connection with foreign key support"""
    if not DB_FILE.exists():
        click.echo("Database not found. Run 'python setup_db.py' first.")
        exit(1)
    
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """Ulwazi - KSB Mapping Tool"""
    init_database()


@cli.command()
@click.argument('course_code')
def course(course_code):
    """Set the current working course (DE5 or DA4)"""
    course_code = course_code.upper()
    
    if course_code not in ['DE5', 'DA4', 'TEST']:
        click.echo("Course must be DE5 or DA4")
        return
    
    config = load_config()
    config['current_course'] = course_code
    save_config(config)
    
    click.echo(f"Set current course to: {course_code}")


@cli.command()
def current():
    """Show the current working course"""
    course_code = get_current_course()
    if not course_code:
        click.echo("No current course set. Use 'ulwazi course <DE5|DA4>' to set one.")
        return
    
    click.echo(f"Currently working on: {course_code}")


@cli.command()
@click.argument('code')
@click.option('--add', 'description', help='Add a new KSB with description')
@click.option('--update', help='Update KSB description')
@click.option('--remove', is_flag=True, help='Remove KSB (and all mappings)')
def ksb(code, description, update, remove):
    """Manage KSBs (view, add, update, remove)"""
    course_code = get_current_course()

    if not course_code:
        click.echo("No current course set. Use 'ulwazi course <DE5|DA4>' first.")
        return

    code = code.upper()

    # Determine category from code
    if code.startswith('K'):
        category = 'Knowledge'
    elif code.startswith('S'):
        category = 'Skill'
    elif code.startswith('B'):
        category = 'Behaviour'
    else:
        click.echo("KSB code must start with K, S, or B")
        return

    conn = get_db_connection()

    # Add new KSB
    if description:
        try:
            conn.execute('''
                INSERT INTO ksbs (standard, code, category, description)
                VALUES (?, ?, ?, ?)
            ''', (course_code, code, category, description))
            conn.commit()
            click.echo(f"Added {code} ({category}) to {course_code}")
        except sqlite3.IntegrityError:
            click.echo(f"Error: {code} already exists in {course_code}")
            click.echo("Use --update to modify it")
        conn.close()
        return

    # Update existing KSB
    if update:
        result = conn.execute('''
            UPDATE ksbs
            SET description = ?
            WHERE standard = ? AND code = ?
        ''', (update, course_code, code))

        if result.rowcount == 0:
            click.echo(f"Error: {code} not found in {course_code}")
        else:
            conn.commit()
            click.echo(f"Updated {code} description")
        conn.close()
        return

    # Remove KSB
    if remove:
        result = conn.execute('''
            DELETE FROM ksbs
            WHERE standard = ? AND code = ?
        ''', (course_code, code))

        if result.rowcount == 0:
            click.echo(f"Error: {code} not found in {course_code}")
        else:
            conn.commit()
            click.echo(f"Removed {code} (and all mappings)")
        conn.close()
        return

    # View KSB (default behaviour)
    result = conn.execute('''
        SELECT code, category, description
        FROM ksbs
        WHERE standard = ? AND code = ?
    ''', (course_code, code)).fetchone()

    if not result:
        click.echo(f"{code} not found in {course_code}")
        conn.close()
        return

    code, category, desc = result
    click.echo(f"\n{code} ({category})")
    click.echo("-" * 50)
    click.echo(desc)
    click.echo()

    conn.close()

if __name__ == '__main__':
    cli()

