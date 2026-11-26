from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data/retail.db"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

if not DATABASE.exists():
    raise SystemExit("Run python build_database.py first.")

with sqlite3.connect(
    f"{DATABASE.as_uri()}?mode=ro", uri=True
) as connection:
    sales = pd.read_sql_query(
        """
        SELECT CustomerID, InvoiceNo, InvoiceDate, line_value_gbp
        FROM transactions
        WHERE transaction_type = 'sale'
          AND CustomerID IS NOT NULL
          AND TRIM(CustomerID) <> ''
        """,
        connection,
        parse_dates=["InvoiceDate"],
    )

if sales.empty:
    raise SystemExit("No identified customer sales found.")

# Use the dataset's end date, rather than today's date.
snapshot = sales["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)

customers = (
    sales.groupby("CustomerID")
    .agg(
        last_purchase=("InvoiceDate", "max"),
        order_count=("InvoiceNo", "nunique"),
        sales_value_gbp=("line_value_gbp", "sum"),
    )
    .reset_index()
)

customers["recency_days"] = (
    snapshot - customers["last_purchase"].dt.normalize()
).dt.days

customers["average_order_value_gbp"] = (
    customers["sales_value_gbp"] / customers["order_count"]
)

customers = customers.sort_values(
    "sales_value_gbp", ascending=False
)

output = REPORTS / "customer_rfm.csv"
customers.to_csv(output, index=False)

repeat_buyers = customers["order_count"].gt(1).mean() * 100

print(f"Snapshot date: {snapshot.date()}")
print(f"Identified customers: {len(customers):,}")
print(f"Customers with multiple sales invoices: {repeat_buyers:.1f}%")
print("\nTOP 10 CUSTOMERS BY SALES VALUE")
print(
    customers.head(10).round({
        "sales_value_gbp": 2,
        "average_order_value_gbp": 2,
    }).to_string(index=False)
)
print(f"\nSaved: {output.name}")