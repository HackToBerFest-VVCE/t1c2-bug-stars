"""SQL Validator and Security Module for DataPilot.

Ensures that only safe, read-only SELECT or WITH statements are executed against Snowflake.
Blocks dangerous DDL, DML, multi-statement injection, and data-modifying queries.
"""

import re
from typing import Tuple

# Dangerous SQL operations that must be strictly blocked
DISALLOWED_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "MERGE",
    "GRANT",
    "REVOKE",
    "COPY",
    "PUT",
    "REMOVE",
    "CALL",
    "EXECUTE",
    "EXEC",
    "REPLACE",
    "UNDROP",
    "UNSET",
    "COMMIT",
    "ROLLBACK",
    "USE",
    "SYSTEM$",
]


def strip_sql_comments(sql: str) -> str:
    """Remove single-line and multi-line SQL comments.

    Handles:
      - Multi-line comments: /* ... */
      - Single-line comments: -- ... or // ...
    """
    # Remove block comments /* ... */
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove single line comments starting with -- or //
    sql = re.sub(r"(--|//)[^\r\n]*", " ", sql)
    return sql.strip()


def mask_string_literals(sql: str) -> str:
    """Mask string literals ('...') and dollar quotes ($$...$$) with placeholder tokens.

    This ensures that keywords appearing inside string values (e.g. 'DROP')
    are not falsely flagged as malicious statements.
    """
    # Replace dollar-quoted strings if any: $$...$$
    sql = re.sub(r"\$\$.*?\$\$", "'__STR__'", sql, flags=re.DOTALL)
    # Replace single-quoted string literals, handling escaped quotes ''
    sql = re.sub(r"'(?:''|[^'])*'", "'__STR__'", sql)
    return sql


def validate_sql(raw_sql: str) -> Tuple[bool, str, str]:
    """Validate that the given SQL query is a single, safe, read-only query.

    Returns:
        (is_valid: bool, message: str, cleaned_sql: str)
    """
    if not raw_sql or not raw_sql.strip():
        return False, "Query is empty.", ""

    # 1. Clean markdown code fences if present
    sql = raw_sql.strip()
    if sql.startswith("```"):
        # Match ```sql ... ``` or ``` ... ```
        lines = sql.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        sql = "\n".join(lines).strip()

    # 2. Strip comments
    comment_free_sql = strip_sql_comments(sql)
    if not comment_free_sql:
        return False, "Query contains only comments or whitespace.", ""

    # 3. Check for multiple statements (semicolons separating queries)
    # Strip trailing semicolons first
    cleaned_sql = comment_free_sql.rstrip("; \t\r\n").strip()

    # Mask strings to inspect structural semicolons and keywords safely
    masked_sql = mask_string_literals(cleaned_sql)

    # Detect any internal semicolons outside strings
    if ";" in masked_sql:
        return False, "Unsafe SQL was blocked: Multiple SQL statements are not permitted.", ""

    # 4. Verify the statement begins with SELECT or WITH
    first_word_match = re.match(r"^\s*([A-Za-z]+)", masked_sql)
    if not first_word_match:
        return False, "Unsafe SQL was blocked: Could not parse query command.", ""

    first_keyword = first_word_match.group(1).upper()
    if first_keyword not in ("SELECT", "WITH"):
        return (
            False,
            f"Unsafe SQL was blocked: Only SELECT and WITH queries are allowed. Found '{first_keyword}'.",
            "",
        )

    # 5. If it's a WITH (CTE) statement, ensure it contains a SELECT
    if first_keyword == "WITH":
        # Check that a SELECT keyword exists in the masked SQL
        if not re.search(r"\bSELECT\b", masked_sql, re.IGNORECASE):
            return (
                False,
                "Unsafe SQL was blocked: WITH expression must contain a valid SELECT query.",
                "",
            )

    # 6. Check for disallowed destructive/administrative keywords outside strings
    for keyword in DISALLOWED_KEYWORDS:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, masked_sql, re.IGNORECASE):
            return (
                False,
                f"Unsafe SQL was blocked: Disallowed keyword '{keyword}' detected.",
                "",
            )

    return True, "SQL is safe and read-only.", cleaned_sql
