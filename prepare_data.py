from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data/raw/Online Retail.xlsx"
OUTPUT = ROOT / "data/processed"
REPORTS = ROOT / "reports"

OUTPUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

print("Reading transactions...")
df = pd.read_excel(
    SOURCE,
    dtype={
        "InvoiceNo": "string",
        "StockCode": "string",
        "CustomerID": "string",
    },
)

report = {
    "source_rows": len(df),
    "missing_values": {
        column: int(count)
        for column, count in df.isna().sum().items()
    },
    "repeated_rows_after_first": int(df.duplicated().sum()),
    "negative_quantity_rows": int(df["Quantity"].lt(0).sum()),
    "zero_or_negative_price_rows": int(df["UnitPrice"].le(0).sum()),
}

# Preserve every source row; repeated rows are flagged for review.
df.insert(0, "source_row", range(2, len(df) + 2))
df["is_repeated_row"] = df.drop(columns="source_row").duplicated()

df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
df["is_cancellation"] = df["InvoiceNo"].str.upper().str.startswith(
    "C", na=False
)
df["is_negative_quantity"] = df["Quantity"].lt(0)
df["has_customer_id"] = df["CustomerID"].notna()

# These are analysis rules, rather than claims about every transaction.
valid = (
    df["InvoiceNo"].notna()
    & df["StockCode"].notna()
    & df["InvoiceDate"].notna()
    & df["Quantity"].notna()
    & df["UnitPrice"].gt(0)
)

sales = valid & df["Quantity"].gt(0) & ~df["is_cancellation"]
credits = valid & df["Quantity"].lt(0)

df["transaction_type"] = "review"
df.loc[sales, "transaction_type"] = "sale"
df.loc[credits, "transaction_type"] = "credit_or_adjustment"

df["line_value_gbp"] = (df["Quantity"] * df["UnitPrice"]).round(2)

report["transaction_types"] = {
    str(label): int(count)
    for label, count in df["transaction_type"].value_counts().items()
}

df.to_csv(OUTPUT / "transactions_prepared.csv", index=False)
df.loc[df["transaction_type"].eq("review")].to_csv(
    OUTPUT / "transactions_for_review.csv", index=False
)

with (REPORTS / "data_quality.json").open("w") as file:
    json.dump(report, file, indent=2)

print(json.dumps(report, indent=2))
print("\nSaved prepared transactions and data-quality report.")