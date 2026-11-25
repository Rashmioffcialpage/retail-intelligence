from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Retail Intelligence",
    page_icon="📊",
    layout="wide",
)

st.title("Retail Intelligence")
st.caption("Transaction analysis · UCI Online Retail · GBP")

@st.cache_data
def load_data():
    return pd.read_csv(
        ROOT / "data/processed/transactions_prepared.csv",
        dtype={
            "InvoiceNo": "string",
            "StockCode": "string",
            "CustomerID": "string",
        },
        parse_dates=["InvoiceDate"],
    )

df = load_data()

st.sidebar.header("Filters")

countries = st.sidebar.multiselect(
    "Countries",
    sorted(df["Country"].dropna().unique()),
    default=["United Kingdom"],
)

exclude_repeats = st.sidebar.checkbox(
    "Exclude flagged repeated rows",
    value=False,
)

if not countries:
    st.info("Select at least one country.")
    st.stop()

filtered = df.loc[df["Country"].isin(countries)].copy()

if exclude_repeats:
    repeated = (
        filtered["is_repeated_row"]
        .astype(str)
        .str.lower()
        .eq("true")
    )
    filtered = filtered.loc[~repeated].copy()

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

monthly = sales.groupby(
    "month", as_index=False
)["line_value_gbp"].sum()

st.plotly_chart(
    px.bar(
        monthly,
        x="month",
        y="line_value_gbp",
        title="Monthly sales value",
        labels={
            "month": "Month",
            "line_value_gbp": "Sales value (£)",
        },
        color_discrete_sequence=["#2563EB"],
    ),
    use_container_width=True,
)

left, right = st.columns(2)

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
    .nlargest(10, "sales_value_gbp")
)

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