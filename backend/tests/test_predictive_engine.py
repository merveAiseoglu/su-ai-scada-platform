import pytest
from app.predictive_engine import analyze_trend

def test_analyze_trend_rising():
    # Clearly rising values
    # e.g., 7.0, 7.2, 7.5, 7.8, 8.1
    recent_values = [7.0 + (i * 0.3) for i in range(10)]
    result = analyze_trend(station_id=1, parameter="ph", recent_values=recent_values)
    
    assert result["trend_direction"] == "rising"
    assert result["trend_risk_score"] >= 50
    assert result["projected_value"] is not None
    assert "keskin bir yükseliş trendinde" in result["projection_message"]

def test_analyze_trend_stable():
    # Flat/stable values
    # e.g., 7.2, 7.21, 7.19, 7.2
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
    # The function should catch exceptions and return safe defaults.
    recent_values = [None, "bad_value", 7.2]
    result = analyze_trend(station_id=1, parameter="ph", recent_values=recent_values)
    
    # Depending on how it fails (value error on float cast), it returns safe defaults
    assert result["trend_direction"] == "stable"
    assert result["trend_risk_score"] == 0
    assert result["projected_value"] is None
    
    # Another test for empty list
    result_empty = analyze_trend(station_id=1, parameter="ph", recent_values=[])
    assert result_empty["trend_direction"] == "stable"
    assert result_empty["trend_risk_score"] == 0
