import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
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
    .score-excellent { color: #00ff88; font-size: 24px; font-weight: bold; }
    .score-good { color: #88ff00; font-size: 24px; font-weight: bold; }
    .score-neutral { color: #ffaa00; font-size: 24px; font-weight: bold; }
    .score-weak { color: #ff4444; font-size: 24px; font-weight: bold; }
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
    period = st.sidebar.selectbox("Zeitraum:", ["1mo", "3mo", "6mo", "1y"], index=1)
else:
    st.sidebar.subheader("🎯 Scanner-Typ")
    scanner_type = st.sidebar.radio(
        "Wähle Modus:",
        ["⚡ Quick Scan (Top 100)", "📊 Standard Scan", "💾 Watchlist Scan"],
        index=0
    )
    
    if scanner_type == "💾 Watchlist Scan":
        if 'user_watchlist' not in st.session_state or len(st.session_state.user_watchlist) == 0:
            st.sidebar.warning("⚠️ Watchlist ist leer! Füge unten Ticker hinzu.")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Filter-Preset")
    
    filter_preset = st.sidebar.selectbox(
        "Wähle Preset:",
        ["📊 Moderat (60+)", "✅ Gut (70+)", "🏆 Exzellent (80+)", "🔧 Eigene Einstellungen"],
        index=0  # Standard: Moderat für mehr Ergebnisse!
    )
    
    if filter_preset == "📊 Moderat (60+)":
        min_swing_score = 60
        min_volume = 1000000
        rsi_min = 30
        rsi_max = 75
        adx_min = 15
        volume_surge_min = 0.8
        require_sma_above = False
        require_macd_bullish = False
        min_market_cap = "Keine"
    elif filter_preset == "✅ Gut (70+)":
        min_swing_score = 70
        min_volume = 5000000
        rsi_min = 40
        rsi_max = 65
        adx_min = 25
        volume_surge_min = 1.2
        require_sma_above = True
        require_macd_bullish = True
        min_market_cap = "Mid Cap (>2B)"
    elif filter_preset == "🏆 Exzellent (80+)":
        min_swing_score = 80
        min_volume = 10000000
        rsi_min = 45
        rsi_max = 60
        adx_min = 30
        volume_surge_min = 1.5
        require_sma_above = True
        require_macd_bullish = True
        min_market_cap = "Large Cap (>10B)"
    else:
        min_swing_score = st.sidebar.slider("Min. Swing-Score:", 0, 100, 50)
        min_volume = st.sidebar.number_input("Min. Volumen ($):", 0, 1000000000, 1000000, 500000)
        rsi_min = st.sidebar.slider("RSI Min:", 0, 100, 30)
        rsi_max = st.sidebar.slider("RSI Max:", 0, 100, 75)
        adx_min = st.sidebar.slider("ADX Min:", 0, 100, 15)
        volume_surge_min = st.sidebar.slider("Vol Ratio:", 0.5, 5.0, 0.8)
        require_sma_above = st.sidebar.checkbox("Kurs > SMA20", value=False)
        require_macd_bullish = st.sidebar.checkbox("MACD bullisch", value=False)
        min_market_cap = st.sidebar.selectbox("Marktkap.:", 
            ["Keine", "Micro (>50M)", "Small (>300M)", "Mid (>2B)", "Large (>10B)"], index=0)
    
    market_cap_map = {
        "Keine": 0, "Micro (>50M)": 50000000, "Small (>300M)": 300000000,
        "Mid (>2B)": 2000000000, "Large (>10B)": 10000000000
    }
    
    if 'max_price' not in locals():
        max_price = 10000.0
    
    # Watchlist in Sidebar
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
        st.sidebar.markdown(f"**{len(st.session_state.user_watchlist)} Ticker**")
        if st.sidebar.button("🗑️ Leeren"):
            st.session_state.user_watchlist = []
            st.rerun()
    
    # Cache Button
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Cache leeren & neustarten"):
        st.cache_data.clear()
        st.success("Cache geleert!")
        time.sleep(1)
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ Keine Finanzberatung. Nur Bildungszwecke.")

# ----------------------------------
# FALLBACK-TICKER (immer verfügbar)
# ----------------------------------
FALLBACK_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "JNJ",
    "V", "PG", "XOM", "UNH", "MA", "HD", "CVX", "MRK", "ABBV", "PEP",
    "KO", "WMT", "AVGO", "LLY", "COST", "TMO", "MCD", "CSCO", "ACN", "ABT",
    "DHR", "VZ", "NKE", "CRM", "NEE", "DIS", "AMD", "PM", "TXN", "LIN",
    "NFLX", "ADBE", "INTC", "CMCSA", "INTU", "QCOM", "AMGN", "HON", "SBUX", "GILD",
    "REGN", "VRTX", "ADP", "ISRG", "LRCX", "MU", "KLAC", "SNPS", "CDNS", "MELI",
    "MAR", "ORLY", "CTAS", "PCAR", "ROP", "MNST", "KDP", "ASML", "AZN", "SAP",
    "TMUS", "FI", "ANET", "PANW", "PLTR", "UBER", "SQ", "SNAP", "PINS", "ZM",
    "DDOG", "CRWD", "SNOW", "NET", "RBLX", "AFRM", "HOOD", "SOFI", "IONQ", "RIVN"
]

# ----------------------------------
# HILFSFUNKTIONEN
# ----------------------------------

@st.cache_data(ttl=1800)
def get_tickers_safe():
    """Holt Ticker mit Fallback"""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        tickers = [t.replace('.', '-') for t in tickers]
        return tickers[:100]  # Top 100 für Schnelligkeit
    except:
        return FALLBACK_TICKERS

def calculate_indicators_safe(df):
    """Berechnet Indikatoren mit Fehlerbehandlung"""
    if len(df) < 20:
        return None
    try:
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        df['MACD'] = ta.trend.macd(df['Close'])
        df['MACD_signal'] = ta.trend.macd_signal(df['Close'])
        df['MACD_hist'] = ta.trend.macd_diff(df['Close'])
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        return df
    except Exception as e:
        return None

def swing_score_simple(df):
    """Einfacher Swing-Score (0-100)"""
    if df is None or len(df) < 20:
        return 0
    try:
        latest = df.iloc[-1]
        score = 0
        
        # Trend (30 Punkte)
        if pd.notna(latest.get('SMA_20')) and pd.notna(latest.get('SMA_50')):
            if latest['SMA_20'] > latest['SMA_50']:
                score += 15
            if latest['Close'] > latest['SMA_20']:
                score += 10
            if latest['Close'] > latest['SMA_50']:
                score += 5
        
        # ADX (25 Punkte)
        if pd.notna(latest.get('ADX')):
            adx = latest['ADX']
            if adx > 40: score += 25
            elif adx > 30: score += 20
            elif adx > 25: score += 15
            elif adx > 20: score += 10
            elif adx > 15: score += 5
            else: score += 2
        
        # RSI (20 Punkte)
        if pd.notna(latest.get('RSI')):
            rsi = latest['RSI']
            if 45 <= rsi <= 60: score += 20
            elif 40 <= rsi <= 70: score += 15
            elif 30 <= rsi <= 75: score += 10
            else: score += 5
        
        # Volumen (15 Punkte)
        if pd.notna(latest.get('Volume_Ratio')):
            vr = latest['Volume_Ratio']
            if 1.2 <= vr <= 2.5: score += 15
            elif 1.0 <= vr <= 3.0: score += 10
            elif vr > 0.7: score += 5
            else: score += 2
        
        # MACD (10 Punkte)
        if pd.notna(latest.get('MACD')) and pd.notna(latest.get('MACD_signal')):
            if latest['MACD'] > latest['MACD_signal']: score += 7
            if latest['MACD'] > 0: score += 3
        
        return min(100, score)
    except:
        return 0

def scan_one(ticker):
    """Scannt einen Ticker"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo", interval="1d")
        
        if df.empty or len(df) < 20:
            return None
        
        # Volumen-Check (einfacher)
        avg_vol = df['Volume'].tail(20).mean()
        price = df['Close'].iloc[-1]
        if avg_vol * price < 500000:  # Min $500k Tagesvolumen
            return None
        
        df = calculate_indicators_safe(df)
        if df is None:
            return None
        
        score = swing_score_simple(df)
        latest = df.iloc[-1]
        
        # Name holen
        try:
            name = stock.info.get('shortName', ticker)
        except:
            name = ticker
        
        return {
            'Ticker': ticker,
            'Name': name[:50],
            'Preis': round(latest['Close'], 2),
            'Swing-Score': score,
            'RSI': round(latest['RSI'], 1) if pd.notna(latest.get('RSI')) else 50,
            'ADX': round(latest['ADX'], 1) if pd.notna(latest.get('ADX')) else 20,
            'Vol Ratio': round(latest['Volume_Ratio'], 1) if pd.notna(latest.get('Volume_Ratio')) else 1.0,
            'ATR%': round((latest['ATR']/latest['Close']*100), 2) if pd.notna(latest.get('ATR')) else 2.0,
            'SMA20': 'Above' if pd.notna(latest.get('SMA_20')) and latest['Close'] > latest['SMA_20'] else 'Below',
            'MACD': 'Bullish' if pd.notna(latest.get('MACD')) and pd.notna(latest.get('MACD_signal')) and latest['MACD'] > latest['MACD_signal'] else 'Bearish',
            'Volumen': avg_vol * price
        }
    except Exception as e:
        return None

def run_scan(tickers, max_workers=10):
    """Scannt Ticker-Liste"""
    results = []
    progress = st.progress(0)
    status = st.empty()
    total = len(tickers)
    done = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_one, t): t for t in tickers}
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                results.append(result)
            progress.progress(done / total)
            status.text(f"Scan... {done}/{total} ({len(results)} gefunden)")
    
    progress.empty()
    status.empty()
    return pd.DataFrame(results) if results else pd.DataFrame()

# ----------------------------------
# HAUPTBEREICH
# ----------------------------------

if mode == "📈 Einzelanalyse":
    st.title(f"📈 {ticker_input}")
    
    try:
        stock = yf.Ticker(ticker_input)
        df = stock.history(period=period, interval="1d")
        
        if df.empty:
            st.error(f"❌ Keine Daten für {ticker_input}")
            st.info("💡 Tipp: Probiere AAPL, MSFT oder TSLA zum Testen")
        else:
            df = calculate_indicators_safe(df)
            
            if df is not None:
                latest = df.iloc[-1]
                score = swing_score_simple(df)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Swing-Score", f"{score}/100")
                with col2:
                    st.metric("Preis", f"${latest['Close']:.2f}")
                with col3:
                    st.metric("RSI", f"{latest['RSI']:.1f}" if pd.notna(latest.get('RSI')) else "N/A")
                with col4:
                    st.metric("ADX", f"{latest['ADX']:.1f}" if pd.notna(latest.get('ADX')) else "N/A")
                
                # Chart
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'], name="Kurs"))
                if pd.notna(latest.get('SMA_20')):
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', 
                        line=dict(color='blue', width=1)))
                fig.update_layout(height=500, template='plotly_dark', 
                    margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Nicht genug Daten für Analyse")
    except Exception as e:
        st.error(f"Fehler: {e}")
        st.info("💡 Häufigster Grund: Yahoo Finance temporär nicht erreichbar. Warte 2 Min und versuche es erneut.")

else:
    st.title("🔎 Market Scanner")
    
    # Info-Box
    st.info("💡 **Tipp:** Starte mit 'Quick Scan' und 'Moderat (60+)' für die meisten Ergebnisse!")
    
    if scanner_type == "⚡ Quick Scan (Top 100)":
        st.markdown("### ⚡ Quick Scan (~30 Sekunden)")
    elif scanner_type == "💾 Watchlist Scan":
        st.markdown(f"### 💾 Watchlist Scan ({len(st.session_state.get('user_watchlist', []))} Aktien)")
    else:
        st.markdown("### 📊 Standard Scan")
    
    # Scan Button
    btn_labels = {
        "⚡ Quick Scan (Top 100)": "⚡ QUICK SCAN STARTEN",
        "📊 Standard Scan": "🚀 SCAN STARTEN",
        "💾 Watchlist Scan": "💾 WATCHLIST SCANNEN"
    }
    
    if st.button(btn_labels[scanner_type], type="primary", use_container_width=True):
        
        # Ticker sammeln
        if scanner_type == "💾 Watchlist Scan":
            if len(st.session_state.get('user_watchlist', [])) == 0:
                st.error("❌ Watchlist leer! Füge Ticker in der Sidebar hinzu.")
                st.stop()
            tickers = st.session_state.user_watchlist
        else:
            tickers = get_tickers_safe()
            if scanner_type == "⚡ Quick Scan (Top 100)":
                tickers = tickers[:100]
        
        st.markdown(f"**Scanne {len(tickers)} Aktien...**")
        
        # Scan ausführen
        start = time.time()
        df_results = run_scan(tickers, max_workers=15)
        duration = time.time() - start
        
        if df_results.empty:
            st.error("❌ Keine Ergebnisse!")
            st.markdown("""
            **Mögliche Gründe:**
            1. Yahoo Finance blockt Anfragen → **Cache leeren & in 2 Min nochmal**
            2. Filter zu streng → **Preset 'Moderat' wählen**
            3. Markt geschlossen → Am Wochenende weniger Daten
            
            **Sofort-Lösung:** Klick '🗑️ Cache leeren' in der Sidebar!
            """)
        else:
            # Filtern
            df_filtered = df_results.copy()
            df_filtered = df_filtered[df_filtered['Swing-Score'] >= min_swing_score]
            df_filtered = df_filtered[df_filtered['Volumen'] >= min_volume]
            df_filtered = df_filtered[(df_filtered['RSI'] >= rsi_min) & (df_filtered['RSI'] <= rsi_max)]
            df_filtered = df_filtered[df_filtered['ADX'] >= adx_min]
            df_filtered = df_filtered[df_filtered['Vol Ratio'] >= volume_surge_min]
            
            if require_sma_above:
                df_filtered = df_filtered[df_filtered['SMA20'] == 'Above']
            if require_macd_bullish:
                df_filtered = df_filtered[df_filtered['MACD'] == 'Bullish']
            
            min_cap = market_cap_map.get(min_market_cap, 0)
            if min_cap > 0 and 'Marktkapitalisierung' not in df_filtered.columns:
                pass  # Keine Marktkap-Daten verfügbar
            
            df_filtered = df_filtered.sort_values('Swing-Score', ascending=False)
            
            # Ergebnisse anzeigen
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Treffer", len(df_filtered))
            with col2:
                st.metric("⏱ Dauer", f"{duration:.1f}s")
            with col3:
                best = df_filtered['Swing-Score'].max() if not df_filtered.empty else 0
                st.metric("🏆 Bester Score", f"{best}/100")
            
            if not df_filtered.empty:
                # Einfärbung
                def color_score(val):
                    if val >= 80: return 'background-color: #00ff8820; color: #00ff88; font-weight: bold'
                    elif val >= 70: return 'background-color: #88ff0020; color: #88ff00; font-weight: bold'
                    elif val >= 60: return 'background-color: #ffaa0020; color: #ffaa00'
                    else: return ''
                
                styled = df_filtered.style.applymap(color_score, subset=['Swing-Score'])
                styled = styled.format({
                    'Preis': '${:.2f}', 'RSI': '{:.1f}', 'ADX': '{:.1f}',
                    'Vol Ratio': '{:.1f}x', 'ATR%': '{:.2f}%', 'Volumen': '${:,.0f}'
                })
                
                st.dataframe(styled, use_container_width=True, height=400)
                
                # CSV Download
                csv = df_filtered.to_csv(index=False)
                st.download_button("📥 CSV Download", csv, f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
                
                # Top 5
                st.markdown("---")
                st.subheader("🏆 Top 5 Kandidaten")
                
                top5 = df_filtered.head(5)
                for i, (_, row) in enumerate(top5.iterrows()):
                    with st.expander(f"#{i+1} {row['Ticker']} | Score: {row['Swing-Score']}/100 | ${row['Preis']:.2f}", expanded=(i==0)):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Score", f"{row['Swing-Score']}/100")
                            st.metric("Preis", f"${row['Preis']:.2f}")
                        with c2:
                            st.metric("RSI", f"{row['RSI']:.1f}")
                            st.metric("ADX", f"{row['ADX']:.1f}")
                        with c3:
                            st.metric("ATR%", f"{row['ATR%']:.2f}%")
                            st.metric("Vol Ratio", f"{row['Vol Ratio']:.1f}x")
                        
                        # Mini-Chart
                        try:
                            mini = yf.Ticker(row['Ticker']).history(period="1mo")
                            if not mini.empty:
                                fig_m = go.Figure()
                                fig_m.add_trace(go.Candlestick(x=mini.index, open=mini['Open'],
                                    high=mini['High'], low=mini['Low'], close=mini['Close']))
                                fig_m.update_layout(height=150, margin=dict(l=0,r=0,t=0,b=0),
                                    xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False),
                                    template='plotly_dark', showlegend=False)
                                st.plotly_chart(fig_m, use_container_width=True)
                        except:
                            pass
            else:
                st.warning("⚠️ Keine Aktien erfüllen die aktuellen Filter.")
                st.markdown("""
                **Schnelle Lösungen:**
                - Wähle Preset **'📊 Moderat (60+)'**
                - Reduziere Swing-Score auf **50**
                - Erhöhe RSI-Max auf **75**
                - Setze ADX runter auf **15**
                """)
    else:
        # Kein Scan - zeige Hilfe
        st.info("👆 Wähle Filter-Preset und klick auf den Scan-Button!")
        st.markdown("""
        ### 📊 Empfohlene Einstellungen für den Start:
        - **Scanner-Typ:** Quick Scan
        - **Filter-Preset:** Moderat (60+)
        - Dann auf **'QUICK SCAN STARTEN'** klicken
        
        ### 💡 Tipps:
        - Quick Scan = ~30 Sekunden
        - Je strenger der Filter, desto weniger Ergebnisse
        - Am Wochenende sind weniger Daten verfügbar
        """)

# Footer
st.markdown("---")
st.caption("⚠️ Keine Finanzberatung. Daten von Yahoo Finance (15-20 Min verzögert).")
st.caption(f"🕐 Letzter Update: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
