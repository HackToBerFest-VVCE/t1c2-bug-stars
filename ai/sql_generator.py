"""SQL Generator module powered by local Llama 3.2.

Translates natural language questions into secure Snowflake SQL queries
using the actual TPC-H SF1 database schema.

This module also prevents unsupported questions from being converted into
queries merely because an entity mentioned in the question exists in the
dataset.
"""

import re
from typing import Tuple, Optional

from ai.ollama_client import OllamaClient
from database.schema_inspector import get_schema_prompt_context
from utils.sql_validator import validate_sql


# ================================================================
# SQL GENERATION SYSTEM PROMPT
# ================================================================

SYSTEM_PROMPT = """You are a SQL generation assistant for Snowflake TPC-H data.

Your ONLY job is to translate an ANSWERABLE user question into a valid
Snowflake SQL query.

The answer MUST be derivable from the supplied database schema and data.

IMPORTANT:

An entity appearing in the dataset does NOT mean that every fact about
that entity is available.

For example:

The NATION table may contain:
N_NAME = INDIA

That does NOT mean the database contains:
- Prime Minister
- President
- Population
- Weather
- Current events
- Political information
- Government information
- Any other information not represented by the schema

Never change the user's question into a simpler question just because
one word or entity from the question exists in the database.

For example:

User:
"Who is the Prime Minister of India?"

WRONG interpretation:
"Find information about India."

WRONG SQL:
SELECT * FROM NATION WHERE N_NAME = 'INDIA';

The question asks for a PRIME MINISTER, and TPC-H does not contain
Prime Minister information. Such a question must NOT be converted into SQL.

STRICT SQL RULES:

1. Generate ONLY one SELECT or WITH ... SELECT query.

2. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
   TRUNCATE, MERGE, GRANT, REVOKE, or other modifying statements.

3. Use Snowflake-compatible SQL.

4. Use ONLY tables and columns from the supplied schema.

5. TPC-H table and column names are uppercase.

6. Always add a reasonable LIMIT for top-N, bottom-N, highest,
   lowest, largest, smallest, maximum, minimum, or ranking questions.

7. Do NOT use GROUP BY unless aggregation is actually required.

8. If a column already contains the requested value for each entity,
   do NOT aggregate it unnecessarily.

9. Top/highest/largest/maximum/most = DESC.

10. Bottom/lowest/smallest/minimum/least = ASC.

11. Simple ranking questions should use ORDER BY + LIMIT.

12. CUSTOMER account balance = C_ACCTBAL.

13. SUPPLIER account balance = S_ACCTBAL.

14. Customer account balance questions normally use CUSTOMER directly.

15. Supplier account balance questions normally use SUPPLIER directly.

16. Total spending by customer requires CUSTOMER + ORDERS and
    SUM(O_TOTALPRICE).

17. When aggregation is used, every selected non-aggregated column
    must appear in GROUP BY.

18. Use clear aliases such as:
    CUSTOMER
    ACCOUNT_BALANCE
    TOTAL_SPENDING
    CUSTOMER_COUNT
    TOTAL_REVENUE

19. Return ONLY raw SQL.

20. Never invent information that is not in the dataset.
"""


# ================================================================
# FEW-SHOT SQL EXAMPLES
# ================================================================

FEW_SHOT_EXAMPLES = """
REFERENCE EXAMPLES:

Question:
"Show me the top 10 customers by total spending."

SQL:
SELECT
    c.C_CUSTKEY,
    c.C_NAME AS CUSTOMER,
    ROUND(SUM(o.O_TOTALPRICE), 2) AS TOTAL_SPENDING
FROM CUSTOMER c
JOIN ORDERS o
    ON c.C_CUSTKEY = o.O_CUSTKEY
GROUP BY c.C_CUSTKEY, c.C_NAME
ORDER BY TOTAL_SPENDING DESC
LIMIT 10;


Question:
"Show the top 10 customers by account balance."

SQL:
SELECT
    c.C_CUSTKEY,
    c.C_NAME AS CUSTOMER,
    c.C_ACCTBAL AS ACCOUNT_BALANCE
FROM CUSTOMER c
ORDER BY c.C_ACCTBAL DESC
LIMIT 10;


Question:
"Show the 10 customers with the lowest account balance."

SQL:
SELECT
    c.C_CUSTKEY,
    c.C_NAME AS CUSTOMER,
    c.C_ACCTBAL AS ACCOUNT_BALANCE
FROM CUSTOMER c
ORDER BY c.C_ACCTBAL ASC
LIMIT 10;


Question:
"Which nations have the most customers?"

SQL:
SELECT
    n.N_NAME AS NATION,
    COUNT(c.C_CUSTKEY) AS CUSTOMER_COUNT
FROM NATION n
JOIN CUSTOMER c
    ON n.N_NATIONKEY = c.C_NATIONKEY
GROUP BY n.N_NAME
ORDER BY CUSTOMER_COUNT DESC
LIMIT 10;


Question:
"Show the number of orders by year."

SQL:
SELECT
    EXTRACT(YEAR FROM O_ORDERDATE) AS ORDER_YEAR,
    COUNT(*) AS TOTAL_ORDERS
FROM ORDERS
GROUP BY ORDER_YEAR
ORDER BY ORDER_YEAR;


Question:
"Which regions have the highest revenue?"

SQL:
SELECT
    r.R_NAME AS REGION,
    ROUND(SUM(o.O_TOTALPRICE), 2) AS TOTAL_REVENUE
FROM REGION r
JOIN NATION n
    ON r.R_REGIONKEY = n.N_REGIONKEY
JOIN CUSTOMER c
    ON n.N_NATIONKEY = c.C_NATIONKEY
JOIN ORDERS o
    ON c.C_CUSTKEY = o.O_CUSTKEY
GROUP BY r.R_NAME
ORDER BY TOTAL_REVENUE DESC
LIMIT 10;
"""


# ================================================================
# DETERMINISTIC UNSUPPORTED-QUESTION CHECK
# ================================================================

UNSUPPORTED_PATTERNS = [
    r"\bprime minister\b",
    r"\bpresident\b",
    r"\bweather\b",
    r"\btemperature\b",
    r"\bpopulation\b",
    r"\bcapital city\b",
    r"\bcapital of\b",
    r"\bceo\b",
    r"\bchief executive\b",
    r"\bgovernment\b",
    r"\belection\b",
    r"\belections\b",
    r"\bpolitical party\b",
    r"\bpolitical parties\b",
    r"\bminister\b",
    r"\bparliament\b",
    r"\bcurrent affairs\b",
    r"\bnews\b",
    r"\bpresidential\b",
]


def contains_known_unsupported_topic(question: str) -> bool:
    """Return True for common questions that TPC-H cannot answer."""

    normalized = question.lower().strip()

    for pattern in UNSUPPORTED_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


# ================================================================
# INFORMATION-REQUEST EXTRACTION
# ================================================================

REQUEST_ANALYSIS_SYSTEM_PROMPT = """You are a strict database grounding
classifier.

Your task is to identify WHAT INFORMATION the user is actually requesting.

Do NOT focus only on entities or names.

Example:

Question:
"Who is the Prime Minister of India?"

Requested information:
Prime Minister of India

NOT:
India

Question:
"What is the population of India?"

Requested information:
Population of India

NOT:
India

Question:
"Which nation has the most customers?"

Requested information:
Customer count by nation

Question:
"Show the top 10 customers by account balance."

Requested information:
Customer account balance

Return a short description of the requested information only.
Do not answer the question.
"""


def extract_requested_information(
    question: str,
    ollama_client: OllamaClient,
) -> str:
    """Extract the actual information requested by the user."""

    prompt = f"""USER QUESTION:

{question}

What specific information is the user asking for?

Remember:
Do not reduce the question to an entity name.
Identify the actual requested attribute, metric, fact, or relationship.
"""

    try:
        response = ollama_client.generate(
            prompt=prompt,
            system=REQUEST_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.0,
        )

        return response.strip()

    except Exception:
        return ""


# ================================================================
# SCHEMA-BASED ANSWERABILITY CHECK
# ================================================================

GROUNDING_SYSTEM_PROMPT = """You are a strict database answerability checker.

You receive:

1. Database schema
2. Original user question
3. The specific information requested by the user

Your job is to determine whether the requested information can actually
be derived from the database.

CRITICAL RULE:

Do NOT mark a question ANSWERABLE merely because an entity mentioned
in the question exists in the database.

Example:

Schema contains:
NATION.N_NAME

Question:
"Who is the Prime Minister of India?"

Requested information:
"Prime Minister of India"

Result:
NOT_ANSWERABLE

Reason:
The schema contains nations but no Prime Minister information.

Another example:

Question:
"Which nation has the most customers?"

Requested information:
"Customer count by nation"

Schema contains:
NATION
CUSTOMER
C_NATIONKEY

Result:
ANSWERABLE

Another example:

Question:
"What is the account balance of customers?"

Requested information:
"Customer account balance"

Schema contains:
CUSTOMER.C_ACCTBAL

Result:
ANSWERABLE

Another example:

Question:
"What is the weather in India?"

Requested information:
"Weather in India"

Result:
NOT_ANSWERABLE

You must consider the requested INFORMATION, not just the entity.

Return EXACTLY one of:

ANSWERABLE

NOT_ANSWERABLE

Do not return anything else.
"""


def check_dataset_answerability(
    question: str,
    requested_information: str,
    schema_context: str,
    ollama_client: OllamaClient,
) -> bool:
    """Determine whether the actual requested information exists in dataset."""

    prompt = f"""DATABASE SCHEMA:

{schema_context}

ORIGINAL USER QUESTION:

{question}

ACTUAL REQUESTED INFORMATION:

{requested_information}

Can the requested information be derived using ONLY the supplied
database schema and data?

IMPORTANT:
Do not answer YES merely because an entity such as INDIA, CUSTOMER,
SUPPLIER, or a nation exists.

The requested attribute/fact itself must be represented or derivable
from the available tables and columns.

Return exactly:

ANSWERABLE

or

NOT_ANSWERABLE
"""

    try:
        response = ollama_client.generate(
            prompt=prompt,
            system=GROUNDING_SYSTEM_PROMPT,
            temperature=0.0,
        )

        result = response.strip().upper()

        return result == "ANSWERABLE"

    except Exception:
        # Fail closed.
        return False


# ================================================================
# SQL EXTRACTION
# ================================================================

def extract_sql_from_response(raw_text: str) -> str:
    """Extract SQL query from LLM response."""

    text = raw_text.strip()

    code_block_match = re.search(
        r"```(?:sql)?\s*([\s\S]*?)\s*```",
        text,
        re.IGNORECASE,
    )

    if code_block_match:
        text = code_block_match.group(1).strip()

    text = re.sub(
        r"^(?:SQL|Query):\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    lines = text.splitlines()
    clean_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.lower().startswith(
            (
                "explanation:",
                "note:",
                "this query",
            )
        ):
            if clean_lines and ";" in clean_lines[-1]:
                break

        clean_lines.append(line)

    return "\n".join(clean_lines).strip()


# ================================================================
# SAFE SQL CLEANUP
# ================================================================

def repair_common_sql_errors(sql: str) -> str:
    """Apply conservative cleanup to generated SQL."""

    if not sql:
        return sql

    cleaned = sql.strip()

    cleaned = re.sub(
        r"^```(?:sql)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


# ================================================================
# MAIN SQL GENERATION FUNCTION
# ================================================================

def generate_sql(
    question: str,
    ollama_client: Optional[OllamaClient] = None,
    conn=None,
    override_password: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Generate and validate a Snowflake SQL query.

    Flow:

    1. Retrieve schema
    2. Check obvious unsupported topics
    3. Extract the actual requested information
    4. Check whether that information exists in the dataset
    5. Generate SQL only if answerable
    6. Validate SQL
    """

    if ollama_client is None:
        ollama_client = OllamaClient()

    # ------------------------------------------------------------
    # Retrieve actual database schema
    # ------------------------------------------------------------

    try:
        schema_context = get_schema_prompt_context(
            conn,
            override_password,
        )

    except Exception as e:
        return (
            False,
            f"Could not retrieve database schema: {str(e)}",
            "",
        )

    # ------------------------------------------------------------
    # STEP 1: Deterministic unsupported-topic check
    # ------------------------------------------------------------

    if contains_known_unsupported_topic(question):

        return (
            False,
            (
                "This question cannot be answered from the available "
                "Snowflake dataset. The requested information is not "
                "stored in the TPC-H dataset."
            ),
            "",
        )

    # ------------------------------------------------------------
    # STEP 2: Identify the actual requested information
    # ------------------------------------------------------------

    requested_information = extract_requested_information(
        question,
        ollama_client,
    )

    if not requested_information:
        return (
            False,
            (
                "I could not determine whether this question can be "
                "answered from the available dataset."
            ),
            "",
        )

    # ------------------------------------------------------------
    # STEP 3: Strict schema grounding
    # ------------------------------------------------------------

    is_answerable = check_dataset_answerability(
        question,
        requested_information,
        schema_context,
        ollama_client,
    )

    if not is_answerable:
        return (
            False,
            (
                "This question cannot be answered from the available "
                "Snowflake dataset. The requested information is not "
                "represented in the available TPC-H tables or columns."
            ),
            "",
        )

    # ------------------------------------------------------------
    # STEP 4: Generate SQL
    # ------------------------------------------------------------

    user_prompt = f"""Target Snowflake Schema:

{schema_context}

{FEW_SHOT_EXAMPLES}

ACTUAL USER QUESTION:

"{question}"

IMPORTANT:

Generate SQL for the COMPLETE user question.

Do NOT simplify the question to an entity lookup.

For example, if the question asks:
"Who is the Prime Minister of India?"

you must NOT generate:
SELECT * FROM NATION WHERE N_NAME = 'INDIA';

That question should only reach this SQL generation stage if the
requested information is actually supported by the dataset.

QUERY GENERATION CHECKLIST:

1. Every table and column must exist in the schema.
2. Answer the complete user question.
3. Do not change the requested attribute.
4. GROUP BY only when aggregation is required.
5. Ranking of existing columns uses ORDER BY + LIMIT.
6. Highest/top = DESC.
7. Lowest/bottom/minimum = ASC.
8. Aggregated queries must have correct GROUP BY.
9. Return one executable SELECT/WITH query only.

Output SQL only.
"""

    try:
        raw_response = ollama_client.generate(
            prompt=user_prompt,
            system=SYSTEM_PROMPT,
            temperature=0.1,
        )

    except Exception as e:
        return (
            False,
            f"Could not generate SQL: {str(e)}",
            "",
        )

    # ------------------------------------------------------------
    # STEP 5: Extract SQL
    # ------------------------------------------------------------

    extracted_sql = extract_sql_from_response(
        raw_response
    )

    # ------------------------------------------------------------
    # STEP 6: Conservative cleanup
    # ------------------------------------------------------------

    extracted_sql = repair_common_sql_errors(
        extracted_sql
    )

    # ------------------------------------------------------------
    # STEP 7: Validate SQL
    # ------------------------------------------------------------

    is_valid, validation_msg, cleaned_sql = validate_sql(
        extracted_sql
    )

    if not is_valid:
        return (
            False,
            (
                "Generated SQL validation failed: "
                f"{validation_msg}\n"
                f"SQL was: {extracted_sql}"
            ),
            "",
        )

    return (
        True,
        cleaned_sql,
        cleaned_sql,
    )