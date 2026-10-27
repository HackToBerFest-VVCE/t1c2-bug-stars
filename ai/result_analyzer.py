"""AI Result Analysis Module powered by Llama 3.2.

Provides grounded business insights, trend analysis, anomaly detection,
and key findings derived strictly from Snowflake query results.
"""

from typing import Dict, Any, Optional
import pandas as pd
from ai.ollama_client import OllamaClient


ANALYZER_SYSTEM_PROMPT = """You are an expert AI Data Analyst evaluating Snowflake TPC-H query results.
Provide clear, grounded, and concise business intelligence based strictly on the query result provided.

STRICT GROUNDING RULES:
1. ONLY make claims that are directly supported by the provided data rows or metrics.
2. DO NOT hallucinate, guess, or invent numbers, percentages, or trends not in the data.
3. If there is insufficient data to determine a trend or anomaly, state explicitly: "Not enough data to determine this."
4. Structure your response into these exact markdown sections:
### Key Insight
(1-2 clear sentences summarizing what the result reveals)

### Important Findings
(3 to 5 bullet points highlighting the specific top values, counts, or comparisons from the data)

### Trend
(Describe any clear chronological or numerical progression, or "Not enough data to determine this.")

### Anomaly
(Note any significant outlier or mention "No significant anomalies observed in the returned dataset.")

### Business Meaning
(Explain why this data matters for business strategy, inventory, sales, or supplier management)
"""


def summarize_dataframe_for_llm(df: pd.DataFrame, max_rows: int = 15) -> str:
    """Create a concise, token-efficient text representation of the DataFrame for Llama 3.2."""
    if df is None or df.empty:
        return "No data rows returned."

    total_rows = len(df)
    sample_df = df.head(max_rows)

    # Format into markdown table without external dependencies like tabulate
    headers = [str(c) for c in sample_df.columns]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_rows = []
    for _, row in sample_df.iterrows():
        row_str = "| " + " | ".join(str(val) for val in row.values) + " |"
        data_rows.append(row_str)

    table_markdown = "\n".join([header_line, sep_line] + data_rows)

    summary_lines = [
        f"Total Rows Returned: {total_rows}",
        f"Columns: {', '.join(df.columns.astype(str))}",
        "\nData Sample (first rows):",
        table_markdown,
    ]

    # Include basic stats for numeric columns
    numeric_cols = df.select_dtypes(include=["number"]).columns
    if len(numeric_cols) > 0:
        summary_lines.append("\nSummary Statistics for Numeric Columns:")
        stats_lines = []
        for col in numeric_cols:
            col_min = df[col].min()
            col_max = df[col].max()
            col_mean = round(df[col].mean(), 2)
            col_sum = round(df[col].sum(), 2)
            stats_lines.append(f"- {col}: Min={col_min}, Max={col_max}, Average={col_mean}, Total Sum={col_sum}")
        summary_lines.extend(stats_lines)

    return "\n".join(summary_lines)


def analyze_results(
    question: str,
    sql: str,
    df: pd.DataFrame,
    ollama_client: Optional[OllamaClient] = None,
) -> Dict[str, Any]:
    """Generate business analysis and insights from the Snowflake query results using Llama 3.2.

    Returns:
        dict containing 'raw_text', 'success', and 'error'
    """
    if df is None or df.empty:
        return {
            "success": True,
            "raw_text": (
                "### Key Insight\n"
                "The query executed successfully but returned 0 rows matching the criteria.\n\n"
                "### Important Findings\n"
                "* No matching records found in the specified TPC-H SF1 tables.\n\n"
                "### Trend\n"
                "Not enough data to determine this.\n\n"
                "### Business Meaning\n"
                "No activity or records exist for the filtered condition."
            ),
            "error": "",
        }

    if ollama_client is None:
        ollama_client = OllamaClient()

    data_summary = summarize_dataframe_for_llm(df)

    user_prompt = f"""User Question: "{question}"

Executed Snowflake SQL:
{sql}

Query Results Summary:
{data_summary}

Provide your grounded analysis following the specified format:"""

    try:
        response_text = ollama_client.generate(
            prompt=user_prompt,
            system=ANALYZER_SYSTEM_PROMPT,
            temperature=0.2,
        )
        return {
            "success": True,
            "raw_text": response_text,
            "error": "",
        }
    except Exception as e:
        # Fallback heuristic summary if Ollama has a temporary hiccup
        return {
            "success": False,
            "raw_text": (
                "### Key Insight\n"
                f"Retrieved {len(df)} rows from Snowflake for your question.\n\n"
                "### Important Findings\n"
                f"* Result contains {len(df.columns)} columns: {', '.join(df.columns.astype(str))}.\n"
                f"* Top record: {df.iloc[0].to_dict() if not df.empty else 'N/A'}.\n\n"
                "### Trend\n"
                "Not enough data to determine this.\n\n"
                "### Business Meaning\n"
                "Use the interactive table and visualization above to explore the metrics."
            ),
            "error": f"AI insight generation notice: {str(e)}",
        }
