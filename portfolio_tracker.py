import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, timedelta
import requests
from io import BytesIO
from PIL import Image
import base64

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Mon Portefeuille",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = "portfolio_data.json"

# ─────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: #1c1f2e;
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #2a2d3e;
        margin-bottom: 8px;
    }
    .metric-label { color: #8b8fa8; font-size: 13px; margin-bottom: 4px; }
    .metric-value { color: #ffffff; font-size: 24px; font-weight: 600; }
    .metric-delta-pos { color: #00c896; font-size: 13px; }
    .metric-delta-neg { color: #ff4d6d; font-size: 13px; }
    .section-title {
        color: #e0e0e0;
        font-size: 18px;
        font-weight: 600;
        margin: 24px 0 12px 0;
        border-left: 3px solid #6c63ff;
        padding-left: 12px;
    }
    .stDataFrame { border-radius: 10px; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
    .logo-container { display: flex; align-items: center; gap: 8px; }
    .tag-pea {
        background: #1a3a5c; color: #4db8ff;
        border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600;
    }
    .tag-cto {
        background: #2d1a5c; color: #b84dff;
        border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PERSISTENCE (JSON local)
# ─────────────────────────────────────────────
def load_portfolio():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_portfolio(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────
# INIT SESSION STATE
# ─────────────────────────────────────────────
if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

if "history_cache" not in st.session_state:
    st.session_state.history_cache = {}

# ─────────────────────────────────────────────
# LOGO FETCHER
# ─────────────────────────────────────────────
@st.cache_data(ttl=86400)
def get_logo_url(ticker):
    try:
        info = yf.Ticker(ticker).info
        website = info.get("website", "")
        if website:
            domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            return f"https://logo.clearbit.com/{domain}"
    except:
        pass
    return None

# ─────────────────────────────────────────────
# LIVE PRICE FETCHER
# ─────────────────────────────────────────────
@st.cache_data(ttl=300)  # refresh every 5 min
def get_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
            change_pct = (price - prev) / prev * 100
            info = t.info
            currency = info.get("currency", "USD")
            name = info.get("shortName", ticker)
            return {"price": price, "change_pct": change_pct, "currency": currency, "name": name}
    except:
        pass
    return {"price": 0, "change_pct": 0, "currency": "?", "name": ticker}

@st.cache_data(ttl=3600)
def get_history(ticker, period="1y"):
    try:
        hist = yf.Ticker(ticker).history(period=period)
        return hist["Close"]
    except:
        return pd.Series(dtype=float)

# ─────────────────────────────────────────────
# CURRENCY CONVERTER
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_usd_to_eur():
    try:
        rate = yf.Ticker("EURUSD=X").history(period="1d")["Close"].iloc[-1]
        return 1 / float(rate)
    except:
        return 0.92  # fallback

# ─────────────────────────────────────────────
# SIDEBAR — GESTION DU PORTEFEUILLE
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ➕ Ajouter une action")

    col1, col2 = st.columns(2)
    with col1:
        new_ticker = st.text_input("Ticker", placeholder="Ex: MSFT").upper().strip()
    with col2:
        new_envelope = st.selectbox("Enveloppe", ["PEA", "CTO"])

    col3, col4 = st.columns(2)
    with col3:
        new_qty = st.number_input("Quantité", min_value=0.001, step=1.0, value=1.0)
    with col4:
        new_buy_price = st.number_input("Prix d'achat (€)", min_value=0.01, step=0.01, value=100.0)

    new_currency = st.selectbox("Devise d'achat", ["EUR", "USD"])

    if st.button("✅ Ajouter", use_container_width=True, type="primary"):
        if new_ticker:
            # Check if ticker already exists in same envelope
            exists = any(
                p["ticker"] == new_ticker and p["envelope"] == new_envelope
                for p in st.session_state.portfolio
            )
            if exists:
                st.warning(f"{new_ticker} déjà présent dans le {new_envelope}. Modifiez-le dans le tableau.")
            else:
                st.session_state.portfolio.append({
                    "ticker": new_ticker,
                    "envelope": new_envelope,
                    "quantity": new_qty,
                    "buy_price_eur": new_buy_price if new_currency == "EUR" else new_buy_price * get_usd_to_eur(),
                    "buy_currency": new_currency,
                    "added_date": datetime.now().strftime("%Y-%m-%d"),
                })
                save_portfolio(st.session_state.portfolio)
                st.cache_data.clear()
                st.success(f"✅ {new_ticker} ajouté !")
                st.rerun()
        else:
            st.error("Entrez un ticker valide.")

    st.markdown("---")
    st.markdown("## 🗑️ Supprimer une action")

    if st.session_state.portfolio:
        options = [f"{p['ticker']} ({p['envelope']})" for p in st.session_state.portfolio]
        to_delete = st.selectbox("Sélectionner", options)
        if st.button("Supprimer", use_container_width=True, type="secondary"):
            idx = options.index(to_delete)
            removed = st.session_state.portfolio.pop(idx)
            save_portfolio(st.session_state.portfolio)
            st.cache_data.clear()
            st.success(f"🗑️ {removed['ticker']} supprimé.")
            st.rerun()
    else:
        st.info("Aucune action dans le portefeuille.")

    st.markdown("---")
    st.markdown("## ⚙️ Options")
    history_period = st.selectbox("Période historique", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    if st.button("🔄 Rafraîchir les prix", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────
# MAIN — HEADER
# ─────────────────────────────────────────────
st.markdown("# 📈 Mon Portefeuille Boursier")
st.markdown(f"*Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y à %H:%M')}*")

if not st.session_state.portfolio:
    st.info("👈 Commencez par ajouter vos actions dans le panneau de gauche.")
    st.stop()

# ─────────────────────────────────────────────
# FETCH ALL LIVE DATA
# ─────────────────────────────────────────────
usd_to_eur = get_usd_to_eur()

rows = []
for pos in st.session_state.portfolio:
    ticker = pos["ticker"]
    live = get_live_price(ticker)
    price = live["price"]
    currency = live["currency"]

    # Convert to EUR
    price_eur = price * usd_to_eur if currency == "USD" else price

    qty = pos["quantity"]
    buy_price = pos["buy_price_eur"]
    current_value = price_eur * qty
    invested = buy_price * qty
    pnl = current_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    rows.append({
        "ticker": ticker,
        "name": live["name"],
        "envelope": pos["envelope"],
        "qty": qty,
        "buy_price": buy_price,
        "price_eur": price_eur,
        "currency": currency,
        "change_pct": live["change_pct"],
        "current_value": current_value,
        "invested": invested,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    })

df = pd.DataFrame(rows)

total_value = df["current_value"].sum()
total_invested = df["invested"].sum()
total_pnl = total_value - total_invested
total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

pea_value = df[df["envelope"] == "PEA"]["current_value"].sum()
cto_value = df[df["envelope"] == "CTO"]["current_value"].sum()

# ─────────────────────────────────────────────
# KPI CARDS
# ─────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

def render_card(col, label, value, delta=None, delta_pct=None):
    with col:
        color = "#00c896" if delta and delta >= 0 else "#ff4d6d"
        delta_str = ""
        if delta is not None:
            sign = "+" if delta >= 0 else ""
            delta_str = f'<div class="metric-delta-{"pos" if delta>=0 else "neg"}">{sign}{delta:,.2f} € ({sign}{delta_pct:.2f}%)</div>'
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_str}
        </div>
        """, unsafe_allow_html=True)

render_card(c1, "Valeur totale", f"{total_value:,.2f} €", total_pnl, total_pnl_pct)
render_card(c2, "Investi total", f"{total_invested:,.2f} €")
render_card(c3, "Plus/Moins-value", f"{total_pnl:+,.2f} €")
render_card(c4, "PEA", f"{pea_value:,.2f} €")
render_card(c5, "CTO", f"{cto_value:,.2f} €")

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# TABLEAU DES POSITIONS
# ─────────────────────────────────────────────
st.markdown('<div class="section-title">📋 Mes Positions</div>', unsafe_allow_html=True)

display_df = df.copy()
display_df["Variation jour"] = display_df["change_pct"].apply(lambda x: f"{'🟢' if x>=0 else '🔴'} {x:+.2f}%")
display_df["P&L"] = display_df.apply(
    lambda r: f"{'▲' if r['pnl']>=0 else '▼'} {r['pnl']:+,.2f} € ({r['pnl_pct']:+.1f}%)", axis=1
)
display_df["Enveloppe"] = display_df["envelope"].apply(lambda x: f"🔵 {x}" if x == "PEA" else f"🟣 {x}")

table = display_df[[
    "ticker", "name", "Enveloppe", "qty", "buy_price", "price_eur",
    "Variation jour", "current_value", "P&L"
]].rename(columns={
    "ticker": "Ticker",
    "name": "Nom",
    "qty": "Quantité",
    "buy_price": "Prix achat (€)",
    "price_eur": "Prix actuel (€)",
    "current_value": "Valeur (€)",
})

# Format numbers
table["Prix achat (€)"] = table["Prix achat (€)"].map("{:.2f}".format)
table["Prix actuel (€)"] = table["Prix actuel (€)"].map("{:.2f}".format)
table["Valeur (€)"] = table["Valeur (€)"].map("{:,.2f}".format)
table["Quantité"] = table["Quantité"].map("{:.3g}".format)

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    height=min(400, 60 + len(table) * 45),
)

# ─────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────
st.markdown('<div class="section-title">📊 Répartition du Portefeuille</div>', unsafe_allow_html=True)

col_pie1, col_pie2 = st.columns(2)

# PIE 1 — Par action
with col_pie1:
    fig_pie = go.Figure(go.Pie(
        labels=df["ticker"],
        values=df["current_value"].round(2),
        hole=0.45,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>Valeur: %{value:,.2f} €<br>Part: %{percent}<extra></extra>",
        marker=dict(
            colors=px.colors.qualitative.Bold,
            line=dict(color="#0f1117", width=2)
        ),
    ))
    fig_pie.update_layout(
        title="Répartition par action",
        paper_bgcolor="#0f1117",
        plot_bgcolor="#0f1117",
        font=dict(color="#e0e0e0"),
        legend=dict(bgcolor="#1c1f2e", bordercolor="#2a2d3e"),
        margin=dict(t=50, b=10, l=10, r=10),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# PIE 2 — Par enveloppe
with col_pie2:
    env_df = df.groupby("envelope")["current_value"].sum().reset_index()
    fig_env = go.Figure(go.Pie(
        labels=env_df["envelope"],
        values=env_df["current_value"].round(2),
        hole=0.45,
        textinfo="label+percent+value",
        hovertemplate="<b>%{label}</b><br>%{value:,.2f} €<extra></extra>",
        marker=dict(
            colors=["#4db8ff", "#b84dff"],
            line=dict(color="#0f1117", width=2)
        ),
    ))
    fig_env.update_layout(
        title="PEA vs CTO",
        paper_bgcolor="#0f1117",
        plot_bgcolor="#0f1117",
        font=dict(color="#e0e0e0"),
        legend=dict(bgcolor="#1c1f2e", bordercolor="#2a2d3e"),
        margin=dict(t=50, b=10, l=10, r=10),
    )
    st.plotly_chart(fig_env, use_container_width=True)

# ─────────────────────────────────────────────
# EVOLUTION HISTORIQUE DU PORTEFEUILLE
# ─────────────────────────────────────────────
st.markdown('<div class="section-title">📅 Évolution du Portefeuille</div>', unsafe_allow_html=True)

all_histories = {}
for pos in st.session_state.portfolio:
    ticker = pos["ticker"]
    hist = get_history(ticker, history_period)
    if not hist.empty:
        live = get_live_price(ticker)
        currency = live["currency"]
        multiplier = usd_to_eur if currency == "USD" else 1.0
        all_histories[ticker] = hist * pos["quantity"] * multiplier

if all_histories:
    port_df = pd.DataFrame(all_histories)
    port_df = port_df.fillna(method="ffill").dropna()
    port_df["Total"] = port_df.sum(axis=1)

    fig_evo = go.Figure()

    # Shaded area for total
    fig_evo.add_trace(go.Scatter(
        x=port_df.index,
        y=port_df["Total"].round(2),
        mode="lines",
        name="Portefeuille total",
        line=dict(color="#6c63ff", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(108,99,255,0.12)",
        hovertemplate="%{x|%d/%m/%Y}<br><b>%{y:,.2f} €</b><extra>Total</extra>",
    ))

    # Individual lines (faded)
    colors = px.colors.qualitative.Pastel
    for i, (ticker, series) in enumerate(all_histories.items()):
        series = series.reindex(port_df.index).ffill()
        fig_evo.add_trace(go.Scatter(
            x=series.index,
            y=series.round(2),
            mode="lines",
            name=ticker,
            line=dict(color=colors[i % len(colors)], width=1, dash="dot"),
            opacity=0.6,
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.2f} €<extra>" + ticker + "</extra>",
        ))

    # Ligne investissement initial
    fig_evo.add_hline(
        y=total_invested,
        line_dash="dash",
        line_color="#ff8c42",
        annotation_text=f"Investi: {total_invested:,.0f} €",
        annotation_font_color="#ff8c42",
    )

    fig_evo.update_layout(
        paper_bgcolor="#0f1117",
        plot_bgcolor="#1c1f2e",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2a2d3e", showgrid=True),
        yaxis=dict(gridcolor="#2a2d3e", showgrid=True, ticksuffix=" €"),
        legend=dict(bgcolor="#1c1f2e", bordercolor="#2a2d3e", orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        margin=dict(t=60, b=40, l=60, r=20),
        height=420,
    )
    st.plotly_chart(fig_evo, use_container_width=True)

# ─────────────────────────────────────────────
# PERFORMANCE PAR ACTION (bar chart)
# ─────────────────────────────────────────────
st.markdown('<div class="section-title">🏆 Performance par Action</div>', unsafe_allow_html=True)

df_sorted = df.sort_values("pnl_pct", ascending=True)
colors_bar = ["#00c896" if v >= 0 else "#ff4d6d" for v in df_sorted["pnl_pct"]]

fig_bar = go.Figure(go.Bar(
    x=df_sorted["pnl_pct"].round(2),
    y=df_sorted["ticker"],
    orientation="h",
    marker_color=colors_bar,
    text=[f"{v:+.1f}%" for v in df_sorted["pnl_pct"]],
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>P&L: %{x:.2f}%<extra></extra>",
))

fig_bar.update_layout(
    paper_bgcolor="#0f1117",
    plot_bgcolor="#1c1f2e",
    font=dict(color="#e0e0e0"),
    xaxis=dict(gridcolor="#2a2d3e", ticksuffix="%"),
    yaxis=dict(gridcolor="#2a2d3e"),
    margin=dict(t=20, b=40, l=100, r=80),
    height=max(300, len(df) * 45),
    showlegend=False,
)
fig_bar.add_vline(x=0, line_color="#555", line_width=1)
st.plotly_chart(fig_bar, use_container_width=True)

# ─────────────────────────────────────────────
# LOGOS
# ─────────────────────────────────────────────
st.markdown('<div class="section-title">🏢 Logos des Entreprises</div>', unsafe_allow_html=True)

logo_cols = st.columns(min(len(df), 6))
for i, row in enumerate(df.itertuples()):
    with logo_cols[i % min(len(df), 6)]:
        logo_url = get_logo_url(row.ticker)
        tag = f'<span class="tag-pea">PEA</span>' if row.envelope == "PEA" else f'<span class="tag-cto">CTO</span>'
        if logo_url:
            st.markdown(f"""
            <div style="text-align:center; padding:12px; background:#1c1f2e; border-radius:10px; margin-bottom:8px;">
                <img src="{logo_url}" style="height:40px; max-width:90px; object-fit:contain;" onerror="this.style.display='none'"><br>
                <span style="color:#e0e0e0; font-weight:600; font-size:13px;">{row.ticker}</span><br>
                {tag}<br>
                <span style="color:{'#00c896' if row.pnl_pct >= 0 else '#ff4d6d'}; font-size:12px;">{row.pnl_pct:+.1f}%</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="text-align:center; padding:12px; background:#1c1f2e; border-radius:10px; margin-bottom:8px;">
                <div style="font-size:28px;">📊</div>
                <span style="color:#e0e0e0; font-weight:600; font-size:13px;">{row.ticker}</span><br>
                {tag}<br>
                <span style="color:{'#00c896' if row.pnl_pct >= 0 else '#ff4d6d'}; font-size:12px;">{row.pnl_pct:+.1f}%</span>
            </div>
            """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#555; font-size:12px;'>"
    "Données fournies par Yahoo Finance via yfinance · Mise à jour automatique toutes les 5 min · "
    "Les prix sont indicatifs et ne constituent pas un conseil en investissement."
    "</div>",
    unsafe_allow_html=True
)
