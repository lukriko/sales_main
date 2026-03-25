from django.db import connection
import re

BLOCKED = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'EXEC', ';--', 'GRANT', 'REVOKE']

def is_safe(sql: str) -> bool:
    upper = sql.upper().strip()
    
    # Allow SELECT or WITH (for CTEs)
    if not re.match(r'^\s*(SELECT|WITH)\b', upper):
        return False
    
    return not any(kw in upper for kw in BLOCKED)

def run_query(sql: str, max_rows: int = 200) -> dict:
    if not is_safe(sql):
        return {"error": "Query blocked — only SELECT statements are allowed.", "sql": sql}

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchmany(max_rows)
            return {
                "columns": columns,
                "rows": [dict(zip(columns, row)) for row in rows],
                "row_count": len(rows),
                "sql": sql,
                "error": None
            }
    except Exception as e:
        return {"error": str(e), "sql": sql, "columns": [], "rows": []}