import pytest
from app.predictive_engine import analyze_trend, _apply_physical_bounds


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
    # (pH stays well within 0–14 here so clipping does not fire)
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


# ---------------------------------------------------------------------------
# Fiziksel sınır (clipping) testleri
# ---------------------------------------------------------------------------

def test_analyze_trend_negative_clip_bulaniklik():
    """
    Keskin düşüş trendindeki bir bulanıklık serisi için projected_value
    asla negatif olmamalıdır (NTU fiziksel olarak negatif olamaz).
    """
    # 2.0, 1.6, 1.2, 0.8, 0.4, 0.0 → Holt modeli negatif tahmin üretebilir
    recent_values = [2.0 - i * 0.4 for i in range(10)]  # son değer: -1.6
    result = analyze_trend(station_id=5, parameter="bulaniklik", recent_values=recent_values)

    assert result["projected_value"] is not None
    assert result["projected_value"] >= 0.0, (
        f"projected_value negatif olmamalı, elde edilen: {result['projected_value']}"
    )
    # Trend düşüş yönünde olmaya devam etmeli
    assert result["trend_direction"] == "falling"
    # Mesaj negatif bir sayı içermemeli
    pv_str = f"{result['projected_value']:.2f}"
    assert not pv_str.startswith("-"), (
        f"projection_message'da negatif değer var: {result['projection_message']}"
    )


def test_analyze_trend_negative_clip_serbest_klor():
    """
    Keskin düşüş trendindeki bir serbest_klor serisi için projected_value
    asla negatif olmamalıdır (mg/L fiziksel olarak negatif olamaz).
    """
    recent_values = [1.5 - i * 0.25 for i in range(10)]  # düşer, sona doğru negatif
    result = analyze_trend(station_id=3, parameter="serbest_klor", recent_values=recent_values)

    assert result["projected_value"] is not None
    assert result["projected_value"] >= 0.0, (
        f"projected_value negatif olmamalı, elde edilen: {result['projected_value']}"
    )


def test_analyze_trend_ph_upper_clip():
    """
    pH için projected_value asla 14'ü geçmemelidir.
    Keskin yükseliş trendinde Holt modeli 14+ tahmin üretebilir.
    """
    # 10.0, 10.5, 11.0, ... → Holt 14'ü aşabilir
    recent_values = [10.0 + i * 0.5 for i in range(10)]  # son değer: 14.5
    result = analyze_trend(station_id=2, parameter="ph", recent_values=recent_values)

    assert result["projected_value"] is not None
    assert result["projected_value"] <= 14.0, (
        f"pH 14'ü geçmemeli, elde edilen: {result['projected_value']}"
    )
    assert result["projected_value"] >= 0.0


def test_analyze_trend_sicaklik_allows_negative():
    """
    Sıcaklık (°C) fiziksel olarak negatif olabilir (buz noktası altı).
    Düşüş trendinde projected_value negatif kalabilmelidir — clipping OLMAMALI.
    """
    # 5.0, 4.0, 3.0, 2.0, 1.0, 0.0, -1.0, -2.0, -3.0, -4.0
    recent_values = [5.0 - i * 1.0 for i in range(10)]
    result = analyze_trend(station_id=4, parameter="sicaklik", recent_values=recent_values)

    assert result["projected_value"] is not None
    # Holt doğrusal trend → sonraki değer son değerden (−4) daha düşük, yani negatif
    assert result["projected_value"] < 0.0, (
        f"Sıcaklık negatif olabilmeli, elde edilen: {result['projected_value']}"
    )
    assert result["trend_direction"] == "falling"


def test_apply_physical_bounds_unit():
    """_apply_physical_bounds yardımcı fonksiyonunu doğrudan test eder."""
    # bulaniklik: negatif → 0'a clip edilmeli
    val, clipped = _apply_physical_bounds("bulaniklik", -0.24, station_id=1)
    assert val == 0.0
    assert clipped is True

    # ph: 14.8 → 14'e clip edilmeli
    val, clipped = _apply_physical_bounds("ph", 14.8, station_id=1)
    assert val == 14.0
    assert clipped is True

    # ph: -0.1 → 0'a clip edilmeli
    val, clipped = _apply_physical_bounds("ph", -0.1, station_id=1)
    assert val == 0.0
    assert clipped is True

    # sicaklik: -5.0 → sınır yok, olduğu gibi dönmeli
    val, clipped = _apply_physical_bounds("sicaklik", -5.0, station_id=1)
    assert val == -5.0
    assert clipped is False

    # bilinmeyen parametre: sınır uygulanmaz
    val, clipped = _apply_physical_bounds("bilinmeyen", -999.0, station_id=1)
    assert val == -999.0
    assert clipped is False
