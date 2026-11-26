from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data/retail.db"
SOURCE = ROOT / "data/processed/transactions_prepared.csv"

if not SOURCE.exists() or not DATABASE.exists():
    raise SystemExit(
        "Run prepare_data.py and build_database.py first."
    )

csv_data = pd.read_csv(SOURCE)

with sqlite3.connect(
    f"{DATABASE.as_uri()}?mode=ro", uri=True
) as connection:
    database_data = pd.read_sql_query(
        """
        SELECT source_row, transaction_type, line_value_gbp
        FROM transactions
        """,
        connection,
    )

checks = {
    "CSV and database row counts match":
        len(csv_data) == len(database_data),

    "Database source rows are populated and unique":
        database_data["source_row"].notna().all()
        and database_data["source_row"].is_unique,

    "CSV and database contain the same source rows":
        set(csv_data["source_row"])
        == set(database_data["source_row"]),
}

# Compare each transaction by its original source row.
if checks["Database source rows are populated and unique"]:
    comparison = csv_data[
        ["source_row", "transaction_type", "line_value_gbp"]
    ].merge(
        database_data,
        on="source_row",
        how="outer",
        suffixes=("_csv", "_db"),
        validate="one_to_one",
    )

    checks["Transaction classifications match"] = (
        comparison["transaction_type_csv"]
        .eq(comparison["transaction_type_db"])
        .all()
    )

    csv_values = comparison["line_value_gbp_csv"]
    db_values = comparison["line_value_gbp_db"]

    checks["Transaction values match within floating-point tolerance"] = (
        (csv_values - db_values).abs().le(0.000001)
        | (csv_values.isna() & db_values.isna())
    ).all()

print("\nPIPELINE VALIDATION")

for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL'} — {name}")

if not all(checks.values()):
    raise SystemExit("\nValidation failed. Review the checks above.")

print(f"\nAll checks passed for {len(database_data):,} transactions.")