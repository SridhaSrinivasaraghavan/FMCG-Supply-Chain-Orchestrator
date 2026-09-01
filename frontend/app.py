import streamlit as st
import api_client
import pandas as pd
import json

st.set_page_config(page_title="FMCG Supply Chain AI", page_icon="🏭", layout="wide")

# ─── CSS ───
st.markdown("""
<style>
.badge { padding:2px 10px; border-radius:20px; font-size:0.78em; font-weight:700; display:inline-block; }
.badge-critical { background:#ff4b4b; color:white; }
.badge-high     { background:#ff8c00; color:white; }
.badge-medium   { background:#f5c400; color:#333; }
.badge-low      { background:#21c354; color:white; }
.badge-pending  { background:#f5c400; color:#333; }
.badge-approved { background:#21c354; color:white; }
.badge-rejected { background:#ff4b4b; color:white; }
.badge-active   { background:#1c83e1; color:white; }
.badge-resolved { background:#888; color:white; }
.badge-execute  { background:#ff4b4b; color:white; }
.badge-advisory { background:#1c83e1; color:white; }
.badge-hold     { background:#21c354; color:white; }
.approval-card  { background:#fff8e1; border-left:5px solid #f5c400; padding:16px; border-radius:8px; margin:12px 0; }
.approval-card-rejected { background:#ffeaea; border-left:5px solid #ff4b4b; }
.approval-card-approved { background:#f0fff0; border-left:5px solid #21c354; }
.disruption-card { background:#e8f4fd; border-left:5px solid #1c83e1; padding:12px 16px; border-radius:8px; margin:8px 0; }
.calc-table th { background:#f0f2f6; font-weight:600; }
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

        col1, col2 = st.columns(2)
        with col1:
            market_card = st.empty()
            risk_card = st.empty()
        with col2:
            cfo_card = st.empty()
            strategy_card = st.empty()
        summary_container = st.empty()

        market_card.info("⏳ Market Intel: Waiting...")
        risk_card.info("⏳ Risk Assessment: Waiting...")
        cfo_card.info("⏳ CFO Analyst: Waiting...")
        strategy_card.info("⏳ Strategy Execution: Waiting...")

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
                        market_card.warning(
                            f"**📰 Market Intel — NOT Relevant**\n\n"
                            f"This article is not related to our supply chain. Pipeline stopped early.\n\n"
                            f"**Confidence:** {conf}%"
                        )
                        continue

                    sev = (payload.get("severity") or "MEDIUM").upper()
                    market_card.success(
                        f"**📰 Market Intel Complete**\n\n"
                        f"**Event:** {(payload.get('event_type') or 'N/A').replace('_', ' ').title()}  \n"
                        f"**Region:** {payload.get('region', 'N/A')}  \n"
                        f"**Location:** {payload.get('key_location', 'N/A')}  \n"
                        f"**Severity:** `{sev}`  \n"
                        f"**Est. Delay:** {payload.get('estimated_delay_days', '?')} days *(inferred from event type)*  \n"
                        f"**Confidence Score:** {conf}%  \n"
                        f"**Commodities:** {', '.join(payload.get('affected_commodities', []))}  \n\n"
                        f"**Summary:** _{payload.get('summary', '')}_"
                    )
                    risk_card.warning("🔄 Risk Assessment: Scanning logistics map...")

                elif agent == "risk_assessment":
                    reasoning = data.get("risk_reasoning", "No reasoning.")
                    risk_lvl = data.get("risk_level", "MEDIUM")
                    impacted = data.get("impacted_materials", [])
                    impacted_names = ", ".join([m.get("name", "?") for m in impacted]) if impacted else "None detected"

                    risk_card.success(
                        f"**🗺️ Risk Assessment Complete**\n\n"
                        f"**Overall Risk:** `{risk_lvl}`  \n"
                        f"**Materials at Risk:** {impacted_names}  \n\n"
                        f"**Full Reasoning:**\n{reasoning}"
                    )
                    cfo_card.warning("🔄 CFO Analyst: Running financial calculations...")

                elif agent == "financial_analyst":
                    analysis = data.get("financial_analysis", [])
                    approvals = data.get("approval_items", [])

                    cfo_lines = "**💼 CFO Analyst Complete**\n\n"

                    for item in analysis:
                        rec = item.get("recommendation", "HOLD_AND_MONITOR")
                        rec_label = {
                            "EXECUTE_BACKUP_PO": "🔴 EXECUTE BACKUP PO",
                            "PROACTIVE_ADVISORY": "🔵 PROACTIVE ADVISORY",
                            "HOLD_AND_MONITOR": "🟢 HOLD & MONITOR",
                        }.get(rec, rec)
                        best_alt = item.get("best_alternate") or {}
                        days_rem = item.get("days_remaining", 0)
                        delay = item.get("delay_days", 0)
                        idle_cost = item.get("factory_idle_cost", 0)
                        total_cost = item.get("total_cost", 0)
                        order_qty = item.get("order_qty", 0)

                        cfo_lines += f"---\n**{item.get('material_name', '?')}** → {rec_label}\n\n"
                        cfo_lines += (
                            f"| Metric | Value |\n|--------|-------|\n"
                            f"| 📅 Stock Remaining | **{days_rem:.1f} days** |\n"
                            f"| ⏱️ Estimated Delay | **{delay} days** |\n"
                            f"| 🏭 Factory Idle Cost | **₹{idle_cost:,.0f}** |\n"
                            f"| 🏢 Primary Supplier | {item.get('primary_supplier_name', 'Unknown')} |\n"
                        )
                        if best_alt:
                            cap_note = " *(capacity capped)*" if best_alt.get("capacity_capped") else ""
                            cfo_lines += (
                                f"| 🔀 Backup Supplier | {best_alt.get('supplier_name', 'N/A')} |\n"
                                f"| 📦 Order Quantity | {order_qty:,.1f} units{cap_note} |\n"
                                f"| 💰 Total Cost | **₹{total_cost:,.2f}** |\n"
                                f"| ⭐ Reliability | {best_alt.get('reliability_score', 0)*100:.0f}% |\n"
                            )
                        cfo_lines += f"\n*Rationale: {item.get('rationale', 'N/A')}*\n\n"

                    for item in approvals:
                        trigger = item.get("trigger_reason", "UNKNOWN")
                        reason_label = "💰 Cost exceeds ₹1,00,000 ceiling" if trigger == "COST_CEILING" else f"⚠️ Low confidence ({item.get('confidence_score')}%)"
                        cfo_lines += (
                            f"---\n**{item.get('material_name', '?')}** → 🟡 SENT TO APPROVAL QUEUE\n\n"
                            f"**Reason:** {reason_label}  \n"
                            f"**Proposed Cost:** ₹{item.get('total_cost', 0):,.2f}  \n"
                            f"*A human admin must review and approve this PO.*\n\n"
                        )

                    cfo_card.success(cfo_lines)
                    strategy_card.warning("🔄 Strategy Execution: Executing decisions...")

                elif agent == "strategy_execution":
                    actions = data.get("recommended_actions", [])
                    exec_summary = data.get("executive_summary", "")

                    status_icons = {
                        "EXECUTED": "✅", "ADVISORY_SENT": "📧",
                        "HELD": "⏸️", "DEDUP_BLOCKED": "🛡️",
                        "SKIPPED": "⏭️", "ERROR": "❌",
                        "PENDING_APPROVAL": "🟡", "REVIEW_NEEDED": "⚠️",
                    }
                    strat_lines = "**⚡ Strategy Execution Complete**\n\n"
                    for a in actions:
                        status = a.get("status", "")
                        icon = status_icons.get(status.split(" ")[0], "🔹")
                        strat_lines += f"{icon} **{a.get('material', '?')}**: `{status}`\n\n_{a.get('action', 'N/A')}_\n\n"

                    strategy_card.success(strat_lines)

                    if exec_summary:
                        summary_container.info(
                            f"**📋 Executive Briefing** *(Pipeline `{pipeline_id}`{'  🧪 TEST' if test_mode else ''})*\n\n{exec_summary}"
                        )

                elif agent == "done":
                    if not test_mode:
                        st.balloons()
                    st.success(f"✅ Pipeline `{pipeline_id}` Complete! {'[TEST MODE — no real POs created]' if test_mode else ''}")

                elif agent == "error":
                    st.error(f"Pipeline Error: {event.get('error')}")
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
    if pos:
        df = pd.DataFrame(pos)
        st.dataframe(df, use_container_width=True)
        st.divider()
        st.subheader("✏️ Update PO Status")
        po_ids = [p["po_id"] for p in pos]
        selected_po = st.selectbox("Select PO", po_ids, format_func=lambda x: f"PO #{x}")
        new_status = st.selectbox("New Status", ["CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"])
        if st.button("Update Status"):
            result = api_client.update_po_status(selected_po, new_status)
            if result:
                st.success(f"✅ PO #{selected_po}: status updated to **{new_status}**")
            else:
                st.error("Update failed")
    else:
        st.info("No purchase orders yet.")


# ═══════════════════════════════════════════════════
#  PAGE: DISRUPTION LOGS
# ═══════════════════════════════════════════════════
elif page == "📜 Disruption Logs":
    st.title("📜 All Disruption Logs")
    logs = api_client.get_logs()
    if logs:
        df = pd.DataFrame(logs)
        cols_to_show = [c for c in ["log_id", "timestamp", "pipeline_run_id", "affected_material_id", "severity_level", "source_event", "action_taken", "is_test"] if c in df.columns]
        st.dataframe(df[cols_to_show], use_container_width=True)
    else:
        st.info("No disruption logs yet.")
