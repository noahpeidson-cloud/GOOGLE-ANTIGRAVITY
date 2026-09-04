"""
app.py - Streamlit Visual Staging Area & Hub Dashboard for Sports Card Ecosystem.
Central operational command center unifying AI Vision ingestion, Checklist scraping,
Chrome Extension FastAPI bridge, Sales copy generation, and 16-variable Card Ladder CSV export.
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

# Ensure directory is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from models import (
    CardRecord,
    CardUpdate,
    CardCategory,
    AIStatus,
    VALID_CATEGORIES,
    CATEGORY_MAP,
    synthesize_query,
    format_notes,
    get_current_date_str,
)
from database import (
    DEFAULT_DB_PATH,
    CIRCUIT_BREAKER_BATCH_LIMIT,
    init_db,
    insert_card,
    insert_cards_batch,
    get_card_by_id,
    get_all_cards,
    update_card,
    update_card_status,
    delete_card,
    get_summary_stats,
    get_card_count,
    check_circuit_breaker,
    get_next_child_id,
    clear_staging_table,
    get_cards_for_export,
)
from vision_ingest import (
    extract_card_from_image,
    MockVisionExtractor,
    ingest_vision_card,
    extraction_to_card_record,
    CardExtractionSchema,
)
from scraper_ingest import (
    parse_checklist_html,
    fetch_and_parse_checklist,
    ingest_scraper_cards,
    expand_parallels,
)
from sales_generator import (
    generate_marketplace_listing,
    build_structured_listing,
    MockSalesGenerator,
    build_seo_title,
    build_hashtags,
)
from export import (
    CARD_LADDER_COLUMNS,
    EXCLUDED_INTERNAL_FIELDS,
    export_card_ladder_csv,
    validate_card_ladder_csv,
    cards_to_card_ladder_dataframe,
    fetch_records_for_export,
)
from api import (
    is_port_in_use,
    start_api_server_thread,
    BackgroundServerThread,
)


# ============================================================================
# Session State Initialization
# ============================================================================

def init_session_state():
    """Initializes default keys in st.session_state."""
    resolved_db = os.environ.get("PORTFOLIO_DB_PATH", DEFAULT_DB_PATH)
    st.session_state.setdefault("db_path", resolved_db)
    st.session_state.setdefault("api_server_running", False)
    st.session_state.setdefault("api_server_thread", None)

    # Tab 1: Staging Area
    st.session_state.setdefault("selected_card_id", None)
    st.session_state.setdefault("staging_filter_category", "ALL")
    st.session_state.setdefault("staging_filter_status", "ALL")
    st.session_state.setdefault("staging_filter_year", "")
    st.session_state.setdefault("staging_search_query", "")

    # Tab 2: AI Vision
    st.session_state.setdefault("vision_extraction_result", None)
    st.session_state.setdefault("vision_parent_id", "8492")
    st.session_state.setdefault("vision_cost_basis", 0.0)

    # Tab 3: Checklist Scraper
    st.session_state.setdefault("scraper_raw_cards", [])
    st.session_state.setdefault("scraper_source_type", "📝 Raw HTML Paste / Local Fixture")
    st.session_state.setdefault("scraper_target_set", "")
    st.session_state.setdefault("scraper_target_year", "")
    st.session_state.setdefault("scraper_target_category", "Basketball")
    st.session_state.setdefault("scraper_parallels_input", "Base, Silver Prizm, Red /99, Gold /10")

    # Tab 4: Sales Copy Generator
    st.session_state.setdefault("sales_selected_card_id", None)
    st.session_state.setdefault("sales_asking_price", 50.0)
    st.session_state.setdefault("sales_custom_notes", "Includes magnetic one-touch case. Local pickup available.")
    st.session_state.setdefault("sales_generated_text", "")
    st.session_state.setdefault("sales_structured_data", None)

    # Tab 5: Card Ladder Export
    st.session_state.setdefault("export_status_filter", "CLEARED")
    st.session_state.setdefault("export_apply_normalization", True)
    st.session_state.setdefault("export_row_count", 0)
    st.session_state.setdefault("export_file_paths", [])
    st.session_state.setdefault("export_validation_result", None)


# ============================================================================
# Custom Styling & CSS
# ============================================================================

def render_custom_css():
    """Injects modern minimalist typography and badge styling."""
    st.markdown(
        """
        <style>
        .metric-card {
            background-color: #1e1e24;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            border: 1px solid #2e2e38;
        }
        .badge-cleared {
            background-color: #10B981;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .badge-review {
            background-color: #F59E0B;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .badge-needs {
            background-color: #EF4444;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# API Daemon Cache Helper
# ============================================================================

@st.cache_resource
def get_or_start_api_server(
    host: str = "127.0.0.1",
    port: int = 8002,
    db_path: str = DEFAULT_DB_PATH,
) -> BackgroundServerThread:
    """
    Spawns and caches the FastAPI background listener daemon.
    Guarantees idempotency and prevents port re-binding errors across Streamlit reruns.
    """
    return start_api_server_thread(host=host, port=port, db_path=db_path)


# ============================================================================
# Header & KPI Metrics Bar
# ============================================================================

def render_header(db_path: str):
    """Renders application header and port status badge."""
    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.title("🃏 Sports Card Ecosystem Hub")
        st.caption("Master 21-Variable Ingestion, Visual Staging & Card Ladder Export Engine")

    with col_status:
        port_active = is_port_in_use(8002)
        if port_active:
            st.success("🟢 API Bridge: 8002 (Online)")
        else:
            st.info("⚪ API Bridge: Offline")


def render_kpi_bar(stats: dict[str, Any]):
    """Renders 5 top KPI metrics."""
    col1, col2, col3, col4, col5 = st.columns(5)

    total_cards = stats.get("total_cards", 0)
    total_inv = stats.get("total_investment", 0.0)
    total_est = stats.get("total_estimated_value", 0.0)
    counts_by_status = stats.get("count_by_ai_status", {})

    pending_count = (
        counts_by_status.get("REVIEW VARIATION", 0)
        + counts_by_status.get("NEEDS REVIEW", 0)
    )
    cleared_count = counts_by_status.get("CLEARED", 0)

    with col1:
        cb_warning = "⚠️ 500 Limit" if total_cards >= 500 else None
        st.metric(
            label="Total Cards",
            value=f"{total_cards}",
            delta=cb_warning,
            delta_color="inverse" if total_cards >= 500 else "normal",
        )

    with col2:
        st.metric(
            label="Total Investment",
            value=f"${total_inv:,.2f}",
        )

    with col3:
        roi_delta = None
        if total_inv > 0:
            diff = total_est - total_inv
            pct = (diff / total_inv) * 100
            roi_delta = f"{diff:+,.2f} ({pct:+.1f}%)"
        st.metric(
            label="Total Estimated Value",
            value=f"${total_est:,.2f}",
            delta=roi_delta,
        )

    with col4:
        st.metric(
            label="Pending AI Reviews",
            value=f"{pending_count}",
        )

    with col5:
        st.metric(
            label="Cleared Cards",
            value=f"{cleared_count}",
        )

    st.divider()


# ============================================================================
# Tab 1: 📊 Portfolio Staging Area
# ============================================================================

def render_tab_staging(db_path: str):
    """Tab 1: Master Staging Area with interactive filters, CRUD, and maintenance."""
    st.subheader("📊 Portfolio Staging Area")

    # Filters Row
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        category_options = ["ALL"] + sorted(list(VALID_CATEGORIES))
        selected_category = st.selectbox(
            "Filter by Category",
            options=category_options,
            key="staging_filter_category",
        )

    with f_col2:
        status_options = ["ALL", "CLEARED", "REVIEW VARIATION", "NEEDS REVIEW"]
        selected_status = st.selectbox(
            "Filter by AI Status",
            options=status_options,
            key="staging_filter_status",
        )

    with f_col3:
        year_filter = st.text_input(
            "Filter by Year",
            value="",
            placeholder="e.g. 2020",
            key="staging_filter_year",
        )

    with f_col4:
        search_filter = st.text_input(
            "Search (Player, Set, Query, Notes)",
            value="",
            placeholder="Search keyword...",
            key="staging_search_query",
        )

    # Build filter kwargs
    filters_dict = {}
    if selected_category != "ALL":
        filters_dict["category"] = selected_category
    if selected_status != "ALL":
        filters_dict["ai_status"] = selected_status
    if year_filter.strip():
        filters_dict["year"] = year_filter.strip()
    if search_filter.strip():
        filters_dict["search"] = search_filter.strip()

    cards = get_all_cards(
        filters=filters_dict,
        limit=500,
        order_by="id DESC",
        db_path=db_path,
    )

    # Render Table
    if cards:
        display_columns = [
            "id",
            "ai_status",
            "player",
            "year",
            "set_name",
            "variation",
            "card_number",
            "category",
            "condition",
            "investment",
            "estimated_value",
            "notes",
            "query",
        ]
        df = pd.DataFrame(cards)
        available_cols = [c for c in display_columns if c in df.columns]
        df_display = df[available_cols]

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No staged cards match the active filters. Staging table is currently empty.")

    st.markdown("---")

    # Card Details, Edit, and Status Resolution Expander
    if cards:
        with st.expander("🔍 Card Details, Quick Review & Edit", expanded=True):
            card_options = {
                c["id"]: f"#{c['id']} | {c['year']} {c['set_name']} - {c['player']} {c['variation']} [{c['condition']}] ({c['ai_status']})"
                for c in cards
            }
            selected_id = st.selectbox(
                "Select Staged Card to Inspect / Edit",
                options=list(card_options.keys()),
                format_func=lambda x: card_options[x],
                key="card_select_inspect",
            )

            if selected_id:
                card_data = get_card_by_id(selected_id, db_path=db_path)
                if card_data:
                    # Quick Status Actions
                    st.write("**Quick AI Status Actions:**")
                    q_col1, q_col2, q_col3 = st.columns(3)
                    with q_col1:
                        if st.button("✅ Mark CLEARED", key=f"btn_clear_{selected_id}", use_container_width=True):
                            update_card_status(selected_id, "CLEARED", db_path=db_path)
                            st.toast(f"Card #{selected_id} marked CLEARED!", icon="✅")
                            st.rerun()

                    with q_col2:
                        if st.button("⚠️ Flag REVIEW VARIATION", key=f"btn_rev_var_{selected_id}", use_container_width=True):
                            update_card_status(selected_id, "REVIEW VARIATION", db_path=db_path)
                            st.toast(f"Card #{selected_id} flagged for variation review!", icon="⚠️")
                            st.rerun()

                    with q_col3:
                        if st.button("❌ Flag NEEDS REVIEW", key=f"btn_needs_rev_{selected_id}", use_container_width=True):
                            update_card_status(selected_id, "NEEDS REVIEW", db_path=db_path)
                            st.toast(f"Card #{selected_id} flagged as NEEDS REVIEW!", icon="❌")
                            st.rerun()

                    st.markdown("##### Edit 21-Variable Record")
                    with st.form(key=f"edit_card_form_{selected_id}"):
                        e_col1, e_col2 = st.columns(2)
                        with e_col1:
                            edit_player = st.text_input("Player Name", value=card_data.get("player", ""))
                            edit_year = st.text_input("Year (YYYY)", value=card_data.get("year", ""))
                            edit_set = st.text_input("Set Name", value=card_data.get("set_name", ""))
                            edit_variation = st.text_input("Variation / Parallel", value=card_data.get("variation", ""))
                            edit_card_num = st.text_input("Card Number", value=card_data.get("card_number", ""))
                            edit_category = st.selectbox(
                                "Category",
                                options=sorted(list(VALID_CATEGORIES)),
                                index=sorted(list(VALID_CATEGORIES)).index(card_data.get("category", "Basketball"))
                                if card_data.get("category") in VALID_CATEGORIES
                                else 0,
                            )
                            edit_condition = st.text_input("Condition (e.g. Raw, PSA 10)", value=card_data.get("condition", "Raw"))
                            edit_slab = st.text_input("Slab Serial Number", value=card_data.get("slab_serial_number", ""))
                            edit_investment = st.number_input(
                                "Investment ($)",
                                min_value=0.0,
                                value=float(card_data.get("investment", 0.0)),
                                step=1.0,
                            )

                        with e_col2:
                            edit_estimated_val = st.number_input(
                                "Estimated Value ($)",
                                min_value=0.0,
                                value=float(card_data.get("estimated_value", 0.0)),
                                step=1.0,
                            )
                            edit_date_purchased = st.text_input("Date Purchased (MM/DD/YYYY)", value=card_data.get("date_purchased", ""))
                            edit_quantity = st.number_input("Quantity", min_value=1, value=int(card_data.get("quantity", 1)), step=1)
                            edit_notes = st.text_input("Notes (e.g. 8492-101)", value=card_data.get("notes", ""))
                            edit_tags = st.text_input("Tags", value=card_data.get("tags", ""))
                            edit_ladder_id = st.text_input("Ladder ID", value=card_data.get("ladder_id", ""))
                            edit_date_sold = st.text_input("Date Sold", value=card_data.get("date_sold", ""))
                            sold_p = card_data.get("sold_price")
                            edit_sold_price = st.number_input(
                                "Sold Price ($)",
                                min_value=0.0,
                                value=float(sold_p) if sold_p is not None else 0.0,
                                step=1.0,
                            )
                            edit_image = st.text_input("Front Image Path / URL", value=card_data.get("image", ""))
                            edit_back_image = st.text_input("Back Image Path / URL", value=card_data.get("back_image", ""))
                            status_choices = ["CLEARED", "REVIEW VARIATION", "NEEDS REVIEW"]
                            edit_ai_status = st.selectbox(
                                "AI Review Status",
                                options=status_choices,
                                index=status_choices.index(card_data.get("ai_status", "CLEARED"))
                                if card_data.get("ai_status") in status_choices
                                else 0,
                            )

                        submit_edit = st.form_submit_button("💾 Save Changes", use_container_width=True)
                        if submit_edit:
                            updates = {
                                "player": edit_player,
                                "year": edit_year,
                                "set_name": edit_set,
                                "variation": edit_variation,
                                "card_number": edit_card_num,
                                "category": edit_category,
                                "condition": edit_condition,
                                "slab_serial_number": edit_slab if edit_condition != "Raw" else "",
                                "investment": edit_investment,
                                "estimated_value": edit_estimated_val,
                                "date_purchased": edit_date_purchased,
                                "quantity": edit_quantity,
                                "notes": edit_notes,
                                "tags": edit_tags,
                                "ladder_id": edit_ladder_id,
                                "date_sold": edit_date_sold,
                                "sold_price": edit_sold_price if edit_date_sold.strip() else None,
                                "image": edit_image,
                                "back_image": edit_back_image,
                                "ai_status": edit_ai_status,
                            }
                            try:
                                success = update_card(selected_id, updates, db_path=db_path)
                                if success:
                                    st.toast(f"Card #{selected_id} updated successfully!", icon="✅")
                                    st.rerun()
                                else:
                                    st.error("Failed to update card record.")
                            except Exception as e:
                                st.error(f"Validation Error: {e}")

                    # Card Delete and Sales actions
                    act_col1, act_col2 = st.columns(2)
                    with act_col1:
                        if st.button("🗑️ Delete Card", key=f"btn_delete_{selected_id}", use_container_width=True):
                            delete_card(selected_id, db_path=db_path)
                            st.toast(f"Card #{selected_id} deleted!", icon="🗑️")
                            st.rerun()

                    with act_col2:
                        if st.button("🏷️ Select for Sales Copy Generator", key=f"btn_sel_sales_{selected_id}", use_container_width=True):
                            st.session_state.sales_selected_card_id = selected_id
                            st.toast(f"Card #{selected_id} selected for Sales Copy Generator!", icon="🏷️")

    # Manual Card Entry Form
    with st.expander("➕ Manual Card Entry", expanded=False):
        with st.form("manual_entry_form"):
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                m_player = st.text_input("Player Name *", value="", placeholder="e.g. Victor Wembanyama")
                m_year = st.text_input("Year (YYYY) *", value=str(datetime.now().year))
                m_set = st.text_input("Set Name *", value="", placeholder="e.g. Panini Prizm")
                m_variation = st.text_input("Variation / Parallel", value="", placeholder="e.g. Silver Prizm")
                m_card_number = st.text_input("Card Number", value="", placeholder="e.g. 136")
                m_category = st.selectbox("Category *", options=sorted(list(VALID_CATEGORIES)), index=0)
                m_condition = st.text_input("Condition", value="Raw")
                m_slab = st.text_input("Slab Serial Number (if Graded)", value="")

            with m_col2:
                m_investment = st.number_input("Investment ($)", min_value=0.0, value=0.0, step=1.0)
                m_estimated_val = st.number_input("Estimated Value ($)", min_value=0.0, value=0.0, step=1.0)
                m_date_purchased = st.text_input("Date Purchased (MM/DD/YYYY)", value=get_current_date_str())
                m_parent_id = st.text_input("Parent Image ID for Notes", value="8492")
                m_tags = st.text_input("Tags", value="")
                m_image = st.text_input("Front Image Path / URL", value="")
                m_back_image = st.text_input("Back Image Path / URL", value="")

            m_submit = st.form_submit_button("➕ Add Card to Staging", use_container_width=True)
            if m_submit:
                if not m_player.strip() or not m_set.strip() or not m_year.strip():
                    st.error("Player Name, Year, and Set Name are required.")
                else:
                    child_id = get_next_child_id(m_parent_id, db_path=db_path)
                    notes_val = format_notes(m_parent_id, child_id)
                    card_payload = {
                        "player": m_player,
                        "year": m_year,
                        "set_name": m_set,
                        "variation": m_variation,
                        "card_number": m_card_number,
                        "category": m_category,
                        "condition": m_condition,
                        "slab_serial_number": m_slab if m_condition != "Raw" else "",
                        "investment": m_investment,
                        "estimated_value": m_estimated_val,
                        "date_purchased": m_date_purchased,
                        "notes": notes_val,
                        "tags": m_tags,
                        "image": m_image,
                        "back_image": m_back_image,
                        "ai_status": "REVIEW VARIATION" if m_variation.strip() else "CLEARED",
                    }
                    try:
                        new_id = insert_card(card_payload, db_path=db_path)
                        st.toast(f"Card #{new_id} added to staging!", icon="🃏")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Error adding card: {err}")

    # Staging Table Maintenance
    with st.expander("⚠️ Staging Maintenance / Danger Zone", expanded=False):
        st.warning("Clearing the staging table permanently deletes all card records currently staged.")
        confirm_clear = st.checkbox("I confirm I want to wipe all records in the staging table.")
        if st.button("🗑️ Clear Entire Staging Table", disabled=not confirm_clear):
            count_deleted = clear_staging_table(db_path=db_path)
            st.toast(f"Cleared {count_deleted} cards from staging!", icon="🗑️")
            st.rerun()


# ============================================================================
# Tab 2: 📸 AI Vision Ingestion
# ============================================================================

def render_tab_vision(db_path: str):
    """Tab 2: Multimodal AI Vision Ingestion using Gemini 2.5 Flash / Mock fallback."""
    st.subheader("📸 AI Vision Ingestion")
    st.caption("Upload front/back card images to extract catalog metadata and grade details.")

    v_col1, v_col2 = st.columns(2)
    with v_col1:
        front_file = st.file_uploader(
            "Front Card Photo",
            type=["jpg", "jpeg", "png", "webp"],
            key="vision_front_uploader",
        )
    with v_col2:
        back_file = st.file_uploader(
            "Back Card Photo (Optional)",
            type=["jpg", "jpeg", "png", "webp"],
            key="vision_back_uploader",
        )

    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    with p_col1:
        parent_id = st.text_input("Parent Image ID", value="8492", key="vision_parent_id_input")
    with p_col2:
        cost_basis = st.number_input("Cost Basis ($)", min_value=0.0, value=0.0, step=1.0, key="vision_cost_basis_input")
    with p_col3:
        purchase_date = st.text_input("Purchase Date (MM/DD/YYYY)", value=get_current_date_str(), key="vision_purchase_date_input")
    with p_col4:
        has_api_key = bool(os.environ.get("GEMINI_API_KEY"))
        use_mock = st.checkbox("Offline Mock Mode", value=not has_api_key, key="vision_mock_toggle")

    if st.button("🔍 Extract Card Info with Gemini Vision", key="btn_vision_extract", use_container_width=True):
        child_id = get_next_child_id(parent_id, db_path=db_path)

        front_input: Any = "card_front.jpg"
        back_input: Any = None
        if front_file is not None:
            front_input = front_file.getvalue() if hasattr(front_file, "getvalue") else front_file.name
        if back_file is not None:
            back_input = back_file.getvalue() if hasattr(back_file, "getvalue") else back_file.name

        with st.spinner("Analyzing card photo with Gemini Multimodal API..."):
            try:
                extraction = extract_card_from_image(
                    image_path=front_input,
                    back_image_path=back_input,
                    mock=use_mock,
                    parent_image_id=parent_id,
                    child_card_id=child_id,
                )
                st.session_state.vision_extraction_result = extraction
                st.toast("Card features extracted successfully!", icon="🔍")
            except Exception as e:
                st.error(f"Vision extraction failed: {e}")

    # Display Preview & Commit Form
    extraction_res = st.session_state.get("vision_extraction_result")
    if extraction_res:
        st.markdown("---")
        st.markdown("### 📋 Extraction Preview & Review")

        with st.form("vision_commit_form"):
            c1, c2 = st.columns(2)
            with c1:
                v_player = st.text_input("Player", value=extraction_res.player)
                v_year = st.text_input("Year", value=extraction_res.year)
                v_set = st.text_input("Set Name", value=extraction_res.set_name)
                v_variation = st.text_input("Variation", value=extraction_res.variation)
                v_card_num = st.text_input("Card Number", value=extraction_res.card_number)
                v_cat = st.selectbox(
                    "Category",
                    options=sorted(list(VALID_CATEGORIES)),
                    index=sorted(list(VALID_CATEGORIES)).index(extraction_res.category)
                    if extraction_res.category in VALID_CATEGORIES
                    else 0,
                )

            with c2:
                v_condition = st.text_input("Condition", value=extraction_res.condition)
                v_slab = st.text_input("Slab Serial Number", value=extraction_res.slab_serial_number)
                v_est_val = st.number_input("Estimated Value ($)", min_value=0.0, value=float(extraction_res.estimated_value), step=1.0)
                v_notes = st.text_input("Tracking Notes", value=extraction_res.notes or format_notes(parent_id, get_next_child_id(parent_id, db_path=db_path)))
                v_status_options = ["CLEARED", "REVIEW VARIATION", "NEEDS REVIEW"]
                v_status = st.selectbox(
                    "AI Status",
                    options=v_status_options,
                    index=v_status_options.index(extraction_res.ai_status)
                    if extraction_res.ai_status in v_status_options
                    else 0,
                )

            commit_btn = st.form_submit_button("💾 Commit Card to Staging DB", use_container_width=True)
            if commit_btn:
                committed_card = {
                    "player": v_player,
                    "year": v_year,
                    "set_name": v_set,
                    "variation": v_variation,
                    "card_number": v_card_num,
                    "category": v_cat,
                    "condition": v_condition,
                    "slab_serial_number": v_slab if v_condition != "Raw" else "",
                    "investment": cost_basis,
                    "estimated_value": v_est_val,
                    "date_purchased": purchase_date,
                    "notes": v_notes,
                    "ai_status": v_status,
                }
                try:
                    new_card_id = insert_card(committed_card, db_path=db_path)
                    st.session_state.vision_extraction_result = None
                    st.toast(f"Card #{new_card_id} committed to database!", icon="🃏")
                    st.rerun()
                except Exception as e:
                    st.error(f"Commit error: {e}")


# ============================================================================
# Tab 3: 📋 Checklist Scraper
# ============================================================================

def render_tab_scraper(db_path: str):
    """Tab 3: Bulk Checklist Ingestion from Beckett / Cardboard Connection."""
    st.subheader("📋 Checklist Scraper & Parallel Generator")
    st.caption("Scrape set checklists from Beckett / Cardboard Connection and generate parallel variations.")

    source_type = st.radio(
        "Checklist Source",
        ["📝 Raw HTML Paste / Local Fixture", "🌐 Remote URL (Beckett / Cardboard Connection)"],
        key="scraper_source_radio",
    )

    if "URL" in source_type:
        checklist_url = st.text_input(
            "Beckett / Cardboard Connection URL",
            value="",
            placeholder="https://www.cardboardconnection.com/2023-24-panini-prizm-basketball-cards",
            key="scraper_url_text",
        )
    else:
        html_input = st.text_area(
            "Paste Raw Checklist HTML",
            value="",
            height=140,
            placeholder="<html><body><table><tr><th>Card #</th><th>Player</th>...</tr></table></body></html>",
            key="scraper_html_text",
        )

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        s_set = st.text_input("Set Name (Auto-inferred if blank)", value="", key="scraper_set_input")
    with m_col2:
        s_year = st.text_input("Year (Auto-inferred if blank)", value="", key="scraper_year_input")
    with m_col3:
        s_cat = st.selectbox("Category", options=sorted(list(VALID_CATEGORIES)), index=0, key="scraper_cat_select")
    with m_col4:
        s_parallels = st.text_input(
            "Parallels (comma-separated)",
            value="Base, Silver Prizm, Red /99, Gold /10",
            key="scraper_parallels_text",
        )

    if st.button("📥 Parse Checklist", key="btn_scraper_parse", use_container_width=True):
        parallels_list = [p.strip() for p in s_parallels.split(",") if p.strip()] or ["Base"]
        parsed: list[Any] = []

        try:
            if "URL" in source_type:
                if not checklist_url.strip():
                    st.warning("Please provide a checklist URL.")
                else:
                    fixture_fallback = os.path.join(CURRENT_DIR, "fixtures", "beckett_sample.html")
                    parsed = fetch_and_parse_checklist(
                        url=checklist_url,
                        set_name=s_set,
                        year=s_year,
                        category=s_cat,
                        parallels=parallels_list,
                        fallback_fixture_path=fixture_fallback if os.path.exists(fixture_fallback) else None,
                    )
            else:
                raw_html = html_input.strip()
                if not raw_html:
                    # Check for built-in fixture
                    fixture_path = os.path.join(CURRENT_DIR, "fixtures", "beckett_sample.html")
                    if os.path.exists(fixture_path):
                        with open(fixture_path, "r", encoding="utf-8") as f:
                            raw_html = f.read()
                if raw_html:
                    parsed = parse_checklist_html(
                        html_content=raw_html,
                        set_name=s_set,
                        year=s_year,
                        category=s_cat,
                        parallels=parallels_list,
                    )
                else:
                    st.warning("Please paste checklist HTML or ensure fixtures/beckett_sample.html exists.")

            st.session_state.scraper_raw_cards = parsed
            st.toast(f"Parsed {len(parsed)} cards across {len(parallels_list)} parallels!", icon="📋")
        except Exception as e:
            st.error(f"Failed to parse checklist: {e}")

    # Display Parsed Cards and Bulk Ingest Controls
    parsed_cards = st.session_state.get("scraper_raw_cards", [])
    if parsed_cards:
        st.markdown("---")
        st.markdown(f"### 📋 Parsed Cards Staging Buffer ({len(parsed_cards)} items)")

        df_parsed = pd.DataFrame([c.model_dump() for c in parsed_cards])
        show_cols = [c for c in ["card_number", "player", "year", "set_name", "variation", "category", "ai_status", "notes"] if c in df_parsed.columns]
        st.dataframe(df_parsed[show_cols], use_container_width=True, hide_index=True)

        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            bulk_inv = st.number_input("Cost Basis per Card ($)", min_value=0.0, value=0.50, step=0.10, key="scraper_bulk_inv")
        with b_col2:
            bulk_date = st.text_input("Purchase Date", value=get_current_date_str(), key="scraper_bulk_date_input")
        with b_col3:
            bulk_parent_id = st.text_input("Parent Batch ID", value="9001", key="scraper_bulk_parent_id_input")

        if st.button(f"⚡ Bulk Ingest ({len(parsed_cards)}) Cards to Database", key="btn_scraper_bulk_ingest", use_container_width=True):
            current_total = get_card_count(db_path=db_path)
            if current_total + len(parsed_cards) > 500:
                st.warning(
                    f"⚠️ Batch size ({len(parsed_cards)}) + staged cards ({current_total}) "
                    f"exceeds the 500-card circuit breaker limit. Please reduce selection."
                )
            else:
                try:
                    inserted_ids = ingest_scraper_cards(
                        extractions=parsed_cards,
                        parent_id=bulk_parent_id,
                        date_purchased=bulk_date,
                        investment=bulk_inv,
                        db_path=db_path,
                    )
                    st.session_state.scraper_raw_cards = []
                    st.toast(f"Successfully staged {len(inserted_ids)} cards to database!", icon="🚀")
                    st.rerun()
                except Exception as e:
                    st.error(f"Bulk ingestion error: {e}")


# ============================================================================
# Tab 4: 🏷️ Sales Copy Generator
# ============================================================================

def render_tab_sales(db_path: str):
    """Tab 4: High-Conversion SEO Facebook Marketplace Listing Generator."""
    st.subheader("🏷️ Sales Copy Generator")
    st.caption("Generate structured, SEO-optimized listing copy for Facebook Marketplace and social selling.")

    cards = get_all_cards(limit=500, db_path=db_path)

    src_mode = st.radio(
        "Card Source",
        ["🗄️ Select from Staging Database", "✍️ Manual Card Input"],
        key="sales_src_radio",
    )

    target_card_data: Optional[dict[str, Any]] = None
    default_price = 50.0

    if "Database" in src_mode and cards:
        card_options = {
            c["id"]: f"#{c['id']} | {c['year']} {c['set_name']} {c['player']} {c['variation']} [{c['condition']}] - Est: ${c['estimated_value']:.2f}"
            for c in cards
        }
        default_index = 0
        preselected_id = st.session_state.get("sales_selected_card_id")
        if preselected_id and preselected_id in card_options:
            default_index = list(card_options.keys()).index(preselected_id)

        selected_id = st.selectbox(
            "Select Card from Database",
            options=list(card_options.keys()),
            format_func=lambda x: card_options[x],
            index=default_index,
            key="sales_card_dropdown",
        )
        target_card_data = get_card_by_id(selected_id, db_path=db_path)
        if target_card_data:
            default_price = float(target_card_data.get("estimated_value") or target_card_data.get("investment") or 50.0)
    else:
        m1, m2 = st.columns(2)
        with m1:
            man_player = st.text_input("Player", value="Luka Dončić", key="sales_man_player")
            man_year = st.text_input("Year", value="2020", key="sales_man_year")
            man_set = st.text_input("Set Name", value="Panini Prizm", key="sales_man_set")
            man_variation = st.text_input("Variation", value="Silver Prizm", key="sales_man_var")
        with m2:
            man_card_num = st.text_input("Card #", value="75", key="sales_man_num")
            man_cat = st.selectbox("Category", options=sorted(list(VALID_CATEGORIES)), index=0, key="sales_man_cat")
            man_cond = st.text_input("Condition", value="PSA 10", key="sales_man_cond")
            man_slab = st.text_input("Slab Serial Number", value="48192041", key="sales_man_slab")

        target_card_data = {
            "player": man_player,
            "year": man_year,
            "set_name": man_set,
            "variation": man_variation,
            "card_number": man_card_num,
            "category": man_cat,
            "condition": man_cond,
            "slab_serial_number": man_slab if man_cond != "Raw" else "",
            "estimated_value": 350.0,
            "investment": 150.0,
        }
        default_price = 350.0

    p_col1, p_col2 = st.columns(2)
    with p_col1:
        asking_price = st.number_input(
            "Target Asking Price ($)",
            min_value=0.0,
            value=default_price,
            step=5.0,
            key="sales_price_input",
        )
    with p_col2:
        has_key = bool(os.environ.get("GEMINI_API_KEY"))
        use_mock = st.checkbox(
            "Offline Deterministic SEO Mock",
            value=not has_key,
            key="sales_mock_toggle",
        )

    custom_notes = st.text_area(
        "Custom Condition & Delivery Notes",
        value="Includes magnetic one-touch case. Local pickup available in North Scottsdale.",
        height=80,
        key="sales_notes_text",
    )

    if st.button("✨ Generate SEO Facebook Marketplace Listing", key="btn_sales_generate", use_container_width=True):
        if target_card_data:
            with st.spinner("Crafting SEO listing copy..."):
                raw_copy = generate_marketplace_listing(
                    card=target_card_data,
                    asking_price=asking_price,
                    custom_notes=custom_notes,
                    mock=use_mock,
                    db_path=db_path,
                )
                structured = build_structured_listing(
                    card=target_card_data,
                    asking_price=asking_price,
                    custom_notes=custom_notes,
                    is_mock=use_mock,
                )
                st.session_state.sales_generated_text = raw_copy
                st.session_state.sales_structured_data = structured
                st.toast("SEO Marketplace Listing generated!", icon="🏷️")

    # Display Generated Listing
    if st.session_state.get("sales_generated_text"):
        st.markdown("---")
        st.markdown("### 📢 Facebook Marketplace Copy Preview")

        structured_obj = st.session_state.get("sales_structured_data")
        if structured_obj:
            title_len = len(structured_obj.title)
            char_badge = f"🟢 {title_len}/99 chars" if title_len <= 99 else f"🔴 {title_len}/99 chars"
            st.markdown(f"**Listing Title** ({char_badge})")
            st.subheader(structured_obj.title)
            st.metric("Asking Price", structured_obj.price_formatted)

        st.text_area(
            "Full Listing Copy Block (Copy-Paste Ready)",
            value=st.session_state.sales_generated_text,
            height=260,
            key="sales_copy_output_text",
        )

        st.code(st.session_state.sales_generated_text, language="markdown")


# ============================================================================
# Tab 5: 📤 Card Ladder CSV Export
# ============================================================================

def render_tab_export(db_path: str):
    """Tab 5: Card Ladder 16-Column CSV Export with fuzzy normalization and chunking."""
    st.subheader("📤 Card Ladder CSV Export")
    st.caption("Generate pristine 16-column Card Ladder CSV files with fuzzy player/set normalization and leading-zero preservation.")

    e_col1, e_col2, e_col3 = st.columns(3)
    with e_col1:
        export_status = st.selectbox(
            "AI Status Filter",
            options=["CLEARED", "ALL", "REVIEW VARIATION", "NEEDS REVIEW"],
            index=0,
            key="export_status_select",
        )
    with e_col2:
        apply_norm = st.checkbox(
            "Apply Canonical Player/Set Normalization",
            value=True,
            key="export_norm_checkbox",
        )
    with e_col3:
        output_filename = st.text_input(
            "Base Output Filename",
            value="CardLadder_Bulk_Upload.csv",
            key="export_filename_text",
        )

    # Preview matching records
    matching_rows = fetch_records_for_export(db_path=db_path, status_filter=export_status)
    preview_df = cards_to_card_ladder_dataframe(matching_rows, apply_normalization=apply_norm)

    st.write(f"**Export Scope:** {len(matching_rows)} matching records selected.")
    if len(matching_rows) > 0:
        st.dataframe(preview_df.head(10), use_container_width=True, hide_index=True)
    else:
        st.info("No cards match the selected status filter for export.")

    st.markdown(
        """
        <div style="background-color:#1e293b; padding:8px 12px; border-radius:6px; margin:8px 0;">
            <small>✅ 16 Exact Columns Preserved | Leading Zeros Intact on Card Number | 5 Internal Fields Excluded</small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🚀 Export to Card Ladder CSV", key="btn_export_csv", use_container_width=True):
        if len(matching_rows) == 0:
            st.warning("No records to export. Please adjust status filter.")
        else:
            try:
                total_exported, generated_paths = export_card_ladder_csv(
                    db_path=db_path,
                    output_path=output_filename,
                    status_filter=export_status,
                    max_batch_size=500,
                    apply_normalization=apply_norm,
                )
                validations = [validate_card_ladder_csv(p) for p in generated_paths]
                st.session_state.export_file_paths = generated_paths
                st.session_state.export_row_count = total_exported
                st.session_state.export_validation_result = validations
                st.toast(f"Exported {total_exported} cards across {len(generated_paths)} file(s)!", icon="📤")
            except Exception as e:
                st.error(f"Export failed: {e}")

    # Render Download Buttons
    export_paths = st.session_state.get("export_file_paths", [])
    if export_paths:
        st.markdown("---")
        st.markdown("### 📥 Download Station")

        validations = st.session_state.get("export_validation_result", [])
        all_valid = all(v.get("valid", False) for v in validations) if validations else True
        if all_valid:
            st.success("✅ Forensic Validation Passed: Exact 16 columns verified, 0 internal fields leaked, leading zeroes intact.")
        else:
            st.error(f"Forensic validation error: {validations}")

        if len(export_paths) == 1:
            path = export_paths[0]
            if os.path.exists(path):
                with open(path, "rb") as f:
                    file_bytes = f.read()
                st.download_button(
                    label=f"📥 Download {os.path.basename(path)} ({st.session_state.export_row_count} records)",
                    data=file_bytes,
                    file_name=os.path.basename(path),
                    mime="text/csv",
                    key="btn_download_single_csv",
                    use_container_width=True,
                )
        else:
            # Multiple chunked parts
            for idx, p in enumerate(export_paths, start=1):
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        data_bytes = f.read()
                    st.download_button(
                        label=f"📥 Download Part {idx}: {os.path.basename(p)}",
                        data=data_bytes,
                        file_name=os.path.basename(p),
                        mime="text/csv",
                        key=f"btn_download_part_{idx}",
                    )

            # In-memory ZIP bundle
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for p in export_paths:
                    if os.path.exists(p):
                        zip_file.write(p, arcname=os.path.basename(p))
            zip_buffer.seek(0)

            st.download_button(
                label="📦 Download All Chunks (ZIP Bundle)",
                data=zip_buffer,
                file_name="CardLadder_Exports.zip",
                mime="application/zip",
                key="btn_download_zip",
                use_container_width=True,
            )


# ============================================================================
# Tab 6: 🌐 API Bridge & System Health
# ============================================================================

def render_tab_health(db_path: str):
    """Tab 6: FastAPI Background Bridge, SQLite Storage, and System Diagnostics."""
    st.subheader("🌐 API Bridge & System Health")

    # FastAPI Daemon Section
    st.markdown("#### ⚡ FastAPI Chrome Extension Daemon (Port 8002)")
    port_active = is_port_in_use(8002)

    col1, col2 = st.columns(2)
    with col1:
        if port_active:
            st.success("🟢 API Server is ACTIVE on `http://127.0.0.1:8002`")
            st.markdown("[📖 Open Interactive Swagger Docs](http://127.0.0.1:8002/docs)")
        else:
            st.warning("🔴 API Server is OFFLINE on port 8002")

    with col2:
        if not port_active:
            if st.button("▶️ Start Background API Server", key="btn_start_api"):
                try:
                    server_thread = get_or_start_api_server(port=8002, db_path=db_path)
                    st.toast("FastAPI Daemon started on port 8002!", icon="🚀")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not start API daemon: {e}")
        else:
            st.info("API server is running as a managed background thread.")

    st.markdown("##### Chrome Extension Capture Example")
    sample_curl = """curl -X POST "http://127.0.0.1:8002/api/v1/cards/capture" \\
  -H "Content-Type: application/json" \\
  -d '{
    "player": "Luka Dončić",
    "year": "2020",
    "set_name": "Panini Prizm",
    "variation": "Silver Prizm",
    "card_number": "75",
    "category": "Basketball",
    "condition": "PSA 10",
    "slab_serial_number": "48192041",
    "investment": 150.00,
    "estimated_value": 350.00,
    "parent_image_id": "8492"
  }'"""
    st.code(sample_curl, language="bash")

    st.divider()

    # SQLite Storage & Diagnostics
    st.markdown("#### 🗄️ Database & Storage Diagnostics")
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        st.write(f"**Database Path:** `{db_path}`")
        db_size_kb = 0.0
        if os.path.exists(db_path):
            db_size_kb = os.path.getsize(db_path) / 1024.0
        st.write(f"**File Size:** `{db_size_kb:.2f} KB`")
        st.write("**Journal Mode:** `WAL (Write-Ahead Logging)`")
        st.write("**Busy Timeout:** `5000ms`")

    with d_col2:
        card_count = get_card_count(db_path=db_path)
        pct_used = min(100.0, (card_count / 500.0) * 100.0)
        st.write(f"**Staging Capacity:** {card_count} / 500 Cards ({pct_used:.1f}%)")
        st.progress(pct_used / 100.0)
        if card_count >= 500:
            st.error("⚠️ 500-Card Batch Circuit Breaker Limit Reached! Export or clear cards.")

    # Breakdown by category
    stats = get_summary_stats(db_path=db_path)
    cat_counts = stats.get("count_by_category", {})
    if cat_counts:
        st.markdown("##### Distribution by Category")
        cat_df = pd.DataFrame(
            [{"Category": k, "Count": v} for k, v in cat_counts.items()]
        ).sort_values("Count", ascending=False)
        st.dataframe(cat_df, use_container_width=True, hide_index=True)


# ============================================================================
# Main Application Entry Point
# ============================================================================

def main():
    """Application main entry point."""
    st.set_page_config(
        page_title="Sports Card Ecosystem Hub",
        page_icon="🃏",
        layout="wide",
    )

    init_session_state()
    render_custom_css()

    active_db = st.session_state.db_path
    try:
        init_db(active_db)
    except Exception as e:
        st.error(f"Database initialization error: {e}")

    render_header(active_db)

    stats = get_summary_stats(active_db)
    render_kpi_bar(stats)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Portfolio Staging",
        "📸 AI Vision Ingest",
        "📋 Checklist Scraper",
        "🏷️ Sales Copy Generator",
        "📤 Card Ladder Export",
        "🌐 API Bridge & Health",
    ])

    with tab1:
        render_tab_staging(active_db)

    with tab2:
        render_tab_vision(active_db)

    with tab3:
        render_tab_scraper(active_db)

    with tab4:
        render_tab_sales(active_db)

    with tab5:
        render_tab_export(active_db)

    with tab6:
        render_tab_health(active_db)


if __name__ == "__main__":
    main()
