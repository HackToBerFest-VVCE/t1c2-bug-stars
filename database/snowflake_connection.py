"""Snowflake Connection Manager for DataPilot.

Handles connection lifecycle, credential retrieval, health checks, and secure error formatting.
Never exposes sensitive credentials in error logs or UI messages.
"""

import os
from typing import Tuple, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    import snowflake.connector
    from snowflake.connector.errors import (
        ProgrammingError,
        DatabaseError,
        OperationalError,
        InterfaceError,
    )
except ImportError:
    snowflake = None
    ProgrammingError = DatabaseError = OperationalError = InterfaceError = Exception


def get_snowflake_config(override_password: Optional[str] = None) -> Dict[str, str]:
    """Retrieve Snowflake configuration from environment variables or runtime overrides."""
    # Ensure fresh .env is loaded if modified
    load_dotenv(override=True)

    return {
        "account": os.getenv("SNOWFLAKE_ACCOUNT", "rwtlwzu-we51517").strip(),
        "user": os.getenv("SNOWFLAKE_USER", "BINDU709").strip(),
        "password": (override_password if override_password is not None else os.getenv("SNOWFLAKE_PASSWORD", "")).strip(),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH").strip(),
        "database": os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_SAMPLE_DATA").strip(),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "TPCH_SF1").strip(),
        "role": os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN").strip(),
    }


def get_connection(override_password: Optional[str] = None):
    """Establish and return a Snowflake connection.

    Raises descriptive, safe exceptions without leaking credentials.
    """
    if snowflake is None:
        raise RuntimeError("snowflake-connector-python is not installed in the environment.")

    cfg = get_snowflake_config(override_password)

    if not cfg["password"]:
        raise ValueError(
            "Snowflake password is not configured. Please set SNOWFLAKE_PASSWORD in your .env file "
            "or enter it in the application sidebar."
        )

    try:
        conn = snowflake.connector.connect(
            account=cfg["account"],
            user=cfg["user"],
            password=cfg["password"],
            warehouse=cfg["warehouse"],
            database=cfg["database"],
            schema=cfg["schema"],
            role=cfg["role"],
            autocommit=True,
            client_session_keep_alive=False,
            login_timeout=15,
            network_timeout=30,
        )
        return conn

    except ProgrammingError as pe:
        msg = str(pe)
        if "Incorrect username or password" in msg or "250001" in msg or "Authentication" in msg:
            raise PermissionError("Snowflake authentication failed. Please verify your username and password.")
        elif "Object does not exist" in msg:
            raise LookupError(f"Snowflake warehouse/database/schema not found: {msg}")
        else:
            raise RuntimeError(f"Snowflake query/permission error: {msg}")

    except (OperationalError, InterfaceError) as oe:
        raise ConnectionError(
            f"Snowflake network or host connection error. Check account identifier '{cfg['account']}': {str(oe)}"
        )
    except Exception as e:
        # Never leak password in generic exceptions
        safe_msg = str(e).replace(cfg["password"], "********") if cfg["password"] else str(e)
        raise RuntimeError(f"Snowflake connection error: {safe_msg}")


def test_connection(override_password: Optional[str] = None) -> Tuple[bool, str]:
    """Test the Snowflake connection by running a safe metadata probe.

    Returns:
        (is_connected: bool, status_message: str)
    """
    cfg = get_snowflake_config(override_password)
    if not cfg["password"]:
        return (
            False,
            "Snowflake Not Connected (Password not set in .env or sidebar)",
        )

    try:
        conn = get_connection(override_password)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT CURRENT_VERSION(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
                row = cur.fetchone()
                version, wh, db, sc = row if row else ("Unknown", "", "", "")
                return True, f"Snowflake Connected (v{version} | WH: {wh} | {db}.{sc})"
        finally:
            conn.close()
    except Exception as e:
        return False, f"Snowflake Not Connected: {str(e)}"
