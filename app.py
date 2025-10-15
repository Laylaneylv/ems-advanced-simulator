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
import json
import hashlib
from database import (
    create_user as db_create_user,
    fetch_user,
    get_simulation_details as db_get_simulation_details,
    get_user_simulations as db_get_user_simulations,
    init_db,
    save_simulation_result as db_save_simulation_result,
)
from ems_engine import EMSEngine

# Page configuration
st.set_page_config(
    page_title="ENERMERLION DYNAMIC EMS Simulator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables if present (supports .env files)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _format_simulation_date(value):
    """Format simulation timestamp from Supabase/SQLite."""
    if value is None:
        return "Unknown date"
    if isinstance(value, str):
        return value.split()[0]
    try:
        return value.strftime("%Y-%m-%d")
    except AttributeError:
        return str(value)


def render_header_card(title: str, subtitle: str | None = None, icon: str | None = None, *, login_style: bool = False) -> None:
    """Render a hero card style header."""
    subtitle_html = f'<div class="hero-card-subtitle">{subtitle}</div>' if subtitle else ""
    icon_html = f'<span class="icon">{icon}</span>' if icon else ""
    extra_class = " hero-card-login" if login_style else ""
    st.markdown(
        f"""
        <div class="hero-card{extra_class}">
            <div class="hero-card-title">{icon_html}{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, *, delta: str | None = None, delta_positive: bool | None = None) -> None:
    """Render a metric card with consistent styling."""
    delta_html = ""
    if delta is not None:
        delta_class = "metric-card-delta"
        if delta_positive is not None:
            delta_class += " positive" if delta_positive else " negative"
        delta_html = f'<div class="{delta_class}">{delta}</div>'
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title">{title}</div>
            <div class="metric-card-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

# Initialize database
init_db()

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# User authentication functions
def create_user(username, email, password, company):
    """Create a new user account"""
    password_hash = hash_password(password)
    return db_create_user(username, email, password_hash, company)

def verify_user(username, password):
    """Verify user credentials"""
    password_hash = hash_password(password)
    return fetch_user(username, password_hash)


def save_simulation_result(user_id, project_name, config, results):
    """Save simulation results to database"""
    return db_save_simulation_result(user_id, project_name, config, results)


def get_user_simulations(user_id):
    """Get all simulations for a user"""
    return db_get_user_simulations(user_id)


def get_simulation_details(simulation_id):
    """Get detailed simulation data by ID"""
    return db_get_simulation_details(simulation_id)
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
        background: linear-gradient(135deg, #f8fafc 0%, #eef2f8 100%);
        border: 1px solid #d4ddec;
        border-radius: 12px;
        padding: 1.3rem 1.5rem;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
        transition: box-shadow 0.25s ease, transform 0.25s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-3px) scale(1.01);
        box-shadow: 0 16px 38px rgba(15, 23, 42, 0.18);
    }
    
    .metric-card-title {
        text-transform: uppercase;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12rem;
        color: #475569;
        margin-bottom: 0.55rem;
    }
    
    .metric-card-value {
        font-size: 1.95rem;
        font-weight: 800;
        color: #1a202c;
        line-height: 1.1;
    }
    
    .metric-card-delta {
        font-size: 0.92rem;
        font-weight: 600;
        margin-top: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
    }
    
    .metric-card-delta.positive {
        color: #16a34a;
    }
    
    .metric-card-delta.negative {
        color: #dc2626;
    }
    
    .hero-card {
        background: linear-gradient(120deg, #f9fbff 0%, #e8effd 100%);
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        padding: 1.8rem 2.1rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 14px 40px rgba(15, 23, 42, 0.18);
    }
    
    .hero-card-title {
        font-size: 2.4rem;
        font-weight: 900;
        letter-spacing: 0.18rem;
        text-transform: uppercase;
        color: #1e293b;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    
    .hero-card-title span.icon {
        font-size: 2.6rem;
    }
    
    .hero-card-subtitle {
        margin-top: 0.6rem;
        font-size: 1.05rem;
        letter-spacing: 0.12rem;
        text-transform: uppercase;
        color: #475569;
        font-weight: 600;
    }
    
    .hero-card-login {
        background: linear-gradient(135deg, #f8fafc 0%, #edf2ff 100%);
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
    
    /* Auth Form Styling */
    .auth-form {
        background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 2rem;
        margin: 2rem auto;
        max-width: 500px;
        box-shadow: 0 8px 25px -8px rgba(0, 0, 0, 0.1);
    }
    
    .auth-header {
        text-align: center;
        margin-bottom: 2rem;
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
if 'include_pv_savings' not in st.session_state:
    st.session_state.include_pv_savings = True
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'show_login' not in st.session_state:
    st.session_state.show_login = True
if 'show_register' not in st.session_state:
    st.session_state.show_register = False
if 'loaded_project' not in st.session_state:  # NEW: For loaded projects
    st.session_state.loaded_project = None

# Authentication functions
def show_login_form():
    """Display login form"""
    render_header_card(
        title="ENERMERLION DYNAMIC EMS LOGIN",
        subtitle="Secure industrial access",
        icon="🔐",
        login_style=True,
    )
    st.markdown('<div class="auth-form">', unsafe_allow_html=True)
    st.markdown('<div class="auth-header"><h2>🔐 ENERMERLION DYNAMIC EMS LOGIN</h2></div>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("👤 USERNAME", placeholder="Enter your username")
        password = st.text_input("🔒 PASSWORD", type="password", placeholder="Enter your password")
        login_button = st.form_submit_button("🚀 LOGIN", use_container_width=True)
        
        if login_button:
            if username and password:
                user = verify_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.current_user = user
                    st.session_state.show_login = False
                    st.success(f"✅ Welcome back, {user['username']}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.error("❌ Please fill in all fields")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 CREATE ACCOUNT", use_container_width=True):
            st.session_state.show_login = False
            st.session_state.show_register = True
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_register_form():
    """Display registration form"""
    render_header_card(
        title="Create Industrial Account",
        subtitle="Provision secure access to EMS simulator",
        icon="🛠️",
        login_style=True,
    )
    st.markdown('<div class="auth-form">', unsafe_allow_html=True)
    st.markdown('<div class="auth-header"><h2>🚀 CREATE INDUSTRIAL ACCOUNT</h2></div>', unsafe_allow_html=True)
    
    with st.form("register_form"):
        username = st.text_input("👤 USERNAME", placeholder="Choose a username")
        email = st.text_input("📧 EMAIL", placeholder="Enter your email")
        company = st.text_input("🏢 COMPANY", placeholder="Your company name")
        password = st.text_input("🔒 PASSWORD", type="password", placeholder="Create a password")
        confirm_password = st.text_input("✅ CONFIRM PASSWORD", type="password", placeholder="Confirm your password")
        
        register_button = st.form_submit_button("🚀 CREATE ACCOUNT", use_container_width=True)
        
        if register_button:
            if not all([username, email, password, confirm_password]):
                st.error("❌ Please fill in all required fields")
            elif password != confirm_password:
                st.error("❌ Passwords do not match")
            elif len(password) < 6:
                st.error("❌ Password must be at least 6 characters")
            else:
                success = create_user(username, email, password, company)
                if success:
                    st.success("✅ Account created successfully! Please login.")
                    st.session_state.show_register = False
                    st.session_state.show_login = True
                    st.rerun()
                else:
                    st.error("❌ Username or email already exists")
    
    if st.button("⬅️ BACK TO LOGIN", use_container_width=True):
        st.session_state.show_register = False
        st.session_state.show_login = True
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def logout():
    """Logout user"""
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.session_state.show_login = True
    st.session_state.simulation_run = False
    st.session_state.results = None
    st.rerun()

# Show authentication forms if not authenticated
if not st.session_state.authenticated:
    if st.session_state.show_login:
        show_login_form()
    elif st.session_state.show_register:
        show_register_form()
    
    # Footer for auth pages
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #718096; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;'>"
        "ENERMERLION DYNAMIC EMS | SECURE SUCCESS | INDUSTRIAL GRADE"
        "</p>", 
        unsafe_allow_html=True
    )
    st.stop()

# Main application - only shown when authenticated
# Industrial Header Section
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    render_header_card(
        title="ENERMERLION DYNAMIC EMS SIMULATOR",
        subtitle="Precision Energy Management for Industrial Applications",
        icon="⚡",
    )

with col3:
    st.markdown(f"**👤 Welcome, {st.session_state.current_user['username']}**")
    if st.session_state.current_user['company']:
        st.markdown(f"**🏢 {st.session_state.current_user['company']}**")
    if st.button("🚪 LOGOUT", use_container_width=True):
        logout()

# Sidebar - Industrial Design
with st.sidebar:
    st.markdown("### 🎯 PROJECT CONFIGURATION")
    
    # Project Info with project name
    with st.expander("🌍 PROJECT LOCATION", expanded=True):
        project_name = st.text_input("PROJECT NAME", value=f"Project_{datetime.now().strftime('%Y%m%d_%H%M')}")
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
        
        # NEW: PV Savings Inclusion Option
        st.markdown("#### 📊 ROI CALCULATION OPTIONS")
        include_pv_savings = st.checkbox(
            "INCLUDE PV ENERGY SAVINGS IN ROI",
            value=True,
            help="When checked, PV energy savings are included in ROI calculation. Uncheck for BESS-only analysis."
        )
        st.session_state.include_pv_savings = include_pv_savings

    # User History Section
        # User History Section
        # User History Section
    with st.expander("📁 MY SIMULATIONS", expanded=False):
        simulations = get_user_simulations(st.session_state.current_user['id'])
        if simulations:
            st.markdown("**Recent Projects:**")
            display_options = [
                f"{name} ({_format_simulation_date(date)})"
                for sim_id, name, date in simulations
            ]
            
            # 垂直布局 - 更清晰
            selected_project = st.selectbox(
                "Select a project to load:",
                options=display_options,
                format_func=lambda x: x,
                key="project_selector"
            )
            
            # 全宽按钮
            if st.button("📂 LOAD SELECTED PROJECT", use_container_width=True):
                # 找到选中的项目
                selected_index = display_options.index(selected_project)
                selected_sim_id = simulations[selected_index][0]
                
                # 加载项目数据
                project_data = get_simulation_details(selected_sim_id)
                if project_data:
                    st.session_state.loaded_project = project_data
                    st.session_state.simulation_run = True
                    st.session_state.results = project_data['results']
                    st.session_state.include_pv_savings = project_data['config']['financial'].get('include_pv_savings', True)
                    st.success(f"✅ Project '{project_data['project_name']}' loaded successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to load project data")
            
            # 项目列表（可选）
            with st.expander("📋 Quick Load - Recent Projects", expanded=False):
                for (sim_id, name, date), display_name in zip(simulations[:5], display_options[:5]):  # 只显示最近5个
                    if st.button(f"📁 {display_name}", key=f"load_{sim_id}", use_container_width=True):
                        project_data = get_simulation_details(sim_id)
                        if project_data:
                            st.session_state.loaded_project = project_data
                            st.session_state.simulation_run = True
                            st.session_state.results = project_data['results']
                            st.session_state.include_pv_savings = project_data['config']['financial'].get('include_pv_savings', True)
                            st.success(f"✅ Project '{project_data['project_name']}' loaded!")
                            st.rerun()
        else:
            st.info("No simulations yet. Run your first analysis!")

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
                        'offpeak_energy_rate': offpeak_rate,
                        'include_pv_savings': st.session_state.include_pv_savings  # NEW: Pass the option to engine
                    }
                }
                
                engine = EMSEngine(config)
                results = engine.run_simulation(load_df)
                
                # Save simulation results to database
                save_success = save_simulation_result(
                    st.session_state.current_user['id'],
                    project_name,
                    config,
                    results
                )
                
                st.session_state.simulation_run = True
                st.session_state.results = results
                
                if save_success:
                    st.success("✅ SIMULATION COMPLETED & SAVED")
                else:
                    st.success("✅ SIMULATION COMPLETED")
                
            except Exception as e:
                st.error(f"❌ SIMULATION ERROR: {e}")

# Display Results - Industrial Style
if st.session_state.simulation_run and st.session_state.results is not None:
    results = st.session_state.results
    if st.session_state.loaded_project:
        st.markdown(f"### 📁 LOADED PROJECT: {st.session_state.loaded_project['project_name']}")
        if st.button("🔄 RETURN TO NEW SIMULATION", use_container_width=True):
            st.session_state.loaded_project = None
            st.session_state.simulation_run = False
            st.session_state.results = None
            st.rerun()
    st.markdown("---")
    st.markdown("## 📊 SIMULATION RESULTS")
    
    # Display PV Savings Inclusion Status
    savings_status = "INCLUDED" if st.session_state.include_pv_savings else "EXCLUDED"
    savings_color = "#38a169" if st.session_state.include_pv_savings else "#e53e3e"
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%); border: 2px solid {savings_color}; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
        <h4 style="margin: 0; color: {savings_color}; text-align: center;">
            📊 ROI ANALYSIS: PV ENERGY SAVINGS {savings_status}
        </h4>
        <p style="text-align: center; margin: 0.5rem 0 0 0; color: #4a5568;">
            { 'PV and BESS combined analysis' if st.session_state.include_pv_savings else 'BESS-only analysis (PV savings excluded)' }
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Industrial Metric Cards
    col1, col2, col3, col4 = st.columns(4)
    
    md_baseline = results['analysis']['md_no_pv_no_ems']
    md_reduction_pct = (
        (results['analysis']['total_reduction'] / md_baseline) * 100 if md_baseline else 0
    )
    with col1:
        render_metric_card(
            "MD REDUCTION",
            f"{results['analysis']['total_reduction']:.0f} kW",
            delta=f"-{md_reduction_pct:.1f}% vs baseline",
            delta_positive=True,
        )

    with col2:
        render_metric_card(
            "ANNUAL SAVINGS",
            f"RM {results['analysis']['annual_savings']:,.0f}"
        )

    with col3:
        render_metric_card(
            "PAYBACK PERIOD",
            f"{results['analysis']['payback_years']:.1f} years"
        )

    with col4:
        render_metric_card(
            "10-YEAR ROI",
            f"{results['analysis']['roi_10yr']:.1f}%"
        )

    core_peak_mwh = results['analysis'].get('energy_metrics', {}).get('core_peak_discharge_mwh')
    if core_peak_mwh is not None:
        core_col, _ = st.columns([1, 3])
        with core_col:
            render_metric_card(
                "CORE PEAK SHAVING (18-22H)",
                f"{core_peak_mwh:.2f} MWh"
            )
    
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
        
        # Display PV Savings Inclusion Note
        if not st.session_state.include_pv_savings:
            st.markdown(f"""
            <div class="warning-box">
                <h4>📊 NOTE: PV SAVINGS EXCLUDED</h4>
                <p>PV energy savings are currently excluded from ROI calculations. This analysis shows BESS-only financial performance.</p>
                <p><strong>PV Self-Consumption Savings:</strong> RM {breakdown['pv_self_consumption_savings']:,.0f} (excluded from totals)</p>
            </div>
            """, unsafe_allow_html=True)
    
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
        
        **NEW FEATURE**: Choose whether to include PV energy savings in ROI calculations for BESS-only analysis.
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
    "ENERMERLION DYNAMIC EMS SIMULATOR FROM EWISER_SG| APPLICATION ENGINEERING | BUILT FOR INDUSTRY"
    "</p>", 
    unsafe_allow_html=True
)
