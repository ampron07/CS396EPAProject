"""Small, inspectable CO2 trend forecast for a single EPA facility.

Only historical calendar dates are used as predictors. This avoids requiring
unknown future gross load/heat input. Scenario scaling is a separate assumption.
"""
from datetime import date, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression

MIN_DAYS = 45


def _features(dates, origin):
    """Time trend and day-of-week indicators; no future-known operational data."""
    return np.array([
        [(day - origin).days] + [float(day.weekday() == weekday) for weekday in range(6)]
        for day in dates
    ], dtype=float)


def make_forecast(rows, horizon=30):
    """rows: iterable of (YYYY-MM-DD, CO2 short tons) daily aggregates.

    Returns chart-ready JSON-compatible data and chronological test metrics.
    Invalid or missing observations are not interpreted as zero emissions.
    """
    if horizon not in (7, 30, 90):
        raise ValueError("Forecast horizon must be 7, 30, or 90 days.")
    values_by_date = {}
    for raw_date, mass in rows:
        try:
            day = date.fromisoformat(str(raw_date))
            mass = float(mass)
        except (TypeError, ValueError):
            continue
        if np.isfinite(mass) and mass >= 0:
            values_by_date[day] = mass

    ordered = sorted(values_by_date.items())
    if len(ordered) < MIN_DAYS:
        raise ValueError(f"At least {MIN_DAYS} dated CO₂ observations are required (found {len(ordered)}).")
    days = [item[0] for item in ordered]
    y = np.array([item[1] for item in ordered], dtype=float)
    span = (days[-1] - days[0]).days + 1
    coverage = len(days) / span
    if coverage < 0.75:
        raise ValueError("Too many missing calendar dates for a reliable daily trend (less than 75% coverage).")
    if np.all(y == y[0]):
        raise ValueError("Emissions do not vary enough to evaluate a trend model.")

    origin = days[0]
    X = _features(days, origin)
    split = int(len(y) * 0.8)
    model = LinearRegression().fit(X[:split], y[:split])
    test_pred = np.maximum(0, model.predict(X[split:]))
    actual_test = y[split:]
    mae = float(np.mean(np.abs(actual_test - test_pred)))
    rmse = float(np.sqrt(np.mean((actual_test - test_pred) ** 2)))
    # A simple constant-mean baseline for interpreting regression performance.
    baseline_mae = float(np.mean(np.abs(actual_test - y[:split].mean())))

    model.fit(X, y)
    future_days = [days[-1] + timedelta(days=i) for i in range(1, horizon + 1)]
    future_values = np.maximum(0, model.predict(_features(future_days, origin)))

    historical = [{"date": day.isoformat(), "co2": round(value, 3)}
                  for day, value in ordered[-min(len(ordered), 90):]]
    forecast = [{"date": day.isoformat(), "co2": round(float(value), 3)}
                for day, value in zip(future_days, future_values)]
    holdout = [{"date": day.isoformat(), "actual": round(float(actual), 3),
                "predicted": round(float(pred), 3)}
               for day, actual, pred in zip(days[split:], actual_test, test_pred)]
    notes = []
    if horizon == 90 and span < 365:
        notes.append("A 90-day forecast from less than a year of data is especially uncertain.")
    if mae >= baseline_mae:
        notes.append("The regression did not beat a constant historical-mean baseline on held-out dates.")
    return {
        "historical": historical, "forecast": forecast, "holdout": holdout,
        "mae": round(mae, 2), "rmse": round(rmse, 2),
        "baseline_mae": round(baseline_mae, 2),
        "train_days": split, "test_days": len(y) - split,
        "observations": len(y), "coverage": round(coverage * 100, 1),
        "start_date": days[0].isoformat(), "last_date": days[-1].isoformat(),
        "notes": notes,
    }
