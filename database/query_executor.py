"""Snowflake Query Executor for DataPilot.

Executes validated SQL queries against Snowflake and converts the results to pandas DataFrames.
Safely manages resources, tracks execution time, and provides clear error feedback.
"""

import time
from typing import Dict, Any, Optional
import pandas as pd
from database.snowflake_connection import get_connection
from utils.sql_validator import validate_sql


def execute_query(
    sql: str,
    max_rows: int = 500,
    override_password: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate and execute a read-only SQL query on Snowflake.

    Args:
        sql: SQL query string to run
        max_rows: Maximum rows to fetch into DataFrame (protects memory)
        override_password: Optional password if provided via UI

    Returns:
        dict with keys:
          - success: bool
          - data: pd.DataFrame (if success)
          - row_count: int
          - col_count: int
          - execution_time_sec: float
          - error: str (if failed)
          - validated_sql: str
    """
    # 1. Enforce strict SQL validation before any connection or execution
    is_valid, validation_msg, cleaned_sql = validate_sql(sql)
    if not is_valid:
        return {
            "success": False,
            "data": pd.DataFrame(),
            "row_count": 0,
            "col_count": 0,
            "execution_time_sec": 0.0,
            "error": validation_msg,
            "validated_sql": "",
        }

    start_time = time.time()
    conn = None

    try:
        conn = get_connection(override_password)
        with conn.cursor() as cur:
            cur.execute(cleaned_sql)

            # Retrieve column names
            columns = [desc[0] for desc in cur.description] if cur.description else []

            # Fetch rows with safe ceiling
            rows = cur.fetchmany(max_rows)
            df = pd.DataFrame(rows, columns=columns)

            execution_time = round(time.time() - start_time, 2)

            return {
                "success": True,
                "data": df,
                "row_count": len(df),
                "col_count": len(columns),
                "execution_time_sec": execution_time,
                "error": "",
                "validated_sql": cleaned_sql,
            }

    except PermissionError as pe:
        return {
            "success": False,
            "data": pd.DataFrame(),
            "row_count": 0,
            "col_count": 0,
            "execution_time_sec": round(time.time() - start_time, 2),
            "error": f"Snowflake Authentication Error: {str(pe)}",
            "validated_sql": cleaned_sql,
        }
    except LookupError as le:
        return {
            "success": False,
            "data": pd.DataFrame(),
            "row_count": 0,
            "col_count": 0,
            "execution_time_sec": round(time.time() - start_time, 2),
            "error": f"Snowflake Resource Error: {str(le)}",
            "validated_sql": cleaned_sql,
        }
    except ConnectionError as ce:
        return {
            "success": False,
            "data": pd.DataFrame(),
            "row_count": 0,
            "col_count": 0,
            "execution_time_sec": round(time.time() - start_time, 2),
            "error": f"Snowflake Connection Failed: {str(ce)}",
            "validated_sql": cleaned_sql,
        }
    except Exception as e:
        return {
            "success": False,
            "data": pd.DataFrame(),
            "row_count": 0,
            "col_count": 0,
            "execution_time_sec": round(time.time() - start_time, 2),
            "error": f"Snowflake Query Error: {str(e)}",
            "validated_sql": cleaned_sql,
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
