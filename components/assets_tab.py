import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "data" / "home_assets.db"

CATEGORIES = ["All", "appliances", "HVAC", "plumbing", "electrical", "exterior", "vehicle", "garden", "other"]


def _load_assets(category: str | None = None) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM assets"
    params: tuple = ()
    if category and category != "All":
        query += " WHERE category = ?"
        params = (category,)
    query += " ORDER BY category, name"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def render_assets_tab() -> None:
    st.subheader("Asset Inventory")

    col1, col2 = st.columns([2, 1])
    with col1:
        category_filter = st.selectbox("Filter by category", CATEGORIES, key="asset_cat_filter")
    with col2:
        st.metric("Total assets", _count_assets())

    df = _load_assets(None if category_filter == "All" else category_filter)

    if df.empty:
        st.info("No assets found.")
        return

    display_cols = ["id", "name", "category", "brand", "location", "purchase_date", "warranty_expiry"]
    st.dataframe(
        df[display_cols].rename(columns={
            "id": "ID", "name": "Name", "category": "Category",
            "brand": "Brand", "location": "Location",
            "purchase_date": "Purchased", "warranty_expiry": "Warranty Expires",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Asset Details")
    asset_names = df["name"].tolist()
    selected = st.selectbox("Select an asset to view details", asset_names, key="asset_detail_select")
    if selected:
        row = df[df["name"] == selected].iloc[0]
        _asset_detail_card(row)


def _asset_detail_card(row: pd.Series) -> None:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{row['name']}**")
            st.caption(f"Category: {row['category']}")
            if row.get("brand"):
                st.caption(f"Brand: {row['brand']} · Model: {row.get('model', 'N/A')}")
            if row.get("location"):
                st.caption(f"Location: {row['location']}")
        with col2:
            if row.get("purchase_date"):
                st.caption(f"Purchased: {row['purchase_date']}")
            if row.get("purchase_price"):
                st.caption(f"Cost: ${row['purchase_price']:,.0f}")
            if row.get("warranty_expiry"):
                st.caption(f"Warranty: {row['warranty_expiry']}")
        if row.get("serial"):
            st.caption(f"Serial: {row['serial']}")
        if row.get("notes"):
            st.info(row["notes"])


def _count_assets() -> int:
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.close()
    return count
