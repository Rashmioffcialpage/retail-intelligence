from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data/retail.db"

if not DATABASE.exists():
    raise SystemExit("Run python build_database.py first.")

with sqlite3.connect(DATABASE) as connection:
    connection.execute("BEGIN")

    try:
        # Rebuild only these generated warehouse tables.
        for table in [
            "fact_transactions",
            "dim_product",
            "dim_customer",
            "dim_date",
        ]:
            connection.execute(f"DROP TABLE IF EXISTS {table}")

        connection.execute("""
            CREATE TABLE dim_product (
                stock_code TEXT PRIMARY KEY
            )
        """)

        connection.execute("""
            INSERT INTO dim_product (stock_code)
            SELECT DISTINCT StockCode
            FROM transactions
            WHERE StockCode IS NOT NULL
        """)

        # Keep descriptions on the fact table because a code can
        # have different descriptions across source transactions.
        connection.execute("""
            CREATE TABLE dim_customer (
                customer_id TEXT PRIMARY KEY
            )
        """)

        connection.execute("""
            INSERT INTO dim_customer (customer_id)
            SELECT DISTINCT CustomerID
            FROM transactions
            WHERE CustomerID IS NOT NULL
              AND TRIM(CustomerID) <> ''
        """)

        connection.execute("""
            CREATE TABLE dim_date (
                date_key TEXT PRIMARY KEY,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                weekday_number INTEGER
            )
        """)

        connection.execute("""
            WITH RECURSIVE calendar(date_key) AS (
                SELECT DATE(MIN(InvoiceDate))
                FROM transactions

                UNION ALL

                SELECT DATE(date_key, '+1 day')
                FROM calendar
                WHERE date_key < (
                    SELECT DATE(MAX(InvoiceDate))
                    FROM transactions
                )
            )
            INSERT INTO dim_date
            SELECT
                date_key,
                CAST(STRFTIME('%Y', date_key) AS INTEGER),
                CAST(STRFTIME('%m', date_key) AS INTEGER),
                CAST(STRFTIME('%d', date_key) AS INTEGER),
                CAST(STRFTIME('%w', date_key) AS INTEGER)
            FROM calendar
        """)

        connection.execute("""
            CREATE TABLE fact_transactions AS
            SELECT
                source_row AS transaction_id,
                InvoiceNo AS invoice_no,
                StockCode AS stock_code,
                NULLIF(TRIM(CustomerID), '') AS customer_id,
                DATE(InvoiceDate) AS date_key,
                InvoiceDate AS invoice_timestamp,
                Description AS source_description,
                Country AS transaction_country,
                Quantity AS quantity,
                UnitPrice AS unit_price_gbp,
                line_value_gbp,
                transaction_type,
                is_repeated_row
            FROM transactions
        """)

        connection.execute("""
            CREATE UNIQUE INDEX idx_fact_transaction
            ON fact_transactions (transaction_id)
        """)

        connection.execute("""
            CREATE INDEX idx_fact_date
            ON fact_transactions (date_key)
        """)

        source_count = connection.execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]

        fact_count = connection.execute(
            "SELECT COUNT(*) FROM fact_transactions"
        ).fetchone()[0]

        if source_count != fact_count:
            raise ValueError("Source and fact row counts differ.")

        missing_links = connection.execute("""
            SELECT COUNT(*)
            FROM fact_transactions AS f
            LEFT JOIN dim_product AS p
                ON f.stock_code = p.stock_code
            LEFT JOIN dim_customer AS c
                ON f.customer_id = c.customer_id
            LEFT JOIN dim_date AS d
                ON f.date_key = d.date_key
            WHERE p.stock_code IS NULL
               OR d.date_key IS NULL
               OR (
                   f.customer_id IS NOT NULL
                   AND c.customer_id IS NULL
               )
        """).fetchone()[0]

        if missing_links:
            raise ValueError(
                f"{missing_links} transactions have missing dimension links."
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    print("\nWAREHOUSE BUILT")

    for table in [
        "dim_product",
        "dim_customer",
        "dim_date",
        "fact_transactions",
    ]:
        count = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        print(f"{table}: {count:,} rows")

    print("\nPASS — Source and fact row counts match")
    print("PASS — All required dimension links exist")