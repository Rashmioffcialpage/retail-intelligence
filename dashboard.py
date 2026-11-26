from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data/retail.db"

st.set_page_config(
    page_title="Retail Intelligence",
    page_icon="📊",
    layout="wide",
)

st.title("Retail Intelligence")
st.caption("Transaction analysis · UCI Online Retail · SQLite · GBP")


@st.cache_data
def load_data(database_modified: int) -> pd.DataFrame:
    # The modification time refreshes the cache after a database rebuild.
    with sqlite3.connect(
        f"{DATABASE.as_uri()}?mode=ro",
        uri=True,
    ) as connection:
        data = pd.read_sql_query(
            "SELECT * FROM transactions",
            connection,
            parse_dates=["InvoiceDate"],
        )

    for column in ["InvoiceNo", "StockCode", "CustomerID"]:
        data[column] = data[column].astype("string")

    # SQLite may store Boolean values as integers.
    data["is_repeated_row"] = (
        data["is_repeated_row"]
        .astype("string")
        .str.lower()
        .isin(["true", "1", "1.0"])
    )

    return data


if not DATABASE.exists():
    st.error("Database missing. Run: python build_database.py")
    st.stop()

try:
    df = load_data(DATABASE.stat().st_mtime_ns)
except (sqlite3.Error, pd.errors.DatabaseError) as error:
    st.error("Could not read the database. Run: python build_database.py")
    st.code(str(error))
    st.stop()

st.sidebar.header("Filters")

countries = st.sidebar.multiselect(
    "Countries",
    sorted(df["Country"].dropna().unique().tolist()),
    default=sorted(df["Country"].dropna().unique().tolist()),
)

exclude_repeats = st.sidebar.checkbox(
    "Exclude flagged repeated rows",
    value=False,
)

st.sidebar.caption("Data source: local SQLite database")

if not countries:
    st.info("Select at least one country.")
    st.stop()

filtered = df.loc[df["Country"].isin(countries)].copy()

if exclude_repeats:
    filtered = filtered.loc[~filtered["is_repeated_row"]].copy()

sales = filtered.loc[
    filtered["transaction_type"].eq("sale")
].copy()

credits = filtered.loc[
    filtered["transaction_type"].eq("credit_or_adjustment")
].copy()

gross = sales["line_value_gbp"].sum()
credit_value = credits["line_value_gbp"].sum()
invoice_count = sales["InvoiceNo"].nunique()

a, b, c, d = st.columns(4)
a.metric("Sales value", f"£{gross:,.0f}")
b.metric("Credits / adjustments", f"£{credit_value:,.0f}")
c.metric("Net transaction value", f"£{gross + credit_value:,.0f}")
d.metric("Sales invoices", f"{invoice_count:,}")

st.warning(
    "December 2011 is partial: source coverage ends December 9. "
    "Net transaction value is not profit. "
    "Sales include service codes such as postage."
)

sales["month"] = (
    sales["InvoiceDate"].dt.to_period("M").astype(str)
)

monthly = (
    sales.groupby("month")["line_value_gbp"]
    .sum()
    .reset_index(name="sales_value_gbp")
    .sort_values("month")
)

st.plotly_chart(
    px.bar(
        monthly,
        x="month",
        y="sales_value_gbp",
        title="Monthly sales value",
        labels={
            "month": "Month",
            "sales_value_gbp": "Sales value (£)",
        },
        color_discrete_sequence=["#2563EB"],
    ),
    use_container_width=True,
)

country_sales = (
    sales.groupby("Country")["line_value_gbp"]
    .sum()
    .reset_index(name="sales_value_gbp")
    .sort_values("sales_value_gbp", ascending=False)
    .head(10)
)

product_sales = (
    sales.groupby("StockCode", as_index=False)
    .agg(
        description=("Description", "first"),
        sales_value_gbp=("line_value_gbp", "sum"),
    )
    .sort_values("sales_value_gbp", ascending=False)
    .head(10)
)

left, right = st.columns(2)

with left:
    st.subheader("Sales by country")
    st.dataframe(
        country_sales,
        hide_index=True,
        use_container_width=True,
    )

with right:
    st.subheader("Top product and service codes")
    st.dataframe(
        product_sales,
        hide_index=True,
        use_container_width=True,
    )

st.caption(
    "Missing customer IDs remain included in transaction totals. "
    "Repeated rows are retained unless the sidebar option is selected; "
    "that option is a sensitivity check, not a confirmed correction."
)

st.download_button(
    "Download monthly sales",
    data=monthly.to_csv(index=False).encode("utf-8"),
    file_name="monthly_sales.csv",
    mime="text/csv",
)