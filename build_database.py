from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data/retail.db"

df = pd.read_csv(
    ROOT / "data/processed/transactions_prepared.csv",
    dtype={
        "InvoiceNo": "string",
        "StockCode": "string",
        "CustomerID": "string",
    },
)

with sqlite3.connect(DB_PATH) as connection:
    # Replaces the table on each run to prevent duplicate loads.
    df.to_sql(
        "transactions",
        connection,
        if_exists="replace",
        index=False,
        chunksize=10000,
    )

    connection.execute(
        "CREATE INDEX idx_invoice_date "
        "ON transactions (InvoiceDate)"
    )

    query = """
        SELECT
            Country AS country,
            COUNT(DISTINCT InvoiceNo) AS sales_invoices,
            ROUND(SUM(line_value_gbp), 2) AS sales_value_gbp
        FROM transactions
        WHERE transaction_type = 'sale'
        GROUP BY Country
        ORDER BY sales_value_gbp DESC
        LIMIT 10
    """

    result = pd.read_sql_query(query, connection)

print(f"Loaded {len(df):,} rows into {DB_PATH.name}")
print("\nTOP COUNTRIES — SQL RESULTS")
print(result.to_string(index=False))