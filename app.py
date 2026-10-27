"""DataPilot — Open-Source AI Data Analyst with Snowflake.

HackToBerFest Hack Day Mysore - VectorFlow Club
Track 1 — Challenge B: Best Open-Source AI Project with Snowflake
Team: Bug Stars (Bindu shri N & Chaitra R)
"""

import os
import time
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(override=True)

from ai.ollama_client import OllamaClient
from ai.sql_generator import generate_sql
from ai.result_analyzer import analyze_results
from database.snowflake_connection import test_connection, get_snowflake_config
from database.query_executor import execute_query
from database.schema_inspector import fetch_dynamic_schema, get_available_tables
from visualization.charts import (
    auto_create_chart,
    create_custom_chart,
    detect_column_types,
    pick_best_chart_columns,
    format_column_label,
)

# Set Page Configuration
st.set_page_config(
    page_title="DataPilot — Open-Source AI Data Analyst",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Theme State Initialization (Default: Dark Mode)
if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "🌙 Dark"


def get_theme_css(theme_mode: str) -> str:
    """Return responsive CSS for the selected theme mode (Dark or Light)."""
    is_dark = "Dark" in theme_mode

    if is_dark:
        return """
        <style>
        /* Base App Background & Text */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #0E1117 !important;
            color: #E2E8F0 !important;
        }
        [data-testid="stHeader"] {
            background-color: rgba(14, 17, 23, 0.85) !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #161B22 !important;
            border-right: 1px solid #30363D !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            background-color: #161B22 !important;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #E2E8F0 !important;
        }

        /* Headers & Typography */
        .main-title {
            font-size: 2.3rem;
            font-weight: 800;
            color: #60A5FA !important;
            margin-bottom: 0px;
        }
        .sub-title {
            font-size: 1.1rem;
            color: #94A3B8 !important;
            margin-bottom: 15px;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #F8FAFC !important;
        }
        p, span, label, div {
            color: #E2E8F0;
        }
        [data-testid="stCaptionContainer"], .stCaption {
            color: #94A3B8 !important;
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            margin-right: 6px;
            border-radius: 12px;
            font-size: 0.78rem;
            font-weight: 600;
        }
        .badge-blue { background-color: rgba(30, 58, 138, 0.45) !important; color: #93C5FD !important; border: 1px solid #3B82F6; }
        .badge-cyan { background-color: rgba(22, 78, 99, 0.45) !important; color: #67E8F9 !important; border: 1px solid #06B6D4; }
        .badge-purple { background-color: rgba(88, 28, 135, 0.45) !important; color: #E9D5FF !important; border: 1px solid #A855F7; }
        .badge-green { background-color: rgba(20, 83, 45, 0.45) !important; color: #86EFAC !important; border: 1px solid #22C55E; }
        .badge-amber { background-color: rgba(120, 53, 15, 0.45) !important; color: #FDE68A !important; border: 1px solid #F59E0B; }

        /* Status Cards */
        .status-card {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 0.88rem;
        }
        .status-ok {
            background-color: rgba(16, 185, 129, 0.12) !important;
            border: 1px solid rgba(16, 185, 129, 0.35) !important;
            color: #34D399 !important;
        }
        .status-warn {
            background-color: rgba(245, 158, 11, 0.12) !important;
            border: 1px solid rgba(245, 158, 11, 0.35) !important;
            color: #FCD34D !important;
        }

        /* Metrics */
        .metric-card, [data-testid="stMetric"] {
            background-color: #161B22 !important;
            border: 1px solid #30363D !important;
            border-radius: 8px;
            padding: 10px 14px;
        }
        [data-testid="stMetricLabel"] {
            color: #94A3B8 !important;
        }
        [data-testid="stMetricValue"] {
            color: #F8FAFC !important;
        }

        /* Buttons */
        .stButton > button {
            background-color: #21262D !important;
            color: #F0F6FC !important;
            border: 1px solid #363B42 !important;
            border-radius: 6px;
        }
        .stButton > button:hover {
            background-color: #30363D !important;
            border-color: #8B949E !important;
            color: #FFFFFF !important;
        }
        .stButton > button[kind="primary"], button[data-testid="baseButton-primary"] {
            background-color: #2563EB !important;
            color: #FFFFFF !important;
            border: 1px solid #3B82F6 !important;
            font-weight: 600;
        }
        .stButton > button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
            background-color: #1D4ED8 !important;
            border-color: #60A5FA !important;
        }

        /* Inputs & Select Boxes */
        .stTextInput input {
            background-color: #161B22 !important;
            color: #F0F6FC !important;
            border: 1px solid #30363D !important;
            border-radius: 6px;
        }
        .stTextInput input:focus {
            border-color: #3B82F6 !important;
            box-shadow: 0 0 0 1px #3B82F6 !important;
        }
        .stSelectbox [data-baseweb="select"] {
            background-color: #161B22 !important;
            color: #F0F6FC !important;
            border: 1px solid #30363D !important;
        }

        /* Expanders */
        [data-testid="stExpander"] {
            background-color: #161B22 !important;
            border: 1px solid #30363D !important;
            border-radius: 8px;
        }
        [data-testid="stExpander"] summary {
            color: #F0F6FC !important;
        }
        [data-testid="stExpander"] summary:hover {
            color: #60A5FA !important;
        }

        /* Code Blocks & SQL Viewer */
        pre, code, .stCode {
            background-color: #0D1117 !important;
            color: #E2E8F0 !important;
            border: 1px solid #30363D !important;
            border-radius: 6px;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            border-bottom: 1px solid #30363D !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #8B949E !important;
        }
        .stTabs [aria-selected="true"] {
            color: #60A5FA !important;
            border-bottom-color: #60A5FA !important;
        }

        /* Containers (AI Insights) */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #161B22 !important;
            border: 1px solid #30363D !important;
            border-radius: 8px;
            padding: 14px;
        }

        /* Status Widget */
        [data-testid="stStatusWidget"], .stStatus {
            background-color: #161B22 !important;
            border: 1px solid #30363D !important;
            color: #F0F6FC !important;
        }

        /* Theme Toggle Container */
        .theme-toggle-box {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            margin-top: 5px;
        }
        .theme-toggle-box [data-testid="stRadio"] > div {
            background-color: #161B22;
            padding: 4px 8px;
            border-radius: 20px;
            border: 1px solid #30363D;
        }
        .footer-text {
            text-align: center;
            color: #94A3B8;
            font-size: 0.85rem;
            margin-top: 25px;
        }
        </style>
        """
    else:
        return """
        <style>
        /* Base App Background & Text */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #F8FAFC !important;
            color: #0F172A !important;
        }
        [data-testid="stHeader"] {
            background-color: rgba(248, 250, 252, 0.85) !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #F1F5F9 !important;
            border-right: 1px solid #E2E8F0 !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            background-color: #F1F5F9 !important;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #0F172A !important;
        }

        /* Headers & Typography */
        .main-title {
            font-size: 2.3rem;
            font-weight: 800;
            color: #1E3A8A !important;
            margin-bottom: 0px;
        }
        .sub-title {
            font-size: 1.1rem;
            color: #4B5563 !important;
            margin-bottom: 15px;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #0F172A !important;
        }
        p, span, label, div {
            color: #1E293B;
        }
        [data-testid="stCaptionContainer"], .stCaption {
            color: #64748B !important;
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            margin-right: 6px;
            border-radius: 12px;
            font-size: 0.78rem;
            font-weight: 600;
        }
        .badge-blue { background-color: #DBEAFE !important; color: #1E40AF !important; border: 1px solid #93C5FD; }
        .badge-cyan { background-color: #CFFAFE !important; color: #0E7490 !important; border: 1px solid #67E8F9; }
        .badge-purple { background-color: #F3E8FF !important; color: #6B21A8 !important; border: 1px solid #D8B4FE; }
        .badge-green { background-color: #DCFCE7 !important; color: #166534 !important; border: 1px solid #86EFAC; }
        .badge-amber { background-color: #FEF3C7 !important; color: #92400E !important; border: 1px solid #FDE68A; }

        /* Status Cards */
        .status-card {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 0.88rem;
        }
        .status-ok {
            background-color: #ECFDF5 !important;
            border: 1px solid #A7F3D0 !important;
            color: #065F46 !important;
        }
        .status-warn {
            background-color: #FFFBEB !important;
            border: 1px solid #FDE68A !important;
            color: #92400E !important;
        }

        /* Metrics */
        .metric-card, [data-testid="stMetric"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px;
            padding: 10px 14px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        [data-testid="stMetricLabel"] {
            color: #64748B !important;
        }
        [data-testid="stMetricValue"] {
            color: #0F172A !important;
        }

        /* Buttons */
        .stButton > button {
            background-color: #FFFFFF !important;
            color: #1E293B !important;
            border: 1px solid #CBD5E1 !important;
            border-radius: 6px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }
        .stButton > button:hover {
            background-color: #F1F5F9 !important;
            border-color: #94A3B8 !important;
            color: #0F172A !important;
        }
        .stButton > button[kind="primary"], button[data-testid="baseButton-primary"] {
            background-color: #2563EB !important;
            color: #FFFFFF !important;
            border: 1px solid #1D4ED8 !important;
            font-weight: 600;
        }
        .stButton > button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
            background-color: #1D4ED8 !important;
            border-color: #1E40AF !important;
        }

        /* Inputs & Select Boxes */
        .stTextInput input {
            background-color: #FFFFFF !important;
            color: #0F172A !important;
            border: 1px solid #CBD5E1 !important;
            border-radius: 6px;
        }
        .stTextInput input:focus {
            border-color: #2563EB !important;
            box-shadow: 0 0 0 1px #2563EB !important;
        }
        .stSelectbox [data-baseweb="select"] {
            background-color: #FFFFFF !important;
            color: #0F172A !important;
            border: 1px solid #CBD5E1 !important;
        }

        /* Expanders */
        [data-testid="stExpander"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        [data-testid="stExpander"] summary {
            color: #0F172A !important;
        }
        [data-testid="stExpander"] summary:hover {
            color: #2563EB !important;
        }

        /* Code Blocks & SQL Viewer */
        pre, code, .stCode {
            background-color: #F1F5F9 !important;
            color: #0F172A !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 6px;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            border-bottom: 1px solid #E2E8F0 !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #64748B !important;
        }
        .stTabs [aria-selected="true"] {
            color: #2563EB !important;
            border-bottom-color: #2563EB !important;
        }

        /* Containers (AI Insights) */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px;
            padding: 14px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        /* Status Widget */
        [data-testid="stStatusWidget"], .stStatus {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            color: #0F172A !important;
        }

        /* Theme Toggle Container */
        .theme-toggle-box {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            margin-top: 5px;
        }
        .theme-toggle-box [data-testid="stRadio"] > div {
            background-color: #FFFFFF;
            padding: 4px 8px;
            border-radius: 20px;
            border: 1px solid #CBD5E1;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .footer-text {
            text-align: center;
            color: #64748B;
            font-size: 0.85rem;
            margin-top: 25px;
        }
        </style>
        """


# Inject theme styling
st.markdown(get_theme_css(st.session_state["theme_mode"]), unsafe_allow_html=True)


# Sidebar Configuration & Status
with st.sidebar:
    st.markdown("### ✈️ DataPilot Control Center")
    st.caption("Track 1 — Challenge B | Team Bug Stars")
    st.markdown("---")

    # Data Source & Environment Details
    st.markdown("#### ⚙️ Infrastructure")
    st.markdown(
        """
        - **Data Source:** Snowflake
        - **Dataset:** `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1`
        - **Warehouse:** `COMPUTE_WH`
        - **AI Model:** `Llama 3.2` (Open-Weight)
        - **Runtime:** `Ollama` (Local)
        """
    )

    st.markdown("---")
    st.markdown("#### 🔌 Connection Status")

    # Dynamic Snowflake Password Configuration Option
    env_cfg = get_snowflake_config()
    session_password = None

    if not env_cfg.get("password"):
        st.info("ℹ️ Snowflake password not detected in `.env`.")
        session_password = st.text_input(
            "Enter Snowflake Password:",
            type="password",
            help="Your password will only be kept in memory for this session and never stored.",
            key="sidebar_snowflake_password",
        )
    else:
        # Check if user wants to override
        override = st.checkbox("Override .env password", key="override_pwd_chk")
        if override:
            session_password = st.text_input(
                "New Snowflake Password:",
                type="password",
                key="sidebar_snowflake_override_pwd",
            )

    # Initialize Clients and Test Connections
    ollama_client = OllamaClient()
    ollama_ok, ollama_msg = ollama_client.check_connection()

    sf_ok, sf_msg = test_connection(override_password=session_password)

    # Display Status Badges
    if sf_ok:
        st.markdown(
            f'<div class="status-card status-ok">✅ <b>Snowflake Connected</b><br><small>{sf_msg}</small></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="status-card status-warn">⚠️ <b>Snowflake Not Connected</b><br><small>{sf_msg}</small></div>',
            unsafe_allow_html=True,
        )

    if ollama_ok:
        st.markdown(
            f'<div class="status-card status-ok">✅ <b>Ollama Connected</b><br><small>{ollama_msg}</small></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="status-card status-warn">⚠️ <b>Ollama Not Connected</b><br><small>{ollama_msg}</small></div>',
            unsafe_allow_html=True,
        )

    # Sidebar: Schema Inspector
    st.markdown("---")
    with st.expander("📚 Explore TPC-H SF1 Schema"):
        schema_dict = fetch_dynamic_schema(override_password=session_password)
        selected_tbl = st.selectbox("Select Table:", options=list(schema_dict.keys()))
        if selected_tbl:
            cols = schema_dict[selected_tbl]
            st.markdown(f"**Columns for `{selected_tbl}`:**")
            for c_name, c_type in cols.items():
                st.markdown(f"- `{c_name}`: *{c_type}*")

    # Sidebar: How Snowflake CoCo Helped
    with st.expander("💡 How Snowflake CoCo Helped"):
        st.markdown(
            """
            **Snowflake CoCo** served as our intelligent data exploration and development partner:
            1. **TPC-H SF1 Exploration:** Guided schema discovery across the 8 benchmark tables.
            2. **Relationship Mapping:** Clarified primary and foreign key join conditions (e.g. `ORDERS` to `CUSTOMER`).
            3. **SQL Query Assistance:** Helped formulate optimized analytical queries for aggregation benchmarks.
            4. **Validation:** Assayed Snowflake dialect patterns and date functions (`EXTRACT(YEAR FROM ...)`).
            5. **Workflow Acceleration:** Streamlined end-to-end development of the DataPilot pipeline.
            
            *(Note: Llama 3.2 serves as the local runtime LLM, while CoCo assisted during development).*
            """
        )


def on_theme_change():
    st.session_state["theme_mode"] = st.session_state["theme_radio_selector"]


# Main Interface Header with Top-Right Theme Toggle
header_col1, header_col2 = st.columns([0.76, 0.24])

with header_col1:
    st.markdown('<h1 class="main-title">✈️ DataPilot</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">Open-Source AI Data Analyst with Snowflake & Local Llama 3.2</p>',
        unsafe_allow_html=True,
    )

with header_col2:
    st.markdown('<div class="theme-toggle-box">', unsafe_allow_html=True)
    st.radio(
        label="Theme",
        options=["🌙 Dark", "☀️ Light"],
        index=0 if "Dark" in st.session_state.get("theme_mode", "🌙 Dark") else 1,
        horizontal=True,
        key="theme_radio_selector",
        on_change=on_theme_change,
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

# Badges
st.markdown(
    """
    <div style="margin-bottom: 20px;">
        <span class="badge badge-blue">❄️ Snowflake</span>
        <span class="badge badge-cyan">📈 TPC-H SF1</span>
        <span class="badge badge-purple">🦙 Llama 3.2 (Open-Weight)</span>
        <span class="badge badge-green">⚡ Ollama Local</span>
        <span class="badge badge-amber">🤝 CoCo-Assisted</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Quick Demo Questions
DEMO_QUESTIONS = [
    "Show me the top 10 customers by total spending.",
    "Which nations have the most customers?",
    "Show the number of orders by year.",
    "Which regions have the highest revenue?",
    "Show the top 10 suppliers by account balance.",
]

st.markdown("##### 💡 Try an Example Question:")
example_cols = st.columns(len(DEMO_QUESTIONS))

# Initialize question in session state if not present
if "main_query_input" not in st.session_state:
    st.session_state["main_query_input"] = ""
if "user_question" not in st.session_state:
    st.session_state["user_question"] = ""


def set_example_question(question_text: str):
    st.session_state["main_query_input"] = question_text
    st.session_state["user_question"] = question_text


btn_labels = [
    "Top 10 Customers",
    "Customers by Nation",
    "Orders by Year",
    "Revenue by Region",
    "Top Suppliers",
]

for i, q in enumerate(DEMO_QUESTIONS):
    example_cols[i].button(
        btn_labels[i],
        key=f"ex_btn_{i}",
        use_container_width=True,
        on_click=set_example_question,
        args=(q,),
    )

# Main Question Input
st.markdown("##### 💬 Ask your data a question:")
user_query = st.text_input(
    label="Natural Language Question",
    placeholder="Example: Which 10 customers have the highest total spending?",
    label_visibility="collapsed",
    key="main_query_input",
)

analyze_clicked = st.button("🚀 Analyze with DataPilot", type="primary", use_container_width=True)

# Main Execution Pipeline
if analyze_clicked or (user_query and user_query != st.session_state.get("last_processed_query", None) and False):
    if not user_query.strip():
        st.warning("Please enter a question or select an example above.")
    else:
        # Check Ollama status
        if not ollama_ok:
            st.error("Ollama is not running. Please start the Ollama service (`ollama serve`) and try again.")
        else:
            # Multi-stage Progress Status for Judges
            status_container = st.status("🚀 DataPilot Workflow in Progress...", expanded=True)

            with status_container:
                # Stage 1: Understanding Question & Schema
                st.write("🧠 **Stage 1:** Understanding natural language question & analyzing TPC-H schema...")
                time.sleep(0.2)

                # Stage 2: Generating SQL
                st.write("⚙️ **Stage 2:** Generating Snowflake SQL using local Llama 3.2 via Ollama...")
                gen_ok, gen_sql_or_err, validated_sql = generate_sql(
                    question=user_query,
                    ollama_client=ollama_client,
                    override_password=session_password,
                )

                if not gen_ok:
                    status_container.update(label="❌ SQL Generation Failed", state="error", expanded=True)
                    st.error(f"Could not generate SQL: {gen_sql_or_err}")
                else:
                    st.write("🛡️ **Stage 3:** Validating SQL security (Read-Only SELECT/WITH enforcement)...")
                    st.code(validated_sql, language="sql")
                    time.sleep(0.2)

                    # Stage 4: Querying Snowflake
                    st.write("❄️ **Stage 4:** Executing query against Snowflake `TPCH_SF1`...")
                    
                    if not sf_ok:
                        status_container.update(label="⚠️ Snowflake Not Connected", state="error", expanded=True)
                        st.error(
                            "Snowflake is not connected. Please enter your Snowflake password in the sidebar or `.env` file to execute the query against live data."
                        )
                    else:
                        query_res = execute_query(
                            sql=validated_sql,
                            override_password=session_password,
                        )

                        if not query_res["success"]:
                            status_container.update(label="❌ Query Execution Failed", state="error", expanded=True)
                            st.error(f"Snowflake query execution error: {query_res['error']}")
                        else:
                            df = query_res["data"]
                            st.write(f"✅ Retrieved {query_res['row_count']} rows in {query_res['execution_time_sec']}s.")

                            # Stage 5: Analyzing Results
                            st.write("💡 **Stage 5:** Generating grounded business insights with Llama 3.2...")
                            analysis_res = analyze_results(
                                question=user_query,
                                sql=validated_sql,
                                df=df,
                                ollama_client=ollama_client,
                            )

                            # Stage 6: Visualization
                            st.write("📊 **Stage 6:** Rendering automatic Plotly visual analysis...")
                            status_container.update(
                                label="✅ DataPilot Analysis Complete!",
                                state="complete",
                                expanded=False,
                            )

                            # Store results in session state to display cleanly below
                            st.session_state["last_result"] = {
                                "question": user_query,
                                "sql": validated_sql,
                                "df": df,
                                "row_count": query_res["row_count"],
                                "col_count": query_res["col_count"],
                                "exec_time": query_res["execution_time_sec"],
                                "insights": analysis_res["raw_text"],
                            }

# Display Results Section if Available
if "last_result" in st.session_state:
    res = st.session_state["last_result"]
    df = res["df"]

    st.markdown("---")
    st.markdown("### 📊 Analysis & Insights")

    # Top Metrics Bar
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric(label="Rows Returned", value=res["row_count"])
    with m_col2:
        st.metric(label="Columns", value=res["col_count"])
    with m_col3:
        st.metric(label="Snowflake Execution", value=f"{res['exec_time']}s")
    with m_col4:
        st.metric(label="AI Model", value="Llama 3.2 (Local)")

    # Expandable Generated SQL Section
    with st.expander("🔍 View Generated Snowflake SQL Query", expanded=False):
        st.code(res["sql"], language="sql")
        st.caption("Validated: Read-only SELECT query executed against SNOWFLAKE_SAMPLE_DATA.TPCH_SF1")

    # Two column layout: Left = Visualization & Data, Right = AI Insights
    col_vis, col_ai = st.columns([1.1, 0.9])

    with col_vis:
        st.markdown("#### 📈 Data & Visualization")

        if df.empty:
            st.info("The query returned 0 rows.")
        else:
            # Chart Mode Selector Tabs
            active_theme = "dark" if "Dark" in st.session_state.get("theme_mode", "🌙 Dark") else "light"
            auto_fig, auto_type = auto_create_chart(df, question=res["question"], theme=active_theme)
            
            tab_auto, tab_custom, tab_table = st.tabs(
                [f"✨ Recommended Chart ({auto_type})", "🛠️ Custom Chart", "📋 Data Table"]
            )

            with tab_auto:
                if auto_fig:
                    st.plotly_chart(auto_fig, use_container_width=True)
                else:
                    st.dataframe(df, use_container_width=True, height=350)

            with tab_custom:
                c_col1, c_col2, c_col3 = st.columns(3)
                with c_col1:
                    chart_choice = st.selectbox(
                        "Chart Type",
                        ["Bar Chart", "Line Chart", "Scatter Plot", "Area Chart"],
                        key="custom_chart_type",
                    )
                best_x, best_y, _ = pick_best_chart_columns(df)
                default_x_idx = list(df.columns).index(best_x) if best_x in df.columns else 0
                default_y_idx = list(df.columns).index(best_y) if best_y in df.columns else (1 if len(df.columns) > 1 else 0)

                with c_col2:
                    x_axis = st.selectbox("X-Axis Column", df.columns, index=default_x_idx, key="custom_x_axis")
                with c_col3:
                    y_axis = st.selectbox("Y-Axis Column", df.columns, index=default_y_idx, key="custom_y_axis")

                custom_fig = create_custom_chart(
                    df=df,
                    chart_type=chart_choice,
                    x_col=x_axis,
                    y_col=y_axis,
                    title=f"{format_column_label(y_axis)} by {format_column_label(x_axis)}",
                    theme=active_theme,
                )
                st.plotly_chart(custom_fig, use_container_width=True)

            with tab_table:
                st.dataframe(df, use_container_width=True, height=350)
                # Quick CSV download
                csv_data = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Results CSV",
                    data=csv_data,
                    file_name="datapilot_query_results.csv",
                    mime="text/csv",
                )

    with col_ai:
        st.markdown("#### 💡 AI Analyst Insights")
        # Render AI Insights inside a clean card-like container
        with st.container(border=True):
            st.markdown(res["insights"])


# Hackathon Architecture & Information Section
st.markdown("---")
st.markdown("### 🛠️ How DataPilot Works")

flow_col1, flow_col2, flow_col3, flow_col4, flow_col5 = st.columns(5)
with flow_col1:
    st.markdown("**1. Natural Question**")
    st.caption("User asks in plain English without writing SQL.")
with flow_col2:
    st.markdown("**2. Llama 3.2 (Local)**")
    st.caption("Extracts intent and maps question to Snowflake schema.")
with flow_col3:
    st.markdown("**3. SQL Validation**")
    st.caption("Guarantees read-only safety (SELECT/WITH queries only).")
with flow_col4:
    st.markdown("**4. Snowflake TPC-H**")
    st.caption("Executes query at high performance on Snowflake.")
with flow_col5:
    st.markdown("**5. Plotly & Insights**")
    st.caption("Renders interactive charts & business conclusions.")

st.markdown(
    """
    <div class="footer-text">
        Powered by <b>Snowflake</b> | <b>TPC-H SF1</b> | <b>Snowflake CoCo</b> | <b>Llama 3.2</b> | <b>Ollama</b>
        <br>
        HackToBerFest Hack Day Mysore • VectorFlow Club • Team Bug Stars
    </div>
    """,
    unsafe_allow_html=True,
)
