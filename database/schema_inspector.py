"""Snowflake Schema Inspector for DataPilot.

Dynamically queries Snowflake's INFORMATION_SCHEMA.COLUMNS for SNOWFLAKE_SAMPLE_DATA.TPCH_SF1
to extract accurate table structures, column names, and data types.
Includes a pre-defined schema fallback for offline/disconnected states.
"""

from typing import Dict, List, Optional
from database.snowflake_connection import get_connection

# Comprehensive fallback schema for TPC-H SF1 in case the database is offline or not yet connected
TPCH_SF1_FALLBACK_SCHEMA: Dict[str, Dict[str, str]] = {
    "CUSTOMER": {
        "C_CUSTKEY": "NUMBER(38,0) - Primary Key",
        "C_NAME": "VARCHAR(25) - Customer name (e.g. Customer#000000001)",
        "C_ADDRESS": "VARCHAR(40) - Street address",
        "C_NATIONKEY": "NUMBER(38,0) - FK to NATION.N_NATIONKEY",
        "C_PHONE": "VARCHAR(15) - Phone number",
        "C_ACCTBAL": "NUMBER(12,2) - Account balance",
        "C_MKTSEGMENT": "VARCHAR(10) - Market segment (BUILDING, AUTOMOBILE, MACHINERY, HOUSEHOLD, FURNITURE)",
        "C_COMMENT": "VARCHAR(117) - Comments",
    },
    "ORDERS": {
        "O_ORDERKEY": "NUMBER(38,0) - Primary Key",
        "O_CUSTKEY": "NUMBER(38,0) - FK to CUSTOMER.C_CUSTKEY",
        "O_ORDERSTATUS": "VARCHAR(1) - Order status (O=Open, F=Fulfilled, P=Pending)",
        "O_TOTALPRICE": "NUMBER(12,2) - Total order price / spending",
        "O_ORDERDATE": "DATE - Date order was placed (e.g. 1992 to 1998)",
        "O_ORDERPRIORITY": "VARCHAR(15) - Priority (1-URGENT, 2-HIGH, 3-MEDIUM, 4-NOT SPECIFIED, 5-LOW)",
        "O_CLERK": "VARCHAR(15) - Clerk identifier",
        "O_SHIPPRIORITY": "NUMBER(38,0) - Shipping priority",
        "O_COMMENT": "VARCHAR(79) - Comments",
    },
    "LINEITEM": {
        "L_ORDERKEY": "NUMBER(38,0) - FK to ORDERS.O_ORDERKEY",
        "L_PARTKEY": "NUMBER(38,0) - FK to PART.P_PARTKEY",
        "L_SUPPKEY": "NUMBER(38,0) - FK to SUPPLIER.S_SUPPKEY",
        "L_LINENUMBER": "NUMBER(38,0) - Line number within the order",
        "L_QUANTITY": "NUMBER(12,2) - Quantity ordered",
        "L_EXTENDEDPRICE": "NUMBER(12,2) - Extended lineitem price",
        "L_DISCOUNT": "NUMBER(12,2) - Discount percentage (e.g. 0.05)",
        "L_TAX": "NUMBER(12,2) - Tax percentage",
        "L_RETURNFLAG": "VARCHAR(1) - Return flag (R=Returned, A=Accepted, N=None)",
        "L_LINESTATUS": "VARCHAR(1) - Line status (O=Open, F=Fulfilled)",
        "L_SHIPDATE": "DATE - Shipping date",
        "L_COMMITDATE": "DATE - Commit date",
        "L_RECEIPTDATE": "DATE - Receipt date",
        "L_SHIPINSTRUCT": "VARCHAR(25) - Shipping instructions",
        "L_SHIPMODE": "VARCHAR(10) - Ship mode (AIR, REG AIR, SHIP, TRUCK, MAIL, FOB, RAIL)",
        "L_COMMENT": "VARCHAR(44) - Comments",
    },
    "PART": {
        "P_PARTKEY": "NUMBER(38,0) - Primary Key",
        "P_NAME": "VARCHAR(55) - Part name",
        "P_MFGR": "VARCHAR(25) - Manufacturer (Manufacturer#1 to Manufacturer#5)",
        "P_BRAND": "VARCHAR(10) - Brand",
        "P_TYPE": "VARCHAR(25) - Part type",
        "P_SIZE": "NUMBER(38,0) - Part size",
        "P_CONTAINER": "VARCHAR(10) - Container type (JUMBO BAG, SM BOX, etc.)",
        "P_RETAILPRICE": "NUMBER(12,2) - Retail price",
        "P_COMMENT": "VARCHAR(23) - Comments",
    },
    "SUPPLIER": {
        "S_SUPPKEY": "NUMBER(38,0) - Primary Key",
        "S_NAME": "VARCHAR(25) - Supplier name",
        "S_ADDRESS": "VARCHAR(40) - Address",
        "S_NATIONKEY": "NUMBER(38,0) - FK to NATION.N_NATIONKEY",
        "S_PHONE": "VARCHAR(15) - Contact phone",
        "S_ACCTBAL": "NUMBER(12,2) - Supplier account balance",
        "S_COMMENT": "VARCHAR(101) - Comments",
    },
    "PARTSUPP": {
        "PS_PARTKEY": "NUMBER(38,0) - FK to PART.P_PARTKEY",
        "PS_SUPPKEY": "NUMBER(38,0) - FK to SUPPLIER.S_SUPPKEY",
        "PS_AVAILQTY": "NUMBER(38,0) - Available inventory quantity",
        "PS_SUPPLYCOST": "NUMBER(12,2) - Cost of part from supplier",
        "PS_COMMENT": "VARCHAR(199) - Comments",
    },
    "NATION": {
        "N_NATIONKEY": "NUMBER(38,0) - Primary Key",
        "N_NAME": "VARCHAR(25) - Country name (e.g. UNITED STATES, CHINA, BRAZIL)",
        "N_REGIONKEY": "NUMBER(38,0) - FK to REGION.R_REGIONKEY",
        "N_COMMENT": "VARCHAR(152) - Comments",
    },
    "REGION": {
        "R_REGIONKEY": "NUMBER(38,0) - Primary Key",
        "R_NAME": "VARCHAR(25) - Region name (AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST)",
        "R_COMMENT": "VARCHAR(152) - Comments",
    },
}

TPCH_RELATIONSHIPS = [
    "CUSTOMER.C_NATIONKEY = NATION.N_NATIONKEY",
    "SUPPLIER.S_NATIONKEY = NATION.N_NATIONKEY",
    "NATION.N_REGIONKEY = REGION.R_REGIONKEY",
    "ORDERS.O_CUSTKEY = CUSTOMER.C_CUSTKEY",
    "LINEITEM.L_ORDERKEY = ORDERS.O_ORDERKEY",
    "LINEITEM.L_PARTKEY = PART.P_PARTKEY",
    "LINEITEM.L_SUPPKEY = SUPPLIER.S_SUPPKEY",
    "PARTSUPP.PS_PARTKEY = PART.P_PARTKEY",
    "PARTSUPP.PS_SUPPKEY = SUPPLIER.S_SUPPKEY",
]

_cached_schema: Optional[Dict[str, Dict[str, str]]] = None


def fetch_dynamic_schema(conn=None, override_password: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """Dynamically query INFORMATION_SCHEMA.COLUMNS from Snowflake.

    Returns a mapping of {table_name: {column_name: data_type}}.
    Falls back to TPCH_SF1_FALLBACK_SCHEMA if the query cannot be run.
    """
    global _cached_schema
    if _cached_schema:
        return _cached_schema

    close_conn = False
    if conn is None:
        try:
            conn = get_connection(override_password)
            close_conn = True
        except Exception:
            return TPCH_SF1_FALLBACK_SCHEMA

    schema_dict: Dict[str, Dict[str, str]] = {}
    try:
        query = """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'TPCH_SF1'
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            for table_name, column_name, data_type in rows:
                t = table_name.upper()
                c = column_name.upper()
                if t not in schema_dict:
                    schema_dict[t] = {}
                # Enhance with descriptions if in fallback
                desc = TPCH_SF1_FALLBACK_SCHEMA.get(t, {}).get(c, "")
                schema_dict[t][c] = f"{data_type} ({desc})" if desc else data_type

        if schema_dict:
            _cached_schema = schema_dict
            return _cached_schema
        return TPCH_SF1_FALLBACK_SCHEMA

    except Exception:
        return TPCH_SF1_FALLBACK_SCHEMA
    finally:
        if close_conn and conn:
            try:
                conn.close()
            except Exception:
                pass


def get_schema_prompt_context(conn=None, override_password: Optional[str] = None) -> str:
    """Format the schema and relationships into a concise context block for Llama 3.2."""
    schema = fetch_dynamic_schema(conn, override_password)

    lines = [
        "Database: SNOWFLAKE_SAMPLE_DATA",
        "Schema: TPCH_SF1",
        "\nAVAILABLE TABLES & COLUMNS:",
    ]

    for table, columns in schema.items():
        col_list = [f"{col}: {dtype}" for col, dtype in columns.items()]
        lines.append(f"- Table `{table}`:")
        for col in col_list:
            lines.append(f"    * {col}")

    lines.append("\nTABLE RELATIONSHIPS / JOINS:")
    for rel in TPCH_RELATIONSHIPS:
        lines.append(f"- {rel}")

    return "\n".join(lines)


def get_available_tables() -> List[str]:
    """Return list of table names."""
    return list(TPCH_SF1_FALLBACK_SCHEMA.keys())
