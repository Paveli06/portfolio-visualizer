import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

st.set_page_config(page_title="Portfolio Visualizer", layout="wide")
st.title("📊 Portfolio Visualizer")

# ── Manuální override pro ETF a krypto ──────────────────────────────────────
# Přidej sem své ETF nebo tokeny a nastav jejich alokaci ručně.
# Sektor a region se pak NEbudou stahovat z yfinance.

MANUAL_OVERRIDES = {
    # Příklady ETF:
    "VWCE.DE": {"sector": "ETF – World",      "region": "Global"},
    "CSPX.L":  {"sector": "ETF – S&P 500",    "region": "US"},
    "EUNL.DE": {"sector": "ETF – World",      "region": "Global"},
    "IEMM.L":  {"sector": "ETF – Emerging",   "region": "Emerging Markets"},
    # Krypto:
    "BTC-USD":  {"sector": "Crypto",           "region": "Global"},
    "ETH-USD":  {"sector": "Crypto",           "region": "Global"},
    "SOL-USD":  {"sector": "Crypto",           "region": "Global"},
}

# Mapování zemí → regiony
COUNTRY_TO_REGION = {
    "United States": "US",
    "Canada": "North America",
    "United Kingdom": "Europe",
    "Germany": "Europe",
    "France": "Europe",
    "Netherlands": "Europe",
    "Switzerland": "Europe",
    "Sweden": "Europe",
    "Denmark": "Europe",
    "Norway": "Europe",
    "Finland": "Europe",
    "Italy": "Europe",
    "Spain": "Europe",
    "Belgium": "Europe",
    "Austria": "Europe",
    "Czech Republic": "Europe",
    "Japan": "Asia Pacific",
    "South Korea": "Asia Pacific",
    "Australia": "Asia Pacific",
    "China": "Emerging Markets",
    "India": "Emerging Markets",
    "Brazil": "Emerging Markets",
    "Taiwan": "Emerging Markets",
}

@st.cache_data(show_spinner=False)
def fetch_info(ticker: str):
    if ticker in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[ticker]
    try:
        t = yf.Ticker(ticker)
        info = t.info
        # yfinance občas vrátí prázdný dict – zkus fast_info jako zálohu
        sector = (info.get("sector") 
                  or info.get("category") 
                  or info.get("quoteType") 
                  or "Unknown")
        country = info.get("country", "")
        region = COUNTRY_TO_REGION.get(country, "Other")
        return {"sector": "Unknown", "region": "Other"}

# ── Sidebar – načtení dat ────────────────────────────────────────────────────
with st.sidebar:
    st.header("📁 Načtení portfolia")
    upload_mode = st.radio("Zdroj dat", ["Nahrát CSV / Excel", "Zadat ručně"])

    df_raw = None

    if upload_mode == "Nahrát CSV / Excel":
        st.markdown("""
**Formát souboru:**
| Ticker | Shares | Buy_Price |
|--------|--------|-----------|
| AAPL   | 10     | 150       |
| VWCE.DE| 5      | 90        |
| BTC-USD| 0.1    | 30000     |

*Ticker musí být ve formátu Yahoo Finance.*
""")
        uploaded = st.file_uploader("Nahraj soubor", type=["csv", "xlsx"])
        if uploaded:
            if uploaded.name.endswith(".csv"):
                df_raw = pd.read_csv(uploaded)
            else:
                df_raw = pd.read_excel(uploaded)

    else:
        st.markdown("Zadej pozice (Ticker, Počet kusů, Nákupní cena):")
        default_csv = "Ticker,Shares,Buy_Price\nAAPL,10,150\nMSFT,5,300\nVWCE.DE,8,90\nBTC-USD,0.05,40000"
        raw_text = st.text_area("Data (CSV formát)", value=default_csv, height=180)
        try:
            df_raw = pd.read_csv(StringIO(raw_text))
        except Exception as e:
            st.error(f"Chyba při parsování: {e}")

    st.divider()
    st.header("⚙️ ETF / Krypto override")
    st.markdown("Přidej vlastní ticker a jeho kategorii:")
    custom_ticker  = st.text_input("Ticker (např. VWCE.DE)")
    custom_sector  = st.text_input("Sektor (např. ETF – World)")
    custom_region  = st.text_input("Region (např. Global)")
    if st.button("Přidat override") and custom_ticker:
        MANUAL_OVERRIDES[custom_ticker.upper()] = {
            "sector": custom_sector or "Unknown",
            "region": custom_region or "Other",
        }
        st.success(f"Přidáno: {custom_ticker.upper()}")

# ── Hlavní obsah ─────────────────────────────────────────────────────────────
if df_raw is None:
    st.info("👈 Nahraj soubor nebo zadej data v postranním panelu.")
    st.stop()

required_cols = {"Ticker", "Shares"}
if not required_cols.issubset(df_raw.columns):
    st.error(f"Soubor musí obsahovat sloupce: {required_cols}")
    st.stop()

df_raw["Ticker"] = df_raw["Ticker"].str.strip().str.upper()

# Stažení aktuálních cen
with st.spinner("Stahuji aktuální ceny a informace o tickerech…"):
    tickers = df_raw["Ticker"].tolist()
    prices = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="1d")
            prices[t] = float(hist["Close"].iloc[-1]) if not hist.empty else None
        except Exception:
            prices[t] = None

    df_raw["Current_Price"] = df_raw["Ticker"].map(prices)

    # Pokud chybí Buy_Price, použijeme Current_Price
    if "Buy_Price" not in df_raw.columns:
        df_raw["Buy_Price"] = df_raw["Current_Price"]

    df_raw["Market_Value"] = df_raw["Shares"] * df_raw["Current_Price"]
    df_raw["Cost_Basis"]   = df_raw["Shares"] * df_raw["Buy_Price"]
    df_raw["P&L"]          = df_raw["Market_Value"] - df_raw["Cost_Basis"]
    df_raw["P&L_%"]        = (df_raw["P&L"] / df_raw["Cost_Basis"] * 100).round(2)

    # Metadata
    meta = {t: fetch_info(t) for t in tickers}
    df_raw["Sector"] = df_raw["Ticker"].map(lambda t: meta[t]["sector"])
    df_raw["Region"] = df_raw["Ticker"].map(lambda t: meta[t]["region"])

df = df_raw.dropna(subset=["Market_Value"])
total_value = df["Market_Value"].sum()
total_cost  = df["Cost_Basis"].sum()
total_pnl   = df["P&L"].sum()

# ── KPI ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("💼 Celková hodnota",   f"${total_value:,.0f}")
c2.metric("💵 Vloženo",          f"${total_cost:,.0f}")
c3.metric("📈 P&L",              f"${total_pnl:,.0f}", delta=f"{total_pnl/total_cost*100:.1f}%")
c4.metric("📌 Pozic",            len(df))

st.divider()

# ── Grafy ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["🌍 Regionální expozice", "🏭 Sektorová expozice", "📋 Pozice", "📉 P&L"])

with tab1:
    region_df = df.groupby("Region")["Market_Value"].sum().reset_index()
    region_df["Weight_%"] = (region_df["Market_Value"] / total_value * 100).round(2)
    col1, col2 = st.columns([1.2, 1])
    with col1:
        fig = px.pie(region_df, values="Market_Value", names="Region",
                     title="Regionální expozice (podle hodnoty)",
                     color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.dataframe(
            region_df.sort_values("Market_Value", ascending=False)
                     .rename(columns={"Market_Value": "Hodnota ($)", "Weight_%": "Váha (%)"}),
            use_container_width=True, hide_index=True
        )

with tab2:
    sector_df = df.groupby("Sector")["Market_Value"].sum().reset_index()
    sector_df["Weight_%"] = (sector_df["Market_Value"] / total_value * 100).round(2)
    col1, col2 = st.columns([1.2, 1])
    with col1:
        fig = px.bar(sector_df.sort_values("Market_Value", ascending=True),
                     x="Market_Value", y="Sector", orientation="h",
                     title="Sektorová expozice",
                     color="Market_Value",
                     color_continuous_scale="Blues",
                     labels={"Market_Value": "Hodnota ($)", "Sector": "Sektor"})
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.dataframe(
            sector_df.sort_values("Market_Value", ascending=False)
                     .rename(columns={"Market_Value": "Hodnota ($)", "Weight_%": "Váha (%)"}),
            use_container_width=True, hide_index=True
        )

with tab3:
    display_df = df[["Ticker", "Shares", "Buy_Price", "Current_Price",
                      "Market_Value", "Sector", "Region"]].copy()
    display_df["Váha (%)"] = (display_df["Market_Value"] / total_value * 100).round(2)
    display_df = display_df.sort_values("Market_Value", ascending=False)
    st.dataframe(display_df.rename(columns={
        "Shares": "Kusů", "Buy_Price": "Nák. cena", "Current_Price": "Akt. cena",
        "Market_Value": "Hodnota ($)", "Sector": "Sektor", "Region": "Region"
    }), use_container_width=True, hide_index=True)

with tab4:
    pnl_df = df[["Ticker", "Cost_Basis", "Market_Value", "P&L", "P&L_%"]].copy()
    pnl_df = pnl_df.sort_values("P&L", ascending=False)
    fig = px.bar(pnl_df, x="Ticker", y="P&L",
                 color="P&L", color_continuous_scale=["#ef4444", "#22c55e"],
                 title="P&L podle pozice ($)",
                 labels={"P&L": "Zisk/Ztráta ($)"})
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pnl_df.rename(columns={
        "Cost_Basis": "Vloženo ($)", "Market_Value": "Hodnota ($)",
        "P&L": "P&L ($)", "P&L_%": "P&L (%)"
    }), use_container_width=True, hide_index=True)
