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
from datetime import datetime, time
import json
import hashlib
import textwrap
import plotly.io as pio
import logging
try:
    from fpdf import FPDF
    try:
        from fpdf.enums import XPos, YPos
    except Exception:
        XPos = YPos = None
except ImportError:
    FPDF = None
    XPos = YPos = None
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


def _parse_time_value(value: str | None, fallback: time) -> time:
    """Parse HH:MM string into time; return fallback on failure."""
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return fallback


# --- Currency handling helpers ------------------------------------------------
CURRENCY_PRESETS = [
    {
        "aliases": {"malaysia", "my", "myr", "malaysian"},
        "code": "MYR",
        "symbol": "RM",
        "name": "Malaysian Ringgit",
        "rate_to_myr": 1.0,
    },
    {
        "aliases": {"singapore", "sg", "sgp"},
        "code": "SGD",
        "symbol": "S$",
        "name": "Singapore Dollar",
        "rate_to_myr": 3.45,
    },
    {
        "aliases": {"united states", "usa", "us", "america", "american"},
        "code": "USD",
        "symbol": "$",
        "name": "US Dollar",
        "rate_to_myr": 4.70,
    },
    {
        "aliases": {"euro", "europe", "germany", "france", "italy", "spain", "netherlands"},
        "code": "EUR",
        "symbol": "€",
        "name": "Euro",
        "rate_to_myr": 5.10,
    },
    {
        "aliases": {"united kingdom", "uk", "britain", "england", "great britain"},
        "code": "GBP",
        "symbol": "£",
        "name": "British Pound",
        "rate_to_myr": 6.00,
    },
    {
        "aliases": {"australia", "au", "aus"},
        "code": "AUD",
        "symbol": "A$",
        "name": "Australian Dollar",
        "rate_to_myr": 3.10,
    },
    {
        "aliases": {"china", "cn", "prc", "chinese"},
        "code": "CNY",
        "symbol": "¥",
        "name": "Chinese Yuan",
        "rate_to_myr": 0.65,
    },
    {
        "aliases": {"japan", "jp", "japanese"},
        "code": "JPY",
        "symbol": "¥",
        "name": "Japanese Yen",
        "rate_to_myr": 0.032,
    },
    {
        "aliases": {"south korea", "korea", "kr"},
        "code": "KRW",
        "symbol": "₩",
        "name": "South Korean Won",
        "rate_to_myr": 0.0035,
    },
    {
        "aliases": {"india", "in", "indian"},
        "code": "INR",
        "symbol": "₹",
        "name": "Indian Rupee",
        "rate_to_myr": 0.056,
    },
    {
        "aliases": {"indonesia", "id", "indo"},
        "code": "IDR",
        "symbol": "Rp",
        "name": "Indonesian Rupiah",
        "rate_to_myr": 0.00032,
    },
    {
        "aliases": {"thailand", "th", "thai"},
        "code": "THB",
        "symbol": "฿",
        "name": "Thai Baht",
        "rate_to_myr": 0.13,
    },
    {
        "aliases": {"vietnam", "vn", "viet"},
        "code": "VND",
        "symbol": "₫",
        "name": "Vietnamese Dong",
        "rate_to_myr": 0.00020,
    },
    {
        "aliases": {"philippines", "ph", "philippine"},
        "code": "PHP",
        "symbol": "₱",
        "name": "Philippine Peso",
        "rate_to_myr": 0.085,
    },
]

DEFAULT_CURRENCY_PROFILE = CURRENCY_PRESETS[0]

FINANCIAL_FIELD_DEFAULTS_MYR = {
    "capex": 4_861_625.0,
    "md_charge": 97.0,
    "peak_rate": 0.31,
    "offpeak_rate": 0.27,
}

FINANCIAL_FIELD_STEPS_MYR = {
    "capex": 10_000.0,
    "md_charge": 0.001,
    "peak_rate": 0.001,
    "offpeak_rate": 0.001,
}

FINANCIAL_FIELD_FORMATS = {
    "capex": "%.0f",
    "md_charge": "%.3f",
    "peak_rate": "%.3f",
    "offpeak_rate": "%.3f",
}

FINANCIAL_CONFIG_KEYS = {
    "capex": "capex",
    "md_charge": "md_charge",
    "peak_rate": "peak_energy_rate",
    "offpeak_rate": "offpeak_energy_rate",
}


def _normalize_country(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _format_hour_label(value) -> str:
    """Format hour value (string HH:MM or decimal) into HH:MM."""
    if isinstance(value, str) and ":" in value:
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "00:00"
    hour = int(numeric) % 24
    minute = int(round((numeric - hour) * 60)) % 60
    return f"{hour:02d}:{minute:02d}"


def _build_pdf_report(project_name: str, config: dict, results: dict) -> bytes:
    """Generate a PDF report summarizing the simulation."""
    if FPDF is None:
        raise RuntimeError("PDF export requires the 'fpdf2' package.")

    analysis = results.get('analysis', {}) or {}
    financial = config.get('financial', {}) or {}
    ems_config = config.get('ems_config', {}) or {}
    location = config.get('location', {}) or {}

    currency_symbol = financial.get('currency_symbol') or financial.get('currency_code', '')
    currency_code = financial.get('currency_code', '')
    currency_display = f"{currency_symbol or ''} ({currency_code})".strip()

    def _fmt_currency(value, decimals=0):
        try:
            amount = float(value)
        except (TypeError, ValueError):
            amount = 0.0
        format_str = f"{{:,.{decimals}f}}"
        if not currency_symbol:
            return format_str.format(amount)
        return f"{currency_symbol} {format_str.format(amount)}"

    def _fmt_number(value, decimals=2, unit=""):
        try:
            num = float(value)
        except (TypeError, ValueError):
            return f"0{unit}"
        format_str = f"{{:,.{decimals}f}}"
        return f"{format_str.format(num)}{unit}"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)

    def _pdf_safe(text: str) -> str:
        try:
            text.encode("latin-1")
            return text
        except UnicodeEncodeError:
            return text.encode("latin-1", "replace").decode("latin-1")

    def _cell_line(width, height, text):
        text = _pdf_safe(text)
        if XPos and YPos:
            pdf.cell(width, height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.cell(width, height, text, ln=True)
    bullet = "- "

    def _write_lines(lines):
        for line in lines:
            wrapped_lines = textwrap.wrap(
                line,
                width=90,
                break_long_words=False,
                replace_whitespace=False,
            )
            if not wrapped_lines:
                wrapped_lines = [line or " "]
            for segment in wrapped_lines:
                segment = _pdf_safe(segment)
                pdf.set_x(pdf.l_margin)
                if XPos and YPos:
                    pdf.multi_cell(0, 6, segment, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                else:
                    pdf.multi_cell(0, 6, segment, ln=True)

    _cell_line(0, 10, "EnerMerlion EMS Simulation Report")

    pdf.set_font("Helvetica", "", 11)
    _cell_line(0, 7, f"Project: {project_name}")
    _cell_line(0, 7, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    location_label = ", ".join(filter(None, [location.get('city'), location.get('country')])) or location.get('name') or "N/A"
    _cell_line(0, 7, f"Site: {location_label}")
    if currency_display:
        _cell_line(0, 7, f"Currency: {currency_display}")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    _cell_line(0, 8, "Key Highlights")
    pdf.set_font("Helvetica", "", 10)
    highlights = [
        f"{bullet}Maximum Demand Reduction: {_fmt_number(analysis.get('total_reduction'), 0, ' kW')}",
        f"{bullet}Annual Savings: {_fmt_currency(analysis.get('annual_savings'), 2)}",
    ]
    payback = analysis.get('payback_years')
    highlights.append(f"{bullet}Payback Period: {'N/A' if payback in (None, float('inf')) else _fmt_number(payback, 1, ' years')}")
    control_label = analysis.get('control_mode', 'time_of_control').replace('_', ' ').title()
    highlights.append(f"{bullet}Control Mode: {control_label}")
    _write_lines(highlights)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    _cell_line(0, 8, "System Configuration")
    pdf.set_font("Helvetica", "", 10)
    system_lines = [
        f"{bullet}BESS Capacity: {_fmt_number(ems_config.get('battery_capacity'), 2, ' MWh')}",
        f"{bullet}Max Discharge Power: {_fmt_number(ems_config.get('max_discharge_power'), 0, ' kW')}",
        f"{bullet}Initial SoE: {_fmt_number(ems_config.get('initial_soe'), 1, ' %')}",
        f"{bullet}Target MD: {_fmt_number(ems_config.get('target_md'), 0, ' kW')}",
    ]
    _write_lines(system_lines)

    if analysis.get('control_mode') == 'time_of_use':
        tou_report = analysis.get('time_of_use_report') or {}
        charge_window = tou_report.get('charge_window') or {}
        discharge_window = tou_report.get('discharge_window') or {}
        _write_lines([
            f"{bullet}Charge Window: {_format_hour_label(charge_window.get('start_hour'))} - "
            f"{_format_hour_label(charge_window.get('end_hour'))}",
            f"{bullet}Discharge Window: {_format_hour_label(discharge_window.get('start_hour'))} - "
            f"{_format_hour_label(discharge_window.get('end_hour'))}",
        ])
        min_soe = tou_report.get('min_soe_target', ems_config.get('min_soe'))
        if min_soe is not None:
            _write_lines([f"{bullet}Minimum SoE Target: {_fmt_number(min_soe, 1, ' %')}"])
        last_leftover = tou_report.get('last_leftover') or {}
        remaining_pct = last_leftover.get('excess_above_min_pct', tou_report.get('final_excess_pct', 0))
        remaining_energy = last_leftover.get('excess_energy_kwh', tou_report.get('final_excess_energy_kwh', 0))
        if remaining_pct and remaining_pct > 0:
            timestamp_label = last_leftover.get('timestamp')
            _write_lines([
                f"{bullet}Remaining SoE after discharge: {_fmt_number(remaining_pct, 1, ' %')} "
                f"({_fmt_number(remaining_energy, 0, ' kWh')})"
                + (f" at {timestamp_label}" if timestamp_label else "")
            ])
        else:
            _write_lines([f"{bullet}Remaining SoE after discharge: Fully utilized to minimum threshold."])
    elif analysis.get('control_mode') == 'time_of_control':
        toc_extension = analysis.get('time_of_control_extension') or {}
        if toc_extension:
            initial_excess = float(toc_extension.get('initial_excess_pct') or 0.0)
            extension_energy = float(toc_extension.get('extension_energy_kwh') or 0.0)
            intervals = int(toc_extension.get('extension_intervals') or 0)
            completed = toc_extension.get('completed')
            _write_lines([
                f"{bullet}Post-day discharge utilization: {initial_excess:.1f}% above minimum "
                f"(~{_fmt_number(extension_energy, 0, ' kWh')})."
            ])
            status_text = "completed" if completed else "incomplete"
            _write_lines([f"{bullet}Extension run {status_text} across {intervals} additional intervals."])

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    _cell_line(0, 8, "Energy Performance")
    pdf.set_font("Helvetica", "", 10)
    energy_metrics = analysis.get('energy_metrics', {}) or {}
    energy_lines = [
        f"{bullet}Core Peak Discharge: {_fmt_number(energy_metrics.get('core_peak_discharge_mwh'), 2, ' MWh')}",
        f"{bullet}Total BESS Discharge: {_fmt_number(energy_metrics.get('total_discharge_kwh'), 0, ' kWh')}",
        f"{bullet}PV Self-Consumption: {_fmt_number(energy_metrics.get('pv_self_consumption_kwh'), 0, ' kWh')}",
    ]
    _write_lines(energy_lines)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    _cell_line(0, 8, "Battery Health")
    pdf.set_font("Helvetica", "", 10)
    _write_lines([
        f"{bullet}Final SoH: {_fmt_number(analysis.get('final_soh'), 2, ' %')}",
        f"{bullet}Equivalent Cycles: {_fmt_number(analysis.get('equivalent_cycles'), 2)}",
    ])

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    _cell_line(0, 8, "Financial Inputs")
    pdf.set_font("Helvetica", "", 10)
    financial_lines = [
        f"{bullet}CAPEX: {_fmt_currency(financial.get('capex'))}",
        f"{bullet}MD Charge: {_fmt_currency(financial.get('md_charge'), 3)} per kW",
        f"{bullet}Peak Energy Rate: {_fmt_currency(financial.get('peak_energy_rate'), 3)} per kWh",
        f"{bullet}Off-Peak Energy Rate: {_fmt_currency(financial.get('offpeak_energy_rate'), 3)} per kWh",
        f"{bullet}PV savings are {('included' if analysis.get('include_pv_savings', True) else 'excluded')} in ROI calculations.",
    ]
    _write_lines(financial_lines)

    output_data = pdf.output(dest="S")
    if isinstance(output_data, (bytes, bytearray)):
        return bytes(output_data)
    return output_data.encode("latin-1")


def _build_html_report(project_name: str, config: dict, results: dict, currency_profile: dict) -> bytes:
    """Generate an HTML report containing inputs, key metrics, charts, and recommendations."""
    analysis = results.get("analysis", {}) or {}
    recommendations = results.get("recommendations", {}) or {}
    raw_df = results.get("data")
    chart_df = pd.DataFrame(raw_df).copy() if isinstance(raw_df, (pd.DataFrame, list, dict)) else pd.DataFrame()
    if not chart_df.empty:
        chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])

    financial_cfg = config.get("financial", {})
    ems_cfg = config.get("ems_config", {})
    pv_cfg = config.get("pv_system", {})
    location_cfg = config.get("location", {})

    def _fmt(value, decimals=2, suffix=""):
        try:
            return f"{float(value):,.{decimals}f}{suffix}"
        except (TypeError, ValueError):
            return f"0{suffix}"

    def _fmt_currency_html(value, decimals=2):
        return _format_currency(float(value or 0.0), currency_profile, decimals=decimals)

    logger = logging.getLogger(__name__)
    power_fig_html = ""
    soe_fig_html = ""
    savings_fig_html = ""
    md_fig_html = ""

    if not chart_df.empty:
        time_series = chart_df["timestamp"]
        raw_load = chart_df.get("load")
        raw_pv = chart_df.get("pv_power")
        raw_discharge = chart_df.get("discharge")
        raw_soe = chart_df.get("soe")
        logger.info(
            "HTML report raw column types | load=%s | pv=%s | discharge=%s | soe=%s",
            type(raw_load), type(raw_pv), type(raw_discharge), type(raw_soe)
        )

        load_series = pd.to_numeric(raw_load, errors="coerce")
        pv_series = pd.to_numeric(raw_pv, errors="coerce")
        discharge_series = pd.to_numeric(raw_discharge, errors="coerce").fillna(0)
        soe_series = pd.to_numeric(raw_soe, errors="coerce")

        logger.info(
            "HTML report series stats | load min=%s max=%s | soe min=%s max=%s | discharge min=%s max=%s",
            getattr(load_series, "min", lambda: None)(),
            getattr(load_series, "max", lambda: None)(),
            getattr(soe_series, "min", lambda: None)(),
            getattr(soe_series, "max", lambda: None)(),
            getattr(discharge_series, "min", lambda: None)(),
            getattr(discharge_series, "max", lambda: None)(),
        )

        time_vals = time_series.tolist()
        load_vals = load_series.astype(float).tolist() if load_series is not None else []
        pv_vals = pv_series.astype(float).tolist() if pv_series is not None else []
        discharge_vals = [val if val > 0 else 0 for val in discharge_series.astype(float).tolist()] if discharge_series is not None else []
        charge_vals = [abs(val) if val < 0 else 0 for val in discharge_series.astype(float).tolist()] if discharge_series is not None else []
        soe_vals = soe_series.astype(float).tolist() if soe_series is not None else []

        x_start = min(time_vals) if time_vals else None
        x_end = max(time_vals) if time_vals else None

        power_fig = go.Figure()
        if load_vals:
            power_fig.add_trace(go.Scatter(x=time_vals, y=load_vals, name="Electrical Load", line=dict(color="#2d3748")))
        if pv_vals:
            power_fig.add_trace(go.Scatter(x=time_vals, y=pv_vals, name="PV Generation", line=dict(color="#E9B715")))
        if discharge_vals:
            power_fig.add_trace(go.Scatter(x=time_vals, y=discharge_vals, name="BESS Discharge", line=dict(color="#125ee2")))
        if charge_vals and any(charge_vals):
            power_fig.add_trace(go.Scatter(x=time_vals, y=charge_vals, name="BESS Charge", line=dict(color="#fb7185")))
        tick_vals = pd.date_range(start=x_start, end=x_end, periods=6) if x_start and x_end else None
        power_fig.update_layout(
            title="Power Flow Overview",
            xaxis_title="Timestamp",
            yaxis_title="kW",
            template="plotly_white",
            xaxis=dict(range=[x_start, x_end], tickvals=tick_vals, tickformat="%H:%M\n%d-%b"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=60, r=30, t=70, b=40)
        )
        power_fig_html = pio.to_html(power_fig, include_plotlyjs=False, full_html=False)

        soe_fig = go.Figure()
        if soe_vals:
            soe_fig.add_trace(go.Scatter(x=time_vals, y=soe_vals, name="State of Energy", line=dict(color="#0acfe9")))
        soe_fig.update_layout(
            title="Battery State of Energy",
            xaxis_title="Timestamp",
            yaxis_title="SoE (%)",
            template="plotly_white",
            xaxis=dict(range=[x_start, x_end], tickvals=tick_vals, tickformat="%H:%M\n%d-%b"),
            margin=dict(l=60, r=30, t=70, b=40)
        )
        soe_fig_html = pio.to_html(soe_fig, include_plotlyjs=False, full_html=False)

    md_fig_html = ""

    savings_breakdown = analysis.get("savings_breakdown", {}) or {}
    include_pv_bar = pv_cfg.get("total_capacity_kwp", 0) > 0 and analysis.get("include_pv_savings", True)
    savings_categories = ["MD Savings", "Peak Discharge", "Off-Peak"]
    savings_values = [
        savings_breakdown.get("md_savings", 0),
        savings_breakdown.get("peak_discharge_savings", 0),
        savings_breakdown.get("offpeak_discharge_savings", 0),
    ]
    if include_pv_bar:
        savings_categories.append("PV Self Consumption")
        savings_values.append(savings_breakdown.get("pv_self_consumption_savings", 0))
    savings_fig = go.Figure()
    savings_fig.add_trace(go.Bar(x=savings_categories, y=savings_values, marker_color="#38a169"))
    savings_fig.update_layout(title="Monthly Savings Breakdown", xaxis_title="", yaxis_title=f"Amount ({currency_profile['symbol']})", template="plotly_white")
    savings_fig_html = pio.to_html(savings_fig, include_plotlyjs=False, full_html=False)

    key_highlights = [
        f"Maximum Demand Reduction: {_fmt(analysis.get('total_reduction'), 0, ' kW')}",
        f"Annual Savings: {_fmt_currency_html(analysis.get('annual_savings'), 2)}",
        f"Payback Period: {_fmt(analysis.get('payback_years'), 1, ' years')}",
        f"Control Mode: {ems_cfg.get('control_mode', 'time_of_control').replace('_',' ').title()}",
    ]

    optimization_items = []
    if recommendations.get("has_opportunity"):
        optimization_items.append(f"Additional reduction potential: {_fmt(recommendations.get('additional_reduction'), 0, ' kW')}")
        optimization_items.append(f"Suggested target MD: {_fmt(recommendations.get('suggested_target'), 0, ' kW')}")
        optimization_items.append(f"Potential annual savings uplift: {_fmt_currency_html(recommendations.get('extra_annual_savings'), 2)}")
    else:
        optimization_items.append("Battery utilization is already optimal for the configured scenario.")

    highlights_html = "".join(
        f"<li>{textwrap.shorten(item, width=120, placeholder='...')}</li>" for item in key_highlights
    )
    optimization_html = "".join(
        f"<li>{textwrap.shorten(item, width=140, placeholder='...')}</li>" for item in optimization_items
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>EnerMerlion EMS Report - {project_name}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0; background: #f7f9fc; color: #1f2937; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        h1, h2, h3 {{ color: #0f172a; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
        .card {{ background: #fff; border-radius: 12px; padding: 1.5rem; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); }}
        .metric-value {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 0.25rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; }}
        th, td {{ padding: 0.65rem 0.8rem; border: 1px solid #e2e8f0; text-align: left; }}
        th {{ background: #edf2f7; font-weight: 600; }}
        ul {{ margin: 0.5rem 0 0.5rem 1.25rem; }}
        .chart {{ margin: 1.5rem 0; }}
        .footer {{ text-align: center; margin-top: 2rem; font-size: 0.85rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>EnerMerlion EMS Simulation Report</h1>
        <p><strong>Project:</strong> {project_name}<br>
           <strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")}<br>
           <strong>Site:</strong> {location_cfg.get("city","")} {location_cfg.get("country","")}</p>

        <div class="grid">
            <div class="card">
                <div class="metric-label">MD Reduction</div>
                <div class="metric-value">{_fmt(analysis.get('total_reduction'), 0, ' kW')}</div>
            </div>
            <div class="card">
                <div class="metric-label">Annual Savings</div>
                <div class="metric-value">{_fmt_currency_html(analysis.get('annual_savings'), 2)}</div>
            </div>
            <div class="card">
                <div class="metric-label">Payback Period</div>
                <div class="metric-value">{_fmt(analysis.get('payback_years'), 1, ' years')}</div>
            </div>
            <div class="card">
                <div class="metric-label">Core Peak Discharge</div>
                <div class="metric-value">{_fmt(analysis.get('energy_metrics', {}).get('core_peak_discharge_mwh'), 2, ' MWh')}</div>
            </div>
        </div>

        <div class="card">
            <h2>Configuration Snapshot</h2>
            <table>
                <tr><th colspan="2">PV System</th></tr>
                <tr><td>Capacity</td><td>{_fmt(pv_cfg.get('total_capacity_kwp'), 2, ' kWp')}</td></tr>
                <tr><td>System Loss</td><td>{_fmt(pv_cfg.get('system_loss', 0)*100, 1, ' %')}</td></tr>
                <tr><td>Inverter Capacity</td><td>{_fmt(pv_cfg.get('inverter_capacity_kw'), 2, ' kW')}</td></tr>
                <tr><th colspan="2">Battery</th></tr>
                <tr><td>Capacity</td><td>{_fmt(ems_cfg.get('battery_capacity'), 2, ' MWh')}</td></tr>
                <tr><td>Max Discharge</td><td>{_fmt(ems_cfg.get('max_discharge_power'), 0, ' kW')}</td></tr>
                <tr><td>Initial SoE</td><td>{_fmt(ems_cfg.get('initial_soe'), 1, ' %')}</td></tr>
                <tr><td>Control Mode</td><td>{ems_cfg.get('control_mode', 'time_of_control').replace('_',' ').title()}</td></tr>
            </table>
        </div>

        <div class="card">
            <h2>Key Highlights</h2>
            <ul>
                {highlights_html}
            </ul>
        </div>

        <div class="card">
            <h2>Optimization Insights</h2>
            <ul>
                {optimization_html}
            </ul>
        </div>

        <div class="card">
            <h2>Financial Inputs</h2>
            <ul>
                <li>CAPEX: {_fmt_currency_html(financial_cfg.get('capex'), 2)}</li>
                <li>MD Charge: {_fmt_currency_html(financial_cfg.get('md_charge'), 3)} per kW</li>
                <li>Peak Rate: {_fmt_currency_html(financial_cfg.get('peak_energy_rate'), 3)} per kWh</li>
                <li>Off-Peak Rate: {_fmt_currency_html(financial_cfg.get('offpeak_energy_rate'), 3)} per kWh</li>
            </ul>
        </div>

        <div class="card chart">{power_fig_html or '<p>No power data available for charting.</p>'}</div>
        <div class="card chart">{soe_fig_html or '<p>No SoE data available for charting.</p>'}</div>
        <div class="card chart">{md_fig_html or '<p>No MD comparison data available.</p>'}</div>
        <div class="card chart">{savings_fig_html}</div>

        <div class="footer">
            EnerMerLion Dynamic EMS Simulator — HTML Report
        </div>
    </div>
</body>
</html>
"""
    return html.encode("utf-8")


def _resolve_currency_profile(country: str | None, *, preferred_code: str | None = None) -> dict:
    """Resolve a currency profile from country name or preferred ISO code."""
    if preferred_code:
        for profile in CURRENCY_PRESETS:
            if profile["code"] == preferred_code:
                return profile
    normalized = _normalize_country(country)
    if not normalized:
        return DEFAULT_CURRENCY_PROFILE
    for profile in CURRENCY_PRESETS:
        if normalized in profile["aliases"]:
            return profile
    for profile in CURRENCY_PRESETS:
        if any(alias in normalized for alias in profile["aliases"]):
            return profile
    return DEFAULT_CURRENCY_PROFILE


def _with_override_rate(profile: dict, rate_to_myr: float | None) -> dict:
    """Return a copy of the profile with an overridden exchange rate if provided."""
    if rate_to_myr is None:
        return profile
    new_profile = profile.copy()
    new_profile["rate_to_myr"] = rate_to_myr
    return new_profile


def _convert_from_myr(amount_myr: float, profile: dict) -> float:
    """Convert MYR amount to the target currency."""
    if profile["rate_to_myr"] == 0:
        return amount_myr
    return amount_myr / profile["rate_to_myr"]


def _convert_to_myr(amount: float, profile: dict) -> float:
    """Convert amount in target currency back to MYR."""
    return amount * profile["rate_to_myr"]


def _format_currency(amount: float, profile: dict, *, decimals: int = 0) -> str:
    """Format currency values with symbol and grouping."""
    format_spec = f",.{decimals}f"
    return f"{profile['symbol']} {format(amount, format_spec)}"


def _ensure_financial_state(currency_profile: dict):
    """Initialize or update financial values stored in session state."""
    if "financial_base_myr" not in st.session_state:
        st.session_state.financial_base_myr = FINANCIAL_FIELD_DEFAULTS_MYR.copy()
    if "financial_inputs" not in st.session_state:
        st.session_state.financial_inputs = {
            key: _convert_from_myr(value, currency_profile)
            for key, value in st.session_state.financial_base_myr.items()
        }
    if "financial_currency_code" not in st.session_state:
        st.session_state.financial_currency_code = currency_profile["code"]
    # ensure widget keys exist
    for key, value in st.session_state.financial_inputs.items():
        widget_key = f"{key}_input"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = value


def _compute_step(field_key: str, profile: dict) -> float:
    """Get a numeric step size scaled to the active currency."""
    base_step = FINANCIAL_FIELD_STEPS_MYR[field_key]
    step = _convert_from_myr(base_step, profile)
    # Avoid zero or extremely small step sizes
    min_step = 10 ** -4
    if step <= 0:
        return min_step
    return max(step, min_step)


def _apply_loaded_financial_config(financial_config: dict):
    """Update financial session state using values from a loaded project."""
    if not financial_config:
        return
    preferred_code = financial_config.get("currency_code")
    profile = _resolve_currency_profile(financial_config.get("currency_name"), preferred_code=preferred_code)
    profile = _with_override_rate(profile, financial_config.get("exchange_rate_to_myr"))
    # Ensure state containers exist
    _ensure_financial_state(profile)
    for field_key, config_key in FINANCIAL_CONFIG_KEYS.items():
        value_local = financial_config.get(config_key)
        if value_local is None:
            continue
        base_myr = _convert_to_myr(value_local, profile)
        st.session_state.financial_base_myr[field_key] = base_myr
    # Refresh widget values in the loaded currency
    for field_key, base_value in st.session_state.financial_base_myr.items():
        display_value = _convert_from_myr(base_value, profile)
        st.session_state.financial_inputs[field_key] = display_value
        st.session_state.pending_financial_inputs[f"{field_key}_input"] = display_value
    st.session_state.financial_currency_code = profile["code"]
    st.session_state.currency_profile = profile


def _get_active_currency_profile() -> dict:
    """Get the currency profile associated with the current or last simulation."""
    config = st.session_state.get("last_run_config")
    if config:
        financial = config.get("financial", {})
        profile = _resolve_currency_profile(financial.get("currency_name"), preferred_code=financial.get("currency_code"))
        return _with_override_rate(profile, financial.get("exchange_rate_to_myr"))
    return st.session_state.get("currency_profile", DEFAULT_CURRENCY_PROFILE)


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
        min-height: 175px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
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
if 'control_mode' not in st.session_state:
    st.session_state.control_mode = 'time_of_control'
if 'tou_charge_start' not in st.session_state:
    st.session_state.tou_charge_start = time(0, 0)
if 'tou_charge_end' not in st.session_state:
    st.session_state.tou_charge_end = time(6, 0)
if 'tou_discharge_start' not in st.session_state:
    st.session_state.tou_discharge_start = time(18, 0)
if 'tou_discharge_end' not in st.session_state:
    st.session_state.tou_discharge_end = time(22, 0)
if 'tou_min_soe' not in st.session_state:
    st.session_state.tou_min_soe = 15.0
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
if 'last_run_config' not in st.session_state:
    st.session_state.last_run_config = None
if 'last_project_name' not in st.session_state:
    st.session_state.last_project_name = "EMS Simulation"
if 'currency_profile' not in st.session_state:
    st.session_state.currency_profile = DEFAULT_CURRENCY_PROFILE
if 'pending_financial_inputs' not in st.session_state:
    st.session_state.pending_financial_inputs = {}
if 'pending_initial_soe' not in st.session_state:
    st.session_state.pending_initial_soe = None
if 'pending_location' not in st.session_state:
    st.session_state.pending_location = {}
if 'initial_soe_input' not in st.session_state:
    st.session_state.initial_soe_input = 60.0

# Authentication functions
def show_login_form():
    """Display login form"""
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
    if st.session_state.pending_location:
        pending_loc = st.session_state.pending_location
        if 'country' in pending_loc:
            st.session_state['country_input'] = pending_loc['country']
        if 'city' in pending_loc:
            st.session_state['city_input'] = pending_loc['city']
        st.session_state.pending_location = {}

    with st.expander("🌍 PROJECT LOCATION", expanded=True):
        project_name = st.text_input("PROJECT NAME", value=f"Project_{datetime.now().strftime('%Y%m%d_%H%M')}")
        col1, col2 = st.columns(2)
        with col1:
            country = st.text_input("Country", value="Malaysia", key="country_input")
        with col2:
            city = st.text_input("City", value="Penang", key="city_input")

    previous_currency_code = st.session_state.get("financial_currency_code")
    resolved_profile = _resolve_currency_profile(country)
    if (
        previous_currency_code
        and resolved_profile["code"] == DEFAULT_CURRENCY_PROFILE["code"]
        and _normalize_country(country) not in DEFAULT_CURRENCY_PROFILE["aliases"]
    ):
        # Unrecognized country: keep previous currency selection
        resolved_profile = _resolve_currency_profile(None, preferred_code=previous_currency_code)
    _ensure_financial_state(resolved_profile)
    if st.session_state.pending_financial_inputs:
        for widget_key, pending_value in st.session_state.pending_financial_inputs.items():
            st.session_state[widget_key] = pending_value
        st.session_state.pending_financial_inputs = {}
    if st.session_state.financial_currency_code != resolved_profile["code"]:
        for field_key, base_value in st.session_state.financial_base_myr.items():
            updated_value = _convert_from_myr(base_value, resolved_profile)
            st.session_state.financial_inputs[field_key] = updated_value
            st.session_state.pending_financial_inputs[f"{field_key}_input"] = updated_value
            st.session_state[f"{field_key}_input"] = updated_value
        st.session_state.financial_currency_code = resolved_profile["code"]
    st.session_state.currency_profile = resolved_profile
    
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
        
        if st.session_state.pending_initial_soe is not None:
            st.session_state.initial_soe_input = float(st.session_state.pending_initial_soe)
            st.session_state.pending_initial_soe = None
        initial_soe = st.number_input(
            "INITIAL SOE (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            key="initial_soe_input"
        )
    
    # Target Settings
    with st.expander("🎯 CONTROL STRATEGY", expanded=True):
        control_mode_labels = {
            "TIME-OF-CONTROL MODE": "time_of_control",
            "TIME-OF-USE MODE": "time_of_use",
        }
        loaded_control_mode = st.session_state.control_mode
        if st.session_state.loaded_project:
            loaded_control_mode = st.session_state.loaded_project['config']['ems_config'].get(
                'control_mode', loaded_control_mode
            )
        mode_to_label = {v: k for k, v in control_mode_labels.items()}
        default_label = mode_to_label.get(loaded_control_mode, "TIME-OF-CONTROL MODE")
        label_list = list(control_mode_labels.keys())
        default_index = label_list.index(default_label)
        selected_label = st.selectbox(
            "CONTROL MODE",
            label_list,
            index=default_index,
            help="Switch between the adaptive Time-of-Control algorithm and the schedule-based Time-of-Use mode."
        )
        control_mode = control_mode_labels[selected_label]
        st.session_state.control_mode = control_mode

        peak_period_valid = True
        if control_mode == 'time_of_control':
            default_peak_start = time(18, 0)
            default_peak_end = time(22, 0)

            if st.session_state.loaded_project:
                project_peak_config = st.session_state.loaded_project['config']['ems_config'].get('peak_shaving_period', {})
                peak_start_prefill = _parse_time_value(
                    project_peak_config.get('start_time') or project_peak_config.get('start'),
                    default_peak_start
                )
                peak_end_prefill = _parse_time_value(
                    project_peak_config.get('end_time') or project_peak_config.get('end'),
                    default_peak_end
                )
            else:
                peak_start_prefill = default_peak_start
                peak_end_prefill = default_peak_end

            peak_start_time = st.time_input(
                "BESS PEAK SHAVING START",
                value=peak_start_prefill,
                help="Define when the battery begins peak shaving (default 18:00)."
            )
            peak_end_time = st.time_input(
                "BESS PEAK SHAVING END",
                value=peak_end_prefill,
                help="Define when the battery stops peak shaving (default 22:00)."
            )

            if peak_end_time <= peak_start_time:
                st.error("⚠️ Peak shaving end time must be later than the start time.")
            peak_period_valid = peak_end_time > peak_start_time
        else:
            peak_start_time = time(18, 0)
            peak_end_time = time(22, 0)

            charge_col1, charge_col2 = st.columns(2)
            with charge_col1:
                charge_start_input = st.time_input(
                    "CHARGE WINDOW START",
                    value=st.session_state.tou_charge_start,
                    key="tou_charge_start_input",
                    help="Time-of-Use charging window start (e.g. off-peak or PV surplus hours)."
                )
            with charge_col2:
                charge_end_input = st.time_input(
                    "CHARGE WINDOW END",
                    value=st.session_state.tou_charge_end,
                    key="tou_charge_end_input",
                    help="Charging window end. If the start is later than the end, the window wraps past midnight."
                )

            discharge_col1, discharge_col2 = st.columns(2)
            with discharge_col1:
                discharge_start_input = st.time_input(
                    "DISCHARGE WINDOW START",
                    value=st.session_state.tou_discharge_start,
                    key="tou_discharge_start_input",
                    help="Begin discharging at rated power during this window."
                )
            with discharge_col2:
                discharge_end_input = st.time_input(
                    "DISCHARGE WINDOW END",
                    value=st.session_state.tou_discharge_end,
                    key="tou_discharge_end_input",
                    help="End of the discharging window. Supports wrap-around to early morning hours."
                )

            st.session_state.tou_charge_start = charge_start_input
            st.session_state.tou_charge_end = charge_end_input
            st.session_state.tou_discharge_start = discharge_start_input
            st.session_state.tou_discharge_end = discharge_end_input

            tou_min_soe_input = st.number_input(
                "MINIMUM ALLOWED SOE (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.tou_min_soe),
                step=1.0,
                key="tou_min_soe_input",
                help="Battery keeps discharging until this SoE threshold is hit."
            )
            st.session_state.tou_min_soe = float(tou_min_soe_input)

            st.caption("ℹ️ Discharge windows can span midnight. The controller continues into the next day until the minimum SoE is reached.")

        target_md = st.number_input(
            "TARGET MD (KW)", 
            min_value=0.0, 
            value=6500.0, 
            step=100.0
        )

    peak_start_decimal = peak_start_time.hour + peak_start_time.minute / 60
    peak_end_decimal = peak_end_time.hour + peak_end_time.minute / 60
    tou_charge_start_time = st.session_state.tou_charge_start
    tou_charge_end_time = st.session_state.tou_charge_end
    tou_discharge_start_time = st.session_state.tou_discharge_start
    tou_discharge_end_time = st.session_state.tou_discharge_end
    tou_charge_start_decimal = tou_charge_start_time.hour + tou_charge_start_time.minute / 60
    tou_charge_end_decimal = tou_charge_end_time.hour + tou_charge_end_time.minute / 60
    tou_discharge_start_decimal = tou_discharge_start_time.hour + tou_discharge_start_time.minute / 60
    tou_discharge_end_decimal = tou_discharge_end_time.hour + tou_discharge_end_time.minute / 60
    tou_min_soe = st.session_state.tou_min_soe
    
    # Financial Parameters
    with st.expander("💰 FINANCIAL PARAMETERS", expanded=True):
        currency_label = f"{resolved_profile['symbol']} ({resolved_profile['code']})"
        capex = st.number_input(
            f"TOTAL CAPEX ({currency_label})", 
            min_value=0.0, 
            step=_compute_step("capex", resolved_profile),
            format=FINANCIAL_FIELD_FORMATS["capex"],
            key="capex_input"
        )
        st.session_state.financial_inputs["capex"] = capex
        st.session_state.financial_base_myr["capex"] = _convert_to_myr(capex, resolved_profile)
        
        col1, col2 = st.columns(2)
        with col1:
            md_charge = st.number_input(
                f"MD CHARGE ({currency_label}/KW)", 
                min_value=0.0, 
                step=_compute_step("md_charge", resolved_profile),
                format=FINANCIAL_FIELD_FORMATS["md_charge"],
                key="md_charge_input"
            )
            st.session_state.financial_inputs["md_charge"] = md_charge
            st.session_state.financial_base_myr["md_charge"] = _convert_to_myr(md_charge, resolved_profile)
        with col2:
            peak_rate = st.number_input(
                f"PEAK RATE ({currency_label}/KWH)", 
                min_value=0.0, 
                step=_compute_step("peak_rate", resolved_profile),
                format=FINANCIAL_FIELD_FORMATS["peak_rate"],
                key="peak_rate_input"
            )
            st.session_state.financial_inputs["peak_rate"] = peak_rate
            st.session_state.financial_base_myr["peak_rate"] = _convert_to_myr(peak_rate, resolved_profile)
        
        offpeak_rate = st.number_input(
            f"OFF-PEAK RATE ({currency_label}/KWH)", 
            min_value=0.0, 
            step=_compute_step("offpeak_rate", resolved_profile),
            format=FINANCIAL_FIELD_FORMATS["offpeak_rate"],
            key="offpeak_rate_input"
        )
        st.session_state.financial_inputs["offpeak_rate"] = offpeak_rate
        st.session_state.financial_base_myr["offpeak_rate"] = _convert_to_myr(offpeak_rate, resolved_profile)
        
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
                    financial_cfg = project_data['config'].get('financial', {})
                    _apply_loaded_financial_config(financial_cfg)
                    location_cfg = project_data['config'].get('location', {})
                    loaded_country = location_cfg.get('country')
                    loaded_city = location_cfg.get('city')
                    if not loaded_country and isinstance(location_cfg.get('name'), str):
                        parts = [p.strip() for p in location_cfg['name'].split(",") if p.strip()]
                        if parts:
                            loaded_country = parts[-1]
                        if len(parts) > 1:
                            loaded_city = parts[0]
                    location_pending = {}
                    if loaded_country:
                        location_pending['country'] = loaded_country
                    if loaded_city:
                        location_pending['city'] = loaded_city
                    if location_pending:
                        st.session_state.pending_location = location_pending
                    ems_config_loaded = project_data['config'].get('ems_config', {})
                    initial_soe_loaded = ems_config_loaded.get('initial_soe')
                    if initial_soe_loaded is not None:
                        st.session_state.pending_initial_soe = float(initial_soe_loaded)
                    control_mode_loaded = ems_config_loaded.get('control_mode', 'time_of_control')
                    st.session_state.control_mode = control_mode_loaded
                    tou_cfg = ems_config_loaded.get('time_of_use', {})
                    charge_cfg = tou_cfg.get('charge_window', {})
                    discharge_cfg = tou_cfg.get('discharge_window', {})
                    st.session_state.tou_charge_start = _parse_time_value(
                        charge_cfg.get('start_time'), st.session_state.tou_charge_start
                    )
                    st.session_state.tou_charge_end = _parse_time_value(
                        charge_cfg.get('end_time'), st.session_state.tou_charge_end
                    )
                    st.session_state.tou_discharge_start = _parse_time_value(
                        discharge_cfg.get('start_time'), st.session_state.tou_discharge_start
                    )
                    st.session_state.tou_discharge_end = _parse_time_value(
                        discharge_cfg.get('end_time'), st.session_state.tou_discharge_end
                    )
                    if tou_cfg.get('min_soe') is not None:
                        st.session_state.tou_min_soe = float(tou_cfg['min_soe'])
                    st.session_state.loaded_project = project_data
                    st.session_state.last_project_name = project_data['project_name']
                    st.session_state.simulation_run = True
                    st.session_state.results = project_data['results']
                    st.session_state.include_pv_savings = project_data['config']['financial'].get('include_pv_savings', True)
                    st.session_state.last_run_config = project_data['config']
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
                            financial_cfg = project_data['config'].get('financial', {})
                            _apply_loaded_financial_config(financial_cfg)
                            location_cfg = project_data['config'].get('location', {})
                            loaded_country = location_cfg.get('country')
                            loaded_city = location_cfg.get('city')
                            if not loaded_country and isinstance(location_cfg.get('name'), str):
                                parts = [p.strip() for p in location_cfg['name'].split(",") if p.strip()]
                                if parts:
                                    loaded_country = parts[-1]
                                if len(parts) > 1:
                                    loaded_city = parts[0]
                            location_pending = {}
                            if loaded_country:
                                location_pending['country'] = loaded_country
                            if loaded_city:
                                location_pending['city'] = loaded_city
                            if location_pending:
                                st.session_state.pending_location = location_pending
                            ems_config_loaded = project_data['config'].get('ems_config', {})
                            initial_soe_loaded = ems_config_loaded.get('initial_soe')
                            if initial_soe_loaded is not None:
                                st.session_state.pending_initial_soe = float(initial_soe_loaded)
                            control_mode_loaded = ems_config_loaded.get('control_mode', 'time_of_control')
                            st.session_state.control_mode = control_mode_loaded
                            tou_cfg = ems_config_loaded.get('time_of_use', {})
                            charge_cfg = tou_cfg.get('charge_window', {})
                            discharge_cfg = tou_cfg.get('discharge_window', {})
                            st.session_state.tou_charge_start = _parse_time_value(
                                charge_cfg.get('start_time'), st.session_state.tou_charge_start
                            )
                            st.session_state.tou_charge_end = _parse_time_value(
                                charge_cfg.get('end_time'), st.session_state.tou_charge_end
                            )
                            st.session_state.tou_discharge_start = _parse_time_value(
                                discharge_cfg.get('start_time'), st.session_state.tou_discharge_start
                            )
                            st.session_state.tou_discharge_end = _parse_time_value(
                                discharge_cfg.get('end_time'), st.session_state.tou_discharge_end
                            )
                            if tou_cfg.get('min_soe') is not None:
                                st.session_state.tou_min_soe = float(tou_cfg['min_soe'])
                            st.session_state.loaded_project = project_data
                            st.session_state.last_project_name = project_data['project_name']
                            st.session_state.simulation_run = True
                            st.session_state.results = project_data['results']
                            st.session_state.include_pv_savings = project_data['config']['financial'].get('include_pv_savings', True)
                            st.session_state.last_run_config = project_data['config']
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
        if control_mode == 'time_of_control' and not peak_period_valid:
            st.error("❌ Please ensure the peak shaving end time is later than the start time before running the simulation.")
        else:
            with st.spinner("🔄 RUNNING INDUSTRIAL SIMULATION..."):
                try:
                    tou_config = {
                        'charge_window': {
                            'start_time': tou_charge_start_time.strftime("%H:%M"),
                            'end_time': tou_charge_end_time.strftime("%H:%M"),
                            'start_hour': tou_charge_start_decimal,
                            'end_hour': tou_charge_end_decimal
                        },
                        'discharge_window': {
                            'start_time': tou_discharge_start_time.strftime("%H:%M"),
                            'end_time': tou_discharge_end_time.strftime("%H:%M"),
                            'start_hour': tou_discharge_start_decimal,
                            'end_hour': tou_discharge_end_decimal
                        },
                        'min_soe': tou_min_soe
                    }
                    config = {
                        'location': {
                            'name': f"{city}, {country}",
                            'city': city,
                            'country': country
                        },
                        'pv_system': {
                            'total_capacity_kwp': pv_capacity,
                            'system_loss': system_loss,
                            'inverter_capacity_kw': inverter_capacity
                        },
                        'ems_config': {
                            'target_md': target_md,
                            'max_discharge_power': max_discharge,
                            'battery_capacity': battery_capacity,
                            'initial_soe': float(initial_soe),
                            'control_mode': control_mode,
                            'time_of_use': tou_config,
                            'peak_shaving_period': {
                                'start_time': peak_start_time.strftime("%H:%M"),
                                'end_time': peak_end_time.strftime("%H:%M"),
                                'start_hour': peak_start_decimal,
                                'end_hour': peak_end_decimal
                            }
                        },
                        'financial': {
                            'capex': capex,
                            'md_charge': md_charge,
                            'peak_energy_rate': peak_rate,
                            'offpeak_energy_rate': offpeak_rate,
                            'include_pv_savings': st.session_state.include_pv_savings,  # NEW: Pass the option to engine
                            'currency_code': resolved_profile['code'],
                            'currency_symbol': resolved_profile['symbol'],
                            'currency_name': resolved_profile['name'],
                            'exchange_rate_to_myr': resolved_profile['rate_to_myr'],
                            'base_currency': 'MYR'
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
                    st.session_state.last_run_config = config
                    st.session_state.last_project_name = project_name
                    
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
    config_for_export = st.session_state.last_run_config
    project_title = st.session_state.get('last_project_name', 'EMS Simulation')
    currency_profile_display = _get_active_currency_profile()

    html_bytes = None
    html_message = None
    if config_for_export:
        try:
            html_bytes = _build_html_report(project_title, config_for_export, results, currency_profile_display)
        except Exception as exc:
            html_message = "HTML export unavailable."
            logging.getLogger(__name__).exception("HTML export failed: %s", exc)
    else:
        html_message = "HTML export unavailable (missing config)."

    pdf_bytes = None
    pdf_message = "PDF export has been disabled. Please use the HTML report download above."

    st.markdown("---")
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown("## 📊 SIMULATION RESULTS")
    with header_col2:
        safe_stub = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in project_title) or "ems_report"
        if html_bytes:
            html_file = f"{safe_stub.lower()}_report.html"
            st.download_button(
                "🌐 DOWNLOAD HTML REPORT",
                data=html_bytes,
                file_name=html_file,
                mime="text/html",
                use_container_width=True
            )
        elif html_message:
            st.caption(html_message)
        if pdf_message:
            st.caption(pdf_message)
    
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
    
    currency_label = f"{currency_profile_display['symbol']} ({currency_profile_display['code']})"
    annual_savings_display = _format_currency(results['analysis']['annual_savings'], currency_profile_display)
    peak_period_cfg = (st.session_state.last_run_config or {}).get('ems_config', {}).get('peak_shaving_period', {})
    peak_start_label = _format_hour_label(peak_period_cfg.get('start_time') or peak_period_cfg.get('start_hour'))
    peak_end_label = _format_hour_label(peak_period_cfg.get('end_time') or peak_period_cfg.get('end_hour'))
    peak_window_label = f"{peak_start_label}-{peak_end_label}"
    if peak_window_label == "00:00-00:00":
        peak_window_label = "18:00-22:00"
    
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
            annual_savings_display
        )

    with col3:
        render_metric_card(
            "PAYBACK PERIOD",
            f"{results['analysis']['payback_years']:.1f} years"
        )

    core_peak_mwh = results['analysis'].get('energy_metrics', {}).get('core_peak_discharge_mwh')
    if core_peak_mwh is not None:
        with col4:
            render_metric_card(
                f"CORE PEAK SHAVING ({peak_window_label})",
                f"{core_peak_mwh:.2f} MWh"
            )

    if results['analysis'].get('control_mode') == 'time_of_use':
        tou_report = results['analysis'].get('time_of_use_report') or {}
        charge_win = tou_report.get('charge_window') or {}
        discharge_win = tou_report.get('discharge_window') or {}
        charge_label = f"{_format_hour_label(charge_win.get('start_hour'))} – {_format_hour_label(charge_win.get('end_hour'))}"
        discharge_label = f"{_format_hour_label(discharge_win.get('start_hour'))} – {_format_hour_label(discharge_win.get('end_hour'))}"
        min_soe_target = tou_report.get('min_soe_target')
        if min_soe_target is None:
            min_soe_target = st.session_state.tou_min_soe
        avg_excess_pct = float(tou_report.get('avg_excess_pct', 0.0) or 0.0)
        final_excess_pct = float(tou_report.get('final_excess_pct', 0.0) or 0.0)
        final_excess_energy = float(tou_report.get('final_excess_energy_kwh', 0.0) or 0.0)
        last_leftover = tou_report.get('last_leftover') or {}
        leftover_timestamp = last_leftover.get('timestamp')
        min_soe_display = f"{float(min_soe_target):.1f} %" if min_soe_target is not None else "N/A"

        st.markdown("#### 🕒 TIME-OF-USE MODE INSIGHTS")
        tcol1, tcol2, tcol3 = st.columns(3)
        with tcol1:
            st.markdown(f"**Charge Window**<br>{charge_label}", unsafe_allow_html=True)
        with tcol2:
            st.markdown(f"**Discharge Window**<br>{discharge_label}", unsafe_allow_html=True)
        with tcol3:
            st.markdown(f"**Minimum SoE Target**<br>{min_soe_display}", unsafe_allow_html=True)

        if final_excess_pct and final_excess_pct > 0.05:
            leftover_text = (
                f"Remaining SoE after the scheduled discharge: {final_excess_pct:.1f}% "
                f"(~{final_excess_energy:,.0f} kWh)."
            )
            if leftover_timestamp:
                try:
                    timestamp_fmt = pd.to_datetime(leftover_timestamp).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    timestamp_fmt = str(leftover_timestamp)
                leftover_text += f" Last recorded at {timestamp_fmt}."
            st.info(leftover_text)
            if avg_excess_pct:
                st.caption(f"Average leftover across windows: {avg_excess_pct:.1f}% above the minimum.")
        else:
            st.success("Battery discharged to its minimum State-of-Energy across the configured window.")

        leftover_events = tou_report.get('leftover_events') or []
        if leftover_events:
            with st.expander("Discharge leftover log"):
                events_df = pd.DataFrame(leftover_events)
                if 'timestamp' in events_df.columns:
                    events_df['timestamp'] = pd.to_datetime(events_df['timestamp'])
                display_df = events_df.rename(columns={
                    'timestamp': 'Timestamp',
                    'remaining_soe': 'SoE (%)',
                    'excess_above_min_pct': 'Excess Above Min (%)',
                    'excess_energy_kwh': 'Excess Energy (kWh)',
                    'note': 'Note'
                })
                st.dataframe(display_df, use_container_width=True, hide_index=True)
    elif results['analysis'].get('control_mode') == 'time_of_control':
        toc_extension = results['analysis'].get('time_of_control_extension') or {}
        if toc_extension:
            initial_excess_pct = float(toc_extension.get('initial_excess_pct') or 0.0)
            extension_energy_kwh = float(toc_extension.get('extension_energy_kwh') or 0.0)
            intervals_used = int(toc_extension.get('extension_intervals') or 0)
            completed = bool(toc_extension.get('completed'))
            st.markdown("#### 🕒 EXTENDED DISCHARGE (TIME-OF-CONTROL)")
            if initial_excess_pct > 0.05:
                message = (
                    f"Post-day surplus of {initial_excess_pct:.1f}% "
                    f"(~{extension_energy_kwh:,.0f} kWh) discharged across {intervals_used} early intervals."
                )
                if completed:
                    st.info(f"{message} Battery reached the configured minimum SoE.")
                else:
                    st.warning(f"{message} Battery did not reach the minimum SoE within the available window.")
            else:
                st.success("Battery already met the minimum SoE by the end of the primary simulation window.")
    
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
            capex_value = results['analysis'].get('capex', 0)
            cumulative = [results['analysis']['annual_savings'] * y - capex_value for y in years]
            
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
                yaxis_title=f"CUMULATIVE CASH FLOW ({currency_label})", 
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
            st.metric("MD CHARGE SAVINGS", _format_currency(breakdown['md_savings'], currency_profile_display))
        with col2:
            st.metric("PEAK ENERGY SAVINGS", _format_currency(breakdown['peak_discharge_savings'], currency_profile_display))
        with col3:
            st.metric("OFF-PEAK SAVINGS", _format_currency(breakdown['offpeak_discharge_savings'], currency_profile_display))
        with col4:
            st.metric("PV SELF-CONSUMPTION", _format_currency(breakdown['pv_self_consumption_savings'], currency_profile_display))
        
        # Display PV Savings Inclusion Note
        if not st.session_state.include_pv_savings:
            st.markdown(f"""
            <div class="warning-box">
                <h4>📊 NOTE: PV SAVINGS EXCLUDED</h4>
                <p>PV energy savings are currently excluded from ROI calculations. This analysis shows BESS-only financial performance.</p>
                <p><strong>PV Self-Consumption Savings:</strong> {_format_currency(breakdown['pv_self_consumption_savings'], currency_profile_display)} (excluded from totals)</p>
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
                <p><strong>Additional Annual Savings:</strong> {_format_currency(rec['extra_annual_savings'], currency_profile_display)}</p>
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
