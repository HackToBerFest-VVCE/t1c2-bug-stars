"""Unit tests for DataPilot example question buttons using Streamlit AppTest."""

import os
from streamlit.testing.v1 import AppTest


def test_example_buttons_populate_question_without_auto_executing():
    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    at = AppTest.from_file(app_path, default_timeout=60).run()
    assert not at.exception

    # Initially the text input should be empty
    assert at.text_input(key="main_query_input").value == ""

    expected_questions = [
        ("ex_btn_0", "Show me the top 10 customers by total spending."),
        ("ex_btn_1", "Which nations have the most customers?"),
        ("ex_btn_2", "Show the number of orders by year."),
        ("ex_btn_3", "Which regions have the highest revenue?"),
        ("ex_btn_4", "Show the top 10 suppliers by account balance."),
    ]

    for btn_key, expected_q in expected_questions:
        at.button(key=btn_key).click().run(timeout=60)
        assert not at.exception
        # Confirm input populated with the exact question
        assert at.text_input(key="main_query_input").value == expected_q
        # Confirm that analysis was NOT automatically triggered
        assert "last_result" not in at.session_state
