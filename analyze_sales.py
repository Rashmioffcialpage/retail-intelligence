from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

df = pd.read_csv(
    ROOT / "data/processed/transactions_prepared.csv",
    dtype={
        "InvoiceNo": "string",
        "StockCode": "string",
        "CustomerID": "string",
    },
    parse_dates=["InvoiceDate"],
)

# Retain flagged repeats until we establish a deduplication policy.
sales = df.loc[df["transaction_type"].eq("sale")].copy()
credits = df.loc[
    df["transaction_type"].eq("credit_or_adjustment")
].copy()

sales["month"] = sales["InvoiceDate"].dt.to_period("M").astype(str)

monthly = sales.groupby("month").agg(
    sales_value_gbp=("line_value_gbp", "sum"),
    invoices=("InvoiceNo", "nunique"),
    identified_customers=("CustomerID", "nunique"),
    units=("Quantity", "sum"),
)

credit_months = credits["InvoiceDate"].dt.to_period("M").astype(str)
monthly["credit_value_gbp"] = (
    credits.groupby(credit_months)["line_value_gbp"]
    .sum()
    .reindex(monthly.index, fill_value=0)
)
monthly["net_transaction_value_gbp"] = (
    monthly["sales_value_gbp"] + monthly["credit_value_gbp"]
)

countries = (
    sales.groupby("Country")
    .agg(
        sales_value_gbp=("line_value_gbp", "sum"),
        invoices=("InvoiceNo", "nunique"),
    )
    .sort_values("sales_value_gbp", ascending=False)
)

products = (
    sales.groupby("StockCode")
    .agg(
        description=("Description", "first"),
        units=("Quantity", "sum"),
        sales_value_gbp=("line_value_gbp", "sum"),
    )
    .sort_values("sales_value_gbp", ascending=False)
)

monthly.round(2).to_csv(REPORTS / "monthly_sales.csv")
countries.round(2).to_csv(REPORTS / "sales_by_country.csv")
products.round(2).to_csv(REPORTS / "sales_by_product.csv")

print("\nDATA COVERAGE")
print(sales["InvoiceDate"].min(), "to", sales["InvoiceDate"].max())

print("\nMONTHLY PERFORMANCE")
print(monthly.round(2).to_string())

print("\nTOP 5 COUNTRIES BY SALES VALUE")
print(countries.head(5).round(2).to_string())

print("\nTOP 5 PRODUCT CODES BY SALES VALUE")
print(products.head(5).round(2).to_string())

print("\nSaved three CSV reports in reports/")