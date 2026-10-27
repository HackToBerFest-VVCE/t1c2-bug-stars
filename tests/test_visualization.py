"""Unit tests for DataPilot visualization module."""

import decimal
import pandas as pd
import pytest
from visualization.charts import (
    format_column_label,
    is_currency_metric,
    is_id_or_key_column,
    pick_best_chart_columns,
    auto_create_chart,
    detect_column_types,
    generate_chart_title,
)


def test_format_column_label():
    assert format_column_label("C_NAME") == "Customer"
    assert format_column_label("TOTAL_SPENT") == "Total Spending"
    assert format_column_label("NATION") == "Nation"
    assert format_column_label("CUSTOMER_COUNT") == "Customer Count"
    assert format_column_label("ORDER_YEAR") == "Order Year"
    assert format_column_label("TOTAL_ORDERS") == "Total Orders"
    assert format_column_label("REGION") == "Region"
    assert format_column_label("TOTAL_REVENUE") == "Total Revenue"
    assert format_column_label("S_NAME") == "Supplier"
    assert format_column_label("S_ACCTBAL") == "Account Balance"
    assert format_column_label("C_MKTSEGMENT") == "Market Segment"
    assert format_column_label("L_QUANTITY") == "Quantity"


def test_is_currency_metric():
    assert is_currency_metric("TOTAL_SPENT") is True
    assert is_currency_metric("TOTAL_REVENUE") is True
    assert is_currency_metric("S_ACCTBAL") is True
    assert is_currency_metric("O_TOTALPRICE") is True
    assert is_currency_metric("SPENDING") is True
    assert is_currency_metric("CUSTOMER_COUNT") is False
    assert is_currency_metric("TOTAL_ORDERS") is False
    assert is_currency_metric("ORDER_YEAR") is False


def test_is_id_or_key_column():
    assert is_id_or_key_column("C_CUSTKEY") is True
    assert is_id_or_key_column("O_ORDERKEY") is True
    assert is_id_or_key_column("S_SUPPKEY") is True
    assert is_id_or_key_column("CUSTOMER_ID") is True
    assert is_id_or_key_column("S_PHONE") is True
    assert is_id_or_key_column("TOTAL_SPENT") is False
    assert is_id_or_key_column("C_NAME") is False


def test_top_10_customers_chart():
    df = pd.DataFrame(
        {
            "C_CUSTKEY": [143500, 95257, 100],
            "C_NAME": ["Customer#000143500", "Customer#000095257", "Customer#000000100"],
            "TOTAL_SPENT": [
                decimal.Decimal("7012696.48"),
                decimal.Decimal("6563511.23"),
                decimal.Decimal("5000000.00"),
            ],
        }
    )
    x_col, y_col, ctype = pick_best_chart_columns(df)
    assert x_col == "C_NAME"
    assert y_col == "TOTAL_SPENT"
    assert ctype == "Bar Chart"

    fig, auto_type = auto_create_chart(
        df, question="Show me the top 10 customers by total spending."
    )
    assert auto_type == "Bar Chart"
    assert fig is not None
    assert fig.layout.xaxis.title.text == "Customer"
    assert fig.layout.yaxis.title.text == "Total Spending"
    assert "C_CUSTKEY" not in (fig.layout.yaxis.title.text or "")
    assert fig.layout.title.text == "Top 10 Customers by Total Spending"
    assert fig.layout.yaxis.tickprefix == "$"


def test_customers_by_nation_chart():
    df = pd.DataFrame(
        {
            "NATION": ["INDONESIA", "ROMANIA", "INDIA"],
            "CUSTOMER_COUNT": [6161, 6100, 5900],
        }
    )
    x_col, y_col, ctype = pick_best_chart_columns(df)
    assert x_col == "NATION"
    assert y_col == "CUSTOMER_COUNT"
    assert ctype == "Bar Chart"

    fig, auto_type = auto_create_chart(
        df, question="Which nations have the most customers?"
    )
    assert auto_type == "Bar Chart"
    assert fig.layout.xaxis.title.text == "Nation"
    assert fig.layout.yaxis.title.text == "Customer Count"
    assert fig.layout.title.text == "Customers by Nation"


def test_orders_by_year_chart():
    df = pd.DataFrame(
        {
            "ORDER_YEAR": [1992, 1993, 1994],
            "TOTAL_ORDERS": [227089, 226645, 227500],
        }
    )
    x_col, y_col, ctype = pick_best_chart_columns(df)
    assert x_col == "ORDER_YEAR"
    assert y_col == "TOTAL_ORDERS"
    assert ctype == "Line Chart"

    fig, auto_type = auto_create_chart(
        df, question="Show the number of orders by year."
    )
    assert auto_type == "Line Chart"
    assert fig.layout.xaxis.title.text == "Order Year"
    assert fig.layout.yaxis.title.text == "Total Orders"
    assert fig.layout.title.text == "Orders by Year"


def test_revenue_by_region_chart():
    df = pd.DataFrame(
        {
            "REGION": ["EUROPE", "ASIA", "AMERICA"],
            "TOTAL_REVENUE": [
                decimal.Decimal("45793265459.71"),
                decimal.Decimal("45613415042.56"),
                decimal.Decimal("40000000000.00"),
            ],
        }
    )
    x_col, y_col, ctype = pick_best_chart_columns(df)
    assert x_col == "REGION"
    assert y_col == "TOTAL_REVENUE"
    assert ctype == "Bar Chart"

    fig, auto_type = auto_create_chart(
        df, question="Which regions have the highest revenue?"
    )
    assert auto_type == "Bar Chart"
    assert fig.layout.xaxis.title.text == "Region"
    assert fig.layout.yaxis.title.text == "Total Revenue"
    assert fig.layout.title.text == "Revenue by Region"
    assert fig.layout.yaxis.tickprefix == "$"


def test_top_suppliers_chart():
    df = pd.DataFrame(
        {
            "S_NAME": ["Supplier#000009450", "Supplier#000006343"],
            "S_ACCTBAL": [
                decimal.Decimal("9999.72"),
                decimal.Decimal("9998.20"),
            ],
            "S_PHONE": ["20-729-897-5564", "14-617-999-2300"],
        }
    )
    x_col, y_col, ctype = pick_best_chart_columns(df)
    assert x_col == "S_NAME"
    assert y_col == "S_ACCTBAL"
    assert ctype == "Bar Chart"

    fig, auto_type = auto_create_chart(
        df, question="Show the top 10 suppliers by account balance."
    )
    assert auto_type == "Bar Chart"
    assert fig.layout.xaxis.title.text == "Supplier"
    assert fig.layout.yaxis.title.text == "Account Balance"
    assert fig.layout.title.text == "Top 10 Suppliers by Account Balance"
    assert fig.layout.yaxis.tickprefix == "$"


def test_detect_column_types_handles_decimals():
    df = pd.DataFrame(
        {
            "C_NAME": ["Cust#1", "Cust#2"],
            "TOTAL_SPENT": [decimal.Decimal("100.50"), decimal.Decimal("200.75")],
            "ORDER_DATE": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        }
    )
    types = detect_column_types(df)
    assert "ORDER_DATE" in types["date"]
    assert "TOTAL_SPENT" in types["numeric"]
    assert "C_NAME" in types["categorical"]
