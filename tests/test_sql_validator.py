"""Unit tests for SQL validator and security module."""

import pytest
from utils.sql_validator import validate_sql, strip_sql_comments, mask_string_literals


def test_safe_select_query():
    sql = "SELECT C_CUSTKEY, C_NAME, C_ACCTBAL FROM CUSTOMER LIMIT 10;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is True
    assert "safe" in msg.lower()
    assert "LIMIT 10" in cleaned


def test_safe_with_query():
    sql = """
    WITH TopCustomers AS (
        SELECT C_CUSTKEY, SUM(O_TOTALPRICE) AS TOTAL_SPENT
        FROM CUSTOMER
        JOIN ORDERS ON C_CUSTKEY = O_CUSTKEY
        GROUP BY C_CUSTKEY
    )
    SELECT * FROM TopCustomers ORDER BY TOTAL_SPENT DESC LIMIT 10;
    """
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is True
    assert "safe" in msg.lower()


def test_safe_query_with_markdown_fences():
    sql = """```sql
    SELECT N_NAME, COUNT(*) FROM NATION JOIN CUSTOMER ON N_NATIONKEY = C_NATIONKEY GROUP BY N_NAME;
    ```"""
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is True
    assert not cleaned.startswith("```")


def test_safe_query_with_keyword_inside_string_literal():
    # String literal contains 'DROP' and 'DELETE' which should NOT trigger false positive
    sql = "SELECT * FROM CUSTOMER WHERE C_COMMENT LIKE '%DROP%' AND C_ADDRESS != 'DELETE STREET';"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is True


def test_blocked_insert():
    sql = "INSERT INTO CUSTOMER (C_CUSTKEY, C_NAME) VALUES (99999, 'Hacker');"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_blocked_update():
    sql = "UPDATE CUSTOMER SET C_ACCTBAL = 0 WHERE C_CUSTKEY = 1;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_blocked_delete():
    sql = "DELETE FROM ORDERS WHERE O_ORDERKEY = 100;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_blocked_drop():
    sql = "DROP TABLE CUSTOMER;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_blocked_alter():
    sql = "ALTER TABLE ORDERS DROP COLUMN O_COMMENT;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_blocked_truncate():
    sql = "TRUNCATE TABLE LINEITEM;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_blocked_create():
    sql = "CREATE TABLE MALICIOUS_TABLE (ID INT);"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_blocked_multiple_statements():
    sql = "SELECT * FROM CUSTOMER; DROP TABLE ORDERS;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Multiple SQL statements" in msg or "Unsafe SQL was blocked" in msg


def test_blocked_comment_injection():
    sql = "SELECT 1; -- comment\nDROP TABLE SUPPLIER;"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False


def test_blocked_non_select():
    sql = "EXECUTE IMMEDIATE 'SELECT 1';"
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
    assert "Unsafe SQL was blocked" in msg


def test_empty_query():
    sql = "   "
    is_valid, msg, cleaned = validate_sql(sql)
    assert is_valid is False
