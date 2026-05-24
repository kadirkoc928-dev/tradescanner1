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
    .stButton > button {
        width: 100%;
        background-color: #00ff88;
        color: black;
        font-weight: bold;
        border: none;
        padding: 10px;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #00cc6a;
    }
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
        index=0
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
            st.sidebar.success(f"✅ {new_ticker} hinzugefügt!")
    
    if st.session_state.user_watchlist:
        st.sidebar.markdown(f"**{len(st.session_state.user_watchlist)} Ticker in Watchlist**")
        for t in st.session_state.user_watchlist[-5:]:
            st.sidebar.markdown(f"• {t}")
        if len(st.session_state.user_watchlist) > 5:
            st.sidebar.caption(f"...+{len(st.session_state.user_watchlist)-5} mehr")
        
        if st.sidebar.button("🗑️ Watchlist leeren"):
            st.session_state.user_watchlist = []
            st.rerun()
    
    # Cache Button
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Cache leeren & neustarten"):
        st.cache_data.clear()
        st.success("✅ Cache geleert! Seite wird neu geladen...")
        time.sleep(1)
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ Keine Finanzberatung. Nur zu Bildungszwecken.")
st.sidebar.caption("📊 Daten: Yahoo Finance (verzögert)")

# ----------------------------------
# FALLBACK-TICKER
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
    "DDOG", "CRWD", "SNOW", "NET", "RBLX", "AFRM", "HOOD", "SOFI", "IONQ", "RIVN",
    "BA", "CAT", "DE", "FDX", "UPS", "LMT", "RTX", "GE", "MMM", "EMR"
]

# ----------------------------------
# HILFSFUNKTIONEN
# ----------------------------------

@st.cache_data(ttl=1800)
def get_tickers_safe():
    """Holt Ticker mit Fallback falls Wikipedia nicht erreichbar"""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        tickers = [t.replace('.', '-') for t in tickers]
        return tickers[:100]  # Top 100 für Geschwindigkeit
    except Exception as e:
        st.warning(f"Wikipedia nicht erreichbar, nutze Fallback-Liste ({len(FALLBACK_TICKERS)} Ticker)")
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
    """Einfacher aber robuster Swing-Score (0-100)"""
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
    except Exception as e:
        return 0

def scan_one(ticker):
    """Scannt einen einzelnen Ticker"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo", interval="1d")
        
        if df.empty or len(df) < 20:
            return None
        
        # Einfacher Volumen-Check
        avg_vol = df['Volume'].tail(20).mean()
        price = df['Close'].iloc[-1]
        if avg_vol * price < 500000:
            return None
        
        df = calculate_indicators_safe(df)
        if df is None:
            return None
        
        score = swing_score_simple(df)
        latest = df.iloc[-1]
        
        # Name sicher holen
        try:
            name = stock.info.get('shortName', ticker)
        except:
            name = ticker
        
        # RSI-Wert sicher abrufen
        rsi_val = latest.get('RSI')
        if pd.isna(rsi_val):
            rsi_val = 50
        
        # ADX-Wert sicher abrufen
        adx_val = latest.get('ADX')
        if pd.isna(adx_val):
            adx_val = 20
        
        # Volumen-Ratio sicher abrufen
        vol_ratio = latest.get('Volume_Ratio')
        if pd.isna(vol_ratio):
            vol_ratio = 1.0
        
        # ATR% sicher berechnen
        atr_val = latest.get('ATR')
        if pd.isna(atr_val) or price == 0:
            atr_pct = 2.0
        else:
            atr_pct = (atr_val / price) * 100
        
        # SMA20 Check
        sma20_val = latest.get('SMA_20')
        if pd.isna(sma20_val):
            sma_status = 'N/A'
        else:
            sma_status = 'Above' if price > sma20_val else 'Below'
        
        # MACD Check
        macd_val = latest.get('MACD')
        macd_sig = latest.get('MACD_signal')
        if pd.isna(macd_val) or pd.isna(macd_sig):
            macd_status = 'N/A'
        else:
            macd_status = 'Bullish' if macd_val > macd_sig else 'Bearish'
        
        return {
            'Ticker': ticker,
            'Name': str(name)[:50],
            'Preis': round(price, 2),
            'Swing-Score': score,
            'RSI': round(rsi_val, 1),
            'ADX': round(adx_val, 1),
            'Vol Ratio': round(vol_ratio, 1),
            'ATR%': round(atr_pct, 2),
            'SMA20': sma_status,
            'MACD': macd_status,
            'Volumen': round(avg_vol * price, 0)
        }
    except Exception as e:
        return None

def run_scan(tickers, max_workers=10):
    """Führt parallelen Scan durch"""
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(tickers)
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_one, ticker): ticker for ticker in tickers}
        
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            if result is not None:
                results.append(result)
            
            progress_bar.progress(completed / total)
            status_text.text(f"🔍 Scanne... {completed}/{total} Aktien | ✅ {len(results)} Treffer")
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(results) if results else pd.DataFrame()

# ----------------------------------
# HAUPTBEREICH
# ----------------------------------

if mode == "📈 Einzelanalyse":
    st.title(f"📈 {ticker_input} - Technische Analyse")
    
    try:
        with st.spinner(f"Lade Daten für {ticker_input}..."):
            stock = yf.Ticker(ticker_input)
            df = stock.history(period=period, interval="1d")
        
        if df.empty:
            st.error(f"❌ Keine Daten für **{ticker_input}** gefunden.")
            st.info("💡 **Tipp:** Probiere AAPL, MSFT, NVDA oder TSLA zum Testen.")
        else:
            df = calculate_indicators_safe(df)
            
            if df is not None:
                latest = df.iloc[-1]
                score = swing_score_simple(df)
                
                # Metriken oben
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    score_color = "green" if score >= 70 else "orange" if score >= 50 else "red"
                    st.metric("🎯 Swing-Score", f"{score}/100")
                
                with col2:
                    price = latest['Close']
                    prev_price = df.iloc[-2]['Close'] if len(df) > 1 else price
                    change = ((price - prev_price) / prev_price) * 100
                    st.metric("💵 Preis", f"${price:.2f}", f"{change:.2f}%")
                
                with col3:
                    rsi_val = latest.get('RSI')
                    rsi_display = f"{rsi_val:.1f}" if pd.notna(rsi_val) else "N/A"
                    st.metric("📊 RSI", rsi_display)
                
                with col4:
                    adx_val = latest.get('ADX')
                    adx_display = f"{adx_val:.1f}" if pd.notna(adx_val) else "N/A"
                    st.metric("📈 ADX", adx_display)
                
                with col5:
                    atr_val = latest.get('ATR')
                    if pd.notna(atr_val) and price > 0:
                        atr_display = f"{(atr_val/price)*100:.2f}%"
                    else:
                        atr_display = "N/A"
                    st.metric("📉 ATR%", atr_display)
                
                st.markdown("---")
                
                # Chart
                fig = go.Figure()
                
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name="Kurs",
                    increasing_line_color='#00ff88',
                    decreasing_line_color='#ff4444'
                ))
                
                # SMA20
                if pd.notna(latest.get('SMA_20')):
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['SMA_20'],
                        name='SMA 20',
                        line=dict(color='blue', width=1.5)
                    ))
                
                # SMA50
                if pd.notna(latest.get('SMA_50')):
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['SMA_50'],
                        name='SMA 50',
                        line=dict(color='orange', width=1.5)
                    ))
                
                fig.update_layout(
                    height=600,
                    template='plotly_dark',
                    margin=dict(l=0, r=0, t=20, b=0),
                    xaxis_rangeslider_visible=False,
                    hovermode='x unified'
                )
                
                fig.update_xaxes(title_text="Datum")
                fig.update_yaxes(title_text="Preis ($)")
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Zusätzliche Charts: RSI und MACD
                col1, col2 = st.columns(2)
                
                with col1:
                    if pd.notna(latest.get('RSI')):
                        st.subheader("📊 RSI (14)")
                        fig_rsi = go.Figure()
                        fig_rsi.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI',
                            line=dict(color='purple', width=2)))
                        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5)
                        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5)
                        fig_rsi.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.3)
                        fig_rsi.update_layout(height=300, template='plotly_dark',
                            margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
                        fig_rsi.update_yaxes(range=[0, 100])
                        st.plotly_chart(fig_rsi, use_container_width=True)
                
                with col2:
                    if pd.notna(latest.get('MACD')):
                        st.subheader("📈 MACD")
                        fig_macd = go.Figure()
                        fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD',
                            line=dict(color='blue', width=2)))
                        fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal',
                            line=dict(color='red', width=1)))
                        
                        # MACD Histogramm
                        colors_macd = ['green' if val >= 0 else 'red' for val in df['MACD_hist'].dropna()]
                        fig_macd.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='Histogram',
                            marker_color=colors_macd, opacity=0.5))
                        
                        fig_macd.update_layout(height=300, template='plotly_dark',
                            margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
                        st.plotly_chart(fig_macd, use_container_width=True)
            else:
                st.warning("⚠️ Nicht genügend Daten für eine vollständige Analyse.")
    
    except Exception as e:
        st.error(f"❌ Fehler beim Laden: {str(e)}")
        st.info("💡 Mögliche Ursachen: Ticker existiert nicht, Yahoo Finance nicht erreichbar, oder Internetverbindung prüfen.")

else:
    # =============================================
    # MARKET SCANNER
    # =============================================
    st.title("🔎 Market Scanner")
    
    # Info-Box mit Tipps
    with st.expander("💡 Tipps für beste Ergebnisse", expanded=False):
        st.markdown("""
        - **Quick Scan** = Top 100 Aktien in ~30 Sekunden
        - **Moderat (60+)** = Mehr Ergebnisse, weniger strenge Filter
        - **Cache leeren** wenn keine Ergebnisse kommen (Sidebar-Button)
        - Am Wochenende sind weniger Daten verfügbar
        - Bei "0 Ergebnisse": Filter-Preset auf **Moderat** stellen!
        """)
    
    if scanner_type == "⚡ Quick Scan (Top 100)":
        st.markdown("### ⚡ Quick Scan - Top 100 Aktien")
        st.caption("Scannt die 100 wichtigsten US-Aktien in ~30 Sekunden")
    elif scanner_type == "💾 Watchlist Scan":
        watchlist_count = len(st.session_state.get('user_watchlist', []))
        st.markdown(f"### 💾 Watchlist Scan - {watchlist_count} Aktien")
        st.caption("Scannt nur deine gespeicherten Favoriten")
    else:
        st.markdown("### 📊 Standard Scan")
        st.caption("Scannt S&P 500 Aktien (Top 100)")
    
    st.markdown("---")
    
    # Scan Button
    btn_labels = {
        "⚡ Quick Scan (Top 100)": "⚡ QUICK SCAN STARTEN (30s)",
        "📊 Standard Scan": "🚀 SCAN STARTEN",
        "💾 Watchlist Scan": "💾 WATCHLIST SCANNEN"
    }
    
    scan_clicked = st.button(btn_labels[scanner_type], type="primary", use_container_width=True)
    
    if scan_clicked:
        
        # Ticker sammeln
        if scanner_type == "💾 Watchlist Scan":
            if len(st.session_state.get('user_watchlist', [])) == 0:
                st.error("❌ Watchlist ist leer!")
                st.info("👉 Füge Ticker in der Sidebar hinzu (z.B. AAPL, TSLA, NVDA)")
                st.stop()
            tickers = st.session_state.user_watchlist
        else:
            tickers = get_tickers_safe()
            if scanner_type == "⚡ Quick Scan (Top 100)":
                tickers = tickers[:100]
        
        st.markdown(f"**🔍 Scanne {len(tickers)} Aktien...**")
        st.markdown(f"Filter: Score ≥{min_swing_score} | RSI {rsi_min}-{rsi_max} | ADX ≥{adx_min} | Vol ≥{volume_surge_min}x")
        
        # Scan ausführen
        start_time = time.time()
        df_results = run_scan(tickers, max_workers=15)
        duration = time.time() - start_time
        
        if df_results.empty:
            st.error("❌ Keine Ergebnisse gefunden!")
            st.markdown("""
            ### Mögliche Ursachen:
            1. **Yahoo Finance blockt** → Klick auf **'Cache leeren'** in der Sidebar
            2. **Filter zu streng** → Wähle Preset **'Moderat (60+)'**
            3. **Markt geschlossen** → Am Wochenende/testweise unter der Woche probieren
            
            ### Sofort-Lösung:
            👉 Klick in der Sidebar auf **'🗑️ Cache leeren & neustarten'** und versuche es erneut!
            """)
        else:
            # Filtern
            df_filtered = df_results.copy()
            
            # Basis-Filter anwenden
            df_filtered = df_filtered[df_filtered['Swing-Score'] >= min_swing_score]
            df_filtered = df_filtered[df_filtered['Volumen'] >= min_volume]
            df_filtered = df_filtered[(df_filtered['RSI'] >= rsi_min) & (df_filtered['RSI'] <= rsi_max)]
            df_filtered = df_filtered[df_filtered['ADX'] >= adx_min]
            df_filtered = df_filtered[df_filtered['Vol Ratio'] >= volume_surge_min]
            
            if require_sma_above:
                df_filtered = df_filtered[df_filtered['SMA20'] == 'Above']
            if require_macd_bullish:
                df_filtered = df_filtered[df_filtered['MACD'] == 'Bullish']
            
            # Sortieren nach Score
            df_filtered = df_filtered.sort_values('Swing-Score', ascending=False)
            
            # Ergebnisse anzeigen
            st.markdown("---")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Treffer", f"{len(df_filtered)} Aktien")
            with col2:
                st.metric("⏱ Scan-Dauer", f"{duration:.1f} Sekunden")
            with col3:
                best_score = df_filtered['Swing-Score'].max() if not df_filtered.empty else 0
                st.metric("🏆 Bester Score", f"{best_score}/100")
            
            # Info über Roh-Ergebnisse
            st.caption(f"{len(df_results)} Roh-Treffer → {len(df_filtered)} nach Filtern")
            
            if not df_filtered.empty:
                st.markdown("---")
                st.subheader("📋 Scan-Ergebnisse")
                
                # Farbige Formatierung
                def color_score(val):
                    if val >= 80:
                        return 'background-color: #00ff8820; color: #00ff88; font-weight: bold'
                    elif val >= 70:
                        return 'background-color: #88ff0020; color: #88ff00; font-weight: bold'
                    elif val >= 60:
                        return 'background-color: #ffaa0020; color: #ffaa00; font-weight: bold'
                    else:
                        return ''
                
                def color_macd(val):
                    if val == 'Bullish':
                        return 'color: #00ff88; font-weight: bold'
                    elif val == 'Bearish':
                        return 'color: #ff4444'
                    else:
                        return ''
                
                # Tabelle stylen
                styled_df = df_filtered.style.map(color_score, subset=['Swing-Score'])
                styled_df = styled_df.map(color_macd, subset=['MACD'])
                styled_df = styled_df.format({
                    'Preis': '${:.2f}',
                    'RSI': '{:.1f}',
                    'ADX': '{:.1f}',
                    'Vol Ratio': '{:.1f}x',
                    'ATR%': '{:.2f}%',
                    'Volumen': '${:,.0f}'
                })
                
                st.dataframe(styled_df, use_container_width=True, height=500)
                
                # CSV Download
                csv = df_filtered.to_csv(index=False)
                st.download_button(
                    label=f"📥 {len(df_filtered)} Ergebnisse als CSV herunterladen",
                    data=csv,
                    file_name=f"scanner_ergebnisse_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime='text/csv'
                )
                
                # Top 5 Detail-Ansicht
                st.markdown("---")
                st.subheader("🏆 Top 5 Swing-Trading Kandidaten")
                
                top5 = df_filtered.head(5)
                for i, (_, row) in enumerate(top5.iterrows()):
                    score = row['Swing-Score']
                    emoji = "🌟" if score >= 80 else "✅" if score >= 70 else "📊" if score >= 60 else "📉"
                    
                    with st.expander(
                        f"{emoji} #{i+1} | {row['Ticker']} | Score: {score}/100 | ${row['Preis']:.2f} | {row['Name'][:40]}",
                        expanded=(i == 0)
                    ):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("🎯 Swing-Score", f"{score}/100")
                            st.metric("💵 Preis", f"${row['Preis']:.2f}")
                            st.metric("📊 RSI", f"{row['RSI']:.1f}")
                        
                        with col2:
                            st.metric("📈 ADX", f"{row['ADX']:.1f}")
                            st.metric("📉 ATR%", f"{row['ATR%']:.2f}%")
                            st.metric("📊 Vol Ratio", f"{row['Vol Ratio']:.1f}x")
                        
                        with col3:
                            st.metric("📈 SMA20", row['SMA20'])
                            st.metric("📉 MACD", row['MACD'])
                            st.metric("💰 Volumen", f"${row['Volumen']:,.0f}")
                        
                        # TradingView Link
                        st.markdown(f"""
                        🔗 [Auf TradingView ansehen](https://www.tradingview.com/symbols/{row['Ticker']}/) | 
                        📊 [Yahoo Finance](https://finance.yahoo.com/quote/{row['Ticker']}/)
                        """)
                        
                        # Mini-Chart
                        try:
                            with st.spinner("Lade Mini-Chart..."):
                                stock_mini = yf.Ticker(row['Ticker'])
                                df_mini = stock_mini.history(period="1mo", interval="1d")
                                
                                if not df_mini.empty and len(df_mini) >= 5:
                                    fig_mini = go.Figure()
                                    fig_mini.add_trace(go.Candlestick(
                                        x=df_mini.index,
                                        open=df_mini['Open'],
                                        high=df_mini['High'],
                                        low=df_mini['Low'],
                                        close=df_mini['Close'],
                                        name='',
                                        increasing_line_color='#00ff88',
                                        decreasing_line_color='#ff4444',
                                        showlegend=False
                                    ))
                                    
                                    # SMA20 für Mini-Chart
                                    sma_mini = df_mini['Close'].rolling(window=20).mean()
                                    if len(sma_mini.dropna()) > 0:
                                        fig_mini.add_trace(go.Scatter(
                                            x=df_mini.index,
                                            y=sma_mini,
                                            name='SMA20',
                                            line=dict(color='orange', width=1),
                                            showlegend=False
                                        ))
                                    
                                    fig_mini.update_layout(
                                        height=200,
                                        margin=dict(l=0, r=0, t=0, b=0),
                                        xaxis=dict(showticklabels=False),
                                        yaxis=dict(showticklabels=False),
                                        template='plotly_dark',
                                        showlegend=False
                                    )
                                    st.plotly_chart(fig_mini, use_container_width=True)
                        except Exception as e:
                            st.caption("Mini-Chart nicht verfügbar")
                
            else:
                st.warning("⚠️ Keine Aktien erfüllen die aktuellen Filter.")
                st.markdown("""
                ### Schnelle Lösungen:
                1. 👉 Wähle Preset **'📊 Moderat (60+)'** in der Sidebar
                2. 🔄 Klick auf **'Cache leeren & neustarten'**
                3. 📉 Reduziere den Mindest-Score
                4. 📊 Erweitere die RSI-Grenzen
                5. ⏰ Andere Tageszeit probieren (Yahoo Limits)
                """)
    
    else:
        # Ze
