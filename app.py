import streamlit as st
import sys
from io import StringIO
from datetime import datetime
import riskmonitor
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Suppress print statements for cleaner Streamlit output
class SuppressOutput:
    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        return self
    def __exit__(self, *args):
        sys.stdout = self._stdout
        sys.stderr = self._stderr

st.set_page_config(page_title="Risk Appetite Monitor", layout="wide", initial_sidebar_state="expanded")

# Enhanced Custom CSS with all visual improvements
st.markdown("""
<style>
    /* Main Header with Gradient */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    .metric-card.green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }
    
    .metric-card.yellow {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }
    
    .metric-card.red {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
    }
    
    /* Section Cards with Color Coding */
    .section-card {
        border-left: 4px solid;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        transition: transform 0.2s;
    }
    
    .section-card:hover {
        transform: translateX(5px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .section-card.positive {
        border-left-color: #28a745;
        background-color: #d4edda;
    }
    
    .section-card.negative {
        border-left-color: #dc3545;
        background-color: #f8d7da;
    }
    
    .section-card.neutral {
        border-left-color: #ffc107;
        background-color: #fff3cd;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    .badge-critical {
        background-color: #dc3545;
        color: white;
    }
    
    .badge-risk-on {
        background-color: #28a745;
        color: white;
    }
    
    .badge-risk-off {
        background-color: #dc3545;
        color: white;
    }
    
    .badge-normal {
        background-color: #6c757d;
        color: white;
    }
    
    .badge-watch {
        background-color: #ffc107;
        color: #212529;
    }
    
    .badge-contrarian {
        background-color: #17a2b8;
        color: white;
    }
    
    /* Alert Banner */
    .alert-banner {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
        animation: pulse 2s infinite;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    
    .alert-banner.critical {
        background-color: #dc3545;
        color: white;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.85; }
    }
    
    /* Progress Bar */
    .progress-container {
        background-color: #e9ecef;
        border-radius: 1rem;
        height: 2.5rem;
        position: relative;
        overflow: hidden;
        margin: 1rem 0;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 1rem;
        transition: width 0.8s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 1.1rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
    }
    
    /* Section Header */
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e9ecef;
    }
    
    /* Status Text */
    .status-text {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
        font-weight: 500;
    }
    
    /* Prevent text truncation */
    .stDataFrame {
        font-size: 0.9rem;
    }
    
    .headline-item {
        margin-bottom: 0.5rem;
        word-wrap: break-word;
        white-space: normal;
    }
    
    /* Last Update Timestamp */
    .timestamp {
        font-size: 0.85rem;
        color: #6c757d;
        font-style: italic;
    }
    
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Tooltip style */
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🔥 Risk Appetite Monitor</div>', unsafe_allow_html=True)

# Enhanced Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    refresh_button = st.button("🔄 Refresh Data", type="primary", use_container_width=True)
    
    if refresh_button:
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.subheader("📊 View Options")
    show_charts = st.checkbox("Show Charts", value=True)
    show_gauge = st.checkbox("Show Gauge Chart", value=True)
    compact_view = st.checkbox("Compact View", value=False)
    
    st.markdown("---")
    st.subheader("ℹ️ About")
    st.caption("Professional-grade risk assessment tool with institutional-level indicators")
    st.caption("v4.0 - Enhanced Visual Dashboard")

# Run assessment
@st.cache_data(ttl=3600)
def get_risk_data():
    with SuppressOutput():
        try:
            section_scores, extra_data, all_results = riskmonitor.run_assessment(send_to_telegram=False)
            return section_scores, extra_data, all_results, datetime.now()
        except Exception as e:
            st.error(f"Error running assessment: {str(e)}")
            return None, None, None, None

# Load data
with st.spinner("🔄 Fetching market data..."):
    section_scores, extra_data, all_results, last_update = get_risk_data()

if section_scores is None:
    st.error("Failed to load risk data. Please try again.")
    st.stop()

# Calculate composite score
composite = sum(score * riskmonitor.SECTION_WEIGHTS.get(sec, 0.1) for sec, score in section_scores.items())
composite_scaled = composite * 5

# Determine status and colors
if composite_scaled > 2:
    status_emoji = "🟢"
    status_text = "HIGH RISK APPETITE"
    status_color = "#28a745"
    card_class = "green"
elif composite_scaled > 0:
    status_emoji = "🟡"
    status_text = "MODERATE RISK APPETITE"
    status_color = "#ffc107"
    card_class = "yellow"
elif composite_scaled > -2:
    status_emoji = "🟡"
    status_text = "LOW RISK APPETITE"
    status_color = "#ffc107"
    card_class = "yellow"
else:
    status_emoji = "🔴"
    status_text = "RISK-OFF ENVIRONMENT"
    status_color = "#dc3545"
    card_class = "red"

# Critical Alerts Banner
critical_alerts = []
if extra_data.get('bonds_global', {}).get('us_curve', {}).get('inverted'):
    critical_alerts.append("🚨 YIELD CURVE INVERTED - Recession Warning!")
if extra_data.get('news', {}).get('trump_effect', {}).get('tariff_mentions', 0) > 0:
    tariff_count = extra_data['news']['trump_effect']['tariff_mentions']
    critical_alerts.append(f"🇺🇸⚠️ TRUMP TARIFF ALERT - {tariff_count} mentions - Trade war risk!")

if critical_alerts:
    for alert in critical_alerts:
        st.markdown(f'<div class="alert-banner critical">{alert}</div>', unsafe_allow_html=True)

# Main Metrics with Visual Enhancements
if show_gauge:
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
else:
    col1, col2, col3 = st.columns(3)

with col1:
    if show_gauge:
        st.subheader("Composite Risk Appetite")
        
        # Visual Progress Bar
        progress_value = ((composite_scaled + 5) / 10) * 100
        st.markdown(f"""
        <div class="progress-container">
            <div class="progress-bar" style="width: {progress_value}%; background: {status_color};">
                {composite_scaled:.2f}/5.0
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f'<div style="text-align: center; margin-top: 0.5rem;"><strong>{status_emoji} {status_text}</strong></div>', unsafe_allow_html=True)
        
        # Gauge Chart
        if show_charts:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = composite_scaled,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Risk Appetite Score"},
                gauge = {
                    'axis': {'range': [-5, 5]},
                    'bar': {'color': status_color},
                    'steps': [
                        {'range': [-5, -2], 'color': "#dc3545"},
                        {'range': [-2, 0], 'color': "#ffc107"},
                        {'range': [0, 2], 'color': "#ffc107"},
                        {'range': [2, 5], 'color': "#28a745"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 0
                    }
                }
            ))
            fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.metric("Composite Risk Appetite", f"{composite_scaled:.2f}/5.0")
        st.markdown(f'<div class="status-text">{status_emoji} {status_text}</div>', unsafe_allow_html=True)

with col2:
    positive = sum(1 for s in section_scores.values() if s > 0)
    negative = sum(1 for s in section_scores.values() if s < 0)
    delta_value = positive - negative
    st.metric("Positive Sections", positive, delta=f"{delta_value:+d}" if delta_value != 0 else None)
    st.markdown(f'<div class="status-text">Negative: {negative}</div>', unsafe_allow_html=True)

with col3:
    if extra_data.get('bonds_global', {}).get('us_curve', {}).get('inverted'):
        st.metric("Yield Curve", "🔴 INVERTED", delta="Recession Warning")
    else:
        st.metric("Yield Curve", "✅ Normal", delta="")

if show_gauge:
    with col4:
        total_signals = len([s for s in section_scores.values() if abs(s) > 0.3])
        st.metric("Active Signals", total_signals)
        st.caption("Strong indicators")

# Section Contribution Bar Chart
if show_charts:
    st.markdown("---")
    st.subheader("📊 Section Contribution Breakdown")
    
    section_chart_data = []
    for section, score in section_scores.items():
        weight = riskmonitor.SECTION_WEIGHTS.get(section, 0.1)
        contrib = score * weight * 5
        section_chart_data.append({
            'Section': section.title(),
            'Contribution': contrib,
            'Score': score,
            'Weight': weight
        })
    
    df_chart = pd.DataFrame(section_chart_data)
    df_chart = df_chart.sort_values('Contribution', key=abs, ascending=False)
    
    fig_bar = px.bar(
        df_chart,
        x='Contribution',
        y='Section',
        orientation='h',
        color='Contribution',
        color_continuous_scale=['#dc3545', '#ffc107', '#28a745'],
        title='Weighted Contribution to Composite Score',
        labels={'Contribution': 'Contribution to Score', 'Section': ''}
    )
    fig_bar.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_bar, use_container_width=True)

# Actionable Signals with Badges
st.markdown("---")
st.subheader("📊 Actionable Signals")

signals = []

# Collect all signals with badge types
if extra_data.get('bonds_global', {}).get('us_curve'):
    curve = extra_data['bonds_global']['us_curve']
    if curve.get('inverted'):
        signals.insert(0, {"Signal": "🔴 YIELD CURVE INVERTED", "Type": "Critical", "Action": "Recession warning!", "Badge": "critical"})
    elif curve.get('status') == 'Flat':
        signals.append({"Signal": "🟡 Yield curve flattening", "Type": "Watch", "Action": "Monitor closely", "Badge": "watch"})

if extra_data.get('currencies', {}).get('DXY'):
    dxy = extra_data['currencies']['DXY']
    if dxy.get('roc_5d', 0) > 1.5:
        signals.append({"Signal": "🔴 Dollar surging", "Type": "Risk-Off", "Action": f"DXY +{dxy['roc_5d']:.1f}% - Risk-off pressure", "Badge": "risk-off"})
    elif dxy.get('roc_5d', 0) < -1.5:
        signals.append({"Signal": "🟢 Dollar weakening", "Type": "Risk-On", "Action": f"DXY {dxy['roc_5d']:.1f}% - Risk-on support", "Badge": "risk-on"})

if extra_data.get('credit'):
    credit = extra_data['credit']
    if 'HY Spread' in credit and isinstance(credit['HY Spread'], dict) and credit['HY Spread'].get('current', 999) < 3.0:
        signals.append({"Signal": "🟢 Credit spreads tight", "Type": "Risk-On", "Action": "Supports risk-on", "Badge": "risk-on"})
    elif 'HY Spread' in credit and isinstance(credit['HY Spread'], dict) and credit['HY Spread'].get('current', 0) > 5.0:
        signals.append({"Signal": "🔴 Credit spreads widening", "Type": "Risk-Off", "Action": "Caution warranted", "Badge": "risk-off"})

if extra_data.get('sentiment'):
    pcr = extra_data['sentiment']
    if pcr and pcr.get('signal') == 'contrarian_buy':
        signals.append({"Signal": "🔥 Put/Call elevated", "Type": "Contrarian", "Action": "CONTRARIAN BUY signal", "Badge": "contrarian"})
    elif pcr and pcr.get('signal') == 'contrarian_sell':
        signals.append({"Signal": "⚠️ Put/Call low", "Type": "Contrarian", "Action": "CONTRARIAN SELL signal", "Badge": "contrarian"})

if extra_data.get('breadth'):
    breadth = extra_data['breadth']
    if breadth.get('breadth_trend') == 'improving':
        signals.append({"Signal": "🟢 Market breadth improving", "Type": "Confirming", "Action": "Confirms uptrend", "Badge": "risk-on"})
    elif breadth.get('breadth_trend') == 'deteriorating':
        signals.append({"Signal": "⚠️ Market breadth deteriorating", "Type": "Warning", "Action": "Divergence risk", "Badge": "risk-off"})

if extra_data.get('volatility'):
    vix = extra_data['volatility']
    if vix and vix.get('structure') == 'contango':
        signals.append({"Signal": "🟢 VIX in contango", "Type": "Normal", "Action": "Normal fear structure", "Badge": "normal"})
    elif vix and vix.get('structure') == 'backwardation':
        signals.append({"Signal": "🔴 VIX in backwardation", "Type": "Warning", "Action": "Elevated near-term fear", "Badge": "risk-off"})

if extra_data.get('metals', {}).get('copper_gold'):
    cu_au = extra_data['metals']['copper_gold']
    if cu_au.get('roc_5d', 0) > 2:
        signals.append({"Signal": "🟢 Copper/Gold rising", "Type": "Risk-On", "Action": "Economic optimism", "Badge": "risk-on"})
    elif cu_au.get('roc_5d', 0) < -2:
        signals.append({"Signal": "🔴 Copper/Gold falling", "Type": "Risk-Off", "Action": "Growth concerns", "Badge": "risk-off"})

if extra_data.get('crypto', {}).get('altcoin_perf', {}).get('altseason'):
    signals.append({"Signal": "🔥 Altseason active", "Type": "Crypto", "Action": "Consider altcoin exposure", "Badge": "risk-on"})

if extra_data.get('news'):
    news = extra_data['news']
    sentiment = news.get('overall_sentiment', {})
    if sentiment.get('signal') == 1:
        signals.append({"Signal": "🟢 News sentiment bullish", "Type": "Sentiment", "Action": "Supports risk-on", "Badge": "risk-on"})
    elif sentiment.get('signal') == -1:
        signals.append({"Signal": "🔴 News sentiment bearish", "Type": "Sentiment", "Action": "Caution advised", "Badge": "risk-off"})
    
    trump = news.get('trump_effect')
    if trump:
        if trump.get('tariff_mentions', 0) > 0:
            tariff_count = trump['tariff_mentions']
            signals.insert(0, {
                "Signal": f"🇺🇸⚠️ TRUMP TARIFF ALERT", 
                "Type": "Critical", 
                "Action": f"{tariff_count} tariff mentions detected - Trade war risk! Market volatility expected.",
                "Badge": "critical"
            })
        elif trump.get('signal') == -1:
            signals.append({"Signal": "🇺🇸🔴 Trump Effect negative", "Type": "Policy", "Action": "Policy uncertainty", "Badge": "risk-off"})
        elif trump.get('signal') == 1:
            signals.append({"Signal": "🇺🇸🟢 Trump Effect positive", "Type": "Policy", "Action": "Pro-business sentiment", "Badge": "risk-on"})

# Display signals with badges
if signals:
    signals_display = signals[:10]
    for sig in signals_display:
        badge_class = sig.get('Badge', 'normal')
        col_sig, col_type, col_action = st.columns([2, 1, 3])
        with col_sig:
            st.markdown(f"**{sig['Signal']}**")
        with col_type:
            st.markdown(f'<span class="status-badge badge-{badge_class}">{sig["Type"]}</span>', unsafe_allow_html=True)
        with col_action:
            st.caption(sig['Action'])
        if not compact_view:
            st.markdown("---")
else:
    st.info("🟡 No strong signals detected - mixed conditions")

# Section Breakdown with Color-Coded Cards
st.markdown("---")
st.subheader("📈 Section Breakdown")

for section, score in sorted(section_scores.items(), key=lambda x: -abs(x[1])):
    weight = riskmonitor.SECTION_WEIGHTS.get(section, 0.1)
    contrib = score * weight * 5
    emoji = "🟢" if score > 0.3 else "🔴" if score < -0.3 else "🟡"
    card_class = "positive" if score > 0.3 else "negative" if score < -0.3 else "neutral"
    
    st.markdown(f"""
    <div class="section-card {card_class}">
        <strong>{emoji} {section.title()}</strong><br>
        Score: {score:+.2f} | Weight: {weight:.0%} | Contribution: {contrib:+.2f}
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# DETAILED SECTIONS - Expandable like Telegram Report
# ============================================================================

st.markdown("---")
st.subheader("📊 Detailed Analysis")

# 1. EQUITY INDICES
with st.expander("📈 Equity Indices (US, Europe, Asia, Korea)", expanded=False):
    if 'indices' in all_results and isinstance(all_results['indices'], list):
        indices_data = []
        for item in all_results['indices']:
            if isinstance(item, dict):
                indices_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if indices_data:
            st.dataframe(indices_data, use_container_width=True, hide_index=True)
        else:
            st.info("No equity indices data available")
    else:
        st.info("No equity indices data available")

# 2. MARKET BREADTH
with st.expander("📊 Market Breadth", expanded=False):
    if 'breadth' in all_results and isinstance(all_results['breadth'], list):
        breadth_data = []
        for item in all_results['breadth']:
            if isinstance(item, dict):
                breadth_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if breadth_data:
            st.dataframe(breadth_data, use_container_width=True, hide_index=True)
        
        if extra_data.get('breadth'):
            breadth_extra = extra_data['breadth']
            st.subheader("Breadth Analysis")
            if breadth_extra.get('breadth_trend'):
                st.write(f"**Trend:** {breadth_extra['breadth_trend']}")
            if breadth_extra.get('adv_decline'):
                st.write(f"**Advance/Decline:** {breadth_extra['adv_decline']}")
    else:
        st.info("No market breadth data available")

# 3. GLOBAL BONDS
with st.expander("🏦 Global Bonds (US 2Y/10Y/30Y, Japan, Yield Curve)", expanded=False):
    if 'bonds_global' in all_results and isinstance(all_results['bonds_global'], list):
        bonds_data = []
        for item in all_results['bonds_global']:
            if isinstance(item, dict):
                bonds_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if bonds_data:
            st.dataframe(bonds_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('bonds_global'):
        bonds = extra_data['bonds_global']
        st.subheader("Yield Curve Analysis")
        
        if bonds.get('us_curve'):
            curve = bonds['us_curve']
            if curve.get('inverted'):
                st.error(f"🚨 **YIELD CURVE INVERTED!** 2Y-10Y Spread: {curve.get('spread', 'N/A'):.2f}% - Recession signal")
            elif curve.get('status') == 'Flat':
                st.warning(f"⚠️ Yield Curve: FLAT ({curve.get('spread', 'N/A'):.2f}%)")
            else:
                st.success(f"✅ Yield Curve: Normal ({curve.get('spread', 'N/A'):.2f}%)")
        
        if bonds.get('us_yields'):
            st.subheader("US Yields")
            yields = bonds['us_yields']
            for tenor, data in yields.items():
                if isinstance(data, dict):
                    emoji = "📈" if data.get('pct_change', 0) > 0 else "📉"
                    st.write(f"{emoji} **{tenor}:** {data.get('current', 'N/A'):.2f}% (Change: {data.get('pct_change', 0):+.2f}%)")

# 4. CREDIT SPREADS
with st.expander("💳 Credit Spreads (FRED)", expanded=False):
    if 'credit' in all_results and isinstance(all_results['credit'], list):
        credit_data = []
        for item in all_results['credit']:
            if isinstance(item, dict):
                credit_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if credit_data:
            st.dataframe(credit_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('credit'):
        st.subheader("Credit Analysis")
        credit = extra_data['credit']
        for name, data in credit.items():
            if isinstance(data, dict) and 'current' in data:
                st.write(f"**{name}:** {data['current']:.2f}%")
                if 'pct_change' in data:
                    st.caption(f"Change: {data['pct_change']:+.2f}%")

# 5. CURRENCIES
with st.expander("💱 Currencies (DXY, EUR/USD, USD/JPY)", expanded=False):
    if 'currencies' in all_results and isinstance(all_results['currencies'], list):
        currency_data = []
        for item in all_results['currencies']:
            if isinstance(item, dict):
                currency_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if currency_data:
            st.dataframe(currency_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('currencies'):
        st.subheader("Currency Analysis")
        curr = extra_data['currencies']
        
        if curr.get('DXY'):
            dxy = curr['DXY']
            dxy_emoji = "📈" if dxy.get('roc_5d', 0) > 0 else "📉"
            trend = "Strengthening" if dxy.get('roc_5d', 0) > 0.5 else "Weakening" if dxy.get('roc_5d', 0) < -0.5 else "Stable"
            st.write(f"{dxy_emoji} **DXY:** {dxy.get('current', 'N/A'):.2f} ({trend})")
            st.caption(f"5D Change: {dxy.get('roc_5d', 0):+.2f}%")
            if dxy.get('roc_5d', 0) > 1.5:
                st.warning("⚠️ Dollar surge = Risk-off pressure")
            elif dxy.get('roc_5d', 0) < -1.5:
                st.success("✅ Dollar weakness = Risk-on support")

# 6. GLOBAL LIQUIDITY
with st.expander("💧 Global Liquidity (M2, WALCL, CB Proxies)", expanded=False):
    if 'liquidity' in all_results and isinstance(all_results['liquidity'], list):
        liquidity_data = []
        for item in all_results['liquidity']:
            if isinstance(item, dict):
                liquidity_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if liquidity_data:
            st.dataframe(liquidity_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('liquidity'):
        st.subheader("Liquidity Analysis")
        liq = extra_data['liquidity']
        for name, data in liq.items():
            if isinstance(data, dict):
                st.write(f"**{name}:** {data.get('current', 'N/A')}")

# 7. CRYPTO
with st.expander("₿ Crypto (incl. Fear & Greed, ETF Flows)", expanded=False):
    if 'crypto' in all_results and isinstance(all_results['crypto'], list):
        crypto_data = []
        for item in all_results['crypto']:
            if isinstance(item, dict):
                crypto_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if crypto_data:
            st.dataframe(crypto_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('crypto'):
        st.subheader("Crypto Analysis")
        crypto = extra_data['crypto']
        
        if crypto.get('fear_greed'):
            fg = crypto['fear_greed']
            st.metric("Fear & Greed Index", fg.get('value', 'N/A'), delta=fg.get('classification', ''))
        
        if crypto.get('btc_etf_flows'):
            flows = crypto['btc_etf_flows']
            st.write(f"**BTC ETF Flows:** {flows.get('net_flow', 'N/A')}")
        
        if crypto.get('altcoin_perf'):
            alt = crypto['altcoin_perf']
            if alt.get('altseason'):
                st.success("🔥 Altseason active - consider altcoin exposure")
            st.write(f"**Altcoin Performance:** {alt.get('performance', 'N/A')}%")

# 8. METALS
with st.expander("🥇 Metals & Ratios", expanded=False):
    if 'metals' in all_results and isinstance(all_results['metals'], list):
        metals_data = []
        for item in all_results['metals']:
            if isinstance(item, dict):
                metals_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if metals_data:
            st.dataframe(metals_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('metals'):
        st.subheader("Metals Analysis")
        metals = extra_data['metals']
        
        if metals.get('copper_gold'):
            cu_au = metals['copper_gold']
            st.write(f"**Copper/Gold Ratio:** {cu_au.get('ratio', 'N/A'):.4f}")
            st.caption(f"5D Change: {cu_au.get('roc_5d', 0):+.2f}%")
            if cu_au.get('roc_5d', 0) > 2:
                st.success("🟢 Copper/Gold rising - Economic optimism")
            elif cu_au.get('roc_5d', 0) < -2:
                st.error("🔴 Copper/Gold falling - Growth concerns")

# 9. COMMODITIES
with st.expander("🛢️ Commodities", expanded=False):
    if 'commodities' in all_results and isinstance(all_results['commodities'], list):
        comm_data = []
        for item in all_results['commodities']:
            if isinstance(item, dict):
                comm_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if comm_data:
            st.dataframe(comm_data, use_container_width=True, hide_index=True)

# 10. VOLATILITY
with st.expander("📉 Volatility", expanded=False):
    if 'volatility' in all_results and isinstance(all_results['volatility'], list):
        vol_data = []
        for item in all_results['volatility']:
            if isinstance(item, dict):
                vol_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if vol_data:
            st.dataframe(vol_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('volatility'):
        st.subheader("Volatility Analysis")
        vix = extra_data['volatility']
        if vix.get('current'):
            st.metric("VIX", f"{vix['current']:.2f}")
        if vix.get('structure'):
            structure_emoji = "🟢" if vix['structure'] == 'contango' else "🔴"
            st.write(f"{structure_emoji} **Term Structure:** {vix['structure']}")
            if vix['structure'] == 'backwardation':
                st.warning("⚠️ VIX in backwardation - Elevated near-term fear")

# 11. SENTIMENT
with st.expander("🎭 Sentiment (Put/Call Ratio)", expanded=False):
    if 'sentiment' in all_results and isinstance(all_results['sentiment'], list):
        sent_data = []
        for item in all_results['sentiment']:
            if isinstance(item, dict):
                sent_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if sent_data:
            st.dataframe(sent_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('sentiment'):
        st.subheader("Sentiment Analysis")
        sent = extra_data['sentiment']
        if sent.get('put_call_ratio'):
            st.metric("Put/Call Ratio", f"{sent['put_call_ratio']:.2f}")
        if sent.get('signal'):
            signal_text = sent['signal']
            if signal_text == 'contrarian_buy':
                st.success("🔥 Put/Call elevated - CONTRARIAN BUY signal")
            elif signal_text == 'contrarian_sell':
                st.warning("⚠️ Put/Call low - CONTRARIAN SELL signal")

# 12. NEWS SENTIMENT & TRUMP EFFECT
with st.expander("📰 News Sentiment & Trump Effect", expanded=False):
    if 'news' in all_results and isinstance(all_results['news'], list):
        news_data = []
        for item in all_results['news']:
            if isinstance(item, dict):
                news_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if news_data:
            st.dataframe(news_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('news'):
        st.subheader("News Analysis")
        news = extra_data['news']
        
        if news.get('overall_sentiment'):
            sentiment = news['overall_sentiment']
            signal_val = sentiment.get('signal', 0)
            if signal_val == 1:
                st.success("🟢 News sentiment bullish - Supports risk-on")
            elif signal_val == -1:
                st.error("🔴 News sentiment bearish - Caution advised")
            else:
                st.info("🟡 News sentiment neutral")
        
        if news.get('trump_effect'):
            trump = news['trump_effect']
            
            st.subheader("🇺🇸 Trump Effect Analysis")
            
            if trump.get('tariff_mentions', 0) > 0:
                tariff_count = trump['tariff_mentions']
                st.error(f"🚨 **TRUMP TARIFF ALERT** - {tariff_count} tariff-related mentions detected!")
                st.warning("⚠️ **Trade War Risk:** Tariff news typically causes market volatility and risk-off sentiment")
                
                if trump.get('headlines'):
                    st.write("**Trump-Related Headlines (Tariff/Trade):**")
                    for i, headline in enumerate(trump['headlines'], 1):
                        st.markdown(f"{i}. {headline}")
            else:
                if trump.get('signal') == -1:
                    st.warning("🇺🇸🔴 Trump Effect negative - Policy uncertainty")
                elif trump.get('signal') == 1:
                    st.success("🇺🇸🟢 Trump Effect positive - Pro-business sentiment")
                else:
                    st.info("🇺🇸🟡 Trump Effect neutral")
            
            if trump.get('article_count'):
                st.caption(f"**Articles analyzed:** {trump['article_count']}")
            if trump.get('avg_score') is not None:
                st.caption(f"**Average sentiment score:** {trump['avg_score']:.2f}")
            if trump.get('interpretation'):
                st.caption(f"**Interpretation:** {trump['interpretation']}")
            if trump.get('volatility_triggers', 0) > 0:
                st.caption(f"**Volatility triggers:** {trump['volatility_triggers']}")
        
        if news.get('headlines'):
            st.subheader("📰 Top Market-Moving Headlines")
            headlines = news['headlines']
            
            for i, headline_item in enumerate(headlines, 1):
                if isinstance(headline_item, dict):
                    title = headline_item.get('title', '')
                    sentiment_label = headline_item.get('sentiment', 'neutral')
                    score = headline_item.get('score', 0)
                    
                    if sentiment_label == 'bullish':
                        emoji = "🟢"
                    elif sentiment_label == 'bearish':
                        emoji = "🔴"
                    else:
                        emoji = "🟡"
                    
                    st.markdown(f"{emoji} **{i}. {title}**")
                    st.caption(f"   Sentiment: {sentiment_label} (score: {score:.2f})")
                else:
                    st.markdown(f"**{i}. {headline_item}**")
        
        if news.get('article_count'):
            st.caption(f"**Total articles analyzed:** {news['article_count']}")
        if news.get('bullish_count') is not None:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Bullish", news.get('bullish_count', 0))
            with col2:
                st.metric("Bearish", news.get('bearish_count', 0))
            with col3:
                st.metric("Neutral", news.get('neutral_count', 0))

# 13. BRAZIL MARKETS
with st.expander("🇧🇷 Brazil (Bovespa, EWZ, BRL, ADRs)", expanded=False):
    if 'brazil' in all_results and isinstance(all_results['brazil'], list):
        brazil_data = []
        for item in all_results['brazil']:
            if isinstance(item, dict):
                brazil_data.append({
                    "Indicator": item.get('Indicator', 'N/A'),
                    "Value": item.get('Value', 'N/A'),
                    "Change": item.get('Change', 'N/A'),
                    "%ile": item.get('%ile', 'N/A'),
                    "5D": item.get('5D', 'N/A'),
                    "Signal": item.get('Signal', 'N/A')
                })
        if brazil_data:
            st.dataframe(brazil_data, use_container_width=True, hide_index=True)
    
    if extra_data.get('brazil'):
        st.subheader("Brazil Analysis")
        brazil = extra_data['brazil']
        for name, data in brazil.items():
            if isinstance(data, dict):
                st.write(f"**{name}:** {data.get('current', 'N/A')}")

# Footer with timestamp
st.markdown("---")
if last_update:
    st.markdown(f'<div class="timestamp">Last updated: {last_update.strftime("%Y-%m-%d %H:%M:%S")} | Data refreshes every hour</div>', unsafe_allow_html=True)
else:
    st.caption("💡 Tip: Expand sections above for detailed metrics | Data updates every hour")
