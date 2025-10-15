"""
Energy Management System (EMS) Web Application
Streamlit-based interface for EMS simulation and analysis
Version 3.0 - Cement & Concrete Industrial Design
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from datetime import datetime
from ems_engine import EMSEngine

# Page configuration
st.set_page_config(
    page_title="EMS Industrial Simulator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cement & Concrete Industrial CSS
st.markdown("""
<style>
    /* Main Header - Industrial Style */
    .main-header {
        font-size: 3rem;
        font-weight: 900;
        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1.5rem 0;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* Subheader */
    .sub-header {
        font-size: 1.3rem;
        color: #718096;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 400;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Industrial Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
        border: 2px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px -3px rgba(0, 0, 0, 0.15);
        border-color: #cbd5e0;
    }
    
    /* Industrial Status Boxes */
    .success-box {
        background: linear-gradient(135deg, #f0fff4 0%, #e6fffa 100%);
        border: 2px solid #9ae6b4;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: #2d3748;
    }
    
    .warning-box {
        background: linear-gradient(135deg, #fffaf0 0%, #feebc8 100%);
        border: 2px solid #fbd38d;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: #2d3748;
    }
    
    .danger-box {
        background: linear-gradient(135deg, #fed7d7 0%, #fed7d7 100%);
        border: 2px solid #fc8181;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: #2d3748;
    }
    
    /* Industrial Sidebar */
    .css-1d391kg {
        background-color: #2d3748;
    }
    
    /* Tab Styling - Industrial */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: #edf2f7;
        padding: 4px;
        border-radius: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #e2e8f0;
        border-radius: 6px;
        padding: 12px 24px;
        font-weight: 600;
        color: #4a5568;
        border: 1px solid #cbd5e0;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #2d3748;
        color: white;
        border-color: #2d3748;
    }
    
    /* Industrial Button Styling */
    .stButton button {
        background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
        color: white;
        border: 2px solid #4a5568;
        border-radius: 6px;
        padding: 12px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(45, 55, 72, 0.3);
    }
    
    /* File Uploader - Industrial */
    .uploadedFile {
        background-color: #f7fafc;
        border: 2px dashed #cbd5e0;
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Number Input Styling */
    .stNumberInput input {
        border: 2px solid #e2e8f0;
        border-radius: 6px;
    }
    
    .stNumberInput input:focus {
        border-color: #4a5568;
        box-shadow: 0 0 0 1px #4a5568;
    }
    
    /* Expander Styling */
    .streamlit-expanderHeader {
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'simulation_run' not in st.session_state:
    st.session_state.simulation_run = False
if 'results' not in st.session_state:
    st.session_state.results = None

# Industrial Header Section
st.markdown('<div class="main-header">⚡ EMS INDUSTRIAL SIMULATOR</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Precision Energy Management for Industrial Applications</div>', unsafe_allow_html=True)

# Sidebar - Industrial Design
with st.sidebar:
    st.markdown("### 🎯 PROJECT CONFIGURATION")
    
    # Project Info
    with st.expander("🌍 PROJECT LOCATION", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            country = st.text_input("Country", value="Malaysia")
        with col2:
            city = st.text_input("City", value="Penang")
    
    # Data Upload Section
    with st.expander("📊 LOAD DATA UPLOAD", expanded=True):
        uploaded_file = st.file_uploader(
            "UPLOAD LOAD PROFILE (CSV)", 
            type=['csv'],
            help="Upload CSV with 'timestamp' and 'load' columns"
        )
        
        load_df = None
        if uploaded_file is not None:
            try:
                load_df = pd.read_csv(uploaded_file)
                load_df.columns = load_df.columns.str.lower().str.strip()
                load_df['timestamp'] = pd.to_datetime(load_df['timestamp'])
                
                st.success(f"✅ LOADED {len(load_df)} DATA POINTS")
                
                with st.expander("📋 DATA PREVIEW", expanded=False):
                    st.dataframe(load_df.head(6), use_container_width=True)
                    
            except Exception as e:
                st.error(f"❌ ERROR: {e}")
    
    # System Configuration
    with st.expander("🔧 SYSTEM CONFIGURATION", expanded=True):
        st.markdown("#### ☀️ PV SYSTEM")
        
        col1, col2 = st.columns(2)
        with col1:
            pv_capacity = st.number_input(
                "PV CAPACITY (KWP)", 
                min_value=0.0, 
                value=9109.1, 
                step=100.0
            )
        with col2:
            system_loss = st.number_input(
                "SYSTEM LOSS (%)", 
                min_value=0.0, 
                max_value=50.0, 
                value=14.0, 
                step=1.0
            ) / 100
        
        inverter_capacity = st.number_input(
            "INVERTER CAPACITY (KW)", 
            min_value=0.0, 
            value=9109.1,
            step=100.0
        )
        
        # Inverter sizing analysis
        if pv_capacity > 0:
            inverter_ratio = (inverter_capacity / pv_capacity * 100)
            if inverter_ratio < 100:
                st.error(f"⚠️ UNDERSIZED: {inverter_ratio:.1f}%")
            elif inverter_ratio > 130:
                st.warning(f"🔧 OVERSIZED: {inverter_ratio:.1f}%")
            else:
                st.success(f"✅ OPTIMAL: {inverter_ratio:.1f}%")
        
        st.markdown("#### 🔋 BATTERY STORAGE")
        
        col1, col2 = st.columns(2)
        with col1:
            battery_capacity = st.number_input(
                "BATTERY CAPACITY (MWH)", 
                min_value=0.0, 
                value=7.5, 
                step=0.5
            )
        with col2:
            max_discharge = st.number_input(
                "MAX DISCHARGE (KW)", 
                min_value=0.0, 
                value=2000.0, 
                step=100.0
            )
    
    # Target Settings
    with st.expander("🎯 CONTROL STRATEGY", expanded=True):
        target_md = st.number_input(
            "TARGET MD (KW)", 
            min_value=0.0, 
            value=6500.0, 
            step=100.0
        )
    
    # Financial Parameters
    with st.expander("💰 FINANCIAL PARAMETERS", expanded=True):
        capex = st.number_input(
            "TOTAL CAPEX (RM)", 
            min_value=0.0, 
            value=4861625.0, 
            step=10000.0,
            format="%.0f"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            md_charge = st.number_input(
                "MD CHARGE (RM/KW)", 
                min_value=0.0, 
                value=97.0, 
                step=1.0
            )
        with col2:
            peak_rate = st.number_input(
                "PEAK RATE (RM/KWH)", 
                min_value=0.0, 
                value=0.31, 
                step=0.01
            )
        
        offpeak_rate = st.number_input(
            "OFF-PEAK RATE (RM/KWH)", 
            min_value=0.0, 
            value=0.27, 
            step=0.01
        )

# Main Content Area
if load_df is not None:
    # Run Simulation Section
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_button = st.button(
            "🚀 EXECUTE SIMULATION", 
            type="primary", 
            use_container_width=True
        )
    
    if run_button:
        with st.spinner("🔄 RUNNING INDUSTRIAL SIMULATION..."):
            try:
                config = {
                    'location': {'name': f"{city}, {country}"},
                    'pv_system': {
                        'total_capacity_kwp': pv_capacity,
                        'system_loss': system_loss,
                        'inverter_capacity_kw': inverter_capacity
                    },
                    'ems_config': {
                        'target_md': target_md,
                        'max_discharge_power': max_discharge,
                        'battery_capacity': battery_capacity,
                        'initial_soe': 60
                    },
                    'financial': {
                        'capex': capex,
                        'md_charge': md_charge,
                        'peak_energy_rate': peak_rate,
                        'offpeak_energy_rate': offpeak_rate
                    }
                }
                
                engine = EMSEngine(config)
                results = engine.run_simulation(load_df)
                
                st.session_state.simulation_run = True
                st.session_state.results = results
                st.success("✅ SIMULATION COMPLETED")
                
            except Exception as e:
                st.error(f"❌ SIMULATION ERROR: {e}")

# Display Results - Industrial Style
if st.session_state.simulation_run and st.session_state.results is not None:
    results = st.session_state.results
    
    st.markdown("---")
    st.markdown("## 📊 SIMULATION RESULTS")
    
    # Industrial Metric Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                "MD REDUCTION", 
                f"{results['analysis']['total_reduction']:.0f} kW",
                delta=f"-{results['analysis']['total_reduction']/results['analysis']['md_no_pv_no_ems']*100:.1f}%"
            )
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                "ANNUAL SAVINGS", 
                f"RM {results['analysis']['annual_savings']:,.0f}"
            )
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                "PAYBACK PERIOD", 
                f"{results['analysis']['payback_years']:.1f} years"
            )
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                "10-YEAR ROI", 
                f"{results['analysis']['roi_10yr']:.1f}%"
            )
            st.markdown('</div>', unsafe_allow_html=True)
    
    # System Alerts
    if 'inverter_clipping' in results['analysis']:
        clipping = results['analysis']['inverter_clipping']
        if clipping['hours'] > 0:
            if clipping['percentage'] > 5:
                st.markdown(f"""
                <div class="danger-box">
                    <h4>🚨 SIGNIFICANT INVERTER CLIPPING</h4>
                    <p><strong>Duration:</strong> {clipping['hours']:.1f} hours ({clipping['percentage']:.2f}%)</p>
                    <p><strong>Capacity:</strong> {clipping['capacity_kw']:.0f} kW</p>
                    <p><strong>Energy Lost:</strong> ~{clipping.get('energy_lost_kwh', 0):.0f} kWh</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="warning-box">
                    <h4>⚠️ MINOR INVERTER CLIPPING</h4>
                    <p><strong>Duration:</strong> {clipping['hours']:.1f} hours ({clipping['percentage']:.2f}%)</p>
                    <p><strong>Energy Lost:</strong> ~{clipping.get('energy_lost_kwh', 0):.0f} kWh</p>
                </div>
                """, unsafe_allow_html=True)
    
    # Enhanced Tabs with Aligned Charts
    tab1, tab2, tab3, tab4 = st.tabs(["📈 POWER ANALYTICS", "🔋 BATTERY PERFORMANCE", "💰 FINANCIAL ANALYSIS", "💡 OPTIMIZATION"])
    
    with tab1:
        st.markdown("#### 🏭 POWER FLOW ANALYSIS")
        
        # Get common time range for alignment
        time_data = results['data']['timestamp']
        common_xaxis = dict(
            range=[time_data.min(), time_data.max()],
            tickformat='%H:%M\n%d-%b',
            gridcolor='#e2e8f0',
            gridwidth=1,
            showgrid=True
        )
        
        common_layout = dict(
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='#2d3748'),
            xaxis=common_xaxis,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Power Generation vs Load - FIXED ALIGNMENT
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=time_data, 
            y=results['data']['load'],
            name='ELECTRICAL LOAD', 
            line=dict(color='#2d3748', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(45, 55, 72, 0.1)'
        ))
        fig1.add_trace(go.Scatter(
            x=time_data, 
            y=results['data']['pv_power'],
            name='PV GENERATION', 
            line=dict(color="#E9B715", width=2.5),
            fill='tozeroy',
            fillcolor='rgba(113, 128, 150, 0.2)'
        ))
        
        # Enhanced inverter limit
        fig1.add_hline(
            y=inverter_capacity, 
            line=dict(dash="dash", color="#e53e3e", width=3),
            annotation_text=f"INVERTER LIMIT: {inverter_capacity:.0f} kW",
            annotation_position="top left",
            annotation_font_size=12,
            annotation_font_color="#e53e3e"
        )
        
        fig1.update_layout(
            height=400,
            title="POWER GENERATION WITH INVERTER CLIPPING",
            yaxis_title="POWER (KW)",
            **common_layout
        )
        fig1.update_yaxes(gridcolor="#c9d9ee", gridwidth=1)
        st.plotly_chart(fig1, use_container_width=True)
        
        # MD Comparison Chart - FIXED ALIGNMENT with same x-axis
        st.markdown("#### 📉 MAXIMUM DEMAND ANALYSIS")
        fig2 = go.Figure()
        
        fig2.add_trace(go.Scatter(
            x=time_data, 
            y=results['data']['md30_no_pv_no_ems'],
            name='BASELINE (NO PV/EMS)', 
            line=dict(dash='dash', color='#2d3748', width=2.5)
        ))
        
        fig2.add_trace(go.Scatter(
            x=time_data, 
            y=results['data']['md30_with_pv_no_ems'],
            name='WITH PV ONLY', 
            line=dict(dash='dot', color="#F4C417", width=2.5)
        ))
        
        fig2.add_trace(go.Scatter(
            x=time_data, 
            y=results['data']['md30_with_pv_with_ems'],
            name='WITH PV + EMS', 
            line=dict(color="#0acfe9", width=3)
        ))
        
        fig2.add_hline(
            y=target_md, 
            line=dict(dash="solid", color="#38a169", width=2.5),
            annotation_text=f"TARGET MD: {target_md} kW",
            annotation_position="bottom right"
        )
        
        fig2.update_layout(
            height=400,
            title="MAXIMUM DEMAND COMPARISON",
            yaxis_title="30-MIN MD (KW)",
            **common_layout
        )
        fig2.update_yaxes(gridcolor='#e2e8f0', gridwidth=1)
        st.plotly_chart(fig2, use_container_width=True)
    
    with tab2:
        st.markdown("#### 🔋 BATTERY SYSTEM PERFORMANCE")
        
        # Battery Charts with aligned x-axis
        fig = make_subplots(
            rows=2, cols=1, 
            subplot_titles=("BATTERY POWER FLOW", "STATE OF ENERGY"),
            vertical_spacing=0.12,
            shared_xaxes=True  # This ensures x-axis alignment between subplots
        )
        
        discharge = np.where(results['data']['discharge'] > 0, results['data']['discharge'], 0)
        charge = np.where(results['data']['discharge'] < 0, -results['data']['discharge'], 0)
        
        fig.add_trace(go.Scatter(
            x=time_data, y=discharge,
            name='DISCHARGE', 
            fill='tozeroy', 
            line=dict(color="#125ee2", width=0),
            fillcolor='rgba(45, 55, 72, 0.7)'
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=time_data, y=-charge,
            name='CHARGE', 
            fill='tozeroy', 
            line=dict(color="#EFBC15", width=0),
            fillcolor='rgba(113, 128, 150, 0.7)'
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=time_data, y=results['data']['soe'],
            name='STATE OF ENERGY', 
            line=dict(color='#4a5568', width=3)
        ), row=2, col=1)
        
        fig.update_yaxes(title_text="POWER (KW)", row=1, col=1, gridcolor='#e2e8f0')
        fig.update_yaxes(title_text="SOE (%)", range=[0, 100], row=2, col=1, gridcolor='#e2e8f0')
        fig.update_xaxes(title_text="TIME", row=2, col=1, **common_xaxis)
        fig.update_layout(
            height=600, 
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='#2d3748')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Battery Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("BATTERY CYCLES", f"{results['analysis']['equivalent_cycles']:.2f}")
        with col2:
            st.metric("FINAL SOH", f"{results['analysis']['final_soh']:.1f}%")
        with col3:
            st.metric("EMS CONTRIBUTION", f"{results['analysis']['ems_contribution']:.0f} kW")
        with col4:
            total_discharge = results['analysis']['energy_metrics']['total_discharge_kwh'] / 1000
            st.metric("TOTAL DISCHARGE", f"{total_discharge:.1f} MWh")
    
    with tab3:
        st.markdown("#### 💰 FINANCIAL ANALYSIS")
        
        # Financial Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 📊 MD BREAKDOWN")
            md_fig = go.Figure(data=[
                go.Bar(
                    x=['BASELINE', 'PV ONLY', 'EMS CAPABILITY', 'FINAL'],
                    y=[
                        results['analysis']['md_no_pv_no_ems'],
                        results['analysis']['md_with_pv_no_ems'],
                        max_discharge,
                        results['analysis']['md_with_pv_with_ems']
                    ],
                    marker_color=['#2d3748', '#718096', '#4a5568', '#38a169'],
                    text=[
                        f"{results['analysis']['md_no_pv_no_ems']:.0f} kW",
                        f"{results['analysis']['md_with_pv_no_ems']:.0f} kW",
                        f"{max_discharge:.0f} kW",
                        f"{results['analysis']['md_with_pv_with_ems']:.0f} kW"
                    ],
                    textposition='outside'
                )
            ])
            md_fig.update_layout(
                yaxis_title="MD (KW)", 
                height=600, 
                showlegend=False,
                title="MAXIMUM DEMAND REDUCTION",
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(md_fig, use_container_width=True)
        
        with col2:
            st.markdown("##### 📈 PAYBACK ANALYSIS")
            years = np.arange(0, 11)
            cumulative = [results['analysis']['annual_savings'] * y - capex for y in years]
            
            payback_fig = go.Figure()
            payback_fig.add_trace(go.Scatter(
                x=years, y=cumulative, 
                mode='lines+markers',
                line=dict(color='#2d3748', width=3), 
                marker=dict(size=8, color='#2d3748')
            ))
            payback_fig.add_hline(
                y=0, 
                line_dash="dash", 
                line_color="#e53e3e"
            )
            payback_fig.update_layout(
                xaxis_title="YEARS", 
                yaxis_title="CUMULATIVE CASH FLOW (RM)", 
                height=600,
                title="PROJECT PAYBACK TIMELINE",
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(payback_fig, use_container_width=True)
        
        # Savings Breakdown
        st.markdown("##### 💵 MONTHLY SAVINGS BREAKDOWN")
        breakdown = results['analysis']['savings_breakdown']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("MD CHARGE SAVINGS", f"RM {breakdown['md_savings']:,.0f}")
        with col2:
            st.metric("PEAK ENERGY SAVINGS", f"RM {breakdown['peak_discharge_savings']:,.0f}")
        with col3:
            st.metric("OFF-PEAK SAVINGS", f"RM {breakdown['offpeak_discharge_savings']:,.0f}")
        with col4:
            st.metric("PV SELF-CONSUMPTION", f"RM {breakdown['pv_self_consumption_savings']:,.0f}")
    
    with tab4:
        st.markdown("#### 💡 OPTIMIZATION RECOMMENDATIONS")
        
        rec = results['recommendations']
        
        if rec['has_opportunity']:
            st.markdown(f"""
            <div class="warning-box">
                <h4>🎯 OPTIMIZATION OPPORTUNITY</h4>
                <p><strong>Current Utilization:</strong> {100-rec['utilization_rate']:.1f}% of BESS capacity</p>
                <p><strong>Remaining Capacity:</strong> {rec['remaining_capacity']:.0f} kW available</p>
                <p><strong>Recommended Target:</strong> {rec['suggested_target']:.0f} kW</p>
                <p><strong>Additional Annual Savings:</strong> RM {rec['extra_annual_savings']:,.0f}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="success-box">
                <h4>✅ OPTIMAL PERFORMANCE</h4>
                <p>System operating at optimal utilization levels.</p>
                <p><strong>Current Utilization:</strong> {100-rec.get('utilization_rate', 0):.1f}%</p>
            </div>
            """, unsafe_allow_html=True)

else:
    # Welcome/Instructions Section
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🎯 GETTING STARTED")
        st.markdown("""
        1. **📊 UPLOAD DATA**: Upload load profile CSV
        2. **🔧 CONFIGURE SYSTEM**: Set PV, battery, financial parameters  
        3. **🎯 SET TARGETS**: Define MD reduction goals
        4. **🚀 RUN SIMULATION**: Execute analysis
        5. **📈 REVIEW RESULTS**: Explore analytics
        """)
    
    with col2:
        st.markdown("### 📝 DATA FORMAT")
        sample = pd.DataFrame({
            'timestamp': [
                '2025-01-01 00:00:00', 
                '2025-01-01 00:05:00', 
                '2025-01-01 00:10:00'
            ],
            'load': [7500, 7450, 7600]
        })
        st.dataframe(sample, use_container_width=True)

# Industrial Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #718096; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;'>"
    "EMS INDUSTRIAL SIMULATOR v3.0 | PRECISION ENGINEERING | BUILT FOR INDUSTRY"
    "</p>", 
    unsafe_allow_html=True
)