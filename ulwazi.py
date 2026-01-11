#!/usr/bin/env python3
"""
Ulwazi - KSB Mapping Tool for Apprenticeship Training
"""

import re
import click
import sqlite3
import json

from pathlib import Path
from collections import defaultdict

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


def get_current_course(course):
    """Get the currently set course"""
    if course is not None:
        return course.upper().strip()

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


# Display grouped by category with natural sorting
def natural_sort_key(code):
    """Extract number from code for natural sorting (K1, K2, K11)"""
    match = re.search(r'\d+', code)
    return int(match.group()) if match else 0


# Sort by category first, then by natural number within category
def full_sort_key(code, ksb_data):
    """Sort by category first, then by natural number within category"""
    category = ksb_data[code]['category']
    return (category, natural_sort_key(code))


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """Ulwazi - KSB Mapping Tool"""
    init_database()


@cli.command()
@click.argument('course_code')
def course(course_code):
    """Set the current working course (DE5 or DA4)"""
    course_code = course_code.upper().strip()
    
    if course_code not in ['DE5', 'DA4', 'TEST']:
        click.echo("Course must be DE5 or DA4")
        return
    
    config = load_config()
    config['current_course'] = course_code
    save_config(config)
    
    click.echo(f"Current course now set to: {course_code}")


@cli.command()
def current():
    """Show the current working course"""
    course_code = get_current_course(None)
    if not course_code:
        click.echo("No current course set. Use 'ulwazi course <DE5|DA4>' to set one.")
        return
    
    click.echo(f"Currently working on: {course_code}")


@cli.command()
@click.argument('code')
@click.option('--course', help='Course code (Uses current course if not specified)')
@click.option('--add', 'description', help='Add a new KSB with description')
@click.option('--update', help='Update KSB description')
@click.option('--remove', is_flag=True, help='Remove KSB (and all mappings)')
def ksb(code, course, description, update, remove):
    """Manage KSBs (view, add, update, remove)"""
    course_code = get_current_course(course)

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


@cli.command()
@click.option('--course', help='Course code (Uses current course if not specified)')
@click.option('--ksb', help='Filter by category (k/s/b)')
@click.option('--desc', 'show_desc', is_flag=True, help='Show KSB description')
def show(course, ksb, show_desc):
    """Show all KSBs for current course"""
    course_code = get_current_course(course)
    
    if not course_code:
        click.echo("No current course set. Use 'ulwazi course <DE5|DA4>' first.")
        return
    
    conn = get_db_connection()
    
    # Build query with LEFT JOIN to get module mappings
    query = '''
        SELECT k.code, k.category, k.description, m.phase, m.module_number
        FROM ksbs k
        LEFT OUTER JOIN module_ksbs m 
            ON k.standard = m.standard AND k.code = m.ksb_code
        WHERE k.standard = ?
    '''
    params = [course_code]

    # Build query based on filter
    category = ''
    if ksb:
        category = {
            'k': 'Knowledge',
            's': 'Skill', 
            'b': 'Behaviour'
        }.get(ksb.lower())
        
        if not category:
            click.echo("Use --ksb k, --ksb s, or --ksb b")
            return
 
        query += ' AND k.category = ?'
        params.append(category)
    
    query += ' ORDER BY k.category, k.code, m.phase, m.module_number'
    
    results = conn.execute(query, params).fetchall()
    conn.close()
    
    if not results:
        click.echo(f"List: No {category} KSBs found for {course_code}")
        return
    
    click.echo(f"\nCourse: {course_code}")
    
    # Group results by code
    ksb_data = defaultdict(lambda: {'category': None, 'mappings': []})
    
    for code, category, description, phase, module_number in results:
        ksb_data[code]['category'] = category
        ksb_data[code]['description'] = description
        if phase:  # Only add if there's a mapping
            if phase == 'Discover':
                ksb_data[code]['mappings'].append('Discover')
            else:
                ksb_data[code]['mappings'].append(f'M{module_number}')
    
    # Display grouped by category
    current_category = None
    for code in sorted(ksb_data.keys(), key=lambda c: full_sort_key(c, ksb_data)):
        category = ksb_data[code]['category']
        description = ksb_data[code]['description']
        mappings = ksb_data[code]['mappings']
        
        if category != current_category:
            click.echo(f"\n{category}:")
            current_category = category
        
        if mappings:
            click.echo(f"  {code:<3} - {', '.join(mappings)}")
            if show_desc: click.echo(f"        {description[:100]}\n")
        else:
            click.echo(f"  {code:<3} ~ {description[:100]}")

    click.echo()


@cli.command()
@click.argument('code')
@click.option('--course', help='Course code (Uses current course if not specified)')
@click.option('-m', '--module', type=int, help='Module number (1-7)')
@click.option('--discover', is_flag=True, help='Map to Discover phase')
@click.option('--remove', is_flag=True, help='Remove this mapping')
def map(code, course, module, discover, remove):
    """Map a KSB to a module or Discover phase"""
    course_code = get_current_course(course)

    if not course_code:
        click.echo("No current course set. Use 'ulwazi course <DE5|DA4>' first.")
        return

    code = code.upper()

    # Validate: must specify either module or discover (not both)
    if module and discover:
        click.echo("Error: Specify either --module or --discover, not both")
        return

    if not module and not discover:
        click.echo("Error: Specify either --module <N> or --discover")
        return

    # Determine phase and module_number
    if discover:
        phase = 'Discover'
        module_number = None
    else:
        phase = 'Module'
        module_number = module

    conn = get_db_connection()

    # Check KSB exists
    exists = conn.execute('''
        SELECT 1 FROM ksbs
        WHERE standard = ? AND code = ?
    ''', (course_code, code)).fetchone()

    if not exists:
        click.echo(f"Error: {code} not found in {course_code}")
        click.echo(f"Add it first with: ulwazi ksb {code} --add 'Description'")
        conn.close()
        return

    # Remove mapping
    if remove:
        result = conn.execute('''
            DELETE FROM module_ksbs
            WHERE standard = ? AND ksb_code = ? AND phase = ?
            AND (module_number = ? OR (module_number IS NULL AND ? IS NULL))
        ''', (course_code, code, phase, module_number, module_number))

        if result.rowcount == 0:
            location = f"Discover" if discover else f"M{module}"
            click.echo(f"Error: {course_code} ~ No mapping found for {code} in {location}")
        else:
            conn.commit()
            location = f"Discover" if discover else f"M{module}"
            click.echo(f"{course_code}: Removed {code} from {location}")
        conn.close()
        return

    # Add mapping
    try:
        conn.execute('''
            INSERT INTO module_ksbs (standard, ksb_code, phase, module_number)
            VALUES (?, ?, ?, ?)
        ''', (course_code, code, phase, module_number))
        conn.commit()
        location = f"Discover" if discover else f"M{module}"
        click.echo(f"{course_code}: Mapped {code} to {location}")
    except sqlite3.IntegrityError:
        location = f"Discover" if discover else f"M{module}"
        click.echo(f"Error: {course_code} ~ {code} already mapped to {location}")

    conn.close()


@cli.command()
@click.option('--course', help='Course code (Uses current course if not specified)')
@click.option('-m', '--module', type=int, help='Module number (1-7)')
@click.option('--discover', is_flag=True, help='Show Discover phase KSBs')
@click.option('--ksb', help='Filter by category (k/s/b)')
def coverage(course, module, discover, ksb):
    """Show KSB coverage for a module or Discover phase"""
    course_code = get_current_course(course)
    
    if not course_code:
        click.echo("No current course set. Use 'ulwazi course <DE5|DA4>' first.")
        return
    
    # Validate: must specify either module or discover
    if module and discover:
        click.echo("Error: Specify either --module or --discover, not both")
        return
    
    if not module and not discover:
        click.echo("Error: Specify either --module <N> or --discover")
        return
    
    # Determine phase and module_number
    if discover:
        phase = 'Discover'
        module_number = None
        location = 'Discover'
    else:
        phase = 'Module'
        module_number = module
        location = f'M{module}'
    
    conn = get_db_connection()
    
    # Build query
    query = '''
        SELECT k.code, k.category, k.description
        FROM ksbs k
        INNER JOIN module_ksbs m 
            ON k.standard = m.standard AND k.code = m.ksb_code
        WHERE k.standard = ? AND m.phase = ?
    '''
    params = [course_code, phase]
    
    if not discover:
        query += ' AND m.module_number = ?'
        params.append(module_number)
    
    if ksb:
        category = {
            'k': 'Knowledge',
            's': 'Skill', 
            'b': 'Behaviour'
        }.get(ksb.lower())
        
        if not category:
            click.echo("Use --ksb k, --ksb s, or --ksb b")
            conn.close()
            return
        
        query += ' AND k.category = ?'
        params.append(category)
    
    query += ' ORDER BY k.category, k.code'
    
    results = conn.execute(query, params).fetchall()
    conn.close()
    
    if not results:
        click.echo(f"Coverage: No KSBs found for {course_code} {location}")
        return
    
    click.echo(f"\nCourse: {course_code} - {location}\n")
    
    # Group by category
    by_category = defaultdict(list)
    for code, category, description in results:
        by_category[category].append((code, description))
    
    # Display
    for category in sorted(by_category.keys()):
        click.echo(f"{category}:")
        for code, description in sorted(by_category[category], key=lambda x: natural_sort_key(x[0])):
            click.echo(f"  {code}: {description[:100]}")
        click.echo()


@cli.command()
@click.argument('code')
@click.option('--course', help='Course code (Uses current course if not specified)')
@click.option('-m', '--module', type=int, required=True, help='Module number (1-7)')
@click.option('-d', '--day',    type=int, required=True, help='Day number (1-5)')
@click.option('-s', '--session',type=int, required=True, help='Session number (1-4)')
@click.option('--notes', help='Session notes (how/why this KSB is covered)')
@click.option('--remove', is_flag=True, help='Remove session mapping')
def session(code, course, module, day, session, notes, remove):
    """Map a KSB to a specific session"""
    course_code = get_current_course(course)

    if not course_code:
        click.echo("No current course set. Use 'ulwazi course <DE5|DA4>' first.")
        return

    code = code.upper()

    conn = get_db_connection()

    # Check KSB exists
    exists = conn.execute('''
        SELECT 1 FROM ksbs
        WHERE standard = ? AND code = ?
    ''', (course_code, code)).fetchone()

    if not exists:
        click.echo(f"Error: {code} not found in {course_code}")
        click.echo(f"Add it first with: ulwazi ksb {code} --add 'Description'")
        conn.close()
        return

    # Check KSB is mapped to this module
    module_mapped = conn.execute('''
        SELECT 1 FROM module_ksbs
        WHERE standard = ? AND ksb_code = ?
        AND phase = 'Module' AND module_number = ?
    ''', (course_code, code, module)).fetchone()

    if not module_mapped:
        click.echo(f"Error: {code} not mapped to M{module}")
        click.echo(f"Map it first with: ulwazi map {code} -m {module}")
        conn.close()
        return

    # Remove session mapping
    if remove:
        result = conn.execute('''
            DELETE FROM session_ksbs
            WHERE standard = ? AND ksb_code = ?
            AND module_number = ? AND day_number = ? AND session_number = ?
        ''', (course_code, code, module, day, session))

        if result.rowcount == 0:
            click.echo(f"Error: No session mapping found for {code} in M{module}D{day}S{session}")
        else:
            conn.commit()
            click.echo(f"Session: Removed {code} from M{module}/D{day}S{session}")
        conn.close()
        return

    # Update notes
    if notes:
        result = conn.execute('''
            UPDATE session_ksbs
            SET notes = ?
            WHERE standard = ? AND ksb_code = ?
            AND module_number = ? AND day_number = ? AND session_number = ?
        ''', (notes, course_code, code, module, day, session))

        if result.rowcount == 0:
            click.echo(f"Error: No session mapping found for {code} in M{module}D{day}S{session}")
            click.echo(f"Add it first with: ulwazi session {code} -m {module} -d {day} -s {session}")
        else:
            conn.commit()
            click.echo(f"Session: Updated notes for {code} in M{module}/D{day}S{session}")
        conn.close()
        return

    # Add session mapping (with optional notes)
    try:
        conn.execute('''
            INSERT INTO session_ksbs 
                (standard, ksb_code, module_number, day_number, session_number, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (course_code, code, module, day, session, notes or ''))
        conn.commit()
        notes_part = f" with notes" if notes else ""
        click.echo(f"Session: Mapped {code} to M{module}/D{day}S{session}{notes_part}")
    except sqlite3.IntegrityError:
        click.echo(f"Error: {code} already mapped to M{module}/D{day}S{session}")
        click.echo(f"Use --notes to modify notes or --remove to delete")

    conn.close()


if __name__ == '__main__':
    cli()

