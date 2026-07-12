import html
import math

import pandas as pd
import streamlit as st

from core.session import get_current_user_id
from db import get_provider

CATEGORIES = ["All", "appliances", "HVAC", "plumbing", "electrical", "exterior", "vehicle", "garden", "plants_trees", "other"]

_CAT_ICONS = {
    "appliances": "🏠", "HVAC": "❄️", "plumbing": "🚿", "electrical": "⚡",
    "exterior": "🏡", "vehicle": "🚗", "garden": "🌱", "plants_trees": "🌳", "other": "📦",
}


def _load_assets(category: str | None = None) -> pd.DataFrame:
    result = get_provider().list_assets(get_current_user_id(), category)
    return pd.DataFrame(result["assets"])


def _count_assets() -> int:
    return get_provider().list_assets(get_current_user_id())["count"]


def render_assets_tab() -> None:
    count = _count_assets()

    # Header row: title + metric tile
    col_title, col_metric = st.columns([3, 1])
    with col_title:
        st.subheader("Asset Inventory")
    with col_metric:
        st.html(f"""
        <div style="
            background: linear-gradient(135deg, rgba(108,99,255,0.18), rgba(108,99,255,0.06));
            border: 1px solid rgba(108,99,255,0.35);
            border-radius: 12px; padding: 14px 16px;
            text-align: center; font-family: system-ui, sans-serif;
            margin-top: 6px;
        ">
            <div style="font-size: 28px; font-weight: 700; color: #8b85ff;">{count}</div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.45); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px;">Total Assets</div>
        </div>
        """)

    # Category filter
    category_filter = st.selectbox("Filter by category", CATEGORIES, key="asset_cat_filter")

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


def _safe(val) -> str:
    """Return str(val) or '' if val is None/NaN/empty."""
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    s = str(val).strip()
    return "" if s in ("None", "nan", "NaT") else s


def _asset_detail_card(row: pd.Series) -> None:
    category = _safe(row.get("category")) or "other"
    icon = _CAT_ICONS.get(category, "📦")
    name = html.escape(_safe(row.get("name")))
    brand = html.escape(_safe(row.get("brand")))
    model = html.escape(_safe(row.get("model")))
    location = html.escape(_safe(row.get("location")))
    serial = html.escape(_safe(row.get("serial")))
    purchase_date = _safe(row.get("purchase_date"))
    purchase_price_raw = row.get("purchase_price")
    purchase_price = None if (purchase_price_raw is None or (isinstance(purchase_price_raw, float) and math.isnan(purchase_price_raw))) else purchase_price_raw
    warranty_expiry = _safe(row.get("warranty_expiry"))
    notes = html.escape(_safe(row.get("notes")))

    price_html = f'<div style="font-size:13px;color:#8b85ff;font-weight:600;">💰 ${purchase_price:,.0f}</div>' if purchase_price else ""
    warranty_html = f'<div style="font-size:12px;color:rgba(255,255,255,0.45);margin-top:2px;">Warranty: {html.escape(warranty_expiry)}</div>' if warranty_expiry else ""
    brand_model = f"{brand} · {model}" if (brand and model) else (brand or model)
    brand_html = f'<div style="font-size:12px;color:rgba(255,255,255,0.5);">{brand_model}</div>' if brand_model else ""
    location_html = f'<div style="font-size:12px;color:rgba(255,255,255,0.45);">📍 {location}</div>' if location else ""
    serial_html = f'<div style="font-size:11px;color:rgba(255,255,255,0.3);margin-top:4px;font-family:monospace;">S/N: {serial}</div>' if serial else ""
    purchased_html = f'<div style="font-size:12px;color:rgba(255,255,255,0.45);">Purchased: {html.escape(purchase_date)}</div>' if purchase_date else ""

    st.html(f"""
    <div style="
        border: 1px solid rgba(108,99,255,0.25);
        border-radius: 14px;
        padding: 20px 22px;
        background: linear-gradient(135deg, rgba(108,99,255,0.08), rgba(108,99,255,0.02));
        font-family: system-ui, sans-serif;
        margin-top: 8px;
    ">
        <div style="display: flex; align-items: flex-start; gap: 14px;">
            <div style="
                width: 48px; height: 48px;
                background: rgba(108,99,255,0.2);
                border-radius: 12px;
                display: flex; align-items: center; justify-content: center;
                font-size: 24px; flex-shrink: 0;
            ">{icon}</div>
            <div style="flex: 1; min-width: 0;">
                <div style="font-size: 18px; font-weight: 700; color: #E6EDF3; margin-bottom: 4px;">{name}</div>
                <div style="display: inline-block; background: rgba(108,99,255,0.2); color: #a09af0; border-radius: 5px; padding: 1px 8px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;">{html.escape(category)}</div>
                {brand_html}
                {location_html}
            </div>
            <div style="text-align: right; flex-shrink: 0;">
                {price_html}
                {purchased_html}
                {warranty_html}
            </div>
        </div>
        {serial_html}
        {f'<div style="margin-top: 12px; padding: 10px 14px; background: rgba(255,255,255,0.04); border-radius: 8px; font-size: 13px; color: rgba(255,255,255,0.6); border-left: 3px solid rgba(108,99,255,0.4);">{notes}</div>' if notes and notes != "None" else ""}
    </div>
    """)
