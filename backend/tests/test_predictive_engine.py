import pytest
from app.predictive_engine import analyze_trend


def test_analyze_trend_rising():
    # Clearly rising values: 7.0, 7.3, 7.6, ..., 9.7
    recent_values = [7.0 + (i * 0.3) for i in range(10)]
    result = analyze_trend(station_id=1, parameter="ph", recent_values=recent_values)

    assert result["trend_direction"] == "rising"
    assert result["trend_risk_score"] >= 50
    assert result["projected_value"] is not None
    # Holt model must project a value higher than the last measured value
    assert result["projected_value"] > recent_values[-1]
    assert "keskin bir yükseliş trendinde" in result["projection_message"]


def test_analyze_trend_falling():
    # Clearly falling values: 8.5, 8.25, ..., 6.25
    recent_values = [8.5 - (i * 0.25) for i in range(10)]
    result = analyze_trend(station_id=1, parameter="ph", recent_values=recent_values)

    assert result["trend_direction"] == "falling"
    assert result["trend_risk_score"] >= 50
    assert result["projected_value"] is not None
    # Holt model must project a value lower than the last measured value
    assert result["projected_value"] < recent_values[-1]
    assert "keskin bir düşüş trendinde" in result["projection_message"]


def test_analyze_trend_stable():
    # Flat/stable values
    recent_values = [7.2, 7.21, 7.19, 7.2, 7.2, 7.18, 7.22, 7.2, 7.19, 7.21]
    result = analyze_trend(station_id=1, parameter="ph", recent_values=recent_values)

    assert result["trend_direction"] == "stable"
    assert result["trend_risk_score"] < 20
    assert result["projected_value"] is not None
    assert "genel olarak stabil" in result["projection_message"]


def test_analyze_trend_insufficient_data():
    # Fewer than 3 points
    recent_values = [7.2, 7.3]
    result = analyze_trend(station_id=1, parameter="ph", recent_values=recent_values)

    assert result["trend_direction"] == "stable"
    assert result["trend_risk_score"] == 0
    assert result["projected_value"] is None
    assert "Yeterli veri yok" in result["projection_message"]


def test_analyze_trend_bad_input_no_exception():
    # Bad input with Nones, strings, etc.
    recent_values = [None, "bad_value", 7.2]
    result = analyze_trend(station_id=1, parameter="ph", recent_values=recent_values)

    assert result["trend_direction"] == "stable"
    assert result["trend_risk_score"] == 0
    assert result["projected_value"] is None

    # Empty list
    result_empty = analyze_trend(station_id=1, parameter="ph", recent_values=[])
    assert result_empty["trend_direction"] == "stable"
    assert result_empty["trend_risk_score"] == 0
