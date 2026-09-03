import streamlit as st
import api_client
import pandas as pd
import json

st.set_page_config(page_title="FMCG Supply Chain AI", page_icon="🏭", layout="wide")

# ─── CSS ───
st.markdown("""
<style>
/* Modern styling for badges and cards */
.badge { padding:4px 12px; border-radius:20px; font-size:0.8em; font-weight:700; display:inline-block; letter-spacing:0.5px; box-shadow:0 2px 4px rgba(0,0,0,0.1); }
.badge-critical { background:linear-gradient(135deg, #ff4b4b, #d73838); color:white; }
.badge-high     { background:linear-gradient(135deg, #ff8c00, #e67e00); color:white; }
.badge-medium   { background:linear-gradient(135deg, #f5c400, #dcb000); color:#333; }
.badge-low      { background:linear-gradient(135deg, #21c354, #1da948); color:white; }
.badge-pending  { background:linear-gradient(135deg, #f5c400, #dcb000); color:#333; }
.badge-approved { background:linear-gradient(135deg, #21c354, #1da948); color:white; }
.badge-rejected { background:linear-gradient(135deg, #ff4b4b, #d73838); color:white; }
.badge-active   { background:linear-gradient(135deg, #1c83e1, #166bbb); color:white; }
.badge-resolved { background:linear-gradient(135deg, #888, #777); color:white; }
.badge-execute  { background:linear-gradient(135deg, #ff4b4b, #d73838); color:white; }
.badge-advisory { background:linear-gradient(135deg, #1c83e1, #166bbb); color:white; }
.badge-hold     { background:linear-gradient(135deg, #21c354, #1da948); color:white; }
.approval-card  { background:#fff8e1; border-left:6px solid #f5c400; padding:20px; border-radius:12px; margin:16px 0; box-shadow:0 4px 12px rgba(0,0,0,0.05); }
.approval-card-rejected { background:#ffeaea; border-left:6px solid #ff4b4b; }
.approval-card-approved { background:#f0fff0; border-left:6px solid #21c354; }
.disruption-card { background:#e8f4fd; border-left:6px solid #1c83e1; padding:16px 20px; border-radius:12px; margin:12px 0; box-shadow:0 4px 12px rgba(0,0,0,0.05); }
.calc-table th { background:#f0f2f6; font-weight:700; color:#444; }

/* Streamlit component overrides for better aesthetics */
[data-testid="stAlert"] {
    border-radius: 12px;
    border: none;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stAlert"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.12);
}
h1 {
    font-weight: 800 !important;
    background: -webkit-linear-gradient(45deg, #1c83e1, #904bc3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding-bottom: 5px;
}
div[data-testid="stMetricValue"] {
    font-weight: 700;
    color: #1e1e1e;
}

/* Rich Agent Cards */
.rich-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    border: 1px solid #f0f0f0;
    transition: all 0.3s ease;
    border-left: 8px solid #1c83e1;
}
.rich-card:hover {
    box-shadow: 0 12px 32px rgba(0,0,0,0.12);
    transform: translateY(-2px);
}
.rich-card.market { border-left-color: #8b5cf6; }
.rich-card.risk { border-left-color: #f59e0b; }
.rich-card.cfo { border-left-color: #10b981; }
.rich-card.strategy { border-left-color: #3b82f6; }
.rich-card.error { border-left-color: #ef4444; }
.rich-card.stopped { border-left-color: #6b7280; background: #f9fafb; }

.rich-card-header {
    display: flex;
    align-items: center;
    font-size: 1.25rem;
    font-weight: 800;
    color: #111827;
    margin-bottom: 16px;
    border-bottom: 2px solid #f3f4f6;
    padding-bottom: 12px;
}
.rich-card-header span {
    margin-right: 10px;
}
.rich-card-body {
    font-size: 1rem;
    color: #374151;
    line-height: 1.6;
}
.rich-table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 0.95rem;
}
.rich-table th, .rich-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #e5e7eb;
    text-align: left;
}
.rich-table th {
    background: #f9fafb;
    color: #4b5563;
    font-weight: 600;
}
.rich-table td:first-child {
    color: #6b7280;
}
.rich-table td:last-child {
    font-weight: 600;
    color: #111827;
}
.metric-row {
    display: flex;
    gap: 20px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}
.metric-box {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px 16px;
    flex: 1;
    min-width: 120px;
}
.metric-box-title {
    font-size: 0.8rem;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 4px;
    font-weight: 600;
}
.metric-box-val {
    font-size: 1.1rem;
    font-weight: 700;
    color: #111827;
}
.status-badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    background: #e5e7eb;
    color: #374151;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

# ─── Navigation ───
page = st.sidebar.selectbox("Navigation", [
    "🏠 Overview",
    "🗺️ Network Map",
    "🚨 Disruption Console",
    "🛡️ Admin Approvals",
    "⚡ Active Disruptions",
    "📦 Purchase Orders",
    "📜 Disruption Logs",
])


# ═══════════════════════════════════════════════════
#  PAGE: OVERVIEW
# ═══════════════════════════════════════════════════
if page == "🏠 Overview":
    st.title("🏭 FMCG Supply Chain — Live Dashboard")

    # Pending Approvals Alert
    pending = api_client.get_approvals(status="PENDING")
    if pending:
        st.error(f"⚠️ **{len(pending)} item(s) awaiting human approval** — go to 🛡️ Admin Approvals")

    # Active Disruptions Alert
    active_disruptions = api_client.get_active_disruptions()
    if active_disruptions:
        st.warning(f"🔴 **{len(active_disruptions)} active disruption(s)** being tracked — go to ⚡ Active Disruptions")

    st.divider()

    st.subheader("📡 Live News Scanner")
    scan_status = api_client.get_auto_scan_status()
    if scan_status:
        cols = st.columns(5)
        cols[0].metric("Scanner Status", scan_status.get("status", "Unknown"))
        cols[1].metric("Articles Fetched", scan_status.get("articles_fetched", 0))
        cols[2].metric("Threats Detected", scan_status.get("threats_detected", 0))
        cols[3].metric("Pipelines Triggered", scan_status.get("pipelines_triggered", 0))
        cols[4].metric("Scan Interval", f"{scan_status.get('scan_interval_minutes', '?')} min")

    st.divider()

    st.subheader("📦 Critical Material Inventory")
    inventory = api_client.get_inventory()
    if inventory:
        cols = st.columns(min(len(inventory), 6))
        for i, item in enumerate(inventory[:6]):
            days = item["days_remaining"]
            color = "normal" if days >= 10 else ("off" if days >= 5 else "inverse")
            cols[i % 6].metric(item["name"], f"{days:.1f} days", f"{item['current_stock']} {item['unit']}", delta_color=color)

    st.divider()

    st.subheader("📜 Recent Autonomous Actions (Last 20)")
    logs = api_client.get_logs()
    if logs:
        df = pd.DataFrame(logs[:20])
        cols_to_show = [c for c in ["timestamp", "pipeline_run_id", "affected_material_id", "severity_level", "source_event", "action_taken"] if c in df.columns]
        st.dataframe(df[cols_to_show], use_container_width=True)


# ═══════════════════════════════════════════════════
#  PAGE: NETWORK MAP
# ═══════════════════════════════════════════════════
elif page == "🗺️ Network Map":
    st.title("🗺️ Supply Chain Network")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🚛 Transport Routes")
        routes = api_client.get_routes()
        if routes:
            st.dataframe(pd.DataFrame(routes), use_container_width=True)
        else:
            st.info("No routes found.")
    with col2:
        st.subheader("🏢 Supplier Network")
        suppliers = api_client.get_suppliers()
        if suppliers:
            df = pd.DataFrame(suppliers)
            df["reliability_score"] = df["reliability_score"].apply(lambda x: f"{float(x)*100:.0f}%")
            st.dataframe(df[["supplier_id", "name", "location_region", "lead_time_days", "reliability_score"]], use_container_width=True)

    st.subheader("📅 Delivery Schedules")
    schedules = api_client.get_schedules()
    if schedules:
        st.dataframe(pd.DataFrame(schedules), use_container_width=True)


# ═══════════════════════════════════════════════════
#  PAGE: DISRUPTION CONSOLE
# ═══════════════════════════════════════════════════
elif page == "🚨 Disruption Console":
    st.title("🚨 Live Disruption Console")
    st.markdown("Enter a news event and watch the multi-agent AI pipeline **analyze and react** in real-time.")

    # Test Mode toggle
    col_input, col_toggle = st.columns([4, 1])
    with col_input:
        news_input = st.text_area(
            "Paste News Article:",
            "A major highway blockade is reported near Delhi on NH-58 due to a farmer protest. Trucks have been stuck for hours and officials say the blockade will continue for the next 48 hours.",
            height=100,
        )
    with col_toggle:
        st.markdown("**🧪 Test Mode**")
        test_mode = st.toggle(
            "Bypass dedup",
            value=False,
            help="Bypasses all dedup checks. Writes are tagged as test data and won't affect production.",
        )
        if test_mode:
            st.caption("🟡 Test writes will NOT block real POs")

    if st.button("🚀 Trigger AI Pipeline", type="primary"):
        st.divider()
        st.subheader(f"🧠 Live Agent Thoughts {'[🧪 TEST MODE]' if test_mode else ''}")

        pipeline_container = st.container()
        
        loading_html = """
        <div style="display:flex; align-items:center; justify-content:center; padding: 40px; background: #f9fafb; border-radius: 12px; border: 1px dashed #d1d5db; color: #6b7280; font-weight: 600; margin-bottom: 20px;">
            <div class="spinner" style="border: 4px solid rgba(0, 0, 0, 0.1); width: 24px; height: 24px; border-radius: 50%; border-left-color: #3b82f6; animation: spin 1s linear infinite; margin-right: 12px;"></div>
            <span>{text}</span>
            <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
        </div>
        """
        loading_placeholder = st.empty()
        loading_placeholder.markdown(loading_html.replace("{text}", "🔄 Processing Market Intel..."), unsafe_allow_html=True)
        
        summary_container = st.empty()

        try:
            for event in api_client.stream_disruption(news_input, test_mode=test_mode):
                agent = event.get("agent")
                data = event.get("data", {})
                pipeline_id = event.get("pipeline_run_id", "")

                if agent == "market_intel":
                    payload = data.get("threat_payload") or {}
                    conf = data.get("confidence_score", "?")
                    relevant = data.get("is_supply_chain_relevant", True)

                    if not relevant:
                        html = f"""
                        <div class="rich-card stopped">
                            <div class="rich-card-header"><span>🛑</span> Market Intel — NOT Relevant</div>
                            <div class="rich-card-body">
                                <p>This article is not related to our supply chain. Pipeline stopped early.</p>
                                <p><b>Confidence:</b> {conf}%</p>
                            </div>
                        </div>
                        """
                        pipeline_container.markdown(html, unsafe_allow_html=True)
                        loading_placeholder.empty()
                        continue

                    sev = (payload.get("severity") or "MEDIUM").upper()
                    event_type = (payload.get('event_type') or 'N/A').replace('_', ' ').title()
                    loc = payload.get('key_location', 'N/A')
                    reg = payload.get('region', 'N/A')
                    delay = payload.get('estimated_delay_days', '?')
                    comms = ', '.join(payload.get('affected_commodities', []))
                    summary = payload.get('summary', '')

                    html = f"""
                    <div class="rich-card market">
                        <div class="rich-card-header"><span>📰</span> Market Intel Complete</div>
                        <div class="rich-card-body">
                            <div class="metric-row">
                                <div class="metric-box"><div class="metric-box-title">Event Type</div><div class="metric-box-val">{event_type}</div></div>
                                <div class="metric-box"><div class="metric-box-title">Severity</div><div class="metric-box-val">{sev}</div></div>
                                <div class="metric-box"><div class="metric-box-title">Est. Delay</div><div class="metric-box-val">{delay} days</div></div>
                                <div class="metric-box"><div class="metric-box-title">Confidence</div><div class="metric-box-val">{conf}%</div></div>
                            </div>
                            <p><b>Location:</b> {loc} ({reg})</p>
                            <p><b>Affected Commodities:</b> {comms}</p>
                            <p><i>"{summary}"</i></p>
                        </div>
                    </div>
                    """
                    pipeline_container.markdown(html, unsafe_allow_html=True)
                    loading_placeholder.markdown(loading_html.replace("{text}", "🔄 Risk Assessment: Scanning logistics map..."), unsafe_allow_html=True)

                elif agent == "risk_assessment":
                    reasoning = data.get("risk_reasoning", "No reasoning.").replace('\n', '<br>')
                    risk_lvl = data.get("risk_level", "MEDIUM")
                    impacted = data.get("impacted_materials", [])
                    impacted_names = ", ".join([m.get("name", "?") for m in impacted]) if impacted else "None detected"

                    html = f"""
                    <div class="rich-card risk">
                        <div class="rich-card-header"><span>🗺️</span> Risk Assessment Complete</div>
                        <div class="rich-card-body">
                            <div class="metric-row">
                                <div class="metric-box"><div class="metric-box-title">Overall Risk</div><div class="metric-box-val">{risk_lvl}</div></div>
                                <div class="metric-box"><div class="metric-box-title">Materials at Risk</div><div class="metric-box-val">{impacted_names}</div></div>
                            </div>
                            <p><b>Full Reasoning:</b></p>
                            <p style="background: #f9fafb; padding: 12px; border-radius: 8px; font-size: 0.95em; color: #4b5563;">{reasoning}</p>
                        </div>
                    </div>
                    """
                    pipeline_container.markdown(html, unsafe_allow_html=True)
                    loading_placeholder.markdown(loading_html.replace("{text}", "🔄 CFO Analyst: Running financial calculations..."), unsafe_allow_html=True)

                elif agent == "financial_analyst":
                    analysis = data.get("financial_analysis", [])
                    approvals = data.get("approval_items", [])

                    body_html = ""
                    for item in analysis:
                        rec = item.get("recommendation", "HOLD_AND_MONITOR")
                        rec_label = {
                            "EXECUTE_BACKUP_PO": "<span class='status-badge' style='background:#fef2f2;color:#991b1b;'>🔴 EXECUTE BACKUP PO</span>",
                            "PROACTIVE_ADVISORY": "<span class='status-badge' style='background:#eff6ff;color:#1e40af;'>🔵 PROACTIVE ADVISORY</span>",
                            "HOLD_AND_MONITOR": "<span class='status-badge' style='background:#f0fdf4;color:#166534;'>🟢 HOLD & MONITOR</span>",
                        }.get(rec, f"<span class='status-badge'>{rec}</span>")
                        
                        best_alt = item.get("best_alternate") or {}
                        days_rem = item.get("days_remaining", 0)
                        delay = item.get("delay_days", 0)
                        idle_cost = item.get("factory_idle_cost", 0)
                        total_cost = item.get("total_cost", 0)
                        order_qty = item.get("order_qty", 0)
                        
                        body_html += f"<h4 style='margin-bottom:8px; color:#111827;'>{item.get('material_name', '?')} {rec_label}</h4>"
                        
                        table_html = "<table class='rich-table'>"
                        table_html += f"<tr><td>📅 Stock Remaining</td><td>{days_rem:.1f} days</td></tr>"
                        table_html += f"<tr><td>⏱️ Estimated Delay</td><td>{delay} days</td></tr>"
                        table_html += f"<tr><td>🏭 Factory Idle Cost</td><td>₹{idle_cost:,.0f}</td></tr>"
                        table_html += f"<tr><td>🏢 Primary Supplier</td><td>{item.get('primary_supplier_name', 'Unknown')}</td></tr>"
                        
                        if best_alt:
                            cap_note = " <span style='color:#ef4444;'>(capacity capped)</span>" if best_alt.get("capacity_capped") else ""
                            table_html += f"<tr><td>🔀 Backup Supplier</td><td>{best_alt.get('supplier_name', 'N/A')}</td></tr>"
                            table_html += f"<tr><td>📦 Order Quantity</td><td>{order_qty:,.1f} units{cap_note}</td></tr>"
                            table_html += f"<tr><td>💰 Total Cost</td><td>₹{total_cost:,.2f}</td></tr>"
                            table_html += f"<tr><td>⭐ Reliability</td><td>{best_alt.get('reliability_score', 0)*100:.0f}%</td></tr>"
                        table_html += "</table>"
                        
                        body_html += table_html
                        body_html += f"<p style='color:#4b5563;'><i>Rationale: {item.get('rationale', 'N/A')}</i></p><hr style='border:none;border-top:1px dashed #e5e7eb;margin:20px 0;'>"

                    for item in approvals:
                        trigger = item.get("trigger_reason", "UNKNOWN")
                        reason_label = "💰 Cost ceiling exceeded" if trigger == "COST_CEILING" else f"⚠️ Low confidence ({item.get('confidence_score')}%)"
                        body_html += f"<h4 style='margin-bottom:8px; color:#111827;'>{item.get('material_name', '?')} <span class='status-badge' style='background:#fef9c3;color:#854d0e;'>🟡 SENT TO APPROVAL QUEUE</span></h4>"
                        body_html += f"<p><b>Reason:</b> {reason_label}<br><b>Proposed Cost:</b> ₹{item.get('total_cost', 0):,.2f}</p>"
                        body_html += f"<p style='color:#6b7280;'><i>*A human admin must review and approve this PO.</i></p><hr style='border:none;border-top:1px dashed #e5e7eb;margin:20px 0;'>"

                    html = f"""
                    <div class="rich-card cfo">
                        <div class="rich-card-header"><span>💼</span> CFO Analyst Complete</div>
                        <div class="rich-card-body">
                            {body_html}
                        </div>
                    </div>
                    """
                    pipeline_container.markdown(html, unsafe_allow_html=True)
                    loading_placeholder.markdown(loading_html.replace("{text}", "🔄 Strategy Execution: Executing decisions..."), unsafe_allow_html=True)

                elif agent == "strategy_execution":
                    actions = data.get("recommended_actions", [])
                    exec_summary = data.get("executive_summary", "")

                    status_icons = {
                        "EXECUTED": "✅", "ADVISORY_SENT": "📧",
                        "HELD": "⏸️", "DEDUP_BLOCKED": "🛡️",
                        "SKIPPED": "⏭️", "ERROR": "❌",
                        "PENDING_APPROVAL": "🟡", "REVIEW_NEEDED": "⚠️",
                    }
                    
                    body_html = ""
                    for a in actions:
                        status = a.get("status", "")
                        icon = status_icons.get(status.split(" ")[0], "🔹")
                        body_html += f"<div style='background: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #e5e7eb;'>"
                        body_html += f"<div style='font-weight: 700; margin-bottom: 4px; color:#111827;'>{icon} {a.get('material', '?')} <span class='status-badge'>{status}</span></div>"
                        body_html += f"<div style='color: #4b5563; font-size: 0.95em;'>{a.get('action', 'N/A')}</div></div>"

                    html = f"""
                    <div class="rich-card strategy">
                        <div class="rich-card-header"><span>⚡</span> Strategy Execution Complete</div>
                        <div class="rich-card-body">
                            {body_html}
                        </div>
                    </div>
                    """
                    pipeline_container.markdown(html, unsafe_allow_html=True)

                    if exec_summary:
                        summary_container.info(
                            f"**📋 Executive Briefing** *(Pipeline `{pipeline_id}`{'  🧪 TEST' if test_mode else ''})*\n\n{exec_summary}"
                        )

                elif agent == "done":
                    loading_placeholder.empty()
                    if not test_mode:
                        st.balloons()
                    st.success(f"✅ Pipeline `{pipeline_id}` Complete! {'[TEST MODE — no real POs created]' if test_mode else ''}")

                elif agent == "error":
                    loading_placeholder.empty()
                    html = f"""
                    <div class="rich-card error">
                        <div class="rich-card-header"><span>❌</span> Pipeline Error</div>
                        <div class="rich-card-body">
                            <p>{event.get('error')}</p>
                        </div>
                    </div>
                    """
                    pipeline_container.markdown(html, unsafe_allow_html=True)
                    break

        except Exception as e:
            st.error(f"Connection failed: {e}")


# ═══════════════════════════════════════════════════
#  PAGE: ADMIN APPROVALS
# ═══════════════════════════════════════════════════
elif page == "🛡️ Admin Approvals":
    st.title("🛡️ Human Approval Queue")
    st.markdown("Review AI-flagged purchase orders that require human authorization before being placed.")

    tab_pending, tab_history = st.tabs(["🟡 Pending Approvals", "📚 Review History"])

    reviewer_name = st.sidebar.text_input("Your Name (Reviewer)", value="Admin", key="reviewer")

    with tab_pending:
        pending = api_client.get_approvals(status="PENDING")

        if not pending:
            st.success("✅ No pending approvals — all clear!")
        else:
            st.warning(f"**{len(pending)} item(s) awaiting your review**")

            for item in pending:
                trigger = item.get("trigger_reason", "UNKNOWN")
                trigger_label = "💰 Cost Ceiling Exceeded" if trigger == "COST_CEILING" else f"⚠️ Low AI Confidence ({item.get('confidence_score')}%)"
                severity = (item.get("severity") or "HIGH").upper()
                sev_class = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(severity, "high")

                with st.expander(
                    f"#{item['approval_id']} — {item['material_name']} | "
                    f"{trigger_label} | ₹{item.get('total_cost', 0):,.0f}",
                    expanded=True,
                ):
                    col_info, col_action = st.columns([3, 1])

                    with col_info:
                        st.markdown(f"**Pipeline:** `{item.get('pipeline_run_id', 'N/A')}`")
                        st.markdown(f"**Severity:** `{severity}`  |  **Confidence:** `{item.get('confidence_score', '?')}%`  |  **Trigger:** `{trigger}`")
                        st.markdown("---")

                        st.markdown("**📰 What Happened (Threat Summary)**")
                        st.info(item.get("threat_summary", "No threat summary available."))

                        st.markdown("**🗺️ Risk Analyst Reasoning**")
                        st.write(item.get("risk_reasoning", "No risk reasoning available."))

                        st.markdown("**💼 CFO Financial Decision & Calculations**")
                        st.warning(item.get("rationale", "No rationale available."))

                        st.markdown("**📦 Proposed Purchase Order**")
                        col_a, col_b, col_c = st.columns(3)
                        col_a.metric("Backup Supplier", item.get("backup_supplier_name", "N/A"))
                        col_b.metric("Order Quantity", f"{item.get('order_quantity', 0):,.1f} units")
                        col_c.metric("Total Cost", f"₹{item.get('total_cost', 0):,.2f}")

                    with col_action:
                        st.markdown("**Your Decision:**")
                        notes = st.text_area(
                            "Review Notes", key=f"notes_{item['approval_id']}",
                            placeholder="Optional: explain your decision"
                        )
                        if st.button("✅ APPROVE", key=f"approve_{item['approval_id']}", type="primary"):
                            result = api_client.decide_approval(
                                item["approval_id"], "APPROVED", reviewer_name, notes
                            )
                            if result.get("po_id"):
                                st.success(f"✅ Approved! PO #{result['po_id']} created.")
                                st.rerun()
                            else:
                                st.error(f"Error: {result}")

                        if st.button("❌ REJECT", key=f"reject_{item['approval_id']}"):
                            if not notes:
                                st.error("Please provide a reason for rejection in the notes.")
                            else:
                                result = api_client.decide_approval(
                                    item["approval_id"], "REJECTED", reviewer_name, notes
                                )
                                if "decision" in result:
                                    st.success("❌ Rejected and logged.")
                                    st.rerun()
                                else:
                                    st.error(f"Error: {result}")

    with tab_history:
        approved = api_client.get_approvals(status="APPROVED")
        rejected = api_client.get_approvals(status="REJECTED")
        history = approved + rejected
        history.sort(key=lambda x: x.get("reviewed_at") or "", reverse=True)

        if not history:
            st.info("No review history yet.")
        else:
            for item in history:
                status = item["status"]
                icon = "✅" if status == "APPROVED" else "❌"
                po_note = f"→ PO Created" if status == "APPROVED" else "→ Rejected"
                with st.expander(
                    f"{icon} #{item['approval_id']} — {item['material_name']} | "
                    f"₹{item.get('total_cost', 0):,.0f} | {po_note} | "
                    f"Reviewed by: {item.get('reviewed_by', '?')} at {(item.get('reviewed_at') or 'N/A')[:16]}"
                ):
                    st.markdown(f"**Trigger:** `{item.get('trigger_reason')}`  |  **Confidence:** `{item.get('confidence_score')}%`")
                    st.markdown(f"**CFO Rationale:** {item.get('rationale', 'N/A')}")
                    st.markdown(f"**Review Notes:** {item.get('review_notes') or 'None'}")


# ═══════════════════════════════════════════════════
#  PAGE: ACTIVE DISRUPTIONS
# ═══════════════════════════════════════════════════
elif page == "⚡ Active Disruptions":
    st.title("⚡ Active Disruption Tracker")
    st.markdown(
        "All real-world events currently being tracked. "
        "**Mark as Resolved** when the situation is cleared to allow new POs for the same region/event type."
    )

    disruptions = api_client.get_active_disruptions()

    if not disruptions:
        st.success("✅ No active disruptions — supply chain is operating normally.")
    else:
        st.warning(f"🔴 **{len(disruptions)} active disruption(s)** detected")

        for d in disruptions:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f"**#{d['disruption_id']}** — `{d['event_type'].replace('_', ' ').title()}` "
                    f"in **{d['region']}** | Detected: {(d.get('detected_at') or '')[:16]}  \n"
                    f"**Action Taken:** {d.get('action_taken', 'N/A')}  |  "
                    f"**Confidence:** {d.get('confidence_score', '?')}%  |  "
                    f"**Pipeline:** `{d.get('pipeline_run_id', 'N/A')}`"
                )
            with col2:
                if st.button("✅ Resolve", key=f"resolve_{d['disruption_id']}"):
                    result = api_client.resolve_disruption(d["disruption_id"])
                    if result.get("status") == "RESOLVED":
                        st.success(f"Disruption #{d['disruption_id']} resolved.")
                        st.rerun()
                    else:
                        st.error(str(result))
            st.divider()


# ═══════════════════════════════════════════════════
#  PAGE: PURCHASE ORDERS
# ═══════════════════════════════════════════════════
elif page == "📦 Purchase Orders":
    st.title("📦 Purchase Orders")
    pos = api_client.get_purchase_orders()
    if not pos:
        st.info("No purchase orders yet.")
    else:
        for po in pos:
            status = po.get("status", "UNKNOWN")
            status_color = {
                "ISSUED": "#f5c400",
                "CONFIRMED": "#1c83e1",
                "SHIPPED": "#8b5cf6",
                "DELIVERED": "#21c354",
                "CANCELLED": "#ef4444"
            }.get(status, "#6b7280")
            
            with st.expander(f"📦 PO #{po['po_id']} | Status: {status} | ₹{po.get('total_cost', 0):,.2f}"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Material ID", po.get("material_id"))
                col2.metric("Supplier ID", po.get("supplier_id"))
                col3.metric("Quantity", f"{po.get('order_quantity', 0):,.1f}")
                
                st.markdown(f"**Pipeline Run ID:** `{po.get('pipeline_run_id', 'N/A')}`")
                st.markdown(f"**Created At:** {po.get('created_at')}")
                st.markdown("---")
                
                # Status Update Form
                st.markdown("**Update Status**")
                new_status = st.selectbox(
                    "New Status", 
                    ["ISSUED", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"], 
                    index=["ISSUED", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"].index(status) if status in ["ISSUED", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"] else 0,
                    key=f"status_{po['po_id']}"
                )
                if st.button("Update Status", key=f"btn_{po['po_id']}"):
                    if new_status != status:
                        result = api_client.update_po_status(po['po_id'], new_status)
                        if result:
                            st.success(f"✅ Status updated to **{new_status}**")
                            st.rerun()
                        else:
                            st.error("Update failed")
                    else:
                        st.info("Status is already " + status)


# ═══════════════════════════════════════════════════
#  PAGE: DISRUPTION LOGS
# ═══════════════════════════════════════════════════
elif page == "📜 Disruption Logs":
    st.title("📜 All Disruption Logs")
    logs = api_client.get_logs()
    if not logs:
        st.info("No disruption logs yet.")
    else:
        for log in logs:
            severity = log.get("severity_level", "UNKNOWN")
            sev_class = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(severity, "medium")
            test_badge = " <span class='badge badge-hold'>TEST DATA</span>" if log.get("is_test") else ""
            
            with st.expander(f"📝 Log #{log['log_id']} | {log['disruption_type']} | {severity}"):
                st.markdown(f"**Pipeline Run ID:** `{log.get('pipeline_run_id', 'N/A')}`{test_badge}", unsafe_allow_html=True)
                st.markdown(f"**Timestamp:** {log.get('timestamp')}")
                st.markdown("---")
                
                st.markdown("**📰 Source Event**")
                st.info(log.get("source_event", "N/A"))
                
                st.markdown("**⚡ Action Taken (Reasoning & Result)**")
                st.success(log.get("action_taken", "N/A"))
                
                if log.get("estimated_cost") or log.get("estimated_avoided_loss"):
                    col1, col2 = st.columns(2)
                    col1.metric("Estimated Cost", f"₹{log.get('estimated_cost', 0):,.2f}")
                    col2.metric("Avoided Loss", f"₹{log.get('estimated_avoided_loss', 0):,.2f}")
