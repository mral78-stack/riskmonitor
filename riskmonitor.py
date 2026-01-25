#!/usr/bin/env python3
"""
Ultimate Risk Appetite Monitor v4.0
====================================
Professional-grade risk assessment tool with institutional-level indicators.
Now with Telegram bot integration!

Sections:
- Equity Indices (US, Europe, Asia, including Russell 2000)
- Market Breadth (Advance/Decline, % above MAs, New Highs/Lows)
- Bonds & Credit (Yields, Credit Spreads from FRED)
- Global Liquidity (US M2, China M2, ECB, BOJ, Fed Balance Sheet WALCL)
- Crypto (BTC, ETH, Altcoins, BTC Dominance, Altseason, Fear & Greed, ETF Flows)
- Metals & Commodities (Gold, Silver, Copper, Oil, Key Ratios)
- Volatility (VIX, Term Structure)
- Sentiment (Put/Call Ratio, Fear & Greed proxy)

Features:
- Credit spreads from FRED (HY, IG, HY-IG differential)
- Global Liquidity tracking (US M2, China M2, ECB, BOJ, WALCL)
- Crypto Fear & Greed Index and Bitcoin ETF inflow/outflow
- CBOE Put/Call ratio (contrarian indicator)
- Market breadth analysis
- Percentile rankings for historical context
- Rate of change calculations
- Weighted composite scoring
- Actionable entry signals
- Telegram bot notifications

Requirements:
    pip install pandas yfinance tabulate requests

Usage:
    python riskmonitor_v4.py                    # Run once (console only)
    python riskmonitor_v4.py --telegram         # Run once + send to Telegram
    python riskmonitor_v4.py --schedule         # Run every 4 hours (console)
    python riskmonitor_v4.py --schedule --telegram  # Run every 4 hours + Telegram
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tabulate import tabulate
import argparse
import sys
import warnings
import requests

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Organized by section
INDICATORS = {
    'indices': {
        # US Indices
        'S&P 500': '^GSPC',
        'NASDAQ': '^IXIC',
        'Dow Jones': '^DJI',
        'Russell 2000': '^RUT',
        # European Indices
        'FTSE 100': '^FTSE',
        'DAX': '^GDAXI',
        'CAC 40': '^FCHI',
        # Asian Indices
        'Nikkei 225': '^N225',
        'Hang Seng': '^HSI',
        'SSE Composite': '000001.SS',
        'KOSPI': '^KS11',          # Korean index
        # Canadian
        'TSX Composite': '^GSPTSE',
        # Brazilian
        'Bovespa': '^BVSP',
    },
    # Dedicated Bond Markets Section (US + Japan)
    'bonds_us': {
        'US 2Y Yield': '^IRX',     # 13-week T-Bill (proxy for 2Y, actual 2Y is harder to get)
        'US 10Y Yield': '^TNX',    # 10-Year Treasury
        'US 30Y Yield': '^TYX',    # 30-Year Treasury
    },
    'bonds_japan': {
        # Japan Government Bonds - using ETFs as proxies since direct yields harder to get
        'JP 10Y ETF': '1321.T',    # Nikko Listed Index Fund JGB (proxy)
    },
    # Legacy bonds section (for backward compatibility)
    'bonds': {
        '10Y Treasury Yield': '^TNX',
        '2Y Treasury Yield': '^IRX',
        '30Y Treasury Yield': '^TYX',
    },
    'currencies': {
        'DXY': 'DX-Y.NYB',         # US Dollar Index
        'EUR/USD': 'EURUSD=X',     # Euro to Dollar
        'USD/JPY': 'JPY=X',        # Dollar to Yen
    },
    'crypto': {
        'Bitcoin': 'BTC-USD',
        'Ethereum': 'ETH-USD',
        'Solana': 'SOL-USD',
        'Cardano': 'ADA-USD',
        'XRP': 'XRP-USD',
        'Avalanche': 'AVAX-USD',
    },
    'metals': {
        'Gold': 'GC=F',
        'Silver': 'SI=F',
        'Copper': 'HG=F',
        'Platinum': 'PL=F',
    },
    'commodities': {
        'Crude Oil WTI': 'CL=F',
        'Brent Crude': 'BZ=F',
        'Natural Gas': 'NG=F',
    },
    'volatility': {
        'VIX': '^VIX',
        'VIX 3-Month': '^VIX3M',
    },
    # Brazilian Markets Section
    'brazil': {
        'EWZ': 'EWZ',              # iShares MSCI Brazil ETF
        'USD/BRL': 'BRL=X',        # US Dollar to Brazilian Real
        'Petrobras': 'PBR',        # Petrobras ADR
        'Vale': 'VALE',            # Vale ADR (mining giant)
        'Itau Unibanco': 'ITUB',   # Major Brazilian bank ADR
        'Bradesco': 'BBD',         # Major Brazilian bank ADR
        'B3 SA': 'B3SA3.SA',       # Brazilian stock exchange
    },
}

# FRED series IDs for credit spreads
FRED_SERIES = {
    'HY Spread': 'BAMLH0A0HYM2',      # ICE BofA US High Yield OAS
    'IG Spread': 'BAMLC0A0CM',         # ICE BofA US Corporate Master OAS
    'BBB Spread': 'BAMLC0A4CBBB',      # ICE BofA BBB US Corporate OAS
    'CCC Spread': 'BAMLH0A3HYC',       # ICE BofA CCC & Lower US HY OAS
}

# FRED series for Bond Yields (more reliable than Yahoo for some)
BOND_FRED_SERIES = {
    'US 2Y': 'DGS2',               # 2-Year Treasury Constant Maturity
    'US 10Y': 'DGS10',             # 10-Year Treasury Constant Maturity
    'US 30Y': 'DGS30',             # 30-Year Treasury Constant Maturity
    'US 2Y-10Y Spread': None,      # Calculated: DGS10 - DGS2 (yield curve)
}

# FRED series for Global Liquidity metrics
LIQUIDITY_FRED_SERIES = {
    'US M2': 'M2SL',                    # US M2 Money Stock (Billions, Seasonally Adjusted)
    'WALCL': 'WALCL',                   # Fed Total Assets (Balance Sheet)
}

# Risk signal logic
RISK_DIRECTION = {
    # Indices - rising = risk on
    'S&P 500': True, 'NASDAQ': True, 'Dow Jones': True, 'Russell 2000': True,
    'FTSE 100': True, 'DAX': True, 'CAC 40': True,
    'Nikkei 225': True, 'Hang Seng': True, 'SSE Composite': True, 'TSX Composite': True,
    'Bovespa': True, 'KOSPI': True,  # Korean index
    # US Bonds - rising yields = generally risk off (but complex)
    '10Y Treasury Yield': False, '2Y Treasury Yield': False, '30Y Treasury Yield': False,
    'US 2Y Yield': False, 'US 10Y Yield': False, 'US 30Y Yield': False,
    # Japan Bonds
    'JP 10Y ETF': True,  # Rising bond ETF = falling yields = risk on
    # Currencies
    'DXY': False,        # Rising dollar = risk off (tightening conditions)
    'EUR/USD': True,     # Rising EUR/USD = weaker dollar = risk on
    'USD/JPY': True,     # Rising USD/JPY = weaker yen = risk on (carry trade)
    # Crypto - rising = risk on
    'Bitcoin': True, 'Ethereum': True, 'Solana': True, 'Cardano': True, 'XRP': True,
    'Avalanche': True,
    # Metals
    'Gold': False, 'Silver': False, 'Copper': True, 'Platinum': True,
    # Commodities
    'Crude Oil WTI': True, 'Brent Crude': True, 'Natural Gas': False,
    # Volatility
    'VIX': False, 'VIX 3-Month': False,
    # Credit spreads - tightening (falling) = risk on
    'HY Spread': False, 'IG Spread': False, 'BBB Spread': False, 'CCC Spread': False,
    # Brazilian assets
    'EWZ': True,           # Rising EWZ = risk on for Brazil
    'USD/BRL': False,      # Rising USD/BRL (weakening Real) = risk off for Brazil
    'Petrobras': True,     # Rising = risk on
    'Vale': True,          # Rising = risk on (commodities proxy)
    'Itau Unibanco': True, # Rising = risk on (financials)
    'Bradesco': True,      # Rising = risk on (financials)
    'B3 SA': True,         # Rising = risk on
}

# Section weights for composite score
SECTION_WEIGHTS = {
    'indices': 0.12,
    'breadth': 0.05,
    'bonds_global': 0.10,  # Combined US + Japan bonds section
    'credit': 0.12,        # Credit spreads are highly predictive
    'currencies': 0.06,    # DXY and major pairs
    'liquidity': 0.08,     # Global liquidity - important macro indicator
    'crypto': 0.06,
    'metals': 0.05,
    'commodities': 0.04,
    'volatility': 0.07,
    'sentiment': 0.04,
    'news': 0.09,          # News sentiment including Trump Effect
    'brazil': 0.08,        # Brazilian markets section
    # Legacy keys for backward compatibility
    'bonds': 0.04,
}

# Credit spread thresholds
CREDIT_THRESHOLDS = {
    'HY Spread': {'risk_on': 3.0, 'neutral': 4.5, 'risk_off': 6.0},
    'IG Spread': {'risk_on': 1.0, 'neutral': 1.5, 'risk_off': 2.0},
}

# Put/Call ratio thresholds (contrarian)
PCR_THRESHOLDS = {
    'extreme_fear': 1.2,    # Contrarian BUY
    'fear': 1.0,            # Cautious bullish
    'neutral_high': 0.8,
    'neutral_low': 0.6,
    'greed': 0.5,           # Caution
    'extreme_greed': 0.4,   # Contrarian SELL
}

# ============================================================================
# NEWS SENTIMENT CONFIGURATION
# ============================================================================

# Keywords for market-moving news categories
NEWS_KEYWORDS = {
    'bullish': [
        'rally', 'surge', 'soar', 'jump', 'gain', 'bullish', 'optimism', 'growth',
        'beat expectations', 'record high', 'breakthrough', 'stimulus', 'rate cut',
        'dovish', 'strong earnings', 'upgrade', 'buy rating', 'outperform',
        'expansion', 'recovery', 'boom', 'positive', 'upbeat', 'confidence'
    ],
    'bearish': [
        'crash', 'plunge', 'tumble', 'fall', 'drop', 'bearish', 'fear', 'recession',
        'miss expectations', 'record low', 'crisis', 'default', 'rate hike', 'hawkish',
        'weak earnings', 'downgrade', 'sell rating', 'underperform', 'contraction',
        'slowdown', 'bust', 'negative', 'downbeat', 'concern', 'warning', 'risk'
    ],
    'volatility': [
        'volatility', 'uncertainty', 'turmoil', 'chaos', 'panic', 'fear',
        'selloff', 'correction', 'whipsaw', 'swing', 'unstable', 'turbulent'
    ]
}

# Trump-specific keywords for the Trump Effect indicator
TRUMP_KEYWORDS = {
    'identifiers': [
        'trump', 'donald trump', 'president trump', 'former president trump',
        'trump administration', 'mar-a-lago', 'truth social', 'president-elect trump'
    ],
    'policy_bullish': [
        'tax cut', 'deregulation', 'tariff deal', 'trade deal', 'pro-business',
        'tax reform', 'infrastructure', 'stimulus', 'lower taxes', 'business friendly'
    ],
    'policy_bearish': [
        'tariff', 'trade war', 'sanctions', 'import tax', 'trade tension',
        'china tariff', 'trade barrier', 'protectionism', 'import duty', 'retaliation',
        'greenland', 'europe tariff', 'eu tariff', 'european union tariff', 'denmark',
        'canada tariff', 'mexico tariff', 'auto tariff', 'steel tariff', 'aluminum tariff'
    ],
    'market_volatility': [
        'executive order', 'announcement', 'tweet', 'truth social post', 'statement',
        'press conference', 'rally', 'campaign', 'election', 'investigation',
        'indictment', 'trial', 'verdict', 'lawsuit', 'threatens', 'warning', 'ultimatum'
    ]
}

# News sources to scrape (RSS feeds that don't require API keys)
NEWS_RSS_FEEDS = {
    'google_news_business': 'https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en',
    'google_news_markets': 'https://news.google.com/rss/search?q=stock+market+OR+tariff+OR+trade+war&hl=en-US&gl=US&ceid=US:en',
    'google_news_trump': 'https://news.google.com/rss/search?q=trump+tariff+OR+trump+trade&hl=en-US&gl=US&ceid=US:en',
    'cnbc_top': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
    'cnbc_world': 'https://www.cnbc.com/id/100727362/device/rss/rss.html',
    'marketwatch': 'https://feeds.marketwatch.com/marketwatch/topstories/',
    'wsj_markets': 'https://feeds.a]wsj.com/rss/RSSMarketsMain.xml',
    'bloomberg_markets': 'https://feeds.bloomberg.com/markets/news.rss',
}

# Emojis
EMOJI = {
    'green': '🟢',
    'red': '🔴',
    'yellow': '🟡',
    'up': '↑',
    'down': '↓',
    'flat': '→',
    'fire': '🔥',
    'warning': '⚠️',
    'check': '✅',
    'x': '❌',
}

# ============================================================================
# TELEGRAM CONFIGURATION
# ============================================================================

TELEGRAM_BOT_TOKEN = "7993777288:AAGa_F9zgeG3K7l_L6YZCEOOPr35EIG8C3Q"
TELEGRAM_CHAT_ID = "7959262031"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_telegram_message(message: str, parse_mode: str = "HTML") -> bool:
    """
    Send a message to Telegram.
    
    Args:
        message: Text to send (supports HTML formatting)
        parse_mode: "HTML" or "Markdown"
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True
        else:
            print(f"  ⚠️ Telegram error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"  ⚠️ Telegram exception: {e}")
        return False


def format_telegram_section(title: str, results: list, section_score: float) -> str:
    """Format a section for Telegram message."""
    score_emoji = EMOJI['green'] if section_score > 0.3 else EMOJI['red'] if section_score < -0.3 else EMOJI['yellow']
    
    lines = [f"\n<b>{title}</b> {score_emoji} ({section_score:+.2f})"]
    lines.append("─" * 30)
    
    for row in results[:8]:  # Limit rows to avoid message too long
        indicator = row.get('Indicator', '')[:12].ljust(12)
        value = str(row.get('Value', ''))[:10].ljust(10)
        change = str(row.get('Change', ''))[:10]
        signal = row.get('Signal', '')
        lines.append(f"<code>{indicator} {value} {change}</code> {signal}")
    
    return "\n".join(lines)


# ============================================================================
# DATA FETCHING - YAHOO FINANCE
# ============================================================================

def fetch_data(symbol: str, period: str = '60d') -> dict:
    """Fetch market data with extended history."""
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty or len(hist) < 2:
            return None
        
        current = hist['Close'].iloc[-1]
        previous = hist['Close'].iloc[-2]
        pct_change = ((current - previous) / previous) * 100 if previous != 0 else 0
        
        # Percentile rank
        percentile = (hist['Close'] < current).sum() / len(hist['Close']) * 100
        
        # 5-day ROC
        roc_5d = ((current - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else pct_change
        
        # 20-day ROC
        roc_20d = ((current - hist['Close'].iloc[-20]) / hist['Close'].iloc[-20]) * 100 if len(hist) >= 20 else roc_5d
        
        return {
            'current': current,
            'previous': previous,
            'pct_change': pct_change,
            'percentile': percentile,
            'roc_5d': roc_5d,
            'roc_20d': roc_20d,
            'high_52w': hist['Close'].max(),
            'low_52w': hist['Close'].min(),
        }
        
    except Exception as e:
        return None


# ============================================================================
# DATA FETCHING - FRED (Credit Spreads)
# ============================================================================

def fetch_fred_series(series_id: str, days: int = 60) -> dict:
    """
    Fetch data from FRED API (free, no key required for basic access).
    """
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        url = f"https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': 'DEMO_KEY',  # FRED allows limited requests with DEMO_KEY
            'file_type': 'json',
            'observation_start': start_date,
            'observation_end': end_date,
        }
        
        # Try without API key first (works for some endpoints)
        alt_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        
        try:
            df = pd.read_csv(alt_url)
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            
            if len(df) < 2:
                return None
            
            current = df['value'].iloc[-1]
            previous = df['value'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100 if previous != 0 else 0
            
            # Percentile
            percentile = (df['value'] < current).sum() / len(df['value']) * 100
            
            return {
                'current': current,
                'previous': previous,
                'pct_change': pct_change,
                'percentile': percentile,
                'history': df['value'].tolist()[-30:],
            }
        except:
            return None
            
    except Exception as e:
        return None


def fetch_credit_spreads() -> dict:
    """Fetch all credit spread data."""
    spreads = {}
    
    for name, series_id in FRED_SERIES.items():
        data = fetch_fred_series(series_id)
        if data:
            spreads[name] = data
    
    # Calculate HY-IG differential if both available
    if 'HY Spread' in spreads and 'IG Spread' in spreads:
        hy = spreads['HY Spread']['current']
        ig = spreads['IG Spread']['current']
        spreads['HY-IG Differential'] = {
            'current': hy - ig,
            'interpretation': 'Quality concern' if (hy - ig) > 3.5 else 'Normal'
        }
    
    return spreads


# ============================================================================
# DATA FETCHING - GLOBAL LIQUIDITY
# ============================================================================

def fetch_global_liquidity() -> dict:
    """
    Fetch global liquidity metrics from FRED and other sources.
    Includes US M2, WALCL (Fed Balance Sheet), and estimates for other major CBs.
    """
    liquidity_data = {}
    
    # Fetch US M2
    print("    Fetching US M2...")
    m2_data = fetch_fred_series('M2SL', days=365)
    if m2_data:
        # Calculate YoY change for M2
        liquidity_data['US M2'] = {
            'current': m2_data['current'],
            'pct_change': m2_data['pct_change'],
            'percentile': m2_data['percentile'],
            'unit': 'B USD',
        }
    
    # Fetch WALCL (Fed Balance Sheet)
    print("    Fetching Fed Balance Sheet (WALCL)...")
    walcl_data = fetch_fred_series('WALCL', days=365)
    if walcl_data:
        liquidity_data['WALCL'] = {
            'current': walcl_data['current'],
            'pct_change': walcl_data['pct_change'],
            'percentile': walcl_data['percentile'],
            'unit': 'M USD',
        }
    
    # Fetch China M2 proxy using FXI (China Large-Cap ETF) as proxy
    # Real China M2 data is not easily available via free APIs
    print("    Fetching China liquidity proxy...")
    try:
        import yfinance as yf
        # Use CNYUSD and China ETFs as proxies for China monetary conditions
        fxi = yf.Ticker('FXI')
        fxi_hist = fxi.history(period='60d')
        if not fxi_hist.empty and len(fxi_hist) >= 2:
            current = fxi_hist['Close'].iloc[-1]
            previous = fxi_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100 if previous != 0 else 0
            
            # 20-day change as proxy for trend
            if len(fxi_hist) >= 20:
                pct_change_20d = ((current - fxi_hist['Close'].iloc[-20]) / fxi_hist['Close'].iloc[-20]) * 100
            else:
                pct_change_20d = pct_change
            
            liquidity_data['China (FXI proxy)'] = {
                'current': current,
                'pct_change': pct_change,
                'pct_change_20d': pct_change_20d,
                'percentile': (fxi_hist['Close'] < current).sum() / len(fxi_hist['Close']) * 100,
                'unit': 'USD',
                'note': 'FXI ETF as proxy'
            }
    except Exception as e:
        pass
    
    # Fetch ECB proxy using EZU (Eurozone ETF)
    print("    Fetching ECB liquidity proxy...")
    try:
        ezu = yf.Ticker('EZU')
        ezu_hist = ezu.history(period='60d')
        if not ezu_hist.empty and len(ezu_hist) >= 2:
            current = ezu_hist['Close'].iloc[-1]
            previous = ezu_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100 if previous != 0 else 0
            
            if len(ezu_hist) >= 20:
                pct_change_20d = ((current - ezu_hist['Close'].iloc[-20]) / ezu_hist['Close'].iloc[-20]) * 100
            else:
                pct_change_20d = pct_change
            
            liquidity_data['ECB (EZU proxy)'] = {
                'current': current,
                'pct_change': pct_change,
                'pct_change_20d': pct_change_20d,
                'percentile': (ezu_hist['Close'] < current).sum() / len(ezu_hist['Close']) * 100,
                'unit': 'USD',
                'note': 'EZU ETF as proxy'
            }
    except Exception as e:
        pass
    
    # Fetch BOJ proxy using EWJ (Japan ETF) and USDJPY
    print("    Fetching BOJ liquidity proxy...")
    try:
        ewj = yf.Ticker('EWJ')
        ewj_hist = ewj.history(period='60d')
        if not ewj_hist.empty and len(ewj_hist) >= 2:
            current = ewj_hist['Close'].iloc[-1]
            previous = ewj_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100 if previous != 0 else 0
            
            if len(ewj_hist) >= 20:
                pct_change_20d = ((current - ewj_hist['Close'].iloc[-20]) / ewj_hist['Close'].iloc[-20]) * 100
            else:
                pct_change_20d = pct_change
            
            liquidity_data['BOJ (EWJ proxy)'] = {
                'current': current,
                'pct_change': pct_change,
                'pct_change_20d': pct_change_20d,
                'percentile': (ewj_hist['Close'] < current).sum() / len(ewj_hist['Close']) * 100,
                'unit': 'USD',
                'note': 'EWJ ETF as proxy'
            }
    except Exception as e:
        pass
    
    # Calculate Global Liquidity Index (composite)
    if liquidity_data:
        components = []
        if 'US M2' in liquidity_data:
            components.append(liquidity_data['US M2']['pct_change'])
        if 'WALCL' in liquidity_data:
            components.append(liquidity_data['WALCL']['pct_change'])
        if 'China (FXI proxy)' in liquidity_data:
            components.append(liquidity_data['China (FXI proxy)']['pct_change'])
        if 'ECB (EZU proxy)' in liquidity_data:
            components.append(liquidity_data['ECB (EZU proxy)']['pct_change'])
        if 'BOJ (EWJ proxy)' in liquidity_data:
            components.append(liquidity_data['BOJ (EWJ proxy)']['pct_change'])
        
        if components:
            liquidity_data['Global Liquidity Index'] = {
                'avg_change': np.mean(components),
                'expanding': np.mean(components) > 0,
                'components': len(components),
            }
    
    return liquidity_data


def process_liquidity_section() -> tuple:
    """Process global liquidity section."""
    results = []
    total_score = 0
    count = 0
    
    liquidity_data = fetch_global_liquidity()
    
    if not liquidity_data:
        return [], 0, None
    
    # US M2
    if 'US M2' in liquidity_data:
        m2 = liquidity_data['US M2']
        # Rising M2 = liquidity expansion = risk-on
        signal = 1 if m2['pct_change'] > 0 else -1
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'US M2',
            'Value': f"${m2['current']/1000:.1f}T",
            'Change': format_change(m2['pct_change']),
            '%ile': f"{m2['percentile']:.0f}%",
            '5D': 'Monthly',
            'Signal': format_signal(signal)
        })
    
    # WALCL (Fed Balance Sheet)
    if 'WALCL' in liquidity_data:
        walcl = liquidity_data['WALCL']
        # Rising balance sheet = QE/liquidity injection = risk-on
        signal = 1 if walcl['pct_change'] > 0 else -1
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'Fed B/S (WALCL)',
            'Value': f"${walcl['current']/1000000:.2f}T",
            'Change': format_change(walcl['pct_change']),
            '%ile': f"{walcl['percentile']:.0f}%",
            '5D': 'Weekly',
            'Signal': format_signal(signal)
        })
    
    # China proxy
    if 'China (FXI proxy)' in liquidity_data:
        china = liquidity_data['China (FXI proxy)']
        signal = 1 if china['pct_change_20d'] > 0 else -1
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'China (FXI)',
            'Value': f"${china['current']:.2f}",
            'Change': format_change(china['pct_change']),
            '%ile': f"{china['percentile']:.0f}%",
            '5D': format_change(china['pct_change_20d']),
            'Signal': format_signal(signal)
        })
    
    # ECB proxy
    if 'ECB (EZU proxy)' in liquidity_data:
        ecb = liquidity_data['ECB (EZU proxy)']
        signal = 1 if ecb['pct_change_20d'] > 0 else -1
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'ECB (EZU)',
            'Value': f"${ecb['current']:.2f}",
            'Change': format_change(ecb['pct_change']),
            '%ile': f"{ecb['percentile']:.0f}%",
            '5D': format_change(ecb['pct_change_20d']),
            'Signal': format_signal(signal)
        })
    
    # BOJ proxy
    if 'BOJ (EWJ proxy)' in liquidity_data:
        boj = liquidity_data['BOJ (EWJ proxy)']
        signal = 1 if boj['pct_change_20d'] > 0 else -1
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'BOJ (EWJ)',
            'Value': f"${boj['current']:.2f}",
            'Change': format_change(boj['pct_change']),
            '%ile': f"{boj['percentile']:.0f}%",
            '5D': format_change(boj['pct_change_20d']),
            'Signal': format_signal(signal)
        })
    
    # Global Liquidity Index
    if 'Global Liquidity Index' in liquidity_data:
        gli = liquidity_data['Global Liquidity Index']
        signal = 1 if gli['expanding'] else -1
        total_score += signal
        count += 1
        emoji = EMOJI['green'] if gli['expanding'] else EMOJI['red']
        results.append({
            'Indicator': 'Global Liq Idx',
            'Value': f"{gli['avg_change']:+.2f}%",
            'Change': f"{emoji} {'Expanding' if gli['expanding'] else 'Contracting'}",
            '%ile': 'N/A',
            '5D': f"{gli['components']} sources",
            'Signal': format_signal(signal)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, liquidity_data


# ============================================================================
# DATA FETCHING - PUT/CALL RATIO
# ============================================================================

def fetch_put_call_ratio() -> dict:
    """
    Fetch CBOE Put/Call ratio.
    Uses Yahoo Finance for CBOE equity put/call.
    """
    try:
        import yfinance as yf
        
        # Try to get VIX as proxy for fear (PCR data not directly available)
        # We'll estimate PCR from options flow
        
        # Alternative: scrape from CBOE or use estimated value
        # For now, we'll use a proxy calculation
        
        spy = yf.Ticker('SPY')
        
        # Get options data if available
        try:
            options_dates = spy.options
            if options_dates:
                nearest_expiry = options_dates[0]
                chain = spy.option_chain(nearest_expiry)
                
                # Calculate put/call ratio from volume
                put_volume = chain.puts['volume'].sum()
                call_volume = chain.calls['volume'].sum()
                
                if call_volume > 0:
                    pcr = put_volume / call_volume
                    
                    # Determine signal (contrarian)
                    if pcr > PCR_THRESHOLDS['extreme_fear']:
                        signal = 'contrarian_buy'
                        interpretation = 'Extreme fear - Contrarian BUY'
                    elif pcr > PCR_THRESHOLDS['fear']:
                        signal = 'bullish'
                        interpretation = 'Elevated fear - Bullish'
                    elif pcr < PCR_THRESHOLDS['extreme_greed']:
                        signal = 'contrarian_sell'
                        interpretation = 'Extreme greed - Contrarian SELL'
                    elif pcr < PCR_THRESHOLDS['greed']:
                        signal = 'bearish'
                        interpretation = 'Elevated greed - Caution'
                    else:
                        signal = 'neutral'
                        interpretation = 'Neutral sentiment'
                    
                    return {
                        'pcr': pcr,
                        'put_volume': put_volume,
                        'call_volume': call_volume,
                        'signal': signal,
                        'interpretation': interpretation,
                    }
        except:
            pass
        
        return None
        
    except Exception as e:
        return None


# ============================================================================
# DATA FETCHING - MARKET BREADTH
# ============================================================================

def fetch_market_breadth() -> dict:
    """
    Calculate market breadth indicators.
    Uses S&P 500 components analysis.
    """
    try:
        import yfinance as yf
        
        # Get S&P 500 ETF and related breadth ETFs
        spy = yf.Ticker('SPY')
        spy_hist = spy.history(period='60d')
        
        if spy_hist.empty:
            return None
        
        # Calculate SPY's position relative to moving averages
        spy_close = spy_hist['Close']
        spy_current = spy_close.iloc[-1]
        
        # Moving averages
        ma_50 = spy_close.rolling(50).mean().iloc[-1] if len(spy_close) >= 50 else spy_close.mean()
        ma_200 = spy_close.rolling(200).mean().iloc[-1] if len(spy_close) >= 200 else spy_close.mean()
        
        above_50ma = spy_current > ma_50
        above_200ma = spy_current > ma_200
        
        # Get advance/decline proxy from market ETFs
        # RSP (equal weight S&P) vs SPY shows breadth
        try:
            rsp = yf.Ticker('RSP')  # Equal weight S&P 500
            rsp_hist = rsp.history(period='60d')
            
            if not rsp_hist.empty and len(rsp_hist) >= 5:
                # RSP/SPY ratio - rising = improving breadth
                rsp_spy_ratio = rsp_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-1]
                rsp_spy_ratio_5d = rsp_hist['Close'].iloc[-5] / spy_hist['Close'].iloc[-5]
                breadth_trend = 'improving' if rsp_spy_ratio > rsp_spy_ratio_5d else 'deteriorating'
            else:
                breadth_trend = 'unknown'
                rsp_spy_ratio = 1.0
        except:
            breadth_trend = 'unknown'
            rsp_spy_ratio = 1.0
        
        # Small cap vs Large cap (risk appetite)
        try:
            iwm = yf.Ticker('IWM')  # Russell 2000 ETF
            iwm_hist = iwm.history(period='20d')
            
            if not iwm_hist.empty and len(iwm_hist) >= 5:
                iwm_return_5d = ((iwm_hist['Close'].iloc[-1] - iwm_hist['Close'].iloc[-5]) / iwm_hist['Close'].iloc[-5]) * 100
                spy_return_5d = ((spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[-5]) / spy_hist['Close'].iloc[-5]) * 100
                small_vs_large = iwm_return_5d - spy_return_5d
                risk_appetite = 'high' if small_vs_large > 1 else 'low' if small_vs_large < -1 else 'neutral'
            else:
                small_vs_large = 0
                risk_appetite = 'unknown'
        except:
            small_vs_large = 0
            risk_appetite = 'unknown'
        
        # New highs vs new lows proxy (using 52-week high proximity)
        pct_from_high = ((spy_current - spy_close.max()) / spy_close.max()) * 100
        
        # Estimate % of stocks above 50-day MA (simplified)
        # In reality, you'd need constituent data
        estimated_above_50ma = 60 + (20 if above_50ma else -20) + (10 if breadth_trend == 'improving' else -10)
        estimated_above_50ma = max(20, min(90, estimated_above_50ma))
        
        return {
            'spy_above_50ma': above_50ma,
            'spy_above_200ma': above_200ma,
            'breadth_trend': breadth_trend,
            'rsp_spy_ratio': rsp_spy_ratio,
            'small_vs_large_5d': small_vs_large,
            'risk_appetite': risk_appetite,
            'pct_from_52w_high': pct_from_high,
            'estimated_above_50ma': estimated_above_50ma,
        }
        
    except Exception as e:
        return None


# ============================================================================
# CRYPTO ANALYSIS
# ============================================================================

def fetch_btc_dominance() -> dict:
    """Calculate BTC dominance proxy using BTC/ETH ratio."""
    try:
        import yfinance as yf
        
        btc = yf.Ticker('BTC-USD').history(period='30d')
        eth = yf.Ticker('ETH-USD').history(period='30d')
        
        if btc.empty or eth.empty:
            return None
        
        current_ratio = btc['Close'].iloc[-1] / eth['Close'].iloc[-1]
        prev_ratio = btc['Close'].iloc[-2] / eth['Close'].iloc[-2]
        ratio_5d = btc['Close'].iloc[-5] / eth['Close'].iloc[-5] if len(btc) >= 5 else prev_ratio
        
        pct_change = ((current_ratio - prev_ratio) / prev_ratio) * 100
        pct_change_5d = ((current_ratio - ratio_5d) / ratio_5d) * 100
        
        # Rising BTC/ETH ratio = BTC dominance rising = risk-off in crypto
        trend = 'rising' if pct_change_5d > 0 else 'falling'
        
        return {
            'btc_eth_ratio': current_ratio,
            'pct_change': pct_change,
            'pct_change_5d': pct_change_5d,
            'trend': trend,
            'signal': 'risk_off' if trend == 'rising' else 'risk_on',
        }
    except:
        return None


def fetch_altcoin_performance() -> dict:
    """Calculate altcoin performance vs BTC."""
    try:
        import yfinance as yf
        
        tickers = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'ADA': 'ADA-USD',
            'AVAX': 'AVAX-USD',
        }
        
        returns = {}
        for name, symbol in tickers.items():
            hist = yf.Ticker(symbol).history(period='30d')
            if not hist.empty and len(hist) >= 7:
                ret_7d = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-7]) / hist['Close'].iloc[-7]) * 100
                returns[name] = ret_7d
        
        if 'BTC' not in returns:
            return None
        
        btc_return = returns['BTC']
        alt_outperformance = {}
        
        for name, ret in returns.items():
            if name != 'BTC':
                alt_outperformance[name] = ret - btc_return
        
        avg_outperformance = np.mean(list(alt_outperformance.values())) if alt_outperformance else 0
        altseason = avg_outperformance > 5
        
        return {
            'returns_7d': returns,
            'alt_vs_btc': alt_outperformance,
            'avg_outperformance': avg_outperformance,
            'altseason': altseason,
        }
    except:
        return None


def fetch_crypto_fear_greed() -> dict:
    """
    Fetch Crypto Fear & Greed Index from Alternative.me API.
    Returns current value, historical data, and signal.
    """
    try:
        # Alternative.me Fear & Greed API (free, no key required)
        url = "https://api.alternative.me/fng/?limit=7"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if 'data' not in data or len(data['data']) == 0:
            return None
        
        current = data['data'][0]
        current_value = int(current['value'])
        current_class = current['value_classification']
        
        # Get 7-day average for trend
        values = [int(d['value']) for d in data['data']]
        avg_7d = np.mean(values)
        
        # Determine trend
        if len(values) >= 2:
            trend = 'rising' if values[0] > values[-1] else 'falling' if values[0] < values[-1] else 'flat'
        else:
            trend = 'unknown'
        
        # Determine signal (contrarian interpretation)
        # Extreme Fear (0-24) = Contrarian BUY
        # Fear (25-49) = Cautiously bullish
        # Neutral (50) = Neutral
        # Greed (51-74) = Cautious
        # Extreme Greed (75-100) = Contrarian SELL
        if current_value <= 24:
            signal = 1  # Contrarian buy
            interpretation = 'Extreme Fear - Contrarian BUY'
        elif current_value <= 44:
            signal = 1
            interpretation = 'Fear - Bullish opportunity'
        elif current_value <= 55:
            signal = 0
            interpretation = 'Neutral'
        elif current_value <= 74:
            signal = -1
            interpretation = 'Greed - Caution'
        else:
            signal = -1  # Contrarian sell
            interpretation = 'Extreme Greed - Contrarian SELL'
        
        return {
            'value': current_value,
            'classification': current_class,
            'avg_7d': avg_7d,
            'trend': trend,
            'signal': signal,
            'interpretation': interpretation,
            'timestamp': current.get('timestamp'),
        }
        
    except Exception as e:
        print(f"    ⚠️ Fear & Greed fetch error: {e}")
        return None


def fetch_bitcoin_etf_flows() -> dict:
    """
    Fetch Bitcoin ETF flow data by analyzing major BTC ETF price/volume changes.
    Uses IBIT, FBTC, GBTC as proxies for institutional flow.
    """
    try:
        import yfinance as yf
        
        etfs = {
            'IBIT': 'IBIT',    # iShares Bitcoin Trust
            'FBTC': 'FBTC',    # Fidelity Wise Origin Bitcoin
            'GBTC': 'GBTC',    # Grayscale Bitcoin Trust
            'BITB': 'BITB',    # Bitwise Bitcoin ETF
        }
        
        etf_data = {}
        total_volume_change = 0
        total_price_change = 0
        count = 0
        
        for name, symbol in etfs.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='30d')
                
                if hist.empty or len(hist) < 5:
                    continue
                
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                price_5d = hist['Close'].iloc[-5]
                
                pct_change = ((current_price - prev_price) / prev_price) * 100
                pct_change_5d = ((current_price - price_5d) / price_5d) * 100
                
                # Volume analysis
                avg_volume_5d = hist['Volume'].iloc[-5:].mean()
                avg_volume_prev = hist['Volume'].iloc[-10:-5].mean() if len(hist) >= 10 else avg_volume_5d
                volume_change = ((avg_volume_5d - avg_volume_prev) / avg_volume_prev) * 100 if avg_volume_prev > 0 else 0
                
                etf_data[name] = {
                    'price': current_price,
                    'pct_change': pct_change,
                    'pct_change_5d': pct_change_5d,
                    'volume_5d_avg': avg_volume_5d,
                    'volume_change': volume_change,
                }
                
                total_volume_change += volume_change
                total_price_change += pct_change_5d
                count += 1
                
            except Exception as e:
                continue
        
        if count == 0:
            return None
        
        avg_volume_change = total_volume_change / count
        avg_price_change = total_price_change / count
        
        # Determine flow signal
        # Rising prices + rising volume = strong inflows
        # Rising prices + falling volume = weak rally
        # Falling prices + rising volume = distribution (outflows)
        # Falling prices + falling volume = weak selling
        
        if avg_price_change > 1 and avg_volume_change > 10:
            flow_signal = 1
            interpretation = 'Strong Inflows'
        elif avg_price_change > 0:
            flow_signal = 1 if avg_volume_change > 0 else 0
            interpretation = 'Moderate Inflows' if avg_volume_change > 0 else 'Weak Inflows'
        elif avg_price_change < -1 and avg_volume_change > 10:
            flow_signal = -1
            interpretation = 'Distribution (Outflows)'
        elif avg_price_change < 0:
            flow_signal = -1 if avg_volume_change > 0 else 0
            interpretation = 'Moderate Outflows' if avg_volume_change > 0 else 'Weak Selling'
        else:
            flow_signal = 0
            interpretation = 'Neutral Flow'
        
        return {
            'etfs': etf_data,
            'avg_price_change_5d': avg_price_change,
            'avg_volume_change': avg_volume_change,
            'flow_signal': flow_signal,
            'interpretation': interpretation,
            'etf_count': count,
        }
        
    except Exception as e:
        print(f"    ⚠️ ETF flow fetch error: {e}")
        return None


# ============================================================================
# METALS RATIOS
# ============================================================================

def fetch_copper_gold_ratio() -> dict:
    """Calculate Copper/Gold ratio - economic barometer."""
    try:
        import yfinance as yf
        
        copper = yf.Ticker('HG=F').history(period='60d')
        gold = yf.Ticker('GC=F').history(period='60d')
        
        if copper.empty or gold.empty:
            return None
        
        # Copper in cents/lb, Gold in $/oz - create comparable ratio
        current_ratio = (copper['Close'].iloc[-1] * 100) / gold['Close'].iloc[-1]
        prev_ratio = (copper['Close'].iloc[-2] * 100) / gold['Close'].iloc[-2]
        
        pct_change = ((current_ratio - prev_ratio) / prev_ratio) * 100
        
        # 5-day and 20-day trend
        if len(copper) >= 5:
            ratio_5d = (copper['Close'].iloc[-5] * 100) / gold['Close'].iloc[-5]
            roc_5d = ((current_ratio - ratio_5d) / ratio_5d) * 100
        else:
            roc_5d = pct_change
        
        if len(copper) >= 20:
            ratio_20d = (copper['Close'].iloc[-20] * 100) / gold['Close'].iloc[-20]
            roc_20d = ((current_ratio - ratio_20d) / ratio_20d) * 100
        else:
            roc_20d = roc_5d
        
        return {
            'ratio': current_ratio,
            'pct_change': pct_change,
            'roc_5d': roc_5d,
            'roc_20d': roc_20d,
            'trend': 'rising' if roc_5d > 0 else 'falling',
            'signal': 'risk_on' if roc_5d > 0 else 'risk_off',
        }
    except:
        return None


def fetch_gold_silver_ratio() -> dict:
    """Calculate Gold/Silver ratio - fear gauge."""
    try:
        import yfinance as yf
        
        gold = yf.Ticker('GC=F').history(period='60d')
        silver = yf.Ticker('SI=F').history(period='60d')
        
        if gold.empty or silver.empty:
            return None
        
        current_ratio = gold['Close'].iloc[-1] / silver['Close'].iloc[-1]
        prev_ratio = gold['Close'].iloc[-2] / silver['Close'].iloc[-2]
        
        pct_change = ((current_ratio - prev_ratio) / prev_ratio) * 100
        
        # Interpretation
        if current_ratio > 80:
            signal = 'risk_off'
            interpretation = 'Fear elevated (>80)'
        elif current_ratio < 60:
            signal = 'risk_on'
            interpretation = 'Risk appetite (<60)'
        else:
            signal = 'neutral'
            interpretation = 'Normal range (60-80)'
        
        return {
            'ratio': current_ratio,
            'pct_change': pct_change,
            'signal': signal,
            'interpretation': interpretation,
        }
    except:
        return None


# ============================================================================
# NEWS SENTIMENT & TRUMP EFFECT ANALYSIS
# ============================================================================

def fetch_news_from_rss(feed_url: str, max_items: int = 20) -> list:
    """
    Fetch news articles from RSS feed.
    Returns list of dicts with title, description, published date.
    """
    try:
        import xml.etree.ElementTree as ET
        
        response = requests.get(feed_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        })
        
        if response.status_code != 200:
            return []
        
        # Try to parse as XML
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            return []
        
        articles = []
        
        # Handle different RSS formats (standard RSS and Atom)
        # Standard RSS items
        for item in root.findall('.//item')[:max_items]:
            title = item.find('title')
            desc = item.find('description')
            pub_date = item.find('pubDate')
            
            if title is not None and title.text:
                articles.append({
                    'title': title.text.strip(),
                    'description': desc.text.strip() if desc is not None and desc.text else '',
                    'published': pub_date.text if pub_date is not None else '',
                })
        
        # Atom entries (Google News uses this)
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry')[:max_items]:
            title = entry.find('{http://www.w3.org/2005/Atom}title')
            content = entry.find('{http://www.w3.org/2005/Atom}content')
            published = entry.find('{http://www.w3.org/2005/Atom}published')
            
            if title is not None and title.text:
                articles.append({
                    'title': title.text.strip(),
                    'description': content.text.strip() if content is not None and content.text else '',
                    'published': published.text if published is not None else '',
                })
        
        return articles
        
    except Exception as e:
        return []


def fetch_news_from_yahoo_finance() -> list:
    """
    Fetch latest market news from Yahoo Finance.
    Uses yfinance's built-in news functionality.
    """
    try:
        import yfinance as yf
        
        articles = []
        
        # Get news from major market tickers - expanded list
        tickers_for_news = ['SPY', '^GSPC', '^DJI', 'QQQ', 'EFA', 'VGK', 'AAPL', 'NVDA']
        
        for ticker_symbol in tickers_for_news:
            try:
                ticker = yf.Ticker(ticker_symbol)
                news = ticker.news
                
                if news:
                    for item in news[:5]:  # Get top 5 from each
                        articles.append({
                            'title': item.get('title', ''),
                            'description': item.get('summary', item.get('title', '')),
                            'published': item.get('providerPublishTime', ''),
                            'source': item.get('publisher', 'Unknown'),
                            'url': item.get('link', ''),
                        })
            except:
                continue
        
        # Remove duplicates based on title
        seen_titles = set()
        unique_articles = []
        for article in articles:
            if article['title'] and article['title'] not in seen_titles:
                seen_titles.add(article['title'])
                unique_articles.append(article)
        
        return unique_articles[:25]  # Return top 25 unique articles
        
    except Exception as e:
        return []


def fetch_all_news() -> list:
    """
    Fetch news from ALL available sources (Yahoo Finance + RSS feeds).
    More aggressive approach to get fresh news.
    """
    all_articles = []
    
    # 1. Try Yahoo Finance first
    print("    Fetching from Yahoo Finance...")
    yahoo_articles = fetch_news_from_yahoo_finance()
    if yahoo_articles:
        all_articles.extend(yahoo_articles)
        print(f"    ✓ Got {len(yahoo_articles)} from Yahoo Finance")
    
    # 2. Fetch from ALL RSS feeds (don't stop early)
    print("    Fetching from RSS feeds...")
    for feed_name, feed_url in NEWS_RSS_FEEDS.items():
        try:
            rss_articles = fetch_news_from_rss(feed_url, max_items=15)
            if rss_articles:
                all_articles.extend(rss_articles)
                print(f"    ✓ Got {len(rss_articles)} from {feed_name}")
        except Exception as e:
            continue
    
    # 3. Remove duplicates based on title similarity
    seen_titles = set()
    unique_articles = []
    for article in all_articles:
        title = article.get('title', '').strip().lower()
        # Simple deduplication - check if title is similar
        if title and len(title) > 10:
            # Create a simplified key for comparison
            title_key = ''.join(title.split()[:5])  # First 5 words
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_articles.append(article)
    
    print(f"    Total unique articles: {len(unique_articles)}")
    return unique_articles


def analyze_sentiment(text: str) -> dict:
    """
    Analyze sentiment of text using keyword matching.
    Returns sentiment score from -1 (bearish) to +1 (bullish) and volatility flag.
    """
    if not text:
        return {'score': 0, 'label': 'neutral', 'volatility': False}
    
    text_lower = text.lower()
    
    bullish_count = sum(1 for kw in NEWS_KEYWORDS['bullish'] if kw in text_lower)
    bearish_count = sum(1 for kw in NEWS_KEYWORDS['bearish'] if kw in text_lower)
    volatility_count = sum(1 for kw in NEWS_KEYWORDS['volatility'] if kw in text_lower)
    
    total = bullish_count + bearish_count
    
    if total == 0:
        score = 0
    else:
        score = (bullish_count - bearish_count) / total
    
    # Determine label
    if score > 0.3:
        label = 'bullish'
    elif score < -0.3:
        label = 'bearish'
    else:
        label = 'neutral'
    
    return {
        'score': score,
        'label': label,
        'bullish_hits': bullish_count,
        'bearish_hits': bearish_count,
        'volatility': volatility_count > 0,
    }


def analyze_trump_effect(text: str) -> dict:
    """
    Analyze text for Trump-related content and assess market impact.
    Returns Trump Effect score and classification.
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Check if article mentions Trump
    trump_mentioned = any(kw in text_lower for kw in TRUMP_KEYWORDS['identifiers'])
    
    if not trump_mentioned:
        return None
    
    # Analyze policy sentiment
    bullish_policy = sum(1 for kw in TRUMP_KEYWORDS['policy_bullish'] if kw in text_lower)
    bearish_policy = sum(1 for kw in TRUMP_KEYWORDS['policy_bearish'] if kw in text_lower)
    volatility_triggers = sum(1 for kw in TRUMP_KEYWORDS['market_volatility'] if kw in text_lower)
    
    # Calculate Trump Effect score
    policy_total = bullish_policy + bearish_policy
    
    if policy_total == 0:
        policy_score = 0
    else:
        policy_score = (bullish_policy - bearish_policy) / policy_total
    
    # Classify the Trump Effect
    if bearish_policy > 0 and 'tariff' in text_lower:
        effect_type = 'tariff_risk'
        interpretation = 'Tariff/Trade War Risk'
    elif bullish_policy > bearish_policy:
        effect_type = 'pro_business'
        interpretation = 'Pro-Business Policy'
    elif bearish_policy > bullish_policy:
        effect_type = 'policy_risk'
        interpretation = 'Policy Uncertainty'
    elif volatility_triggers > 0:
        effect_type = 'volatility_event'
        interpretation = 'Volatility Trigger'
    else:
        effect_type = 'mention'
        interpretation = 'General Mention'
    
    return {
        'mentioned': True,
        'policy_score': policy_score,
        'bullish_policies': bullish_policy,
        'bearish_policies': bearish_policy,
        'volatility_triggers': volatility_triggers,
        'effect_type': effect_type,
        'interpretation': interpretation,
    }


def fetch_news_sentiment() -> dict:
    """
    Fetch news and analyze overall market sentiment + Trump Effect.
    Returns comprehensive news analysis.
    """
    # Use the new aggressive fetching approach
    articles = fetch_all_news()
    
    if not articles:
        return {
            'overall_sentiment': {'score': 0, 'label': 'neutral', 'signal': 0},
            'trump_effect': None,
            'article_count': 0,
            'bullish_count': 0,
            'bearish_count': 0,
            'neutral_count': 0,
            'headlines': [],
        }
    
    print(f"    Analyzing {len(articles)} articles...")
    
    # Analyze all articles
    sentiments = []
    trump_articles = []
    headlines = []
    
    for article in articles:
        text = f"{article.get('title', '')} {article.get('description', '')}"
        
        # General sentiment
        sentiment = analyze_sentiment(text)
        sentiments.append(sentiment)
        
        # Trump Effect
        trump_analysis = analyze_trump_effect(text)
        if trump_analysis:
            trump_articles.append({
                'title': article.get('title', ''),
                'analysis': trump_analysis,
            })
        
        # Store headline with sentiment
        headlines.append({
            'title': article.get('title', '')[:80],
            'sentiment': sentiment['label'],
            'score': sentiment['score'],
        })
    
    # Calculate overall sentiment
    avg_score = np.mean([s['score'] for s in sentiments]) if sentiments else 0
    bullish_count = sum(1 for s in sentiments if s['label'] == 'bullish')
    bearish_count = sum(1 for s in sentiments if s['label'] == 'bearish')
    neutral_count = sum(1 for s in sentiments if s['label'] == 'neutral')
    
    # Determine signal
    if avg_score > 0.15:
        signal = 1
        label = 'bullish'
    elif avg_score < -0.15:
        signal = -1
        label = 'bearish'
    else:
        signal = 0
        label = 'neutral'
    
    # Aggregate Trump Effect
    trump_effect = None
    if trump_articles:
        trump_scores = [a['analysis']['policy_score'] for a in trump_articles]
        avg_trump_score = np.mean(trump_scores)
        
        # Count effect types
        tariff_count = sum(1 for a in trump_articles if a['analysis']['effect_type'] == 'tariff_risk')
        volatility_count = sum(1 for a in trump_articles if a['analysis']['volatility_triggers'] > 0)
        
        # Determine Trump signal
        if tariff_count > 0:
            trump_signal = -1
            trump_interpretation = f'⚠️ Tariff/Trade concerns ({tariff_count} articles)'
        elif avg_trump_score > 0.2:
            trump_signal = 1
            trump_interpretation = 'Pro-business policy sentiment'
        elif avg_trump_score < -0.2:
            trump_signal = -1
            trump_interpretation = 'Policy uncertainty/risk'
        elif volatility_count > 0:
            trump_signal = 0
            trump_interpretation = f'Volatility trigger ({volatility_count} events)'
        else:
            trump_signal = 0
            trump_interpretation = 'Neutral mentions'
        
        trump_effect = {
            'article_count': len(trump_articles),
            'avg_score': avg_trump_score,
            'signal': trump_signal,
            'interpretation': trump_interpretation,
            'tariff_mentions': tariff_count,
            'volatility_triggers': volatility_count,
            'headlines': [a['title'] for a in trump_articles[:3]],
        }
    
    return {
        'overall_sentiment': {
            'score': avg_score,
            'label': label,
            'signal': signal,
        },
        'trump_effect': trump_effect,
        'article_count': len(articles),
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
        'neutral_count': neutral_count,
        'volatility_detected': any(s['volatility'] for s in sentiments),
        'headlines': sorted(headlines, key=lambda x: abs(x['score']), reverse=True)[:5],
    }


def process_news_section() -> tuple:
    """
    Process news sentiment section including Trump Effect.
    Returns: (results_list, section_score, news_data)
    """
    results = []
    total_score = 0
    count = 0
    
    news_data = fetch_news_sentiment()
    
    if news_data['article_count'] == 0:
        return results, 0, news_data
    
    # Overall News Sentiment
    sentiment = news_data['overall_sentiment']
    signal = sentiment['signal']
    total_score += signal
    count += 1
    
    sentiment_emoji = EMOJI['green'] if signal == 1 else EMOJI['red'] if signal == -1 else EMOJI['yellow']
    results.append({
        'Indicator': 'News Sentiment',
        'Value': f"{sentiment['score']:.2f}",
        'Change': f"{sentiment['label'].title()}",
        '%ile': 'N/A',
        '5D': f"{news_data['article_count']} articles",
        'Signal': format_signal(signal)
    })
    
    # Bullish vs Bearish breakdown
    bull_bear_ratio = news_data['bullish_count'] / max(news_data['bearish_count'], 1)
    results.append({
        'Indicator': 'Bull/Bear Ratio',
        'Value': f"{bull_bear_ratio:.2f}",
        'Change': f"B:{news_data['bullish_count']} / R:{news_data['bearish_count']}",
        '%ile': 'N/A',
        '5D': f"Ntrl:{news_data['neutral_count']}",
        'Signal': format_signal(1 if bull_bear_ratio > 1.5 else -1 if bull_bear_ratio < 0.67 else 0)
    })
    
    # Volatility Detection
    vol_signal = -1 if news_data.get('volatility_detected') else 0
    results.append({
        'Indicator': 'Vol. Keywords',
        'Value': 'Detected' if news_data.get('volatility_detected') else 'None',
        'Change': 'Caution' if news_data.get('volatility_detected') else 'Calm',
        '%ile': 'N/A',
        '5D': 'N/A',
        'Signal': format_signal(vol_signal)
    })
    if news_data.get('volatility_detected'):
        total_score += vol_signal
        count += 1
    
    # Trump Effect (sub-indicator)
    trump = news_data.get('trump_effect')
    if trump:
        trump_signal = trump['signal']
        total_score += trump_signal
        count += 1
        
        results.append({
            'Indicator': '🇺🇸 Trump Effect',
            'Value': f"{trump['avg_score']:.2f}",
            'Change': trump['interpretation'][:25],
            '%ile': 'N/A',
            '5D': f"{trump['article_count']} mentions",
            'Signal': format_signal(trump_signal)
        })
        
        # Tariff Risk sub-indicator
        if trump['tariff_mentions'] > 0:
            results.append({
                'Indicator': '  └ Tariff Risk',
                'Value': f"{trump['tariff_mentions']} mentions",
                'Change': '⚠️ Trade War Risk',
                '%ile': 'N/A',
                '5D': 'ALERT',
                'Signal': format_signal(-1)
            })
            total_score -= 1  # Extra penalty for tariff mentions
            count += 1
    else:
        results.append({
            'Indicator': '🇺🇸 Trump Effect',
            'Value': 'None',
            'Change': 'No recent mentions',
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(0)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, news_data

def fetch_vix_term_structure() -> dict:
    """Calculate VIX term structure."""
    try:
        import yfinance as yf
        
        vix = yf.Ticker('^VIX').history(period='30d')
        vix3m = yf.Ticker('^VIX3M').history(period='30d')
        
        if vix.empty or vix3m.empty:
            return None
        
        current_vix = vix['Close'].iloc[-1]
        current_vix3m = vix3m['Close'].iloc[-1]
        
        ratio = current_vix / current_vix3m
        
        structure = 'contango' if ratio < 1 else 'backwardation'
        signal = 'risk_on' if ratio < 0.95 else 'risk_off' if ratio > 1.05 else 'neutral'
        
        return {
            'vix': current_vix,
            'vix3m': current_vix3m,
            'ratio': ratio,
            'structure': structure,
            'signal': signal,
        }
    except:
        return None


# ============================================================================
# SIGNAL FORMATTING
# ============================================================================

def calculate_signal(name: str, pct_change: float) -> int:
    """Calculate risk signal: 1=risk-on, -1=risk-off, 0=neutral"""
    if abs(pct_change) < 0.05:
        return 0
    
    rising_is_risk_on = RISK_DIRECTION.get(name, True)
    
    if rising_is_risk_on:
        return 1 if pct_change > 0 else -1
    else:
        return -1 if pct_change > 0 else 1


def format_signal(signal: int) -> str:
    if signal == 1:
        return f"{EMOJI['green']} On"
    elif signal == -1:
        return f"{EMOJI['red']} Off"
    else:
        return f"{EMOJI['yellow']} Ntrl"


def format_change(pct_change: float) -> str:
    if pct_change > 0.1:
        return f"{EMOJI['up']} +{pct_change:.2f}%"
    elif pct_change < -0.1:
        return f"{EMOJI['down']} {pct_change:.2f}%"
    else:
        return f"{EMOJI['flat']} {pct_change:.2f}%"


def format_value(value: float, name: str) -> str:
    if 'Yield' in name or 'Spread' in name:
        return f"{value:.2f}%"
    elif name in ['Bitcoin', 'Ethereum', 'Gold', 'Platinum']:
        return f"${value:,.0f}"
    elif name in ['Silver', 'Copper', 'Crude Oil WTI', 'Brent Crude', 'Natural Gas']:
        return f"${value:.2f}"
    elif 'VIX' in name:
        return f"{value:.1f}"
    elif name in ['Solana', 'Cardano', 'XRP', 'Avalanche']:
        return f"${value:.2f}"
    else:
        return f"{value:,.2f}"


# ============================================================================
# SECTION PROCESSORS
# ============================================================================

def process_section(section_name: str, indicators: dict) -> tuple:
    """Process a section of indicators."""
    results = []
    total_score = 0
    count = 0
    
    for name, symbol in indicators.items():
        data = fetch_data(symbol)
        
        if data is None:
            continue
        
        signal = calculate_signal(name, data['pct_change'])
        total_score += signal
        count += 1
        
        results.append({
            'Indicator': name,
            'Value': format_value(data['current'], name),
            'Change': format_change(data['pct_change']),
            '%ile': f"{data['percentile']:.0f}%",
            '5D': format_change(data['roc_5d']),
            'Signal': format_signal(signal)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, count


def process_credit_section() -> tuple:
    """Process credit spreads section."""
    results = []
    total_score = 0
    count = 0
    
    spreads = fetch_credit_spreads()
    
    for name, data in spreads.items():
        if name == 'HY-IG Differential':
            continue
        
        if data is None:
            continue
        
        # Credit spreads: falling = risk on
        signal = calculate_signal(name, data['pct_change'])
        
        # Additional threshold-based signal
        if name in CREDIT_THRESHOLDS:
            thresholds = CREDIT_THRESHOLDS[name]
            if data['current'] < thresholds['risk_on']:
                signal = 1
            elif data['current'] > thresholds['risk_off']:
                signal = -1
        
        total_score += signal
        count += 1
        
        results.append({
            'Indicator': name,
            'Value': f"{data['current']:.2f}%",
            'Change': format_change(data['pct_change']),
            '%ile': f"{data['percentile']:.0f}%",
            '5D': 'N/A',
            'Signal': format_signal(signal)
        })
    
    # Add HY-IG differential
    if 'HY-IG Differential' in spreads:
        diff = spreads['HY-IG Differential']
        results.append({
            'Indicator': 'HY-IG Diff',
            'Value': f"{diff['current']:.2f}%",
            'Change': diff['interpretation'],
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(-1 if 'concern' in diff['interpretation'].lower() else 1)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, spreads


def process_global_bonds_section() -> tuple:
    """
    Process comprehensive global bond markets section.
    Includes US Treasury yields (2Y, 10Y, 30Y), yield curve, and Japan bonds.
    """
    results = []
    total_score = 0
    count = 0
    bond_data = {}
    
    import yfinance as yf
    
    # ===== US TREASURY YIELDS =====
    us_yields = {}
    
    # US 2Y (using ^IRX as proxy - 13 week, or fetch from FRED)
    try:
        data_2y = fetch_fred_series('DGS2', days=60)
        if data_2y:
            us_yields['2Y'] = data_2y
            signal = calculate_signal('US 2Y Yield', data_2y['pct_change'])
            total_score += signal
            count += 1
            results.append({
                'Indicator': '🇺🇸 US 2Y Yield',
                'Value': f"{data_2y['current']:.2f}%",
                'Change': format_change(data_2y['pct_change']),
                '%ile': f"{data_2y['percentile']:.0f}%",
                '5D': 'FRED',
                'Signal': format_signal(signal)
            })
    except:
        pass
    
    # US 10Y
    try:
        data_10y = fetch_fred_series('DGS10', days=60)
        if data_10y:
            us_yields['10Y'] = data_10y
            signal = calculate_signal('US 10Y Yield', data_10y['pct_change'])
            total_score += signal
            count += 1
            results.append({
                'Indicator': '🇺🇸 US 10Y Yield',
                'Value': f"{data_10y['current']:.2f}%",
                'Change': format_change(data_10y['pct_change']),
                '%ile': f"{data_10y['percentile']:.0f}%",
                '5D': 'FRED',
                'Signal': format_signal(signal)
            })
    except:
        pass
    
    # US 30Y
    try:
        data_30y = fetch_fred_series('DGS30', days=60)
        if data_30y:
            us_yields['30Y'] = data_30y
            signal = calculate_signal('US 30Y Yield', data_30y['pct_change'])
            total_score += signal
            count += 1
            results.append({
                'Indicator': '🇺🇸 US 30Y Yield',
                'Value': f"{data_30y['current']:.2f}%",
                'Change': format_change(data_30y['pct_change']),
                '%ile': f"{data_30y['percentile']:.0f}%",
                '5D': 'FRED',
                'Signal': format_signal(signal)
            })
    except:
        pass
    
    # US 2Y-10Y Spread (Yield Curve)
    if '2Y' in us_yields and '10Y' in us_yields:
        spread_2y10y = us_yields['10Y']['current'] - us_yields['2Y']['current']
        # Inverted yield curve (negative spread) = risk off / recession signal
        signal = 1 if spread_2y10y > 0.5 else -1 if spread_2y10y < 0 else 0
        total_score += signal
        count += 1
        
        curve_status = "Normal" if spread_2y10y > 0.25 else "Flat" if spread_2y10y > -0.1 else "INVERTED"
        emoji = EMOJI['green'] if spread_2y10y > 0.25 else EMOJI['yellow'] if spread_2y10y > -0.1 else EMOJI['red']
        
        results.append({
            'Indicator': '🇺🇸 2Y-10Y Spread',
            'Value': f"{spread_2y10y:.2f}%",
            'Change': f"{emoji} {curve_status}",
            '%ile': 'N/A',
            '5D': 'Yield Curve',
            'Signal': format_signal(signal)
        })
        
        bond_data['us_curve'] = {
            'spread': spread_2y10y,
            'status': curve_status,
            'inverted': spread_2y10y < 0
        }
    
    bond_data['us_yields'] = us_yields
    
    # ===== JAPAN BONDS =====
    jp_data = {}
    
    # Japan 10Y Government Bond Yield (using ETF proxy or direct)
    try:
        # Try to get Japan 10Y yield via various methods
        # Method 1: Use ^TNX equivalent for Japan if available
        # Method 2: Use JGB ETF (1321.T or similar)
        # Method 3: Use TLT Japan equivalent
        
        # Using iShares Japan ETF as proxy for now
        ewj = yf.Ticker('EWJ')
        ewj_hist = ewj.history(period='60d')
        
        if not ewj_hist.empty:
            # Also try to get actual Japan 10Y from a reliable source
            pass
        
        # Try BNDX (international bond ETF) for broader exposure
        bndx = yf.Ticker('BNDX')
        bndx_hist = bndx.history(period='60d')
        
        if not bndx_hist.empty and len(bndx_hist) >= 2:
            current = bndx_hist['Close'].iloc[-1]
            previous = bndx_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100
            
            # Rising BNDX = falling intl yields = risk on
            signal = 1 if pct_change > 0.1 else -1 if pct_change < -0.1 else 0
            total_score += signal
            count += 1
            
            results.append({
                'Indicator': '🌍 Intl Bonds (BNDX)',
                'Value': f"${current:.2f}",
                'Change': format_change(pct_change),
                '%ile': 'N/A',
                '5D': 'ETF proxy',
                'Signal': format_signal(signal)
            })
            
            jp_data['bndx'] = {
                'price': current,
                'pct_change': pct_change
            }
    except:
        pass
    
    # Japan-specific: Try to get Japan Gov Bond futures or ETF
    try:
        # 2511.T is iShares Japan Government Bond ETF
        jgb = yf.Ticker('2511.T')
        jgb_hist = jgb.history(period='60d')
        
        if not jgb_hist.empty and len(jgb_hist) >= 2:
            current = jgb_hist['Close'].iloc[-1]
            previous = jgb_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100
            
            signal = 1 if pct_change > 0.05 else -1 if pct_change < -0.05 else 0
            total_score += signal
            count += 1
            
            results.append({
                'Indicator': '🇯🇵 JGB ETF',
                'Value': f"¥{current:.0f}",
                'Change': format_change(pct_change),
                '%ile': 'N/A',
                '5D': 'Japan Bonds',
                'Signal': format_signal(signal)
            })
            
            jp_data['jgb_etf'] = {
                'price': current,
                'pct_change': pct_change
            }
    except:
        pass
    
    bond_data['japan'] = jp_data
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, bond_data


def process_currencies_section() -> tuple:
    """
    Process currencies section including DXY, EUR/USD, USD/JPY.
    """
    results = []
    total_score = 0
    count = 0
    currency_data = {}
    
    import yfinance as yf
    
    # DXY - US Dollar Index
    try:
        dxy = yf.Ticker('DX-Y.NYB')
        dxy_hist = dxy.history(period='60d')
        
        if not dxy_hist.empty and len(dxy_hist) >= 2:
            current = dxy_hist['Close'].iloc[-1]
            previous = dxy_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100
            
            # 5D ROC
            if len(dxy_hist) >= 5:
                roc_5d = ((current - dxy_hist['Close'].iloc[-5]) / dxy_hist['Close'].iloc[-5]) * 100
            else:
                roc_5d = pct_change
            
            percentile = (dxy_hist['Close'] < current).sum() / len(dxy_hist['Close']) * 100
            
            # Rising DXY = stronger dollar = risk off (tightening)
            signal = -1 if pct_change > 0.1 else 1 if pct_change < -0.1 else 0
            total_score += signal
            count += 1
            
            results.append({
                'Indicator': '💵 DXY',
                'Value': f"{current:.2f}",
                'Change': format_change(pct_change),
                '%ile': f"{percentile:.0f}%",
                '5D': format_change(roc_5d),
                'Signal': format_signal(signal)
            })
            
            currency_data['DXY'] = {
                'current': current,
                'pct_change': pct_change,
                'roc_5d': roc_5d,
                'percentile': percentile
            }
    except Exception as e:
        print(f"    ⚠️ DXY fetch error: {e}")
    
    # EUR/USD
    try:
        eurusd = yf.Ticker('EURUSD=X')
        eurusd_hist = eurusd.history(period='60d')
        
        if not eurusd_hist.empty and len(eurusd_hist) >= 2:
            current = eurusd_hist['Close'].iloc[-1]
            previous = eurusd_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100
            
            if len(eurusd_hist) >= 5:
                roc_5d = ((current - eurusd_hist['Close'].iloc[-5]) / eurusd_hist['Close'].iloc[-5]) * 100
            else:
                roc_5d = pct_change
            
            # Rising EUR/USD = weaker dollar = risk on
            signal = 1 if pct_change > 0.1 else -1 if pct_change < -0.1 else 0
            total_score += signal
            count += 1
            
            results.append({
                'Indicator': '💶 EUR/USD',
                'Value': f"{current:.4f}",
                'Change': format_change(pct_change),
                '%ile': 'N/A',
                '5D': format_change(roc_5d),
                'Signal': format_signal(signal)
            })
            
            currency_data['EUR/USD'] = {
                'current': current,
                'pct_change': pct_change,
                'roc_5d': roc_5d
            }
    except:
        pass
    
    # USD/JPY
    try:
        usdjpy = yf.Ticker('JPY=X')
        usdjpy_hist = usdjpy.history(period='60d')
        
        if not usdjpy_hist.empty and len(usdjpy_hist) >= 2:
            current = usdjpy_hist['Close'].iloc[-1]
            previous = usdjpy_hist['Close'].iloc[-2]
            pct_change = ((current - previous) / previous) * 100
            
            if len(usdjpy_hist) >= 5:
                roc_5d = ((current - usdjpy_hist['Close'].iloc[-5]) / usdjpy_hist['Close'].iloc[-5]) * 100
            else:
                roc_5d = pct_change
            
            # Rising USD/JPY = weaker yen = risk on (carry trade)
            signal = 1 if pct_change > 0.1 else -1 if pct_change < -0.1 else 0
            total_score += signal
            count += 1
            
            results.append({
                'Indicator': '💴 USD/JPY',
                'Value': f"¥{current:.2f}",
                'Change': format_change(pct_change),
                '%ile': 'N/A',
                '5D': format_change(roc_5d),
                'Signal': format_signal(signal)
            })
            
            currency_data['USD/JPY'] = {
                'current': current,
                'pct_change': pct_change,
                'roc_5d': roc_5d
            }
    except:
        pass
    
    # Dollar Strength Assessment
    if 'DXY' in currency_data:
        dxy_roc = currency_data['DXY'].get('roc_5d', 0)
        if dxy_roc > 1:
            currency_data['dollar_trend'] = 'strengthening'
        elif dxy_roc < -1:
            currency_data['dollar_trend'] = 'weakening'
        else:
            currency_data['dollar_trend'] = 'stable'
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, currency_data


def print_bonds_analysis(bond_data: dict):
    """Print bond market analysis."""
    if not bond_data:
        return
    
    print(f"\n{'─' * 75}")
    print("  📊 BOND MARKET ANALYSIS")
    print(f"{'─' * 75}")
    
    # US Yield Curve
    if 'us_curve' in bond_data:
        curve = bond_data['us_curve']
        if curve['inverted']:
            print(f"  {EMOJI['red']} US YIELD CURVE: INVERTED ({curve['spread']:.2f}%)")
            print(f"     ⚠️ Historically precedes recessions by 12-18 months")
        elif curve['status'] == 'Flat':
            print(f"  {EMOJI['yellow']} US YIELD CURVE: FLAT ({curve['spread']:.2f}%)")
            print(f"     Watch for potential inversion")
        else:
            print(f"  {EMOJI['green']} US YIELD CURVE: NORMAL ({curve['spread']:.2f}%)")
            print(f"     Healthy term structure")
    
    # US Yields Summary
    if 'us_yields' in bond_data and bond_data['us_yields']:
        yields = bond_data['us_yields']
        print(f"\n  US Treasury Yields:")
        for tenor, data in yields.items():
            emoji = EMOJI['red'] if data['pct_change'] > 0 else EMOJI['green']
            print(f"    {emoji} {tenor}: {data['current']:.2f}% ({data['pct_change']:+.2f}% chg)")


def print_currencies_analysis(currency_data: dict):
    """Print currency market analysis."""
    if not currency_data:
        return
    
    print(f"\n{'─' * 75}")
    print("  💱 CURRENCY ANALYSIS")
    print(f"{'─' * 75}")
    
    # Dollar trend
    if 'dollar_trend' in currency_data:
        trend = currency_data['dollar_trend']
        if trend == 'strengthening':
            emoji = EMOJI['red']
            impact = "Headwind for risk assets, EM pressure"
        elif trend == 'weakening':
            emoji = EMOJI['green']
            impact = "Tailwind for risk assets, commodities"
        else:
            emoji = EMOJI['yellow']
            impact = "Neutral impact"
        
        print(f"  {emoji} Dollar Trend: {trend.upper()}")
        print(f"     → {impact}")
    
    # DXY level
    if 'DXY' in currency_data:
        dxy = currency_data['DXY']
        level = "Strong" if dxy['current'] > 105 else "Weak" if dxy['current'] < 100 else "Normal"
        print(f"\n  DXY Level: {dxy['current']:.2f} ({level})")
        print(f"     5D Change: {dxy['roc_5d']:+.2f}%")


def process_breadth_section() -> tuple:
    """Process market breadth section."""
    results = []
    total_score = 0
    count = 0
    
    breadth = fetch_market_breadth()
    
    if breadth is None:
        return [], 0, None
    
    # SPY vs 50-day MA
    signal = 1 if breadth['spy_above_50ma'] else -1
    total_score += signal
    count += 1
    results.append({
        'Indicator': 'SPY vs 50-DMA',
        'Value': 'Above' if breadth['spy_above_50ma'] else 'Below',
        'Change': 'N/A',
        '%ile': 'N/A',
        '5D': 'N/A',
        'Signal': format_signal(signal)
    })
    
    # SPY vs 200-day MA
    signal = 1 if breadth['spy_above_200ma'] else -1
    total_score += signal
    count += 1
    results.append({
        'Indicator': 'SPY vs 200-DMA',
        'Value': 'Above' if breadth['spy_above_200ma'] else 'Below',
        'Change': 'N/A',
        '%ile': 'N/A',
        '5D': 'N/A',
        'Signal': format_signal(signal)
    })
    
    # Breadth trend (RSP/SPY)
    signal = 1 if breadth['breadth_trend'] == 'improving' else -1 if breadth['breadth_trend'] == 'deteriorating' else 0
    total_score += signal
    count += 1
    results.append({
        'Indicator': 'Breadth Trend',
        'Value': breadth['breadth_trend'].title(),
        'Change': f"RSP/SPY: {breadth['rsp_spy_ratio']:.3f}",
        '%ile': 'N/A',
        '5D': 'N/A',
        'Signal': format_signal(signal)
    })
    
    # Small cap vs Large cap
    signal = 1 if breadth['risk_appetite'] == 'high' else -1 if breadth['risk_appetite'] == 'low' else 0
    total_score += signal
    count += 1
    results.append({
        'Indicator': 'Small vs Large',
        'Value': breadth['risk_appetite'].title(),
        'Change': format_change(breadth['small_vs_large_5d']),
        '%ile': 'N/A',
        '5D': 'IWM-SPY diff',
        'Signal': format_signal(signal)
    })
    
    # Estimated stocks above 50-DMA
    pct_above = breadth['estimated_above_50ma']
    signal = 1 if pct_above > 60 else -1 if pct_above < 40 else 0
    total_score += signal
    count += 1
    results.append({
        'Indicator': 'Est. >50-DMA',
        'Value': f"~{pct_above:.0f}%",
        'Change': 'Estimated',
        '%ile': 'N/A',
        '5D': 'N/A',
        'Signal': format_signal(signal)
    })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, breadth


def process_sentiment_section() -> tuple:
    """Process sentiment section (Put/Call ratio)."""
    results = []
    total_score = 0
    count = 0
    
    pcr_data = fetch_put_call_ratio()
    
    if pcr_data:
        # Put/Call is contrarian
        if pcr_data['signal'] == 'contrarian_buy':
            signal = 1
        elif pcr_data['signal'] == 'contrarian_sell':
            signal = -1
        elif pcr_data['signal'] == 'bullish':
            signal = 1
        elif pcr_data['signal'] == 'bearish':
            signal = -1
        else:
            signal = 0
        
        total_score += signal
        count += 1
        
        results.append({
            'Indicator': 'Put/Call Ratio',
            'Value': f"{pcr_data['pcr']:.2f}",
            'Change': pcr_data['interpretation'],
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(signal)
        })
        
        results.append({
            'Indicator': 'Put Volume',
            'Value': f"{pcr_data['put_volume']:,.0f}",
            'Change': 'N/A',
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(0)
        })
        
        results.append({
            'Indicator': 'Call Volume',
            'Value': f"{pcr_data['call_volume']:,.0f}",
            'Change': 'N/A',
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(0)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, pcr_data


def process_crypto_section() -> tuple:
    """Process crypto section with BTC dominance, altseason, Fear & Greed, and ETF flows."""
    results = []
    total_score = 0
    count = 0
    
    # Standard crypto
    for name, symbol in INDICATORS['crypto'].items():
        data = fetch_data(symbol)
        
        if data is None:
            continue
        
        signal = calculate_signal(name, data['pct_change'])
        total_score += signal
        count += 1
        
        results.append({
            'Indicator': name,
            'Value': format_value(data['current'], name),
            'Change': format_change(data['pct_change']),
            '%ile': f"{data['percentile']:.0f}%",
            '5D': format_change(data['roc_5d']),
            'Signal': format_signal(signal)
        })
    
    # BTC Dominance
    btc_dom = fetch_btc_dominance()
    if btc_dom:
        signal = -1 if btc_dom['signal'] == 'risk_off' else 1
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'BTC/ETH Ratio',
            'Value': f"{btc_dom['btc_eth_ratio']:.1f}",
            'Change': format_change(btc_dom['pct_change_5d']),
            '%ile': 'N/A',
            '5D': f"{btc_dom['trend'].title()}",
            'Signal': format_signal(signal)
        })
    
    # Altcoin performance
    alt_perf = fetch_altcoin_performance()
    
    # Fear & Greed Index
    print("    Fetching Crypto Fear & Greed Index...")
    fear_greed = fetch_crypto_fear_greed()
    if fear_greed:
        signal = fear_greed['signal']
        total_score += signal
        count += 1
        
        # Color-code based on value
        fg_value = fear_greed['value']
        if fg_value <= 24:
            fg_emoji = '😱'
        elif fg_value <= 44:
            fg_emoji = '😰'
        elif fg_value <= 55:
            fg_emoji = '😐'
        elif fg_value <= 74:
            fg_emoji = '😀'
        else:
            fg_emoji = '🤑'
        
        results.append({
            'Indicator': 'Fear & Greed',
            'Value': f"{fg_emoji} {fg_value}",
            'Change': fear_greed['classification'],
            '%ile': 'N/A',
            '5D': f"7d avg: {fear_greed['avg_7d']:.0f}",
            'Signal': format_signal(signal)
        })
    
    # Bitcoin ETF Flows
    print("    Fetching Bitcoin ETF Flows...")
    etf_flows = fetch_bitcoin_etf_flows()
    if etf_flows:
        signal = etf_flows['flow_signal']
        total_score += signal
        count += 1
        
        flow_emoji = '📈' if signal == 1 else '📉' if signal == -1 else '➡️'
        results.append({
            'Indicator': 'BTC ETF Flow',
            'Value': f"{flow_emoji} {etf_flows['interpretation']}",
            'Change': format_change(etf_flows['avg_price_change_5d']),
            '%ile': 'N/A',
            '5D': f"Vol: {etf_flows['avg_volume_change']:+.1f}%",
            'Signal': format_signal(signal)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, {
        'btc_dominance': btc_dom, 
        'altcoin_perf': alt_perf,
        'fear_greed': fear_greed,
        'etf_flows': etf_flows
    }


def process_metals_section() -> tuple:
    """Process metals section with ratios."""
    results = []
    total_score = 0
    count = 0
    
    # Standard metals
    for name, symbol in INDICATORS['metals'].items():
        data = fetch_data(symbol)
        
        if data is None:
            continue
        
        signal = calculate_signal(name, data['pct_change'])
        total_score += signal
        count += 1
        
        results.append({
            'Indicator': name,
            'Value': format_value(data['current'], name),
            'Change': format_change(data['pct_change']),
            '%ile': f"{data['percentile']:.0f}%",
            '5D': format_change(data['roc_5d']),
            'Signal': format_signal(signal)
        })
    
    # Copper/Gold
    cu_au = fetch_copper_gold_ratio()
    if cu_au:
        signal = 1 if cu_au['signal'] == 'risk_on' else -1
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'Copper/Gold',
            'Value': f"{cu_au['ratio']:.4f}",
            'Change': format_change(cu_au['pct_change']),
            '%ile': 'N/A',
            '5D': format_change(cu_au['roc_5d']),
            'Signal': format_signal(signal)
        })
    
    # Gold/Silver
    au_ag = fetch_gold_silver_ratio()
    if au_ag:
        signal = 1 if au_ag['signal'] == 'risk_on' else -1 if au_ag['signal'] == 'risk_off' else 0
        total_score += signal
        count += 1
        results.append({
            'Indicator': 'Gold/Silver',
            'Value': f"{au_ag['ratio']:.1f}",
            'Change': au_ag['interpretation'],
            '%ile': 'N/A',
            '5D': format_change(au_ag['pct_change']),
            'Signal': format_signal(signal)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, {'copper_gold': cu_au, 'gold_silver': au_ag}


def process_volatility_section() -> tuple:
    """Process volatility section with term structure."""
    results = []
    total_score = 0
    count = 0
    
    # Standard volatility
    for name, symbol in INDICATORS['volatility'].items():
        data = fetch_data(symbol)
        
        if data is None:
            continue
        
        signal = calculate_signal(name, data['pct_change'])
        total_score += signal
        count += 1
        
        results.append({
            'Indicator': name,
            'Value': format_value(data['current'], name),
            'Change': format_change(data['pct_change']),
            '%ile': f"{data['percentile']:.0f}%",
            '5D': format_change(data['roc_5d']),
            'Signal': format_signal(signal)
        })
    
    # Term structure
    vix_term = fetch_vix_term_structure()
    if vix_term:
        signal = 1 if vix_term['signal'] == 'risk_on' else -1 if vix_term['signal'] == 'risk_off' else 0
        total_score += signal
        count += 1
        emoji = EMOJI['green'] if vix_term['structure'] == 'contango' else EMOJI['red']
        results.append({
            'Indicator': 'VIX Term',
            'Value': f"{vix_term['ratio']:.2f}",
            'Change': f"{emoji} {vix_term['structure'].title()}",
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(signal)
        })
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, vix_term


def process_brazil_section() -> tuple:
    """
    Process Brazilian market section with comprehensive analysis.
    Includes Bovespa, EWZ, USD/BRL, major ADRs, and derived indicators.
    """
    results = []
    total_score = 0
    count = 0
    brazil_data = {}
    
    # Fetch all Brazilian indicators
    for name, symbol in INDICATORS['brazil'].items():
        data = fetch_data(symbol)
        
        if data is None:
            continue
        
        signal = calculate_signal(name, data['pct_change'])
        total_score += signal
        count += 1
        
        # Format value based on type
        if name == 'USD/BRL':
            value_str = f"R${data['current']:.4f}"
        elif name in ['EWZ', 'Petrobras', 'Vale', 'Itau Unibanco', 'Bradesco']:
            value_str = f"${data['current']:.2f}"
        else:
            value_str = f"{data['current']:,.2f}"
        
        results.append({
            'Indicator': name,
            'Value': value_str,
            'Change': format_change(data['pct_change']),
            '%ile': f"{data['percentile']:.0f}%",
            '5D': format_change(data['roc_5d']),
            'Signal': format_signal(signal)
        })
        
        brazil_data[name] = data
    
    # Calculate Brazil-specific indicators
    
    # 1. EWZ vs SPY (Brazil relative to US)
    try:
        import yfinance as yf
        ewz_hist = yf.Ticker('EWZ').history(period='30d')
        spy_hist = yf.Ticker('SPY').history(period='30d')
        
        if not ewz_hist.empty and not spy_hist.empty and len(ewz_hist) >= 5:
            ewz_return_5d = ((ewz_hist['Close'].iloc[-1] - ewz_hist['Close'].iloc[-5]) / ewz_hist['Close'].iloc[-5]) * 100
            spy_return_5d = ((spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[-5]) / spy_hist['Close'].iloc[-5]) * 100
            ewz_vs_spy = ewz_return_5d - spy_return_5d
            
            signal = 1 if ewz_vs_spy > 1 else -1 if ewz_vs_spy < -1 else 0
            total_score += signal
            count += 1
            
            results.append({
                'Indicator': 'EWZ vs SPY',
                'Value': f"{ewz_vs_spy:+.2f}%",
                'Change': 'Outperform' if ewz_vs_spy > 0 else 'Underperform',
                '%ile': 'N/A',
                '5D': '5D relative',
                'Signal': format_signal(signal)
            })
            
            brazil_data['ewz_vs_spy'] = {
                'value': ewz_vs_spy,
                'ewz_return': ewz_return_5d,
                'spy_return': spy_return_5d,
            }
    except:
        pass
    
    # 2. BRL Strength Index (inverse of USD/BRL change)
    if 'USD/BRL' in brazil_data:
        brl_data = brazil_data['USD/BRL']
        # Negative USD/BRL change = BRL strengthening = risk on
        brl_strength = -brl_data['pct_change']
        brl_strength_5d = -brl_data['roc_5d']
        
        signal = 1 if brl_strength > 0.2 else -1 if brl_strength < -0.2 else 0
        
        results.append({
            'Indicator': 'BRL Strength',
            'Value': f"{brl_strength:+.2f}%",
            'Change': 'Strengthening' if brl_strength > 0 else 'Weakening',
            '%ile': 'N/A',
            '5D': f"{brl_strength_5d:+.2f}%",
            'Signal': format_signal(signal)
        })
        
        brazil_data['brl_strength'] = {
            'daily': brl_strength,
            '5d': brl_strength_5d,
        }
    
    # 3. Brazil Commodity Exposure (Vale + Petrobras average)
    if 'Vale' in brazil_data and 'Petrobras' in brazil_data:
        vale_chg = brazil_data['Vale']['pct_change']
        pbr_chg = brazil_data['Petrobras']['pct_change']
        commodity_avg = (vale_chg + pbr_chg) / 2
        
        signal = 1 if commodity_avg > 0.5 else -1 if commodity_avg < -0.5 else 0
        
        results.append({
            'Indicator': 'Commodity Proxy',
            'Value': f"{commodity_avg:+.2f}%",
            'Change': 'VALE+PBR avg',
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(signal)
        })
        
        brazil_data['commodity_proxy'] = commodity_avg
    
    # 4. Brazil Financials (Banks average)
    if 'Itau Unibanco' in brazil_data and 'Bradesco' in brazil_data:
        itub_chg = brazil_data['Itau Unibanco']['pct_change']
        bbd_chg = brazil_data['Bradesco']['pct_change']
        banks_avg = (itub_chg + bbd_chg) / 2
        
        signal = 1 if banks_avg > 0.5 else -1 if banks_avg < -0.5 else 0
        
        results.append({
            'Indicator': 'Banks Proxy',
            'Value': f"{banks_avg:+.2f}%",
            'Change': 'ITUB+BBD avg',
            '%ile': 'N/A',
            '5D': 'N/A',
            'Signal': format_signal(signal)
        })
        
        brazil_data['banks_proxy'] = banks_avg
    
    section_score = total_score / count if count > 0 else 0
    return results, section_score, brazil_data


def print_brazil_analysis(brazil_data: dict):
    """Print Brazilian market analysis."""
    if not brazil_data:
        return
    
    print(f"\n{'─' * 75}")
    print("  🇧🇷 BRAZIL MARKET DEEP DIVE")
    print(f"{'─' * 75}")
    
    # Currency analysis
    if 'brl_strength' in brazil_data:
        brl = brazil_data['brl_strength']
        emoji = EMOJI['green'] if brl['daily'] > 0 else EMOJI['red']
        trend = "strengthening" if brl['daily'] > 0 else "weakening"
        print(f"  {emoji} Brazilian Real: {trend} ({brl['daily']:+.2f}% daily, {brl['5d']:+.2f}% 5D)")
        if brl['5d'] < -2:
            print(f"     ⚠️ Significant BRL weakness - watch for capital outflows")
        elif brl['5d'] > 2:
            print(f"     ✅ Strong BRL - favorable for local equities")
    
    # Relative performance
    if 'ewz_vs_spy' in brazil_data:
        rel = brazil_data['ewz_vs_spy']
        emoji = EMOJI['green'] if rel['value'] > 0 else EMOJI['red']
        print(f"\n  {emoji} EWZ vs SPY (5D): {rel['value']:+.2f}%")
        print(f"     EWZ: {rel['ewz_return']:+.2f}% | SPY: {rel['spy_return']:+.2f}%")
        if rel['value'] > 3:
            print(f"     🔥 Brazil significantly outperforming US!")
        elif rel['value'] < -3:
            print(f"     ⚠️ Brazil significantly underperforming US")
    
    # Sector analysis
    if 'commodity_proxy' in brazil_data:
        comm = brazil_data['commodity_proxy']
        emoji = EMOJI['green'] if comm > 0 else EMOJI['red']
        print(f"\n  {emoji} Commodities (Vale+Petrobras): {comm:+.2f}%")
    
    if 'banks_proxy' in brazil_data:
        banks = brazil_data['banks_proxy']
        emoji = EMOJI['green'] if banks > 0 else EMOJI['red']
        print(f"  {emoji} Financials (Itau+Bradesco): {banks:+.2f}%")
    
    # Overall Brazil assessment
    signals = []
    if brazil_data.get('brl_strength', {}).get('5d', 0) > 1:
        signals.append("BRL strength")
    if brazil_data.get('ewz_vs_spy', {}).get('value', 0) > 2:
        signals.append("outperforming US")
    if brazil_data.get('commodity_proxy', 0) > 1:
        signals.append("commodities rallying")
    if brazil_data.get('banks_proxy', 0) > 1:
        signals.append("financials strong")
    
    if len(signals) >= 3:
        print(f"\n  🔥 BRAZIL OUTLOOK: BULLISH ({', '.join(signals)})")
    elif len(signals) >= 1:
        print(f"\n  🟡 BRAZIL OUTLOOK: MIXED ({', '.join(signals) if signals else 'no clear signals'})")
    else:
        print(f"\n  ⚠️ BRAZIL OUTLOOK: CAUTIOUS (no bullish signals)")


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def print_header():
    """Print report header."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n{'█' * 75}")
    print(f"█{'':73}█")
    print(f"█{'ULTIMATE RISK APPETITE MONITOR v4.0':^73}█")
    print(f"█{'Professional-Grade Risk Assessment':^73}█")
    print(f"█{f'Generated: {timestamp}':^73}█")
    print(f"█{'':73}█")
    print(f"{'█' * 75}")


def print_section(title: str, results: list, section_score: float, weight: float = 0.1):
    """Print a formatted section."""
    score_emoji = EMOJI['green'] if section_score > 0.3 else EMOJI['red'] if section_score < -0.3 else EMOJI['yellow']
    weighted_contrib = section_score * weight * 5
    
    print(f"\n{'═' * 75}")
    print(f"  {title}")
    print(f"  Section Score: {section_score:+.2f} {score_emoji}  │  Weight: {weight:.0%}  │  Contribution: {weighted_contrib:+.2f}")
    print(f"{'═' * 75}")
    
    if results:
        df = pd.DataFrame(results)
        print(tabulate(df, headers='keys', tablefmt='simple', showindex=False))
    else:
        print("  ⚠️  No data available for this section")


def print_crypto_analysis(crypto_data: dict):
    """Print crypto-specific analysis."""
    if not crypto_data:
        return
    
    print(f"\n{'─' * 75}")
    print("  CRYPTO DEEP DIVE")
    print(f"{'─' * 75}")
    
    if crypto_data.get('btc_dominance'):
        dom = crypto_data['btc_dominance']
        trend_emoji = EMOJI['red'] if dom['trend'] == 'rising' else EMOJI['green']
        print(f"  BTC Dominance Trend: {trend_emoji} {dom['trend'].title()} (5D: {dom['pct_change_5d']:+.1f}%)")
        print(f"  → {dom['trend'].title()} BTC/ETH ratio = {'Altcoin weakness' if dom['trend'] == 'rising' else 'Altseason potential'}")
    
    if crypto_data.get('altcoin_perf'):
        alt = crypto_data['altcoin_perf']
        print(f"\n  7-Day Returns:")
        for name, ret in alt['returns_7d'].items():
            emoji = EMOJI['green'] if ret > 0 else EMOJI['red']
            print(f"    {name:6} {emoji} {ret:+.1f}%", end='')
            if name in alt['alt_vs_btc']:
                vs_btc = alt['alt_vs_btc'][name]
                vs_emoji = EMOJI['green'] if vs_btc > 0 else EMOJI['red']
                print(f"  (vs BTC: {vs_emoji} {vs_btc:+.1f}%)")
            else:
                print()
        
        if alt['altseason']:
            print(f"\n  {EMOJI['fire']} ALTSEASON DETECTED: Altcoins outperforming BTC by {alt['avg_outperformance']:.1f}%")
        else:
            print(f"\n  {EMOJI['yellow']} No altseason signal (avg outperformance: {alt['avg_outperformance']:.1f}%)")
    
    # Fear & Greed Index
    if crypto_data.get('fear_greed'):
        fg = crypto_data['fear_greed']
        print(f"\n  Fear & Greed Index:")
        fg_bar = '█' * (fg['value'] // 5) + '░' * (20 - fg['value'] // 5)
        print(f"    Current: {fg['value']} ({fg['classification']}) [{fg_bar}]")
        print(f"    7-Day Avg: {fg['avg_7d']:.0f} | Trend: {fg['trend'].title()}")
        print(f"    Signal: {fg['interpretation']}")
    
    # ETF Flows
    if crypto_data.get('etf_flows'):
        flows = crypto_data['etf_flows']
        print(f"\n  Bitcoin ETF Analysis ({flows['etf_count']} ETFs):")
        print(f"    5D Price Change: {flows['avg_price_change_5d']:+.2f}%")
        print(f"    Volume Change: {flows['avg_volume_change']:+.1f}%")
        flow_emoji = EMOJI['green'] if flows['flow_signal'] == 1 else EMOJI['red'] if flows['flow_signal'] == -1 else EMOJI['yellow']
        print(f"    Flow Signal: {flow_emoji} {flows['interpretation']}")


def print_credit_analysis(credit_data: dict):
    """Print credit spread analysis."""
    if not credit_data:
        return
    
    print(f"\n{'─' * 75}")
    print("  CREDIT MARKET ANALYSIS")
    print(f"{'─' * 75}")
    
    if 'HY Spread' in credit_data:
        hy = credit_data['HY Spread']['current']
        if hy < 3.0:
            print(f"  {EMOJI['green']} HY Spread at {hy:.2f}% - TIGHT (historically favorable)")
        elif hy > 6.0:
            print(f"  {EMOJI['red']} HY Spread at {hy:.2f}% - WIDE (stress signal)")
        else:
            print(f"  {EMOJI['yellow']} HY Spread at {hy:.2f}% - Normal range")
    
    if 'HY-IG Differential' in credit_data:
        diff = credit_data['HY-IG Differential']
        print(f"  HY-IG Differential: {diff['current']:.2f}% - {diff['interpretation']}")


def print_liquidity_analysis(liquidity_data: dict):
    """Print global liquidity analysis."""
    if not liquidity_data:
        return
    
    print(f"\n{'─' * 75}")
    print("  GLOBAL LIQUIDITY ANALYSIS")
    print(f"{'─' * 75}")
    
    # US M2
    if 'US M2' in liquidity_data:
        m2 = liquidity_data['US M2']
        emoji = EMOJI['green'] if m2['pct_change'] > 0 else EMOJI['red']
        print(f"  {emoji} US M2: ${m2['current']/1000:.1f}T ({m2['pct_change']:+.2f}% MoM)")
    
    # Fed Balance Sheet
    if 'WALCL' in liquidity_data:
        walcl = liquidity_data['WALCL']
        emoji = EMOJI['green'] if walcl['pct_change'] > 0 else EMOJI['red']
        print(f"  {emoji} Fed Balance Sheet: ${walcl['current']/1000000:.2f}T ({walcl['pct_change']:+.2f}% WoW)")
    
    # Global Liquidity Index
    if 'Global Liquidity Index' in liquidity_data:
        gli = liquidity_data['Global Liquidity Index']
        emoji = EMOJI['green'] if gli['expanding'] else EMOJI['red']
        status = "EXPANDING" if gli['expanding'] else "CONTRACTING"
        print(f"\n  {emoji} Global Liquidity: {status} (avg: {gli['avg_change']:+.2f}%)")
        print(f"     Based on {gli['components']} liquidity sources")
        
        if gli['expanding']:
            print(f"     → Favorable for risk assets (equities, crypto)")
        else:
            print(f"     → Headwind for risk assets, favor quality")


def print_news_analysis(news_data: dict):
    """Print news sentiment and Trump Effect analysis."""
    if not news_data or news_data.get('article_count', 0) == 0:
        print(f"\n{'─' * 75}")
        print("  NEWS ANALYSIS")
        print(f"{'─' * 75}")
        print(f"  {EMOJI['yellow']} No news data available")
        return
    
    print(f"\n{'─' * 75}")
    print("  NEWS SENTIMENT ANALYSIS")
    print(f"{'─' * 75}")
    
    sentiment = news_data['overall_sentiment']
    emoji = EMOJI['green'] if sentiment['signal'] == 1 else EMOJI['red'] if sentiment['signal'] == -1 else EMOJI['yellow']
    
    print(f"  Overall Sentiment: {emoji} {sentiment['label'].upper()} (score: {sentiment['score']:.2f})")
    print(f"  Articles Analyzed: {news_data['article_count']}")
    print(f"  Breakdown: 🟢 Bullish: {news_data['bullish_count']} | 🔴 Bearish: {news_data['bearish_count']} | 🟡 Neutral: {news_data['neutral_count']}")
    
    if news_data.get('volatility_detected'):
        print(f"  {EMOJI['warning']} Volatility keywords detected in news!")
    
    # Top headlines
    if news_data.get('headlines'):
        print(f"\n  Top Market-Moving Headlines:")
        for i, hl in enumerate(news_data['headlines'][:3], 1):
            sent_emoji = EMOJI['green'] if hl['sentiment'] == 'bullish' else EMOJI['red'] if hl['sentiment'] == 'bearish' else EMOJI['yellow']
            print(f"    {i}. {sent_emoji} {hl['title'][:65]}...")
    
    # Trump Effect
    trump = news_data.get('trump_effect')
    if trump:
        print(f"\n{'─' * 75}")
        print("  🇺🇸 TRUMP EFFECT ANALYSIS")
        print(f"{'─' * 75}")
        
        trump_emoji = EMOJI['green'] if trump['signal'] == 1 else EMOJI['red'] if trump['signal'] == -1 else EMOJI['yellow']
        print(f"  Signal: {trump_emoji} {trump['interpretation']}")
        print(f"  Articles Mentioning Trump: {trump['article_count']}")
        print(f"  Policy Score: {trump['avg_score']:.2f}")
        
        if trump['tariff_mentions'] > 0:
            print(f"  {EMOJI['warning']} TARIFF ALERT: {trump['tariff_mentions']} tariff-related mentions!")
            print(f"     → Trade war/tariff news typically causes market volatility")
        
        if trump['volatility_triggers'] > 0:
            print(f"  {EMOJI['warning']} Volatility Triggers: {trump['volatility_triggers']} events detected")
        
        if trump.get('headlines'):
            print(f"\n  Trump-Related Headlines:")
            for i, hl in enumerate(trump['headlines'][:2], 1):
                print(f"    {i}. {hl[:70]}...")


def print_actionable_signals(section_scores: dict, extra_data: dict):
    """Print actionable trading signals."""
    composite = sum(score * SECTION_WEIGHTS.get(section, 0.1) for section, score in section_scores.items())
    composite_scaled = composite * 5
    
    print(f"\n{'╔' + '═' * 73 + '╗'}")
    print(f"║{'ACTIONABLE SIGNALS':^73}║")
    print(f"{'╠' + '═' * 73 + '╣'}")
    
    signals = []
    
    # Yield curve signal (CRITICAL)
    if extra_data.get('bonds_global', {}).get('us_curve'):
        curve = extra_data['bonds_global']['us_curve']
        if curve.get('inverted'):
            signals.insert(0, f"{EMOJI['red']} YIELD CURVE INVERTED - Recession warning!")
        elif curve.get('status') == 'Flat':
            signals.append(f"{EMOJI['yellow']} Yield curve flattening - Watch closely")
    
    # DXY / Dollar signal
    if extra_data.get('currencies', {}).get('DXY'):
        dxy = extra_data['currencies']['DXY']
        if dxy.get('roc_5d', 0) > 1.5:
            signals.append(f"{EMOJI['red']} Dollar surging (DXY +{dxy['roc_5d']:.1f}%) - Risk-off pressure")
        elif dxy.get('roc_5d', 0) < -1.5:
            signals.append(f"{EMOJI['green']} Dollar weakening (DXY {dxy['roc_5d']:.1f}%) - Risk-on support")
    
    # Credit spread signal
    if extra_data.get('credit'):
        credit = extra_data['credit']
        if 'HY Spread' in credit and credit['HY Spread']['current'] < 3.0:
            signals.append(f"{EMOJI['green']} Credit spreads tight - supports risk-on")
        elif 'HY Spread' in credit and credit['HY Spread']['current'] > 5.0:
            signals.append(f"{EMOJI['red']} Credit spreads widening - caution warranted")
    
    # Put/Call signal
    if extra_data.get('sentiment'):
        pcr = extra_data['sentiment']
        if pcr and pcr.get('signal') == 'contrarian_buy':
            signals.append(f"{EMOJI['fire']} Put/Call elevated - CONTRARIAN BUY signal")
        elif pcr and pcr.get('signal') == 'contrarian_sell':
            signals.append(f"{EMOJI['warning']} Put/Call low - CONTRARIAN SELL signal")
    
    # Breadth signal
    if extra_data.get('breadth'):
        breadth = extra_data['breadth']
        if breadth.get('breadth_trend') == 'improving':
            signals.append(f"{EMOJI['green']} Market breadth improving - confirms uptrend")
        elif breadth.get('breadth_trend') == 'deteriorating':
            signals.append(f"{EMOJI['warning']} Market breadth deteriorating - divergence risk")
    
    # VIX signal
    if extra_data.get('volatility'):
        vix = extra_data['volatility']
        if vix and vix.get('structure') == 'contango':
            signals.append(f"{EMOJI['green']} VIX in contango - normal fear structure")
        elif vix and vix.get('structure') == 'backwardation':
            signals.append(f"{EMOJI['red']} VIX in backwardation - elevated near-term fear")
    
    # Copper/Gold
    if extra_data.get('metals', {}).get('copper_gold'):
        cu_au = extra_data['metals']['copper_gold']
        if cu_au['roc_5d'] > 2:
            signals.append(f"{EMOJI['green']} Copper/Gold rising - economic optimism")
        elif cu_au['roc_5d'] < -2:
            signals.append(f"{EMOJI['red']} Copper/Gold falling - growth concerns")
    
    # Crypto
    if extra_data.get('crypto', {}).get('altcoin_perf', {}).get('altseason'):
        signals.append(f"{EMOJI['fire']} Altseason active - consider altcoin exposure")
    
    # News Sentiment
    if extra_data.get('news'):
        news = extra_data['news']
        sentiment = news.get('overall_sentiment', {})
        if sentiment.get('signal') == 1:
            signals.append(f"{EMOJI['green']} News sentiment bullish - supports risk-on")
        elif sentiment.get('signal') == -1:
            signals.append(f"{EMOJI['red']} News sentiment bearish - caution advised")
        
        # Trump Effect - prioritized if tariff-related
        trump = news.get('trump_effect')
        if trump:
            if trump.get('tariff_mentions', 0) > 0:
                signals.insert(0, f"🇺🇸{EMOJI['warning']} TRUMP TARIFF ALERT - {trump['tariff_mentions']} mentions - Trade war risk!")
            elif trump.get('signal') == -1:
                signals.append(f"🇺🇸{EMOJI['red']} Trump Effect negative - Policy uncertainty")
            elif trump.get('signal') == 1:
                signals.append(f"🇺🇸{EMOJI['green']} Trump Effect positive - Pro-business sentiment")
    
    for sig in signals[:10]:  # Show top 10 signals
        print(f"║  {sig}".ljust(74) + "║")
    
    if not signals:
        print(f"║  {EMOJI['yellow']} No strong signals detected - mixed conditions".ljust(74) + "║")
    
    print(f"{'╚' + '═' * 73 + '╝'}")


def print_composite_score(section_scores: dict):
    """Print weighted composite score."""
    composite = sum(score * SECTION_WEIGHTS.get(section, 0.1) for section, score in section_scores.items())
    composite_scaled = composite * 5
    
    # Create visual bar
    bar_pos = int((composite_scaled + 5) / 10 * 20)
    bar = '░' * 20
    bar = bar[:bar_pos] + '█' + bar[bar_pos+1:]
    
    if composite_scaled > 2:
        signal = f"{EMOJI['green']} HIGH RISK APPETITE"
        action = "Favor: Equities, Small Caps, Crypto, Cyclicals"
    elif composite_scaled > 0:
        signal = f"{EMOJI['yellow']} MODERATE RISK APPETITE"
        action = "Favor: Balanced approach, selective risk-on"
    elif composite_scaled > -2:
        signal = f"{EMOJI['yellow']} LOW RISK APPETITE"
        action = "Favor: Quality, defensive sectors, reduce leverage"
    else:
        signal = f"{EMOJI['red']} RISK-OFF ENVIRONMENT"
        action = "Favor: Cash, Bonds, Gold, defensive positioning"
    
    print(f"\n{'╔' + '═' * 73 + '╗'}")
    print(f"║{'COMPOSITE RISK APPETITE SCORE':^73}║")
    print(f"{'╠' + '═' * 73 + '╣'}")
    print(f"║{' ':73}║")
    print(f"║  {'Score:':<10} {composite_scaled:+.2f} / 5.0".ljust(74) + "║")
    print(f"║  {'Visual:':<10} -5 [{bar}] +5".ljust(74) + "║")
    print(f"║  {'Signal:':<10} {signal}".ljust(74) + "║")
    print(f"║  {'Action:':<10} {action}".ljust(74) + "║")
    print(f"║{' ':73}║")
    print(f"{'╠' + '═' * 73 + '╣'}")
    print(f"║  {'SECTION BREAKDOWN':^71}║")
    print(f"{'╠' + '═' * 73 + '╣'}")
    
    for section, score in sorted(section_scores.items(), key=lambda x: -abs(x[1])):
        weight = SECTION_WEIGHTS.get(section, 0.1)
        contrib = score * weight * 5
        emoji = EMOJI['green'] if score > 0.3 else EMOJI['red'] if score < -0.3 else EMOJI['yellow']
        line = f"  {section.title():12} {emoji} Score: {score:+.2f}  Weight: {weight:>4.0%}  Contrib: {contrib:+.2f}"
        print(f"║{line}".ljust(74) + "║")
    
    print(f"{'╚' + '═' * 73 + '╝'}")


def print_footer():
    """Print report footer."""
    print(f"\n{'─' * 75}")
    print("  LEGEND")
    print(f"{'─' * 75}")
    print("  %ile    = Percentile rank in 60-day range (high = near highs)")
    print("  5D      = 5-day rate of change")
    print("  Signal  = Risk-on (🟢), Risk-off (🔴), Neutral (🟡)")
    print("  Credit  = Tightening spreads = Risk-on, Widening = Risk-off")
    print("  P/C     = Put/Call ratio is CONTRARIAN (high fear = buy signal)")
    print(f"{'─' * 75}")
    print("  Data: Yahoo Finance, FRED  |  Not financial advice")
    print(f"{'─' * 75}\n")


# ============================================================================
# MAIN ASSESSMENT
# ============================================================================

def run_assessment(send_to_telegram: bool = False):
    """Run the full risk appetite assessment."""
    print_header()
    
    section_scores = {}
    extra_data = {}
    all_results = {}  # Store for Telegram
    
    # 1. EQUITY INDICES
    print("\n  📊 Fetching Equity Indices...")
    results, score, _ = process_section('indices', INDICATORS['indices'])
    print_section('📈 EQUITY INDICES (US, Europe, Asia, Korea)', results, score, SECTION_WEIGHTS['indices'])
    section_scores['indices'] = score
    all_results['indices'] = results
    
    # 2. MARKET BREADTH
    print("\n  📊 Analyzing Market Breadth...")
    results, score, breadth_data = process_breadth_section()
    print_section('📊 MARKET BREADTH', results, score, SECTION_WEIGHTS['breadth'])
    section_scores['breadth'] = score
    extra_data['breadth'] = breadth_data
    all_results['breadth'] = results
    
    # 3. GLOBAL BONDS (US + Japan) - NEW DEDICATED SECTION
    print("\n  🏦 Fetching Global Bond Markets (US + Japan)...")
    results, score, bond_data = process_global_bonds_section()
    print_section('🏦 GLOBAL BONDS (US 2Y/10Y/30Y, Japan, Yield Curve)', results, score, SECTION_WEIGHTS['bonds_global'])
    print_bonds_analysis(bond_data)
    section_scores['bonds_global'] = score
    extra_data['bonds_global'] = bond_data
    all_results['bonds_global'] = results
    
    # 4. CREDIT SPREADS
    print("\n  📊 Fetching Credit Spreads from FRED...")
    results, score, credit_data = process_credit_section()
    print_section('💳 CREDIT SPREADS (FRED)', results, score, SECTION_WEIGHTS['credit'])
    print_credit_analysis(credit_data)
    section_scores['credit'] = score
    extra_data['credit'] = credit_data
    all_results['credit'] = results
    
    # 5. CURRENCIES (DXY, EUR/USD, USD/JPY) - NEW SECTION
    print("\n  💱 Fetching Currency Markets...")
    results, score, currency_data = process_currencies_section()
    print_section('💱 CURRENCIES (DXY, EUR/USD, USD/JPY)', results, score, SECTION_WEIGHTS['currencies'])
    print_currencies_analysis(currency_data)
    section_scores['currencies'] = score
    extra_data['currencies'] = currency_data
    all_results['currencies'] = results
    
    # 6. GLOBAL LIQUIDITY
    print("\n  💧 Fetching Global Liquidity Metrics...")
    results, score, liquidity_data = process_liquidity_section()
    print_section('💧 GLOBAL LIQUIDITY (M2, WALCL, CB Proxies)', results, score, SECTION_WEIGHTS['liquidity'])
    print_liquidity_analysis(liquidity_data)
    section_scores['liquidity'] = score
    extra_data['liquidity'] = liquidity_data
    all_results['liquidity'] = results
    
    # 7. CRYPTO
    print("\n  📊 Fetching Crypto...")
    results, score, crypto_data = process_crypto_section()
    print_section('₿ CRYPTO (incl. Fear & Greed, ETF Flows)', results, score, SECTION_WEIGHTS['crypto'])
    print_crypto_analysis(crypto_data)
    section_scores['crypto'] = score
    extra_data['crypto'] = crypto_data
    all_results['crypto'] = results
    
    # 8. METALS
    print("\n  📊 Fetching Metals...")
    results, score, metals_data = process_metals_section()
    print_section('🥇 METALS & RATIOS', results, score, SECTION_WEIGHTS['metals'])
    section_scores['metals'] = score
    extra_data['metals'] = metals_data
    all_results['metals'] = results
    
    # 9. COMMODITIES
    print("\n  📊 Fetching Commodities...")
    results, score, _ = process_section('commodities', INDICATORS['commodities'])
    print_section('🛢️ COMMODITIES', results, score, SECTION_WEIGHTS['commodities'])
    section_scores['commodities'] = score
    all_results['commodities'] = results
    
    # 10. VOLATILITY
    print("\n  📊 Fetching Volatility...")
    results, score, vix_data = process_volatility_section()
    print_section('📉 VOLATILITY', results, score, SECTION_WEIGHTS['volatility'])
    section_scores['volatility'] = score
    extra_data['volatility'] = vix_data
    all_results['volatility'] = results
    
    # 11. SENTIMENT (Put/Call)
    print("\n  📊 Fetching Sentiment...")
    results, score, sentiment_data = process_sentiment_section()
    print_section('🎭 SENTIMENT (Put/Call Ratio)', results, score, SECTION_WEIGHTS['sentiment'])
    section_scores['sentiment'] = score
    extra_data['sentiment'] = sentiment_data
    all_results['sentiment'] = results
    
    # 12. NEWS SENTIMENT & TRUMP EFFECT
    print("\n  📰 Analyzing News Sentiment & Trump Effect...")
    results, score, news_data = process_news_section()
    print_section('📰 NEWS SENTIMENT & TRUMP EFFECT', results, score, SECTION_WEIGHTS['news'])
    print_news_analysis(news_data)
    section_scores['news'] = score
    extra_data['news'] = news_data
    all_results['news'] = results
    
    # 12. BRAZIL MARKETS
    print("\n  🇧🇷 Fetching Brazilian Markets...")
    results, score, brazil_data = process_brazil_section()
    print_section('🇧🇷 BRAZIL (Bovespa, EWZ, BRL, ADRs)', results, score, SECTION_WEIGHTS['brazil'])
    print_brazil_analysis(brazil_data)
    section_scores['brazil'] = score
    extra_data['brazil'] = brazil_data
    all_results['brazil'] = results
    
    # COMPOSITE SCORE
    print_composite_score(section_scores)
    
    # ACTIONABLE SIGNALS
    print_actionable_signals(section_scores, extra_data)
    
    # FOOTER
    print_footer()
    
    # SEND TO TELEGRAM
    if send_to_telegram:
        print("\n  📤 Sending to Telegram...")
        send_telegram_report(section_scores, all_results, extra_data)
    
    return section_scores, extra_data, all_results


def send_telegram_report(section_scores: dict, all_results: dict, extra_data: dict):
    """
    Send the complete report to Telegram in multiple messages.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate composite score
    composite = sum(score * SECTION_WEIGHTS.get(section, 0.1) for section, score in section_scores.items())
    composite_scaled = composite * 5
    
    # Determine signal
    if composite_scaled > 2:
        signal_text = "🟢 HIGH RISK APPETITE"
        action = "Favor: Equities, Small Caps, Crypto"
    elif composite_scaled > 0:
        signal_text = "🟡 MODERATE RISK APPETITE"
        action = "Favor: Balanced approach"
    elif composite_scaled > -2:
        signal_text = "🟡 LOW RISK APPETITE"
        action = "Favor: Quality, reduce leverage"
    else:
        signal_text = "🔴 RISK-OFF ENVIRONMENT"
        action = "Favor: Cash, Bonds, Gold"
    
    # ========== MESSAGE 1: HEADER & COMPOSITE SCORE ==========
    msg1_lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🎯 <b>RISK APPETITE MONITOR</b> 🎯",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 {timestamp}",
        "",
        "═══════════════════════════",
        "📊 <b>COMPOSITE SCORE</b>",
        "═══════════════════════════",
        f"<b>Score: {composite_scaled:+.2f} / 5.0</b>",
        f"{signal_text}",
        f"<i>{action}</i>",
        "",
        "<b>Section Breakdown:</b>",
    ]
    
    for section, score in sorted(section_scores.items(), key=lambda x: -abs(x[1])):
        emoji = EMOJI['green'] if score > 0.3 else EMOJI['red'] if score < -0.3 else EMOJI['yellow']
        weight = SECTION_WEIGHTS.get(section, 0.1)
        msg1_lines.append(f"  {emoji} {section.title()}: {score:+.2f} ({weight:.0%})")
    
    send_telegram_message("\n".join(msg1_lines))
    
    # ========== MESSAGE 2: EQUITY INDICES ==========
    msg2 = format_telegram_section("📈 EQUITY INDICES", all_results.get('indices', []), section_scores.get('indices', 0))
    send_telegram_message(msg2)
    
    # ========== MESSAGE 2.5: GLOBAL BONDS (NEW) ==========
    msg2_5_lines = [format_telegram_section("🏦 GLOBAL BONDS", all_results.get('bonds_global', []), section_scores.get('bonds_global', 0))]
    
    if extra_data.get('bonds_global'):
        bonds = extra_data['bonds_global']
        
        # Yield Curve Status (CRITICAL)
        if 'us_curve' in bonds:
            curve = bonds['us_curve']
            if curve.get('inverted'):
                msg2_5_lines.append(f"\n🚨 <b>YIELD CURVE INVERTED!</b>")
                msg2_5_lines.append(f"   2Y-10Y Spread: {curve['spread']:.2f}%")
                msg2_5_lines.append(f"   ⚠️ Recession signal")
            elif curve.get('status') == 'Flat':
                msg2_5_lines.append(f"\n⚠️ Yield Curve: FLAT ({curve['spread']:.2f}%)")
            else:
                msg2_5_lines.append(f"\n✅ Yield Curve: Normal ({curve['spread']:.2f}%)")
        
        # US Yields Summary
        if 'us_yields' in bonds and bonds['us_yields']:
            yields = bonds['us_yields']
            yield_line = "US Yields: "
            for tenor, data in yields.items():
                emoji = "📈" if data['pct_change'] > 0 else "📉"
                yield_line += f"{tenor}={data['current']:.2f}% {emoji} "
            msg2_5_lines.append(yield_line.strip())
    
    send_telegram_message("\n".join(msg2_5_lines))
    
    # ========== MESSAGE 2.6: CURRENCIES (NEW) ==========
    msg2_6_lines = [format_telegram_section("💱 CURRENCIES", all_results.get('currencies', []), section_scores.get('currencies', 0))]
    
    if extra_data.get('currencies'):
        curr = extra_data['currencies']
        
        # DXY Status
        if 'DXY' in curr:
            dxy = curr['DXY']
            dxy_emoji = "📈" if dxy['roc_5d'] > 0 else "📉"
            trend = "Strengthening" if dxy['roc_5d'] > 0.5 else "Weakening" if dxy['roc_5d'] < -0.5 else "Stable"
            msg2_6_lines.append(f"\n💵 <b>DXY:</b> {dxy['current']:.2f} ({trend})")
            msg2_6_lines.append(f"   5D Change: {dxy['roc_5d']:+.2f}%")
            
            if dxy['roc_5d'] > 1.5:
                msg2_6_lines.append(f"   ⚠️ Dollar surge = Risk-off pressure")
            elif dxy['roc_5d'] < -1.5:
                msg2_6_lines.append(f"   ✅ Dollar weakness = Risk-on support")
        
        # Dollar trend
        if 'dollar_trend' in curr:
            trend_emoji = "🔴" if curr['dollar_trend'] == 'strengthening' else "🟢" if curr['dollar_trend'] == 'weakening' else "🟡"
            msg2_6_lines.append(f"\n{trend_emoji} Dollar Trend: {curr['dollar_trend'].upper()}")
    
    send_telegram_message("\n".join(msg2_6_lines))
    
    # ========== MESSAGE 3: CREDIT & BREADTH ==========
    msg3_lines = [format_telegram_section("💳 CREDIT SPREADS", all_results.get('credit', []), section_scores.get('credit', 0))]
    
    # Add credit analysis
    if extra_data.get('credit') and 'HY Spread' in extra_data['credit']:
        hy = extra_data['credit']['HY Spread']['current']
        if hy < 3.0:
            msg3_lines.append(f"\n✅ HY Spread {hy:.2f}% - TIGHT (favorable)")
        elif hy > 5.0:
            msg3_lines.append(f"\n⚠️ HY Spread {hy:.2f}% - WIDE (stress)")
        else:
            msg3_lines.append(f"\nℹ️ HY Spread {hy:.2f}% - Normal")
    
    msg3_lines.append(format_telegram_section("📊 MARKET BREADTH", all_results.get('breadth', []), section_scores.get('breadth', 0)))
    send_telegram_message("\n".join(msg3_lines))
    
    # ========== MESSAGE 3.5: GLOBAL LIQUIDITY (NEW) ==========
    msg3_5_lines = [format_telegram_section("💧 GLOBAL LIQUIDITY", all_results.get('liquidity', []), section_scores.get('liquidity', 0))]
    
    if extra_data.get('liquidity'):
        liq = extra_data['liquidity']
        if 'Global Liquidity Index' in liq:
            gli = liq['Global Liquidity Index']
            gli_emoji = "🟢" if gli['expanding'] else "🔴"
            status = "EXPANDING" if gli['expanding'] else "CONTRACTING"
            msg3_5_lines.append(f"\n{gli_emoji} <b>Global Liquidity: {status}</b>")
            msg3_5_lines.append(f"   Avg change: {gli['avg_change']:+.2f}%")
        
        if 'US M2' in liq:
            m2_emoji = "🟢" if liq['US M2']['pct_change'] > 0 else "🔴"
            msg3_5_lines.append(f"{m2_emoji} US M2: ${liq['US M2']['current']/1000:.1f}T")
        
        if 'WALCL' in liq:
            walcl_emoji = "🟢" if liq['WALCL']['pct_change'] > 0 else "🔴"
            msg3_5_lines.append(f"{walcl_emoji} Fed B/S: ${liq['WALCL']['current']/1000000:.2f}T")
    
    send_telegram_message("\n".join(msg3_5_lines))
    
    # ========== MESSAGE 4: CRYPTO (Enhanced with Fear & Greed and ETF Flows) ==========
    msg4_lines = [format_telegram_section("₿ CRYPTO", all_results.get('crypto', []), section_scores.get('crypto', 0))]
    
    # Add altseason indicator
    if extra_data.get('crypto', {}).get('altcoin_perf'):
        alt = extra_data['crypto']['altcoin_perf']
        if alt.get('altseason'):
            msg4_lines.append(f"\n🔥 <b>ALTSEASON ACTIVE</b> (+{alt['avg_outperformance']:.1f}% vs BTC)")
        else:
            msg4_lines.append(f"\nℹ️ No altseason ({alt['avg_outperformance']:+.1f}% vs BTC)")
    
    # Fear & Greed Index (NEW)
    if extra_data.get('crypto', {}).get('fear_greed'):
        fg = extra_data['crypto']['fear_greed']
        fg_emoji = "😱" if fg['value'] <= 24 else "😰" if fg['value'] <= 44 else "😐" if fg['value'] <= 55 else "😀" if fg['value'] <= 74 else "🤑"
        msg4_lines.append(f"\n{fg_emoji} <b>Fear & Greed:</b> {fg['value']} ({fg['classification']})")
        msg4_lines.append(f"   {fg['interpretation']}")
    
    # ETF Flows (NEW)
    if extra_data.get('crypto', {}).get('etf_flows'):
        flows = extra_data['crypto']['etf_flows']
        flow_emoji = "📈" if flows['flow_signal'] == 1 else "📉" if flows['flow_signal'] == -1 else "➡️"
        msg4_lines.append(f"\n{flow_emoji} <b>BTC ETF Flow:</b> {flows['interpretation']}")
        msg4_lines.append(f"   5D Price: {flows['avg_price_change_5d']:+.1f}% | Vol: {flows['avg_volume_change']:+.1f}%")
    
    send_telegram_message("\n".join(msg4_lines))
    
    # ========== MESSAGE 5: METALS & VOLATILITY ==========
    msg5_lines = [format_telegram_section("🥇 METALS", all_results.get('metals', []), section_scores.get('metals', 0))]
    
    # Copper/Gold analysis
    if extra_data.get('metals', {}).get('copper_gold'):
        cu_au = extra_data['metals']['copper_gold']
        trend = "📈 Rising (Optimism)" if cu_au['roc_5d'] > 0 else "📉 Falling (Caution)"
        msg5_lines.append(f"\nCopper/Gold: {trend}")
    
    msg5_lines.append(format_telegram_section("📉 VOLATILITY", all_results.get('volatility', []), section_scores.get('volatility', 0)))
    
    # VIX term structure
    if extra_data.get('volatility'):
        vix = extra_data['volatility']
        if vix:
            structure = "🟢 Contango (Calm)" if vix.get('structure') == 'contango' else "🔴 Backwardation (Fear)"
            msg5_lines.append(f"\nVIX Structure: {structure}")
    
    send_telegram_message("\n".join(msg5_lines))
    
    # ========== MESSAGE 5.5: BRAZIL ==========
    msg5_5_lines = [format_telegram_section("🇧🇷 BRAZIL", all_results.get('brazil', []), section_scores.get('brazil', 0))]
    
    if extra_data.get('brazil'):
        brazil = extra_data['brazil']
        
        # BRL Strength
        if 'brl_strength' in brazil:
            brl = brazil['brl_strength']
            brl_emoji = "🟢" if brl['daily'] > 0 else "🔴"
            msg5_5_lines.append(f"\n{brl_emoji} BRL: {'Strengthening' if brl['daily'] > 0 else 'Weakening'} ({brl['daily']:+.2f}%)")
        
        # EWZ vs SPY
        if 'ewz_vs_spy' in brazil:
            rel = brazil['ewz_vs_spy']
            rel_emoji = "🟢" if rel['value'] > 0 else "🔴"
            msg5_5_lines.append(f"{rel_emoji} EWZ vs SPY (5D): {rel['value']:+.2f}%")
        
        # Commodity and Banks proxy
        if 'commodity_proxy' in brazil:
            comm_emoji = "🟢" if brazil['commodity_proxy'] > 0 else "🔴"
            msg5_5_lines.append(f"{comm_emoji} Commodities: {brazil['commodity_proxy']:+.2f}%")
        
        if 'banks_proxy' in brazil:
            banks_emoji = "🟢" if brazil['banks_proxy'] > 0 else "🔴"
            msg5_5_lines.append(f"{banks_emoji} Banks: {brazil['banks_proxy']:+.2f}%")
    
    send_telegram_message("\n".join(msg5_5_lines))
    
    # ========== MESSAGE 6: ACTIONABLE SIGNALS ==========
    signals = []
    
    # Yield Curve signal (CRITICAL - should be first if inverted)
    if extra_data.get('bonds_global', {}).get('us_curve'):
        curve = extra_data['bonds_global']['us_curve']
        if curve.get('inverted'):
            signals.insert(0, "🚨 YIELD CURVE INVERTED → Recession warning!")
        elif curve.get('status') == 'Flat':
            signals.append("⚠️ Yield curve flattening → Watch closely")
    
    # DXY / Dollar signal
    if extra_data.get('currencies', {}).get('DXY'):
        dxy = extra_data['currencies']['DXY']
        if dxy.get('roc_5d', 0) > 1.5:
            signals.append(f"💵⚠️ Dollar surging ({dxy['roc_5d']:+.1f}%) → Risk-off")
        elif dxy.get('roc_5d', 0) < -1.5:
            signals.append(f"💵✅ Dollar weakening ({dxy['roc_5d']:+.1f}%) → Risk-on")
    
    # Credit signal
    if extra_data.get('credit') and 'HY Spread' in extra_data['credit']:
        hy = extra_data['credit']['HY Spread']['current']
        if hy < 3.0:
            signals.append("✅ Credit tight → Risk-on supported")
        elif hy > 5.0:
            signals.append("⚠️ Credit wide → Caution warranted")
    
    # Liquidity signal (NEW)
    if extra_data.get('liquidity', {}).get('Global Liquidity Index'):
        gli = extra_data['liquidity']['Global Liquidity Index']
        if gli['expanding']:
            signals.append("💧✅ Global liquidity expanding → Risk-on")
        else:
            signals.append("💧⚠️ Global liquidity contracting → Caution")
    
    # Put/Call signal
    if extra_data.get('sentiment'):
        pcr = extra_data['sentiment']
        if pcr and pcr.get('signal') == 'contrarian_buy':
            signals.append("🔥 Put/Call high → CONTRARIAN BUY")
        elif pcr and pcr.get('signal') == 'contrarian_sell':
            signals.append("⚠️ Put/Call low → Contrarian sell")
    
    # Breadth signal
    if extra_data.get('breadth'):
        breadth = extra_data['breadth']
        if breadth and breadth.get('breadth_trend') == 'improving':
            signals.append("✅ Breadth improving → Confirms trend")
        elif breadth and breadth.get('breadth_trend') == 'deteriorating':
            signals.append("⚠️ Breadth deteriorating → Watch for reversal")
    
    # VIX signal
    if extra_data.get('volatility'):
        vix = extra_data['volatility']
        if vix and vix.get('structure') == 'backwardation':
            signals.append("⚠️ VIX backwardation → Near-term fear")
    
    # Copper/Gold
    if extra_data.get('metals', {}).get('copper_gold'):
        cu_au = extra_data['metals']['copper_gold']
        if cu_au['roc_5d'] > 2:
            signals.append("✅ Cu/Au rising → Economic optimism")
        elif cu_au['roc_5d'] < -2:
            signals.append("⚠️ Cu/Au falling → Growth concerns")
    
    # Altseason
    if extra_data.get('crypto', {}).get('altcoin_perf', {}).get('altseason'):
        signals.append("🔥 Altseason → Consider altcoin exposure")
    
    # Fear & Greed (NEW)
    if extra_data.get('crypto', {}).get('fear_greed'):
        fg = extra_data['crypto']['fear_greed']
        if fg['value'] <= 24:
            signals.append("😱 Extreme Fear → Contrarian BUY signal")
        elif fg['value'] >= 75:
            signals.append("🤑 Extreme Greed → Contrarian SELL signal")
    
    # ETF Flows (NEW)
    if extra_data.get('crypto', {}).get('etf_flows'):
        flows = extra_data['crypto']['etf_flows']
        if flows['flow_signal'] == 1:
            signals.append("📈 BTC ETF inflows → Institutional buying")
        elif flows['flow_signal'] == -1:
            signals.append("📉 BTC ETF outflows → Institutional selling")
    
    # Brazil signals
    if extra_data.get('brazil'):
        brazil = extra_data['brazil']
        # BRL strength/weakness
        if brazil.get('brl_strength', {}).get('5d', 0) > 2:
            signals.append("🇧🇷✅ BRL strengthening → Brazil risk-on")
        elif brazil.get('brl_strength', {}).get('5d', 0) < -2:
            signals.append("🇧🇷⚠️ BRL weakening → Brazil caution")
        # EWZ outperformance
        if brazil.get('ewz_vs_spy', {}).get('value', 0) > 3:
            signals.append("🇧🇷🔥 Brazil outperforming US!")
        elif brazil.get('ewz_vs_spy', {}).get('value', 0) < -3:
            signals.append("🇧🇷⚠️ Brazil underperforming US")
    
    # News Sentiment
    if extra_data.get('news'):
        news = extra_data['news']
        sentiment = news.get('overall_sentiment', {})
        if sentiment.get('signal') == 1:
            signals.append("✅ News sentiment bullish → Supports risk-on")
        elif sentiment.get('signal') == -1:
            signals.append("⚠️ News sentiment bearish → Caution")
        
        # Trump Effect
        trump = news.get('trump_effect')
        if trump:
            if trump.get('tariff_mentions', 0) > 0:
                signals.append(f"🇺🇸⚠️ TRUMP TARIFF ALERT → {trump['tariff_mentions']} mentions!")
            elif trump.get('signal') == -1:
                signals.append("🇺🇸⚠️ Trump Effect negative → Policy risk")
            elif trump.get('signal') == 1:
                signals.append("🇺🇸✅ Trump Effect positive → Pro-business")
    
    msg6_lines = [
        "",
        "═══════════════════════════",
        "🎯 <b>ACTIONABLE SIGNALS</b>",
        "═══════════════════════════",
    ]
    
    if signals:
        for sig in signals[:14]:  # Increased limit for more signals
            msg6_lines.append(sig)
    else:
        msg6_lines.append("🟡 No strong signals - Mixed conditions")
    
    msg6_lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<i>Data: Yahoo Finance, FRED</i>",
        "<i>Not financial advice</i>",
    ])
    
    send_telegram_message("\n".join(msg6_lines))
    
    # ========== MESSAGE 7: NEWS & TRUMP EFFECT (Fixed headline truncation) ==========
    news = extra_data.get('news', {})
    if news and news.get('article_count', 0) > 0:
        msg7_lines = [
            "",
            "═══════════════════════════",
            "📰 <b>NEWS SENTIMENT</b>",
            "═══════════════════════════",
        ]
        
        sentiment = news.get('overall_sentiment', {})
        sent_emoji = "🟢" if sentiment.get('signal') == 1 else "🔴" if sentiment.get('signal') == -1 else "🟡"
        
        msg7_lines.append(f"{sent_emoji} Overall: {sentiment.get('label', 'N/A').upper()} ({sentiment.get('score', 0):.2f})")
        msg7_lines.append(f"📊 Articles: {news.get('article_count', 0)} analyzed")
        msg7_lines.append(f"   🟢 Bullish: {news.get('bullish_count', 0)} | 🔴 Bearish: {news.get('bearish_count', 0)}")
        
        if news.get('volatility_detected'):
            msg7_lines.append(f"\n⚠️ <b>VOLATILITY KEYWORDS DETECTED</b>")
        
        # Top headlines (FIXED - showing fuller headlines)
        headlines = news.get('headlines', [])
        if headlines:
            msg7_lines.append("\n<b>Top Headlines:</b>")
            for hl in headlines[:5]:  # Show up to 5 headlines
                hl_emoji = "🟢" if hl['sentiment'] == 'bullish' else "🔴" if hl['sentiment'] == 'bearish' else "🟡"
                # Show fuller headline (up to 75 chars)
                title = hl['title'][:75] + ('...' if len(hl['title']) > 75 else '')
                msg7_lines.append(f"{hl_emoji} {title}")
        
        send_telegram_message("\n".join(msg7_lines))
        
        # Trump Effect (separate message if exists for better formatting)
        trump = news.get('trump_effect')
        if trump:
            msg_trump = [
                "",
                "─" * 27,
                "🇺🇸 <b>TRUMP EFFECT</b>",
                "─" * 27,
            ]
            
            trump_emoji = "🟢" if trump['signal'] == 1 else "🔴" if trump['signal'] == -1 else "🟡"
            msg_trump.append(f"{trump_emoji} {trump['interpretation']}")
            msg_trump.append(f"📰 {trump['article_count']} Trump-related articles")
            
            if trump.get('tariff_mentions', 0) > 0:
                msg_trump.append(f"\n🚨 <b>TARIFF ALERT!</b>")
                msg_trump.append(f"   {trump['tariff_mentions']} tariff mentions detected")
                msg_trump.append(f"   → Trade war risk elevated")
            
            if trump.get('headlines'):
                msg_trump.append("\n<b>Trump Headlines:</b>")
                for hl in trump['headlines'][:3]:  # Show up to 3 Trump headlines
                    # Show fuller headlines (up to 65 chars)
                    headline = hl[:65] + ('...' if len(hl) > 65 else '')
                    msg_trump.append(f"• {headline}")
            
            send_telegram_message("\n".join(msg_trump))
    
    print("  ✅ Telegram report sent successfully!")


# ============================================================================
# SCHEDULING
# ============================================================================

def run_scheduled(send_to_telegram: bool = False):
    """Run on schedule."""
    try:
        import schedule
        import time
        
        mode = "with Telegram" if send_to_telegram else "console only"
        print(f"Starting scheduled risk monitor ({mode}, every 4 hours)...")
        print("Press Ctrl+C to stop.\n")
        
        # Run immediately
        run_assessment(send_to_telegram=send_to_telegram)
        
        # Schedule future runs
        schedule.every(4).hours.do(lambda: run_assessment(send_to_telegram=send_to_telegram))
        
        while True:
            schedule.run_pending()
            time.sleep(60)
            
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
    except ImportError:
        print("Error: 'schedule' module not installed. Run: pip install schedule")
        sys.exit(1)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Ultimate Risk Appetite Monitor v4.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python riskmonitor_v4.py                      # Run once (console only)
  python riskmonitor_v4.py --telegram           # Run once + send to Telegram
  python riskmonitor_v4.py --schedule           # Run every 4 hours (console)
  python riskmonitor_v4.py --schedule --telegram  # Run every 4 hours + Telegram

New in v4.0:
  - Global Liquidity tracking (US M2, WALCL, China/ECB/BOJ proxies)
  - Crypto Fear & Greed Index
  - Bitcoin ETF inflow/outflow analysis
  - Improved Telegram headline formatting

Requirements:
  pip install pandas yfinance tabulate requests
        """
    )
    
    parser.add_argument('--schedule', '-s', action='store_true',
                        help='Run continuously every 4 hours')
    parser.add_argument('--telegram', '-t', action='store_true',
                        help='Send results to Telegram bot')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output as JSON (for integration)')
    
    args = parser.parse_args()
    
    if args.schedule:
        run_scheduled(send_to_telegram=args.telegram)
    else:
        run_assessment(send_to_telegram=args.telegram)


if __name__ == "__main__":
    main()