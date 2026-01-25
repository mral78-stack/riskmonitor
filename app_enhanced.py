import streamlit as st
import sys
from io import StringIO
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

# Enhanced Custom CSS
st.markdown("""
<style>
    /* Main Header */
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
    
    /* Section Cards */
    .section-card {
        border-left: 4px solid;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
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
    
    /* Alert Banner */
    .alert-banner {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
        animation: pulse 2s infinite;
    }
    
    .alert-banner.critical {
        background-color: #dc3545;
        color: white;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
    }
    
    /* Progress Bar */
    .progress-container {
        background-color: #e9ecef;
        border-radius: 1rem;
        height: 2rem;
        position: relative;
        overflow: hidden;
        margin: 1rem 0;
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 1rem;
        transition: width 0.5s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
    }
    
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🔥 Risk Appetite Monitor</div>', unsafe_allow_html=True)

# Sidebar with enhanced controls
with st.sidebar:
    st.header("⚙️ Controls")
    refresh_button = st.button("🔄 Refresh Data", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.subheader("📊 View Options")
    show_charts = st.checkbox("Show Charts", value=True)
    show_details = st.checkbox("Show Detailed Sections", value=True)
    compact_view = st.checkbox("Compact View", value=False)
    
    st.markdown("---")
    st.subheader("ℹ️ About")
    st.caption("Professional-grade risk assessment tool with institutional-level indicators")
    
    if refresh_button:
        st.cache_data.clear()
        st.rerun()

# Run assessment
@st.cache_data(ttl=3600)
def get_risk_data():
    with SuppressOutput():
        try:
            section_scores, extra_data, all_results = riskmonitor.run_assessment(send_to_telegram=False)
            return section_scores, extra_data, all_results
        except Exception as e:
            st.error(f"Error running assessment: {str(e)}")
            return None, None, None

# Load data
with st.spinner("🔄 Fetching market data..."):
    section_scores, extra_data, all_results = get_risk_data()

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
    status_color = "green"
elif composite_scaled > 0:
    status_emoji = "🟡"
    status_text = "MODERATE RISK APPETITE"
    status_color = "yellow"
elif composite_scaled > -2:
    status_emoji = "🟡"
    status_text = "LOW RISK APPETITE"
    status_color = "yellow"
else:
    status_emoji = "🔴"
    status_text = "RISK-OFF ENVIRONMENT"
    status_color = "red"

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

# Main Metrics with Visual Gauge
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

with col1:
    st.subheader("Composite Risk Appetite")
    
    # Visual Progress Bar
    progress_value = ((composite_scaled + 5) / 10) * 100  # Convert -5 to +5 scale to 0-100%
    progress_color = "#28a745" if composite_scaled > 2 else "#ffc107" if composite_scaled > 0 else "#dc3545"
    
    st.markdown(f"""
    <div class="progress-container">
        <div class="progress-bar" style="width: {progress_value}%; background: {progress_color};">
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
            title = {'text': "Risk Appetite"},
            gauge = {
                'axis': {'range': [-5, 5]},
                'bar': {'color': progress_color},
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
        fig_gauge.update_layout(height=250)
        st.plotly_chart(fig_gauge, use_container_width=True)

with col2:
    positive = sum(1 for s in section_scores.values() if s > 0)
    negative = sum(1 for s in section_scores.values() if s < 0)
    delta_value = positive - negative
    st.metric("Positive Sections", positive, delta=f"{delta_value:+d}")
    st.caption(f"Negative: {negative}")

with col3:
    if extra_data.get('bonds_global', {}).get('us_curve', {}).get('inverted'):
        st.metric("Yield Curve", "🔴 INVERTED", delta="Recession Warning")
    else:
        st.metric("Yield Curve", "✅ Normal", delta="")

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
        title='Weighted Contribution to Composite Score'
    )
    fig_bar.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_bar, use_container_width=True)

# Actionable Signals with Badges
st.markdown("---")
st.subheader("📊 Actionable Signals")

signals = []

# Collect all signals (same logic as before)
if extra_data.get('bonds_global', {}).get('us_curve'):
    curve = extra_data['bonds_global']['us_curve']
    if curve.get('inverted'):
        signals.insert(0, {"Signal": "🔴 YIELD CURVE INVERTED", "Type": "Critical", "Action": "Recession warning!", "Badge": "critical"})
    elif curve.get('status') == 'Flat':
        signals.append({"Signal": "🟡 Yield curve flattening", "Type": "Watch", "Action": "Monitor closely", "Badge": "normal"})

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
        signals.append({"Signal": "🔥 Put/Call elevated", "Type": "Contrarian", "Action": "CONTRARIAN BUY signal", "Badge": "risk-on"})
    elif pcr and pcr.get('signal') == 'contrarian_sell':
        signals.append({"Signal": "⚠️ Put/Call low", "Type": "Contrarian", "Action": "CONTRARIAN SELL signal", "Badge": "risk-off"})

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
            signals.insert(0, {"Signal": f"🇺🇸⚠️ TRUMP TARIFF ALERT", "Type": "Critical", "Action": f"{trump['tariff_mentions']} mentions - Trade war risk!", "Badge": "critical"})
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
        st.markdown("---")
else:
    st.info("🟡 No strong signals detected - mixed conditions")

# Section Breakdown with Color Coding
st.markdown("---")
st.subheader("📈 Section Breakdown")

section_data = []
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

# Note: The detailed expandable sections would continue here (same as original app.py)
# For brevity, I'm showing the key visual improvements

st.markdown("---")
st.caption("💡 Tip: Expand sections below for detailed metrics | Data updates every hour")
