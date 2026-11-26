from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data/retail.db"

if not DATABASE.exists():
    raise SystemExit("Run python run_pipeline.py first.")

with sqlite3.connect(
    f"{DATABASE.as_uri()}?mode=ro",
    uri=True,
) as connection:
    source = pd.read_sql_query(
        """
        SELECT
            STRFTIME('%Y-%m', InvoiceDate) AS month,
            COUNT(DISTINCT InvoiceNo) AS invoices,
            COUNT(DISTINCT CustomerID) AS customers,
            SUM(line_value_gbp) AS sales_value
        FROM transactions
        WHERE transaction_type = 'sale'
        GROUP BY month
        ORDER BY month
        """,
        connection,
    )

    warehouse = pd.read_sql_query(
        """
        SELECT
            PRINTF('%04d-%02d', d.year, d.month) AS month,
            COUNT(DISTINCT f.invoice_no) AS invoices,
            COUNT(DISTINCT f.customer_id) AS customers,
            SUM(f.line_value_gbp) AS sales_value
        FROM fact_transactions AS f
        JOIN dim_date AS d ON f.date_key = d.date_key
        WHERE f.transaction_type = 'sale'
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month
        """,
        connection,
    )

comparison = source.merge(
    warehouse,
    on="month",
    how="outer",
    suffixes=("_source", "_warehouse"),
    indicator=True,
    validate="one_to_one",
)

checks = {
    "Same months in source and warehouse":
        comparison["_merge"].eq("both").all(),

    "Monthly invoice counts match":
        comparison["invoices_source"]
        .eq(comparison["invoices_warehouse"]).all(),

    "Monthly identified customer counts match":
        comparison["customers_source"]
        .eq(comparison["customers_warehouse"]).all(),

    "Monthly sales values match within £0.01":
        (
            comparison["sales_value_source"]
            - comparison["sales_value_warehouse"]
        ).abs().le(0.01).all(),

    "Source contains sales months":
        not source.empty,
}

print("\nWAREHOUSE RECONCILIATION")

for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL'} — {name}")

if not all(checks.values()):
    raise SystemExit("\nWarehouse reconciliation failed.")

print(f"\nAll checks passed across {len(source)} months.")