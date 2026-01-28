"""
Admin and database tools for the AI cog.
These require admin or owner permissions.
"""
import os
import re
import logging
from database import db

logger = logging.getLogger(__name__)


async def execute_sql(query: str, **kwargs):
    """
    Execute a read-only SQL query (SELECT) immediately.
    Use this to inspect data without waiting for approval.
    
    Args:
        query: The SQL SELECT statement.
    """
    guild_id = kwargs.get('guild_id')
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)

    if not (is_owner or is_admin):
        return "❌ Error: Permission Denied. You must be an Admin or Bot Owner to use this tool."

    query = query.strip()
    
    # Validate query type
    if not query.upper().startswith("SELECT"):
        return "❌ Error: Only SELECT queries are allowed."
    
    if ";" in query:
        return "❌ Error: Multiple statements (;) are not allowed."
    
    # Admin safety check - must include guild_id in query
    if not is_owner and guild_id:
        if str(guild_id) not in query:
            return f"❌ Error: Admin Safety Check Failed. Include `WHERE guild_id = {guild_id}` in your query."
    
    try:
        rows = await db.connection.execute_many(query)
        if not rows:
            return "No results found."
        
        # Format results
        if len(rows) > 20:
            rows = rows[:20]
            footer = "\n... (Truncated to 20 rows)"
        else:
            footer = ""
        
        headers = list(rows[0].keys()) if rows else []
        if headers:
            header_row = " | ".join(headers)
            sep_row = " | ".join(["---"] * len(headers))
            body = "\n".join([" | ".join(str(r[k]) for k in headers) for r in rows])
            return f"### SQL Result\n\n{header_row}\n{sep_row}\n{body}{footer}"
        else:
            return "Query executed. No rows returned."
            
    except Exception as e:
        return f"SQL Error: {e}"


async def search_codebase(query: str, is_regex: bool = False, **kwargs):
    """
    Search for a text pattern in the codebase.
    Returns file paths and line numbers where the pattern is found.
    
    Args:
        query: The string or regex pattern to search for.
        is_regex: If True, treats query as regex. Default False.
    """
    if not (kwargs.get('is_admin') or kwargs.get('is_owner')):
        return "❌ Error: Permission Denied."
    base_path = os.getcwd()
    allowed_extensions = ('.py', '.md', '.txt', '.json', '.sql')
    results = []
    
    pattern = None
    if is_regex:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as e:
            return f"Invalid Regex: {e}"

    count = 0
    MAX_RESULTS = 50

    for root, dirs, files in os.walk(base_path):
        # Skip common non-code directories
        if any(x in root for x in ['.git', '__pycache__', 'venv', 'node_modules', '.gemini']):
            continue
            
        for file in files:
            if not file.endswith(allowed_extensions):
                continue
            if file == '.env':
                continue
            
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_path)
            
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                for i, line in enumerate(lines, 1):
                    match = False
                    if is_regex and pattern:
                        if pattern.search(line):
                            match = True
                    else:
                        if query.lower() in line.lower():
                            match = True
                    
                    if match:
                        results.append(f"{rel_path}:{i}: {line.strip()[:200]}")
                        count += 1
                        if count >= MAX_RESULTS:
                            return "\n".join(results) + "\n... (More results truncated, refine search)"
            except Exception:
                continue
                
    return "\n".join(results) if results else "No matches found."


async def read_file(filename: str, start_line: int = 1, end_line: int = 100, **kwargs):
    """
    Read a file from the bot's codebase. 
    Reads first 100 lines by default. Specify lines to read more.
    
    Args:
        filename: Relative path to the file.
        start_line: Start line number (1-indexed). Default 1.
        end_line: End line number (inclusive). Default 100.
    """
    if not (kwargs.get('is_admin') or kwargs.get('is_owner')):
        return "❌ Error: Permission Denied."
    try:
        start_line = int(float(start_line))
        end_line = int(float(end_line))
    except (ValueError, TypeError):
        return "Invalid line numbers."

    allowed_extensions = ('.py', '.md', '.txt', '.json', '.sql')
    
    base_path = os.getcwd()
    full_path = os.path.normpath(os.path.join(base_path, filename))
    
    if not full_path.startswith(base_path):
        return "Error: Cannot access files outside the bot directory."
        
    if not filename.endswith(allowed_extensions) or '.env' in filename:
        return "Error: File type not allowed or restricted."

    try:
        if not os.path.exists(full_path):
            return f"Error: File '{filename}' not found."
             
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        if start_line < 1:
            start_line = 1
        if end_line > total_lines:
            end_line = total_lines
        
        selected_lines = lines[start_line-1:end_line]
        content = "".join(selected_lines)
        
        result = f"File: {filename} (Lines {start_line}-{end_line} of {total_lines})\n\n{content}"
        
        if end_line < total_lines:
            result += f"\n... (Total {total_lines} lines. Read more with read_file(filename, start_line={end_line+1}, end_line={min(end_line+100, total_lines)}))"
            
        return result
    except Exception as e:
        return f"Error reading file: {e}"


async def get_db_schema(**kwargs):
    """
    Get the current database schema (CREATE TABLE statements).
    Use this to understand table names, columns, and relationships.
    """
    if not (kwargs.get('is_admin') or kwargs.get('is_owner')):
        return "❌ Error: Permission Denied."
    try:
        tables = await db.connection.execute_many(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        
        if not tables:
            return "No tables found in the database."
            
        result = "## Database Schema\n"
        for row in tables:
            name = row['name']
            sql = row['sql']
            result += f"### Table: {name}\n```sql\n{sql}\n```\n"
            
        return result
    except Exception as e:
        return f"Error fetching schema: {e}"


async def update_server_config(setting: str, value: str, **kwargs):
    """
    Update a specific server configuration setting. (Admin Only).
    
    Args:
        setting: The setting to change. Allowed values:
                 - 'mushaf_type': (e.g. 'madani', 'tajweed', '13-line')
                 - 'pages_per_day': (Number 1-20)
                 - 'channel_id': (Channel ID)
                 - 'mosque_id': (String ID)
                 - 'followup_on_completion': ('true' or 'false')
                 - 'wird_role_id': (Role ID)
        value: The new value to set.
    """
    guild_id = kwargs.get('guild_id')
    if not (kwargs.get('is_admin') or kwargs.get('is_owner')):
        return "❌ Error: Permission Denied."
        
    if not guild_id:
        return "Error: Cannot update config without guild context."

    safe_map = {
        'mushaf_type': 'mushaf_type',
        'pages_per_day': 'pages_per_day',
        'channel_id': 'channel_id',
        'mosque_id': 'mosque_id', 
        'followup_on_completion': 'followup_on_completion',
        'wird_role_id': 'wird_role_id'
    }
    
    if setting not in safe_map:
        return f"Error: Setting '{setting}' is not allowed. Allowed: {', '.join(safe_map.keys())}"
    
    db_key = safe_map[setting]
    final_value = value
    
    try:
        if setting == 'pages_per_day':
            final_value = int(value)
            if not (1 <= final_value <= 20):
                raise ValueError("Pages must be between 1 and 20")
        elif setting in ('channel_id', 'wird_role_id'):
            # Extract ID from mention or raw number
            match = re.search(r'(\d+)', str(value))
            if match:
                final_value = int(match.group(1))
            else:
                raise ValueError("Invalid ID format")
        elif setting == 'followup_on_completion':
            final_value = 1 if str(value).lower() in ['true', '1', 'yes'] else 0
            
        kwargs = {db_key: final_value}
        await db.create_or_update_guild(guild_id, **kwargs)
        return f"✅ Successfully updated `{setting}` to `{final_value}`."
        
    except Exception as e:
        return f"Error updating config: {e}"


# Export list
ADMIN_TOOLS = [
    execute_sql,
    search_codebase,
    read_file,
    get_db_schema,
    update_server_config,
]
