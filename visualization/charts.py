"""Visualization Module for DataPilot using Plotly.

Automatically recommends and constructs appropriate visualizations (Bar, Line, Scatter)
based on query result column data types, intelligently selects dimension and metric columns,
formats clean human-readable axes and titles, applies currency formatting, and allows interactive custom charts.
"""

import re
from typing import Tuple, Optional, List, Dict
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def is_id_or_key_column(col_name: str) -> bool:
    """Check if a column is an ID, surrogate key, or phone/code rather than a metric."""
    col_upper = str(col_name).upper().strip()

    if col_upper.endswith(("_KEY", "_ID", "KEY", "ID", "_CODE")):
        return True

    if any(
        k in col_upper
        for k in [
            "_CUSTKEY",
            "_ORDERKEY",
            "_PARTKEY",
            "_SUPPKEY",
            "_NATIONKEY",
            "_REGIONKEY",
            "CUSTKEY",
            "ORDERKEY",
            "PARTKEY",
            "SUPPKEY",
            "NATIONKEY",
            "REGIONKEY",
            "_PHONE",
            "PHONE",
        ]
    ):
        return True

    return False


def is_date_or_year_column(col_series: pd.Series, col_name: str) -> bool:
    """Check if a column represents dates, years, or time periods."""
    col_upper = str(col_name).upper().strip()

    if pd.api.types.is_datetime64_any_dtype(col_series):
        return True

    if any(
        k in col_upper
        for k in ["DATE", "YEAR", "MONTH", "DAY", "PERIOD", "QUARTER"]
    ):
        return True

    return False


def is_currency_metric(col_name: str, label: str = "") -> bool:
    """Check if the column/metric represents monetary currency."""
    combined = (str(col_name) + " " + str(label)).upper()

    currency_keywords = [
        "SPENT",
        "SPENDING",
        "REVENUE",
        "PRICE",
        "BAL",
        "BALANCE",
        "COST",
        "PROFIT",
        "AMOUNT",
        "SALES",
        "FEE",
        "TAX",
        "TOTALPRICE",
        "ACCTBAL",
        "EXTENDEDPRICE",
    ]

    return any(k in combined for k in currency_keywords)


def is_account_balance_metric(col_name: str, label: str = "") -> bool:
    """Check if the metric represents an account balance."""
    combined = (str(col_name) + " " + str(label)).upper()

    return any(
        k in combined
        for k in [
            "ACCTBAL",
            "ACCOUNT BALANCE",
        ]
    )


def format_column_label(col_name: str) -> str:
    """Convert database column name or SQL alias into a clean, human-readable label."""
    col_str = str(col_name).strip()
    col_upper = col_str.upper()

    # Exact known mappings
    mappings = {
        "C_NAME": "Customer",
        "C_CUSTKEY": "Customer Key",
        "S_NAME": "Supplier",
        "S_SUPPKEY": "Supplier Key",
        "P_NAME": "Part",
        "P_PARTKEY": "Part Key",
        "N_NAME": "Nation",
        "NATION": "Nation",
        "R_NAME": "Region",
        "REGION": "Region",
        "TOTAL_SPENT": "Total Spending",
        "TOTAL_SPENDING": "Total Spending",
        "CUSTOMER_COUNT": "Customer Count",
        "ORDER_YEAR": "Order Year",
        "TOTAL_ORDERS": "Total Orders",
        "TOTAL_REVENUE": "Total Revenue",
        "S_ACCTBAL": "Account Balance",
        "C_ACCTBAL": "Account Balance",
        "ACCTBAL": "Account Balance",
        "O_TOTALPRICE": "Total Price",
        "O_ORDERDATE": "Order Date",
        "O_ORDERSTATUS": "Order Status",
        "O_ORDERPRIORITY": "Order Priority",
        "L_EXTENDEDPRICE": "Extended Price",
        "L_DISCOUNT": "Discount",
        "L_TAX": "Tax",
        "L_QUANTITY": "Quantity",
        "C_MKTSEGMENT": "Market Segment",
    }

    if col_upper in mappings:
        return mappings[col_upper]

    clean = col_str

    # Strip standard single-character TPC-H prefix
    # C_, O_, L_, P_, S_, N_, R_
    if (
        len(clean) > 2
        and clean[1] == "_"
        and clean[0].upper() in "COLPSNR"
    ):
        prefix = clean[0].upper()
        remainder = clean[2:]

        if remainder.upper() == "NAME":
            prefix_map = {
                "C": "Customer",
                "S": "Supplier",
                "P": "Part",
                "N": "Nation",
                "R": "Region",
            }

            return prefix_map.get(prefix, "Name")

        clean = remainder

    words = clean.replace("_", " ").split()
    formatted = []

    for w in words:
        wl = w.lower()

        if wl == "spent":
            formatted.append("Spending")
        elif wl == "acctbal":
            formatted.append("Account Balance")
        elif wl == "custkey":
            formatted.append("Customer Key")
        elif wl == "suppkey":
            formatted.append("Supplier Key")
        elif wl == "orderkey":
            formatted.append("Order Key")
        elif wl == "totalprice":
            formatted.append("Total Price")
        else:
            formatted.append(w.capitalize())

    return " ".join(formatted)


def pluralize(word: str) -> str:
    """Return the plural form of an English noun."""
    w = word.strip()

    if not w:
        return ""

    if w.endswith(("s", "sh", "ch", "x", "z")):
        return w + "es"

    if w.endswith("y") and len(w) > 1 and w[-2].lower() not in "aeiou":
        return w[:-1] + "ies"

    return w + "s"


def generate_chart_title(
    x_label: str,
    y_label: str,
    chart_type: str,
    df_len: int,
    question: str = "",
) -> str:
    """Intelligently determine an appropriate chart title from labels and question context."""
    q = (question or "").strip()

    # If the user asked a top-N ranking question
    top_match = re.search(r"top\s*(\d+)?", q, re.IGNORECASE)

    if top_match:
        n_str = top_match.group(1) or (str(df_len) if df_len > 0 else "")
        x_plural = pluralize(x_label)
        n_prefix = f"Top {n_str} " if n_str else "Top "

        return f"{n_prefix}{x_plural} by {y_label}"

    # Line chart or chronological dimension
    if chart_type == "Line Chart" or any(
        k in x_label.lower()
        for k in ["year", "date", "month", "period"]
    ):
        if "year" in x_label.lower() and "order" in y_label.lower():
            return "Orders by Year"

        return f"{y_label} by {x_label}"

    # Common benchmark questions phrasing
    if (
        "nation" in x_label.lower()
        and (
            "customer" in y_label.lower()
            or "count" in y_label.lower()
        )
    ):
        return "Customers by Nation"

    if (
        "region" in x_label.lower()
        and "revenue" in y_label.lower()
    ):
        return "Revenue by Region"

    # Default clean title
    return f"{y_label} by {x_label}"


def prepare_chart_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame copy with Decimal or numeric-convertible object columns converted to float."""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    chart_df = df.copy()

    for col in chart_df.columns:
        col_s = chart_df[col]

        if (
            col_s.dtype == object
            and not col_s.dropna().empty
        ):
            coerced = pd.to_numeric(
                col_s,
                errors="coerce",
            )

            if (
                coerced.notna().sum()
                / len(col_s.dropna())
                >= 0.8
            ):
                chart_df[col] = coerced

    return chart_df


def detect_column_types(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Classify DataFrame columns into date, numeric, and categorical types.

    Correctly handles Decimal objects returned by Snowflake queries.
    """
    date_cols: List[str] = []
    numeric_cols: List[str] = []
    cat_cols: List[str] = []

    if df is None or df.empty:
        return {
            "date": [],
            "numeric": [],
            "categorical": [],
        }

    for col in df.columns:
        col_series = df[col]

        # Check if date/year column
        if is_date_or_year_column(
            col_series,
            str(col),
        ):
            date_cols.append(col)
            continue

        # Check if numeric (or convertible Decimal)
        is_num = pd.api.types.is_numeric_dtype(
            col_series
        )

        if (
            not is_num
            and col_series.dtype == object
            and not col_series.dropna().empty
        ):
            coerced = pd.to_numeric(
                col_series,
                errors="coerce",
            )

            if (
                coerced.notna().sum()
                / len(col_series.dropna())
                >= 0.8
            ):
                is_num = True

        if is_num:
            numeric_cols.append(col)
        else:
            cat_cols.append(col)

    return {
        "date": date_cols,
        "numeric": numeric_cols,
        "categorical": cat_cols,
    }


def pick_best_chart_columns(
    df: pd.DataFrame,
) -> Tuple[Optional[str], Optional[str], str]:
    """Intelligently determine the best (x_col, y_col, chart_type) from DataFrame columns.

    Returns:
        (x_column_name, y_column_name, chart_type_description)
    """
    if (
        df is None
        or df.empty
        or len(df.columns) < 2
    ):
        return None, None, "Table"

    # Identify date/time columns
    date_cols: List[str] = []

    for col in df.columns:
        if is_date_or_year_column(
            df[col],
            str(col),
        ):
            date_cols.append(col)

    # Coerce and score numeric metric candidates
    metric_candidates: List[Tuple[str, float]] = []

    for col in df.columns:
        if col in date_cols:
            continue

        col_s = df[col]

        is_num = pd.api.types.is_numeric_dtype(
            col_s
        )

        if (
            not is_num
            and col_s.dtype == object
            and not col_s.dropna().empty
        ):
            coerced = pd.to_numeric(
                col_s,
                errors="coerce",
            )

            if (
                coerced.notna().sum()
                / len(col_s.dropna())
                >= 0.8
            ):
                is_num = True

        if is_num:
            col_upper = str(col).upper()

            if is_id_or_key_column(col):
                score = 5.0
            else:
                score = 50.0

                if any(
                    k in col_upper
                    for k in [
                        "SPENT",
                        "SPENDING",
                        "REVENUE",
                        "PRICE",
                        "BAL",
                        "BALANCE",
                        "AMOUNT",
                        "TOTAL",
                        "SUM",
                        "AVG",
                        "COUNT",
                        "COST",
                        "PROFIT",
                        "QTY",
                        "QUANTITY",
                        "ORDERS",
                        "CUSTOMERS",
                    ]
                ):
                    score += 50.0

                if is_currency_metric(col):
                    score += 20.0

                if any(
                    col_upper.startswith(p)
                    for p in [
                        "TOTAL_",
                        "SUM_",
                        "COUNT_",
                        "AVG_",
                    ]
                ):
                    score += 20.0

            metric_candidates.append(
                (col, score)
            )

    metric_candidates.sort(
        key=lambda x: x[1],
        reverse=True,
    )

    # Rule 1: Date + Metric -> Line Chart
    if date_cols and metric_candidates:
        x_col = date_cols[0]
        y_col = metric_candidates[0][0]

        return (
            x_col,
            y_col,
            "Line Chart",
        )

    # Rule 2: Categorical Dimension + Metric -> Bar Chart
    selected_metric = (
        metric_candidates[0][0]
        if metric_candidates
        else None
    )

    cat_candidates: List[Tuple[str, float]] = []

    for col in df.columns:
        if col in date_cols or col == selected_metric:
            continue

        col_upper = str(col).upper()
        col_s = df[col]

        is_numeric = pd.api.types.is_numeric_dtype(
            col_s
        )

        score = 50.0

        if is_id_or_key_column(col):
            score = 30.0

        elif any(
            k in col_upper
            for k in [
                "NAME",
                "NATION",
                "REGION",
                "TITLE",
                "TYPE",
                "BRAND",
                "SEGMENT",
                "CATEGORY",
                "STATUS",
                "PRIORITY",
                "MODE",
            ]
        ):
            score = 100.0

        elif any(
            k in col_upper
            for k in [
                "PHONE",
                "ADDRESS",
                "COMMENT",
                "NOTE",
            ]
        ):
            score = 15.0

        elif not is_numeric:
            score = 70.0

        cat_candidates.append(
            (col, score)
        )

    cat_candidates.sort(
        key=lambda x: x[1],
        reverse=True,
    )

    if cat_candidates and metric_candidates:
        x_col = cat_candidates[0][0]
        y_col = metric_candidates[0][0]

        return (
            x_col,
            y_col,
            "Bar Chart",
        )

    # Rule 3: Multiple numeric columns -> Scatter Plot
    if len(metric_candidates) >= 2:
        return (
            metric_candidates[1][0],
            metric_candidates[0][0],
            "Scatter Plot",
        )

    return None, None, "Table"


def apply_currency_formatting(
    fig: go.Figure,
    y_label: str,
    y_col: str,
    is_curr: bool,
    is_inr: bool,
) -> None:
    """Apply correct currency formatting to a chart."""
    if is_inr:
        fig.update_layout(
            yaxis_tickprefix="₹",
            yaxis_tickformat=",",
        )

        fig.update_traces(
            hovertemplate=(
                f"<b>%{{x}}</b><br>"
                f"{y_label}: ₹%{{y:,.2f}}"
                "<extra></extra>"
            )
        )

    elif is_curr:
        fig.update_layout(
            yaxis_tickprefix="$",
            yaxis_tickformat=",",
        )

        fig.update_traces(
            hovertemplate=(
                f"<b>%{{x}}</b><br>"
                f"{y_label}: $%{{y:,.2f}}"
                "<extra></extra>"
            )
        )

    else:
        fig.update_layout(
            yaxis_tickformat=",",
        )


def auto_create_chart(
    df: pd.DataFrame,
    title: str = "",
    question: str = "",
    theme: str = "dark",
) -> Tuple[Optional[go.Figure], str]:
    """Automatically select and build the best Plotly chart.

    Supports:
    - Dark/light themes
    - Human-readable labels
    - INR account balance formatting
    - USD formatting for other monetary metrics
    - Automatic chart type selection
    """
    if (
        df is None
        or df.empty
        or len(df.columns) < 2
    ):
        return None, "Table"

    # Clean question from generic title prefix
    if title and title.startswith(
        "Visual Analysis:"
    ):
        question = (
            question
            or title.replace(
                "Visual Analysis:",
                "",
            ).strip()
        )
        title = ""

    x_col, y_col, chart_type = pick_best_chart_columns(
        df
    )

    if (
        not x_col
        or not y_col
        or chart_type == "Table"
    ):
        return None, "Table"

    df_plot = prepare_chart_dataframe(df)

    x_label = format_column_label(x_col)
    y_label = format_column_label(y_col)

    chart_title = (
        title
        or generate_chart_title(
            x_label,
            y_label,
            chart_type,
            len(df_plot),
            question,
        )
    )

    is_curr = is_currency_metric(
        y_col,
        y_label,
    )

    is_inr = is_account_balance_metric(
        y_col,
        y_label,
    )

    plotly_template = (
        "plotly_dark"
        if str(theme).lower() == "dark"
        else "plotly_white"
    )

    # ---------------------------------------------------------
    # 1. Line Chart
    # ---------------------------------------------------------
    if chart_type == "Line Chart":
        try:
            sorted_df = df_plot.sort_values(
                by=x_col
            )
        except Exception:
            sorted_df = df_plot

        fig = px.line(
            sorted_df,
            x=x_col,
            y=y_col,
            markers=True,
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

        fig.update_layout(
            margin=dict(
                l=40,
                r=40,
                t=50,
                b=40,
            ),
            hovermode="x unified",
            xaxis_title=x_label,
            yaxis_title=y_label,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        apply_currency_formatting(
            fig,
            y_label,
            y_col,
            is_curr,
            is_inr,
        )

        return fig, "Line Chart"

    # ---------------------------------------------------------
    # 2. Bar Chart
    # ---------------------------------------------------------
    if chart_type == "Bar Chart":
        try:
            sorted_df = df_plot.sort_values(
                by=y_col,
                ascending=False,
            )
        except Exception:
            sorted_df = df_plot

        fig = px.bar(
            sorted_df,
            x=x_col,
            y=y_col,
            color=(
                y_col
                if pd.api.types.is_numeric_dtype(
                    df_plot[y_col]
                )
                else None
            ),
            color_continuous_scale="Viridis",
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

        fig.update_layout(
            margin=dict(
                l=40,
                r=40,
                t=50,
                b=40,
            ),
            xaxis_title=x_label,
            yaxis_title=y_label,
            coloraxis_showscale=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        apply_currency_formatting(
            fig,
            y_label,
            y_col,
            is_curr,
            is_inr,
        )

        return fig, "Bar Chart"

    # ---------------------------------------------------------
    # 3. Scatter Plot
    # ---------------------------------------------------------
    if chart_type == "Scatter Plot":
        fig = px.scatter(
            df_plot,
            x=x_col,
            y=y_col,
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

        fig.update_layout(
            margin=dict(
                l=40,
                r=40,
                t=50,
                b=40,
            ),
            xaxis_title=x_label,
            yaxis_title=y_label,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        if is_inr:
            fig.update_layout(
                yaxis_tickprefix="₹",
                yaxis_tickformat=",",
            )

        elif is_curr:
            fig.update_layout(
                yaxis_tickprefix="$",
                yaxis_tickformat=",",
            )

        else:
            fig.update_layout(
                yaxis_tickformat=",",
            )

        return fig, "Scatter Plot"

    return None, "Table"


def create_custom_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_col: str,
    title: str = "",
    theme: str = "dark",
) -> go.Figure:
    """Build a chart of the requested type with user-chosen axes and formatting."""
    df_plot = prepare_chart_dataframe(df)

    x_label = format_column_label(x_col)
    y_label = format_column_label(y_col)

    chart_title = (
        title
        or f"{y_label} by {x_label}"
    )

    is_curr = is_currency_metric(
        y_col,
        y_label,
    )

    is_inr = is_account_balance_metric(
        y_col,
        y_label,
    )

    plotly_template = (
        "plotly_dark"
        if str(theme).lower() == "dark"
        else "plotly_white"
    )

    # ---------------------------------------------------------
    # Bar Chart
    # ---------------------------------------------------------
    if chart_type == "Bar Chart":
        try:
            sorted_df = df_plot.sort_values(
                by=y_col,
                ascending=False,
            )
        except Exception:
            sorted_df = df_plot

        fig = px.bar(
            sorted_df,
            x=x_col,
            y=y_col,
            color=(
                y_col
                if pd.api.types.is_numeric_dtype(
                    df_plot[y_col]
                )
                else None
            ),
            color_continuous_scale="Viridis",
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

    # ---------------------------------------------------------
    # Line Chart
    # ---------------------------------------------------------
    elif chart_type == "Line Chart":
        try:
            sorted_df = df_plot.sort_values(
                by=x_col
            )
        except Exception:
            sorted_df = df_plot

        fig = px.line(
            sorted_df,
            x=x_col,
            y=y_col,
            markers=True,
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

    # ---------------------------------------------------------
    # Scatter Plot
    # ---------------------------------------------------------
    elif chart_type == "Scatter Plot":
        fig = px.scatter(
            df_plot,
            x=x_col,
            y=y_col,
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

    # ---------------------------------------------------------
    # Area Chart
    # ---------------------------------------------------------
    elif chart_type == "Area Chart":
        try:
            sorted_df = df_plot.sort_values(
                by=x_col
            )
        except Exception:
            sorted_df = df_plot

        fig = px.area(
            sorted_df,
            x=x_col,
            y=y_col,
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

    # ---------------------------------------------------------
    # Default Bar Chart
    # ---------------------------------------------------------
    else:
        fig = px.bar(
            df_plot,
            x=x_col,
            y=y_col,
            title=chart_title,
            template=plotly_template,
            labels={
                x_col: x_label,
                y_col: y_label,
            },
        )

    fig.update_layout(
        margin=dict(
            l=40,
            r=40,
            t=50,
            b=40,
        ),
        xaxis_title=x_label,
        yaxis_title=y_label,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    apply_currency_formatting(
        fig,
        y_label,
        y_col,
        is_curr,
        is_inr,
    )

    return fig

