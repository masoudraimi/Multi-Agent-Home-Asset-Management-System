import pandas as pd
import streamlit as st

from db_conn import get_client

CATEGORIES = ["All", "appliances", "HVAC", "plumbing", "electrical", "exterior", "vehicle", "garden", "plants_trees", "other"]


def _load_assets(category: str | None = None) -> pd.DataFrame:
    q = get_client().table("assets").select("*")
    if category and category != "All":
        q = q.eq("category", category)
    data = q.order("category").order("name").execute().data
    return pd.DataFrame(data)


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
    result = get_client().table("assets").select("id", count="exact").execute()
    return result.count or 0
