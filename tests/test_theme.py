"""Unit tests for DataPilot theme toggle and responsiveness."""

import decimal
import pandas as pd
from app import get_theme_css
from visualization.charts import auto_create_chart, create_custom_chart


def test_theme_css_generation():
    dark_css = get_theme_css("🌙 Dark")
    assert "#0E1117" in dark_css
    assert "#161B22" in dark_css
    assert "#60A5FA" in dark_css
    assert "#E2E8F0" in dark_css

    light_css = get_theme_css("☀️ Light")
    assert "#F8FAFC" in light_css
    assert "#1E3A8A" in light_css
    assert "#0F172A" in light_css
    assert "#FFFFFF" in light_css


def test_chart_theme_modes():
    df = pd.DataFrame(
        {
            "C_NAME": ["Cust#1", "Cust#2"],
            "TOTAL_SPENT": [decimal.Decimal("1000.50"), decimal.Decimal("2000.75")],
        }
    )

    fig_dark, type_dark = auto_create_chart(df, question="Top Customers", theme="dark")
    assert fig_dark is not None
    assert type_dark == "Bar Chart"
    assert fig_dark.layout.template.layout.font.color == "#f2f5fa"

    fig_light, type_light = auto_create_chart(df, question="Top Customers", theme="light")
    assert fig_light is not None
    assert type_light == "Bar Chart"
    assert fig_light.layout.template.layout.font.color == "#2a3f5f"

    custom_dark = create_custom_chart(df, "Bar Chart", "C_NAME", "TOTAL_SPENT", theme="dark")
    assert custom_dark is not None
    assert custom_dark.layout.template.layout.font.color == "#f2f5fa"

    custom_light = create_custom_chart(df, "Bar Chart", "C_NAME", "TOTAL_SPENT", theme="light")
    assert custom_light is not None
    assert custom_light.layout.template.layout.font.color == "#2a3f5f"
