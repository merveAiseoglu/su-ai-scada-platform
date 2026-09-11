import logging
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)


class TrendResult(TypedDict):
    trend_risk_score: int
    trend_direction: Literal["rising", "falling", "stable"]
    projected_value: float | None
    projection_message: str


# Fiziksel sınırlar: (min, max) — None = o yönde sınır yok.
# sicaklik fiziksel olarak negatif olabilir (donma altı) → her iki yönde de sınır yok.
_PARAM_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "bulaniklik": (0.0, None),  # NTU: negatif olamaz
    "serbest_klor": (0.0, None),  # mg/L: negatif olamaz
    "iletkenlik": (0.0, None),  # µS/cm: negatif olamaz
    "sicaklik": (None, None),  # °C: donma altı fiziksel olarak geçerli
    "ph": (0.0, 14.0),  # pH ölçeği: 0–14
}


def _apply_physical_bounds(
    parameter: str,
    value: float,
    station_id: int,
) -> tuple[float, bool]:
    """
    Clips *value* to the physical bounds defined for *parameter*.
    Returns (clipped_value, was_clipped).
    """
    bounds = _PARAM_BOUNDS.get(parameter.lower())
    if bounds is None:
        return value, False

    lo, hi = bounds
    original = value
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi

    clipped = value != original
    if clipped:
        logger.debug(
            "analyze_trend: projected_value clipped %.4f → %.4f " "(param=%s, station=%d)",
            original,
            value,
            parameter,
            station_id,
        )
    return value, clipped


def analyze_trend(station_id: int, parameter: str, recent_values: list[float]) -> TrendResult:
    """
    Analyzes the trend of a given parameter based on recent measurements.
    Uses Holt's Linear Exponential Smoothing to predict the next value with trend and basic linear regression for the slope.
    """
    try:
        import numpy as np
        import pandas as pd
        from statsmodels.tsa.holtwinters import Holt
    except ImportError:
        logger.warning("statsmodels/pandas/numpy not installed. Returning safe defaults.")
        return {
            "trend_risk_score": 0,
            "trend_direction": "stable",
            "projected_value": None,
            "projection_message": "Analiz için gerekli kütüphaneler eksik.",
        }

    default_result: TrendResult = {
        "trend_risk_score": 0,
        "trend_direction": "stable",
        "projected_value": None,
        "projection_message": "Yeterli veri yok veya stabil.",
    }

    try:
        data = [float(v) for v in recent_values if v is not None]
        if len(data) < 3:
            return default_result

        # Predict next value using Holt's Linear Trend method
        series = pd.Series(data)
        model = Holt(series, initialization_method="estimated")
        fit_model = model.fit()
        forecast = fit_model.forecast(1)
        projected_value = float(forecast.iloc[0])

        # Determine trend direction using linear regression slope
        x = np.arange(len(data))
        y = np.array(data)
        slope, _ = np.polyfit(x, y, 1)

        trend_direction: Literal["rising", "falling", "stable"] = "stable"
        if slope > 0.05:
            trend_direction = "rising"
        elif slope < -0.05:
            trend_direction = "falling"

        # Calculate risk score (0-100) based on slope magnitude
        # Arbitrary multiplier to map typical slopes (0.05 - 0.3) to 0-100 score
        trend_risk_score = 0
        if trend_direction != "stable":
            risk = min(int(abs(slope) * 300), 100)
            trend_risk_score = risk

        # Fiziksel sınır clipping — modelin fiziksel olarak imkânsız değer
        # üretmesini engelle. Risk skoru ve trend yönü clip'ten ÖNCE hesaplandığı
        # için bunlar etkilenmez.
        projected_value, clipped = _apply_physical_bounds(parameter, projected_value, station_id)

        # Projection message in Turkish
        param_names = {
            "ph": "pH",
            "serbest_klor": "Serbest Klor",
            "bulaniklik": "Bulanıklık",
            "iletkenlik": "İletkenlik",
        }
        tr_param = param_names.get(parameter.lower(), parameter)

        if trend_risk_score >= 60:
            if trend_direction == "rising":
                msg = f"{tr_param} değeri keskin bir yükseliş trendinde, bir sonraki ölçümde {projected_value:.2f} seviyesine ulaşması bekleniyor."
            else:
                if clipped:
                    msg = f"{tr_param} değeri keskin bir düşüş trendinde, bir sonraki ölçümde {projected_value:.2f} seviyesine (fiziksel alt sınıra) yaklaşması bekleniyor."
                else:
                    msg = f"{tr_param} değeri keskin bir düşüş trendinde, bir sonraki ölçümde {projected_value:.2f} seviyesine düşmesi bekleniyor."
        else:
            msg = f"{tr_param} değeri genel olarak stabil veya yavaş bir değişim gösteriyor. Beklenen değer: {projected_value:.2f}."

        return {
            "trend_risk_score": trend_risk_score,
            "trend_direction": trend_direction,
            "projected_value": projected_value,
            "projection_message": msg,
        }
    except Exception as e:
        logger.error(f"Error in analyze_trend for station {station_id}, param {parameter}: {e}")
        return default_result
