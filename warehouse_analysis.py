from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data/retail.db"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

if not DATABASE.exists():
    raise SystemExit("Run build_database.py and build_warehouse.py first.")

with sqlite3.connect(
    f"{DATABASE.as_uri()}?mode=ro",
    uri=True,
) as connection:
    monthly = pd.read_sql_query(
        """
        SELECT
            d.year,
            d.month,
            COUNT(DISTINCT f.invoice_no) AS sales_invoices,
            COUNT(DISTINCT f.customer_id) AS identified_customers,
            ROUND(SUM(f.line_value_gbp), 2) AS sales_value_gbp
        FROM fact_transactions AS f
        JOIN dim_date AS d
            ON f.date_key = d.date_key
        WHERE f.transaction_type = 'sale'
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month
        """,
        connection,
    )

monthly.to_csv(
    REPORTS / "warehouse_monthly_sales.csv",
    index=False,
)

print("\nMONTHLY SALES — WAREHOUSE QUERY")
print(monthly.to_string(index=False))
print("\nSaved warehouse_monthly_sales.csv")