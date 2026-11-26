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
    # Refresh the cache when the database is rebuilt.
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

    data["is_repeated_row"] = (
        data["is_repeated_row"]
        .astype("string")
        .str.lower()
        .isin(["true", "1", "1.0"])
    )

    return data


def assign_segment(row: pd.Series) -> str:
    if row["recency_days"] > 90:
        if row["order_count"] >= 5:
            return "Previously frequent, now inactive"
        return "Other inactive customers"

    if row["recency_days"] <= 30:
        if row["order_count"] >= 5:
            return "Recent frequent buyers"
        if row["order_count"] == 1:
            return "Recent single-purchase buyers"
        return "Recent repeat buyers"

    return "Purchased 31–90 days ago"


if not DATABASE.exists():
    st.error("Database missing. Run: python build_database.py")
    st.stop()

try:
    df = load_data(DATABASE.stat().st_mtime_ns)
except (sqlite3.Error, pd.errors.DatabaseError) as error:
    st.error("Could not read the database. Run: python build_database.py")
    st.code(str(error))
    st.stop()

if df.empty:
    st.info("The database contains no transactions.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")

available_countries = sorted(
    df["Country"].dropna().unique().tolist()
)

countries = st.sidebar.multiselect(
    "Countries",
    options=available_countries,
    default=available_countries,
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

# Sales overview
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

# Customer analytics
st.divider()
st.header("Customer Analytics")

st.caption(
    "Uses the selected countries and repeated-row setting above. "
    "Only identified customers with sales are included."
)

customer_sales = sales.loc[
    sales["CustomerID"].notna()
    & sales["CustomerID"].str.strip().ne("")
].copy()

if customer_sales.empty:
    st.info("No identified customers found for these filters.")
else:
    # One historical snapshot date across all country selections.
    snapshot = (
        df["InvoiceDate"].max().normalize()
        + pd.Timedelta(days=1)
    )

    customers = (
        customer_sales.groupby("CustomerID")
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

    customers["segment"] = customers.apply(
        assign_segment,
        axis=1,
    )

    repeat_percentage = (
        customers["order_count"].gt(1).mean() * 100
    )

    first, second, third = st.columns(3)

    first.metric(
        "Identified customers",
        f"{len(customers):,}",
    )

    second.metric(
        "Customers with multiple invoices",
        f"{repeat_percentage:.1f}%",
    )

    third.metric(
        "Median days since purchase",
        f"{customers['recency_days'].median():.0f}",
    )

    st.caption(
        f"Snapshot: {snapshot.date()}. "
        "Multiple-invoice percentage is not a retention rate. "
        "Spending excludes credits and includes service codes."
    )

    st.plotly_chart(
        px.histogram(
            customers,
            x="recency_days",
            nbins=30,
            title="Days since each customer's last purchase",
            labels={
                "recency_days": "Days since last purchase",
            },
            color_discrete_sequence=["#2563EB"],
        ),
        use_container_width=True,
    )

    st.subheader("Top 20 customers by sales value")

    st.dataframe(
        customers.sort_values(
            "sales_value_gbp",
            ascending=False,
        ).head(20),
        hide_index=True,
        use_container_width=True,
    )

    st.download_button(
        "Download customer analysis",
        data=customers.to_csv(index=False).encode("utf-8"),
        file_name="customer_analysis.csv",
        mime="text/csv",
    )

    # Customer segmentation
    st.subheader("Customer segments")

    st.caption(
        "Exploratory rules: recent = within 30 days; "
        "inactive = over 90 days; frequent = at least 5 invoices. "
        "These thresholds need business validation. "
        "Segments describe behavior at the historical snapshot date."
    )

    segments = (
        customers.groupby("segment")
        .agg(
            customer_count=("CustomerID", "size"),
            sales_value_gbp=("sales_value_gbp", "sum"),
            median_recency_days=("recency_days", "median"),
        )
        .reset_index()
        .sort_values("customer_count", ascending=False)
    )

    segment_chart = px.bar(
        segments,
        x="customer_count",
        y="segment",
        orientation="h",
        title="Customers by segment",
        labels={
            "customer_count": "Customers",
            "segment": "Segment",
        },
        color_discrete_sequence=["#2563EB"],
    )

    segment_chart.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )

    st.plotly_chart(
        segment_chart,
        use_container_width=True,
    )

    st.dataframe(
        segments,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Recent single-purchase buyers have one observed sales invoice; "
        "this does not prove they were newly acquired customers. "
        "Inactive labels describe time since purchase, not confirmed churn."
    )

    st.download_button(
        "Download customer segments",
        data=customers.to_csv(index=False).encode("utf-8"),
        file_name="customer_segments.csv",
        mime="text/csv",
    )