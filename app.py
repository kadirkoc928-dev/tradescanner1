import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import ta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import warnings
warnings.filterwarnings('ignore')

# ----------------------------------
# KONFIGURATION
# ----------------------------------
st.set_page_config(
    page_title="TradeScanner Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------
# CSS
# ----------------------------------
st.markdown("""
<style>
    .score-excellent { color: #00ff88; font-size: 28px; font-weight: bold; }
    .score-good { color: #88ff00; font-size: 28px; font-weight: bold; }
    .score-neutral { color: #ffaa00; font-size: 28px; font-weight: bold; }
    .score-weak { color: #ff4444; font-size: 28px; font-weight: bold; }
    .score-poor { color: #ff0000; font-size: 28px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ----------------------------------
# SIDEBAR
# ----------------------------------
st.sidebar.title("📊 TradeScanner Pro")
st.sidebar.markdown("---")

# Modus
mode = st.sidebar.radio("Modus:", ["📈 Einzelanalyse", "🔎 Market Scanner"], index=1)

if mode == "📈 Einzelanalyse":
    ticker_input = st.sidebar.text_input("Ticker:", value="AAPL").upper()
    interval = st.sidebar.selectbox("Intervall:", ["1d", "1h", "30m"], index=0)
    period = st.sidebar.selectbox("Zeitraum:", ["1mo", "3mo", "6mo", "1y"], index=1)
else:
    st.sidebar.subheader("🎯 Scanner-Typ")
    
    scanner_type = st.sidebar.radio(
        "Wähle Scan-Modus:",
        ["📊 Standard Scan", "⚡ Quick Scan (Top 100)", "💾 Watchlist Scan"],
        index=1
    )
    
    if scanner_type == "💾 Watchlist Scan":
        if 'user_watchlist' not in st.session_state or len(st.session_state.user_watchlist) == 0:
            st.sidebar.warning("⚠️ Watchlist ist leer!")
    
    st.sidebar.markdown("---")
    
    if scanner_type == "📊 Standard Scan":
        st.sidebar.subheader("🌍 Märkte:")
        scan_sp500 = st.sidebar.checkbox("S&P 500 (500)", value=True)
        scan_nasdaq100 = st.sidebar.checkbox("NASDAQ 100 (100)", value=True)
        scan_russell2000 = st.sidebar.checkbox("Russell 2000", value=False)
        scan_dax = st.sidebar.checkbox("Deutsche Aktien", value=False)
        if scan_russell2000:
            russell_sample = st.sidebar.slider("Russell Sample %:", 10, 100, 20)
        else:
            russell_sample = 20
    else:
        scan_sp500 = False
        scan_nasdaq100 = False
        scan_russell2000 = False
        scan_dax = False
        russell_sample = 20
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Filter")
    
    filter_preset = st.sidebar.selectbox(
        "Preset:",
        ["🏆 Nur Beste (80+)", "✅ Gut & Besser (70+)", "📊 Moderat (60+)", "🔧 Eigene Einstellungen"],
        index=1
    )
    
    if filter_preset == "🏆 Nur Beste (80+)":
        min_swing_score = 80
        min_volume = 10000000
        rsi_min = 45
        rsi_max = 60
        adx_min = 30
        volume_surge_min = 1.5
        require_sma_above = True
        require_macd_bullish = True
        min_market_cap = "Mid Cap (>2B)"
    elif filter_preset == "✅ Gut & Besser (70+)":
        min_swing_score = 70
        min_volume = 5000000
        rsi_min = 40
        rsi_max = 65
        adx_min = 25
        volume_surge_min = 1.2
        require_sma_above = True
        require_macd_bullish = True
        min_market_cap = "Mid Cap (>2B)"
    elif filter_preset == "📊 Moderat (60+)":
        min_swing_score = 60
        min_volume = 1000000
        rsi_min = 30
        rsi_max = 70
        adx_min = 20
        volume_surge_min = 1.0
        require_sma_above = False
        require_macd_bullish = False
        min_market_cap = "Small Cap (>300M)"
    else:
        min_swing_score = st.sidebar.slider("Min. Swing-Score:", 0, 100, 70)
        min_volume = st.sidebar.number_input("Min. Volumen (USD):", 0, 1000000000, 5000000, 1000000)
        max_price = st.sidebar.number_input("Max. Preis ($):", 0.0, 100000.0, 500.0)
        rsi_min = st.sidebar.slider("RSI Min:", 0, 100, 40)
        rsi_max = st.sidebar.slider("RSI Max:", 0, 100, 65)
        adx_min = st.sidebar.slider("ADX Min:", 0, 100, 25)
        volume_surge_min = st.sidebar.slider("Vol Ratio Min:", 0.5, 5.0, 1.2)
        require_sma_above = st.sidebar.checkbox("Kurs > SMA20", value=True)
        require_macd_bullish = st.sidebar.checkbox("MACD bullisch", value=True)
        min_market_cap = st.sidebar.selectbox("Min. Marktkap.:", 
            ["Keine", "Micro Cap (>50M)", "Small Cap (>300M)", "Mid Cap (>2B)", "Large Cap (>10B)"], index=3)
    
    if filter_preset != "🔧 Eigene Einstellungen":
        max_price = 500.0
    
    market_cap_map = {
        "Keine": 0, "Micro Cap (>50M)": 50000000, "Small Cap (>300M)": 300000000,
        "Mid Cap (>2B)": 2000000000, "Large Cap (>10B)": 10000000000
    }

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ Keine Finanzberatung. Nur zu Bildungszwecken.")

# ----------------------------------
# HILFSFUNKTIONEN
# ----------------------------------

@st.cache_data(ttl=3600)
def get_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except:
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "JNJ",
                "V", "PG", "XOM", "UNH", "MA", "HD", "CVX", "MRK", "ABBV", "PEP",
                "KO", "WMT", "AVGO", "LLY", "COST", "TMO", "MCD", "CSCO", "ACN", "ABT",
                "DHR", "VZ", "NKE", "CRM", "NEE", "DIS", "AMD", "PM", "TXN", "LIN"]

@st.cache_data(ttl=3600)
def get_nasdaq100_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url)
        for table in tables:
            if 'Ticker' in table.columns or 'Symbol' in table.columns:
                col = 'Ticker' if 'Ticker' in table.columns else 'Symbol'
                tickers = table[col].tolist()
                return [t.replace('.', '-') for t in tickers if isinstance(t, str)]
        return []
    except:
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "NFLX",
                "AMD", "PEP", "ADBE", "CSCO", "INTC", "CMCSA", "INTU", "QCOM", "TXN", "AMGN"]

@st.cache_data(ttl=3600)
def get_russell2000_tickers(sample_percent=20):
    try:
        url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/russell2000.csv"
        df = pd.read_csv(url)
        if 'Symbol' in df.columns:
            tickers = df['Symbol'].tolist()
        elif 'Ticker' in df.columns:
            tickers = df['Ticker'].tolist()
        else:
            tickers = df.iloc[:, 0].tolist()
        if sample_percent < 100:
            sample_size = max(20, int(len(tickers) * sample_percent / 100))
            tickers = np.random.choice(tickers, sample_size, replace=False).tolist()
        return tickers
    except:
        return []

@st.cache_data(ttl=3600)
def get_german_tickers():
    dax = ["ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BMW.DE", 
           "CBK.DE", "CON.DE", "DTE.DE", "DBK.DE", "DB1.DE", "DPW.DE",
           "EOAN.DE", "FRE.DE", "HEI.DE", "HEN3.DE", "IFX.DE",
           "MBG.DE", "MRK.DE", "MUV2.DE", "PAH3.DE", "PUM.DE",
           "RWE.DE", "SAP.DE", "SIE.DE", "VOW3.DE", "VNA.DE", "ZAL.DE"]
    mdax = ["AIXA.DE", "BOSS.DE", "EVT.DE", "FRA.DE", "G24.DE", "HLE.DE", 
            "KGX.DE", "LEG.DE", "LHA.DE", "LXS.DE", "NDA.DE", "OSR.DE"]
    return dax + mdax

def calculate_all_indicators(df):
    if len(df) < 50:
        return None
    try:
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['SMA_200'] = ta.trend.sma_indicator(df['Close'], window=200)
        df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        df['MACD'] = ta.trend.macd(df['Close'])
        df['MACD_signal'] = ta.trend.macd_signal(df['Close'])
        df['MACD_hist'] = ta.trend.macd_diff(df['Close'])
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        return df
    except:
        return None

def calculate_swing_score_fast(df):
    if df is None or len(df) < 50:
        return 0
    try:
        latest = df.iloc[-1]
        score = 0
        if not np.isnan(latest['SMA_20']) and not np.isnan(latest['SMA_50']):
            if latest['SMA_20'] > latest['SMA_50']:
                score += 15
            if latest['Close'] > latest['SMA_20']:
                score += 10
        if not np.isnan(latest['ADX']):
            if latest['ADX'] > 40: score += 25
            elif latest['ADX'] > 30: score += 20
            elif latest['ADX'] > 25: score += 15
            elif latest['ADX'] > 20: score += 10
            else: score += 3
        if not np.isnan(latest['RSI']):
            rsi = latest['RSI']
            if 45 <= rsi <= 60: score += 20
            elif 40 <= rsi <= 65: score += 15
            elif 30 <= rsi <= 40: score += 10
            elif 65 <= rsi <= 75: score += 8
            elif rsi < 30: score += 5
            else: score += 2
        if not np.isnan(latest['Volume_Ratio']):
            vol_ratio = latest['Volume_Ratio']
            if 1.2 <= vol_ratio <= 2.5: score += 15
            elif 1.0 <= vol_ratio < 1.2: score += 10
            elif vol_ratio > 2.5: score += 8
            else: score += 3
        if not np.isnan(latest['MACD']) and not np.isnan(latest['MACD_signal']):
            if latest['MACD'] > latest['MACD_signal']: score += 10
            if latest['MACD'] > 0: score += 5
        return min(100, score)
    except:
        return 0

def scan_single_ticker(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo", interval="1d")
        if df.empty or len(df) < 50:
            return None
        info = stock.info
        avg_volume = info.get('averageVolume', 0) * info.get('currentPrice', df['Close'].iloc[-1])
        if avg_volume < 500000:
            return None
        df = calculate_all_indicators(df)
        if df is None:
            return None
        swing_score = calculate_swing_score_fast(df)
        latest = df.iloc[-1]
        return {
            'Ticker': ticker,
            'Name': info.get('shortName', ticker),
            'Preis': round(latest['Close'], 2),
            'Swing-Score': swing_score,
            'RSI': round(latest['RSI'], 1) if not np.isnan(latest['RSI']) else 0,
            'ADX': round(latest['ADX'], 1) if not np.isnan(latest['ADX']) else 0,
            'Vol Ratio': round(latest['Volume_Ratio'], 1) if not np.isnan(latest['Volume_Ratio']) else 1.0,
            'ATR%': round((latest['ATR']/latest['Close']*100), 2) if not np.isnan(latest['ATR']) else 0,
            'SMA20': 'Above' if latest['Close'] > latest['SMA_20'] else 'Below',
            'MACD': 'Bullish' if latest['MACD'] > latest['MACD_signal'] else 'Bearish',
            'Marktkapitalisierung': info.get('marketCap', 0),
            'Volumen': avg_volume
        }
    except:
        return None

def run_scanner(tickers, max_workers=10):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_single_ticker, ticker): ticker for ticker in tickers}
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            if result is not None:
                results.append(result)
            progress_bar.progress(completed / total)
            status_text.text(f"Scanne... {completed}/{total} ({len(results)} Treffer)")
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results) if results else pd.DataFrame()

# ----------------------------------
# HAUPTBEREICH
# ----------------------------------

if mode == "📈 Einzelanalyse":
    st.title(f"📈 {ticker_input} - Analyse")
    try:
        stock = yf.Ticker(ticker_input)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            st.error(f"Keine Daten für {ticker_input}")
        else:
            df = calculate_all_indicators(df)
            if df is not None:
                latest = df.iloc[-1]
                swing_score = calculate_swing_score_fast(df)
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Swing-Score", f"{swing_score}/100")
                with col2:
                    st.metric("RSI", f"{latest['RSI']:.1f}" if not np.isnan(latest['RSI']) else "N/A")
                with col3:
                    st.metric("ADX", f"{latest['ADX']:.1f}" if not np.isnan(latest['ADX']) else "N/A")
                with col4:
                    st.metric("ATR%", f"{(latest['ATR']/latest['Close']*100):.2f}%" if not np.isnan(latest['ATR']) else "N/A")
                with col5:
                    st.metric("Vol Ratio", f"{latest['Volume_Ratio']:.1f}x" if not np.isnan(latest['Volume_Ratio']) else "N/A")
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'], name="Kurs"))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='blue')))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='orange')))
                fig.update_layout(height=600, template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Fehler: {str(e)}")

else:
    st.title("🔎 Market Scanner")
    
    if scanner_type == "⚡ Quick Scan (Top 100)":
        st.markdown("### ⚡ Quick Scan - Top 100 Aktien (~30 Sekunden)")
    elif scanner_type == "💾 Watchlist Scan":
        st.markdown("### 💾 Watchlist Scan")
    else:
        st.markdown("### 📊 Standard Scan - Alle Märkte")
    
    scan_labels = {
        "📊 Standard Scan": "🚀 VOLLSTÄNDIGEN SCAN STARTEN",
        "⚡ Quick Scan (Top 100)": "⚡ QUICK SCAN STARTEN",
        "💾 Watchlist Scan": "💾 WATCHLIST SCANNEN"
    }
    
    if st.button(scan_labels[scanner_type], type="primary", use_container_width=True):
        all_tickers = []
        ticker_sources = []
        
        if scanner_type == "⚡ Quick Scan (Top 100)":
            sp500_top = get_sp500_tickers()[:50]
            nasdaq_top = get_nasdaq100_tickers()[:50]
            all_tickers = list(set(sp500_top + nasdaq_top))[:100]
            ticker_sources.append(f"Top 100 US-Aktien")
            st.info(f"⚡ {len(all_tickers)} Aktien geladen")
            
        elif scanner_type == "💾 Watchlist Scan":
            if 'user_watchlist' not in st.session_state or len(st.session_state.user_watchlist) == 0:
                st.error("❌ Watchlist leer!")
                st.stop()
            else:
                all_tickers = st.session_state.user_watchlist
                ticker_sources.append(f"Watchlist ({len(all_tickers)})")
                st.info(f"💾 {len(all_tickers)} Aktien geladen")
        else:
            if scan_sp500:
                sp500 = get_sp500_tickers()
                all_tickers.extend(sp500)
                ticker_sources.append(f"S&P 500 ({len(sp500)})")
                st.info(f"✅ S&P 500: {len(sp500)}")
            if scan_nasdaq100:
                nasdaq = get_nasdaq100_tickers()
                nasdaq = [t for t in nasdaq if t not in all_tickers]
                all_tickers.extend(nasdaq)
                ticker_sources.append(f"NASDAQ 100 ({len(nasdaq)})")
                st.info(f"✅ NASDAQ 100: {len(nasdaq)}")
            if scan_russell2000:
                russell = get_russell2000_tickers(russell_sample)
                russell = [t for t in russell if t not in all_tickers]
                all_tickers.extend(russell)
                ticker_sources.append(f"Russell 2000 ({len(russell)})")
                st.info(f"✅ Russell 2000: {len(russell)}")
            if scan_dax:
                german = get_german_tickers()
                german = [t for t in german if t not in all_tickers]
                all_tickers.extend(german)
                ticker_sources.append(f"Deutsche ({len(german)})")
                st.info(f"✅ Deutsche: {len(german)}")
        
        if len(all_tickers) == 0:
            st.error("Keine Ticker!")
        else:
            st.markdown(f"**{len(all_tickers)} Aktien | Score ≥{min_swing_score} | Quellen: {', '.join(ticker_sources)}**")
            start_time = time.time()
            st.markdown("---")
            
            if scanner_type == "⚡ Quick Scan (Top 100)":
                max_workers = 20
            else:
                max_workers = 15
            
            df_results = run_scanner(all_tickers, max_workers=max_workers)
            scan_duration = time.time() - start_time
            
            if df_results.empty:
                st.warning("Keine Ergebnisse. Filter lockern!")
            else:
                df_filtered = df_results.copy()
                df_filtered = df_filtered[df_filtered['Swing-Score'] >= min_swing_score]
                df_filtered = df_filtered[df_filtered['Volumen'] >= min_volume]
                if max_price > 0:
                    df_filtered = df_filtered[df_filtered['Preis'] <= max_price]
                df_filtered = df_filtered[(df_filtered['RSI'] >= rsi_min) & (df_filtered['RSI'] <= rsi_max)]
                df_filtered = df_filtered[df_filtered['ADX'] >= adx_min]
                df_filtered = df_filtered[df_filtered['Vol Ratio'] >= volume_surge_min]
                if require_sma_above:
                    df_filtered = df_filtered[df_filtered['SMA20'] == 'Above']
                if require_macd_bullish:
                    df_filtered = df_filtered[df_filtered['MACD'] == 'Bullish']
                min_cap = market_cap_map[min_market_cap]
                if min_cap > 0:
                    df_filtered = df_filtered[df_filtered['Marktkapitalisierung'] >= min_cap]
                
                df_filtered = df_filtered.sort_values('Swing-Score', ascending=False)
                
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Treffer", len(df_filtered))
                with col2:
                    st.metric("Dauer", f"{scan_duration:.1f}s")
                with col3:
                    st.metric("Bester Score", f"{df_filtered['Swing-Score'].max()}/100" if not df_filtered.empty else "N/A")
                
                if not df_filtered.empty:
                    def color_score(val):
                        if val >= 80: return 'background-color: #00ff8820; color: #00ff88; font-weight: bold'
                        elif val >= 70: return 'background-color: #88ff0020; color: #88ff00; font-weight: bold'
                        elif val >= 60: return 'background-color: #ffaa0020; color: #ffaa00'
                        else: return 'background-color: #ff444420; color: #ff4444'
                    
                    styled_df = df_filtered.style.applymap(color_score, subset=['Swing-Score'])
                    styled_df = styled_df.format({
                        'Preis': '${:.2f}', 'RSI': '{:.1f}', 'ADX': '{:.1f}',
                        'Vol Ratio': '{:.1f}x', 'ATR%': '{:.2f}%',
                        'Marktkapitalisierung': '${:,.0f}', 'Volumen': '${:,.0f}'
                    })
                    
                    st.dataframe(styled_df, use_container_width=True, height=500)
                    
                    csv = df_filtered.to_csv(index=False)
                    st.download_button(
                        "📥 CSV Download",
                        csv,
                        f"scanner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        'text/csv'
                    )
                    
                    st.markdown("---")
                    st.subheader("🏆 Top 10")
                    top10 = df_filtered.head(10)
                    for i, (idx, row) in enumerate(top10.iterrows()):
                        with st.expander(f"#{i+1} {row['Ticker']} - {row['Name'][:50]} | Score: {row['Swing-Score']}/100 | ${row['Preis']:.2f}", expanded=(i==0)):
                            c1, c2, c3, c4 = st.columns(4)
                            with c1:
                                st.metric("Score", f"{row['Swing-Score']}/100")
                                st.metric("Preis", f"${row['Preis']:.2f}")
                            with c2:
                                st.metric("RSI", f"{row['RSI']:.1f}")
                                st.metric("ADX", f"{row['ADX']:.1f}")
                            with c3:
                                st.metric("ATR%", f"{row['ATR%']:.2f}%")
                                st.metric("Vol Ratio", f"{row['Vol Ratio']:.1f}x")
                            with c4:
                                st.metric("SMA20", row['SMA20'])
                                st.metric("MACD", row['MACD'])
                            try:
                                stock = yf.Ticker(row['Ticker'])
                                df_mini = stock.history(period="1mo")
                                if not df_mini.empty:
                                    fig_mini = go.Figure()
                                    fig_mini.add_trace(go.Candlestick(x=df_mini.index, open=df_mini['Open'],
                                        high=df_mini['High'], low=df_mini['Low'], close=df_mini['Close']))
                                    fig_mini.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0),
                                        xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False),
                                        template='plotly_dark', showlegend=False)
                                    st.plotly_chart(fig_mini, use_container_width=True)
                            except:
                                pass
                else:
                    st.warning("Keine Aktien erfüllen die Filter. Versuche:")
                    st.markdown("- Score reduzieren\n- RSI-Grenzen erweitern\n- ADX senken")
    else:
        st.info("👆 Einstellungen wählen und Scan starten!")

# Watchlist Tab
tab_wl = st.container()
with tab_wl:
    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Watchlist")
    
    if 'user_watchlist' not in st.session_state:
        st.session_state.user_watchlist = []
    
    new_ticker = st.sidebar.text_input("Ticker hinzufügen:", key="wl_input").upper()
    if st.sidebar.button("➕ Hinzufügen"):
        if new_ticker and new_ticker not in st.session_state.user_watchlist:
            st.session_state.user_watchlist.append(new_ticker)
            st.sidebar.success(f"✅ {new_ticker}")
    
    if st.session_state.user_watchlist:
        st.sidebar.markdown(f"**{len(st.session_state.user_watchlist)} Ticker:**")
        for t in st.session_state.user_watchlist[-5:]:
            st.sidebar.markdown(f"- {t}")
        if len(st.session_state.user_watchlist) > 5:
            st.sidebar.caption(f"...+{len(st.session_state.user_watchlist)-5} mehr")
        if st.sidebar.button("🗑️ Leeren"):
            st.session_state.user_watchlist = []
            st.rerun()

st.markdown("---")
st.caption("⚠️ Keine Finanzberatung. Daten verzögert. Nur zu Bildungszwecken.")
st.caption(f"📊 Yahoo Finance | {datetime.now().strftime('%d.%m.%Y %H:%M')}")
