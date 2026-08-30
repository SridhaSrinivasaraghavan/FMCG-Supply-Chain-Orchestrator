import streamlit as st
import api_client
import pandas as pd
import json

st.set_page_config(page_title="Autonomous FMCG Supply Chain", page_icon="🏭", layout="wide")

# Navigation
page = st.sidebar.selectbox("Navigation", ["🏠 Overview", "🗺️ Network map", "🚨 Disruption Console"])

if page == "🏠 Overview":
    st.title("🏭 Corporate Supply Chain Overview")
    
    # Auto Scan Status
    st.subheader("📡 Live News Scanner")
    scan_status = api_client.get_auto_scan_status()
    if scan_status:
        cols = st.columns(4)
        cols[0].metric("Scanner Status", scan_status.get("status", "Unknown"))
        cols[1].metric("Articles Fetched", scan_status.get("articles_fetched", 0))
        cols[2].metric("Threats Detected", scan_status.get("threats_detected", 0))
        cols[3].metric("Pipelines Triggered", scan_status.get("pipelines_triggered", 0))
        
    st.divider()
    
    # Inventory Gauges
    st.subheader("📦 Critical Material Inventory")
    inventory = api_client.get_inventory()
    if inventory:
        cols = st.columns(len(inventory))
        for i, item in enumerate(inventory):
            days = item['days_remaining']
            color = "normal"
            if days < 5:
                color = "inverse"
            elif days < 10:
                color = "off"
            cols[i].metric(label=item['name'], value=f"{days:.1f} days", delta=f"{item['current_stock']} {item['unit']}", delta_color=color)

    st.divider()
    
    # Recent Logs
    st.subheader("📜 Recent Autonomous Actions")
    logs = api_client.get_logs()
    if logs:
        df = pd.DataFrame(logs)
        st.dataframe(df[["timestamp", "affected_material_id", "severity_level", "source_event", "action_taken"]], use_container_width=True)


elif page == "🗺️ Network map":
    st.title("🗺️ Supply Chain Network")
    
    st.subheader("🏭 Factories")
    # Using raw mock data to represent the DB since we don't have a direct factory endpoint yet
    # But we can show routes and schedules
    routes = api_client.get_routes()
    if routes:
        df_routes = pd.DataFrame(routes)
        st.dataframe(df_routes, use_container_width=True)
    else:
        st.info("No active routes found.")
        
    st.subheader("📅 Delivery Schedules")
    schedules = api_client.get_schedules()
    if schedules:
        df_sched = pd.DataFrame(schedules)
        st.dataframe(df_sched, use_container_width=True)


elif page == "🚨 Disruption Console":
    st.title("🚨 Live Disruption Console")
    st.markdown("Enter a news event and watch the multi-agent AI pipeline analyze and react in real-time.")
    
    news_input = st.text_area("Paste News Article:", 
                 "Annual marathon on NH-44 near Bangalore announced for tomorrow. Total road closure from 6 AM to 2 PM. Heavy traffic expected post-marathon.",
                 height=100)
                 
    if st.button("Trigger AI Pipeline", type="primary"):
        st.divider()
        st.subheader("🧠 Live Agent Thoughts")
        
        # Containers for streaming output
        col1, col2 = st.columns(2)
        
        with col1:
            market_card = st.empty()
            risk_card = st.empty()
            
        with col2:
            cfo_card = st.empty()
            strategy_card = st.empty()
            
        # Initialize empty states
        market_card.info("⏳ Market Intel: Waiting...")
        risk_card.info("⏳ Risk Assessment: Waiting...")
        cfo_card.info("⏳ Financial Analyst (CFO): Waiting...")
        strategy_card.info("⏳ Strategy Execution: Waiting...")
        
        # Stream from backend
        try:
            for event in api_client.stream_disruption(news_input):
                agent = event.get("agent")
                data = event.get("data", {})
                
                if agent == "market_intel":
                    payload = data.get("threat_payload", {})
                    market_card.success(f"**📰 Market Intel Complete**\n\n**Event:** {payload.get('event_type')}\n\n**Severity:** {payload.get('severity')}\n\n**Summary:** {payload.get('summary')}")
                    risk_card.warning("🔄 Risk Assessment: Analyzing logistics map...")
                    
                elif agent == "risk_assessment":
                    reasoning = data.get("risk_reasoning", "")
                    risk_card.success(f"**🗺️ Risk Assessment Complete**\n\n{reasoning}")
                    cfo_card.warning("🔄 CFO Analyst: Calculating costs and checking policies...")
                    
                elif agent == "financial_analyst":
                    analysis = data.get("financial_analysis", [])
                    cfo_text = "**💼 CFO Analyst Complete**\n\n"
                    for item in analysis:
                        cfo_text += f"- **{item['material_name']}**: {item['recommendation']}\n  - *Rationale*: {item['rationale']}\n"
                    cfo_card.success(cfo_text)
                    strategy_card.warning("🔄 Strategy Execution: Drafting executive summary...")
                    
                elif agent == "strategy_execution":
                    exec_summary = data.get("executive_summary", "")
                    actions = data.get("recommended_actions", [])
                    strat_text = "**⚡ Strategy Execution Complete**\n\n"
                    for a in actions:
                        strat_text += f"- 🛠️ {a['action']} ({a['status']})\n"
                    strat_text += f"\n---\n**Executive Briefing:**\n{exec_summary}"
                    strategy_card.success(strat_text)
                    
                elif agent == "done":
                    st.balloons()
                    st.success("Pipeline Execution Complete!")
                    
                elif agent == "error":
                    st.error(f"Pipeline Error: {event.get('error')}")
                    break
        except Exception as e:
            st.error(f"Connection failed: {e}")
