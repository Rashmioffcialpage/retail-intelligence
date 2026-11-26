from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data/retail.db"
REPORTS = ROOT / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

if not DATABASE.exists():
    raise SystemExit("Run python build_database.py first.")

with sqlite3.connect(
    f"{DATABASE.as_uri()}?mode=ro",
    uri=True,
) as connection:
    data = pd.read_sql_query(
        """
        SELECT InvoiceDate, transaction_type, line_value_gbp
        FROM transactions
        """,
        connection,
        parse_dates=["InvoiceDate"],
    )

if data.empty:
    raise SystemExit("The database contains no transactions.")

if data["InvoiceDate"].isna().any():
    raise SystemExit("Missing or invalid transaction dates found.")

# Overall source coverage determines complete boundary weeks.
coverage_start = pd.Timestamp(data["InvoiceDate"].min()).normalize()
coverage_end = pd.Timestamp(data["InvoiceDate"].max()).normalize()

sales = data.loc[
    data["transaction_type"].eq("sale")
].copy()

if sales.empty:
    raise SystemExit("No sales transactions found.")

# Days without recorded sales are treated as zero.
daily = (
    sales.set_index("InvoiceDate")["line_value_gbp"]
    .resample("D")
    .sum()
    .reindex(
        pd.date_range(
            coverage_start,
            coverage_end,
            freq="D",
        ),
        fill_value=0,
    )
)

# Monday–Sunday weeks, labeled by their ending Sunday.
weekly_all = daily.resample("W-SUN").sum()

week_ends = pd.DatetimeIndex(weekly_all.index)
week_starts = week_ends - pd.Timedelta(days=6)

# Filter once, using arrays of matching lengths.
complete_weeks = (
    (week_starts >= coverage_start)
    & (week_ends <= coverage_end)
)

weekly = weekly_all.loc[complete_weeks].copy()

if len(weekly) < 16:
    raise SystemExit(
        "Not enough complete weeks for evaluation. "
        "At least 16 are required."
    )

test_weeks = 8
rows = []

# Rolling one-week-ahead evaluation:
# each prediction uses only previously observed weeks.
for position in range(len(weekly) - test_weeks, len(weekly)):
    history = weekly.iloc[:position]

    rows.append({
        "week_ending": weekly.index[position],
        "actual_sales_gbp": float(weekly.iloc[position]),
        "previous_week_gbp": float(history.iloc[-1]),
        "four_week_average_gbp": float(history.iloc[-4:].mean()),
    })

results = pd.DataFrame(rows)

actual = results["actual_sales_gbp"]
actual_total = float(actual.abs().sum())
metric_rows = []

for column, name in [
    ("previous_week_gbp", "Previous week baseline"),
    ("four_week_average_gbp", "Four-week average"),
]:
    errors = actual - results[column]

    metric_rows.append({
        "method": name,
        "mae_gbp": float(errors.abs().mean()),
        "rmse_gbp": float(errors.pow(2).mean() ** 0.5),
        "wape_percent": (
            float(errors.abs().sum() / actual_total * 100)
            if actual_total > 0
            else None
        ),
    })

metrics = pd.DataFrame(metric_rows)

results.to_csv(
    REPORTS / "forecast_evaluation.csv",
    index=False,
)

metrics.to_csv(
    REPORTS / "forecast_metrics.csv",
    index=False,
)

print("\nFORECAST EVALUATION")
print(f"Complete weeks available: {len(weekly)}")
print(f"Test weeks: {test_weeks}")
print("Protocol: rolling one-week-ahead evaluation")
print("\n" + metrics.round(2).to_string(index=False))
print("\nSaved forecast_evaluation.csv and forecast_metrics.csv")