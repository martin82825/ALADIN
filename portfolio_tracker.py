import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import time
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Tracker",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = "portfolio_data.json"
AUTO_REFRESH_INTERVAL = 10  # secondes

# ─────────────────────────────────────────────────────────────────────────────
# DESIGN SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    "bg":          "#F7F8FA",
    "surface":     "#FFFFFF",
    "border":      "#E4E7ED",
    "text_primary":"#1A1D23",
    "text_muted":  "#6B7280",
    "accent":      "#2563EB",
    "positive":    "#059669",
    "negative":    "#DC2626",
    "amber":       "#D97706",
    "pea":         "#2563EB",
    "cto":         "#7C3AED",
    "etf_tag":     "#0891B2",
}

CHART_COLORS = [
    "#2563EB","#7C3AED","#059669","#D97706","#DC2626",
    "#0891B2","#BE185D","#65A30D","#EA580C","#6366F1",
]

CHART_LAYOUT_BASE = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#F7F8FA",
    font=dict(family="Inter, Segoe UI, sans-serif", color="#1A1D23", size=12),
    margin=dict(t=50, b=40, l=60, r=20),
    legend=dict(bgcolor="#F7F8FA", bordercolor="#E4E7ED", borderwidth=1),
)

st.markdown(f"""
<style>
  .main .block-container {{ padding-top: 1.5rem; max-width: 1400px; }}
  html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}

  .section-title {{
    font-size: 12px; font-weight: 700; color: {COLORS['text_muted']};
    text-transform: uppercase; letter-spacing: 0.08em;
    margin: 1.8rem 0 0.75rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid {COLORS['border']};
  }}
  .kpi-card {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px; padding: 16px 20px;
  }}
  .kpi-label {{
    font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;
  }}
  .kpi-value {{ font-size: 20px; font-weight: 700; color: {COLORS['text_primary']}; line-height: 1.2; }}
  .kpi-delta-pos {{ font-size: 12px; font-weight: 500; color: {COLORS['positive']}; margin-top: 4px; }}
  .kpi-delta-neg {{ font-size: 12px; font-weight: 500; color: {COLORS['negative']}; margin-top: 4px; }}

  .tag {{ display:inline-block; font-size:10px; font-weight:700;
          letter-spacing:.06em; padding:2px 7px; border-radius:4px; text-transform:uppercase; }}
  .tag-pea {{ background:#DBEAFE; color:#1D4ED8; }}
  .tag-cto {{ background:#EDE9FE; color:#6D28D9; }}
  .tag-etf {{ background:#CFFAFE; color:#0E7490; }}

  .logo-card {{
    background:{COLORS['surface']}; border:1px solid {COLORS['border']};
    border-radius:8px; padding:14px; text-align:center;
  }}
  .logo-ticker {{ font-size:13px; font-weight:700; color:{COLORS['text_primary']}; margin-top:8px; }}

  .app-title {{ font-size:22px; font-weight:700; color:{COLORS['text_primary']}; }}
  .app-subtitle {{ font-size:12px; color:{COLORS['text_muted']}; margin-top:2px; }}

  .status-dot {{ display:inline-block; width:6px; height:6px;
                 background:{COLORS['positive']}; border-radius:50%; margin-right:5px; }}

  #MainMenu, footer {{ visibility:hidden; }}
  [data-testid="stSidebar"] {{ background:{COLORS['surface']}; border-right:1px solid {COLORS['border']}; }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────
def load_portfolio():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_portfolio(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCHERS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def get_live_price(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", auto_adjust=True)
        if hist.empty:
            return {"price": 0, "change_pct": 0, "currency": "?", "name": ticker, "ok": False}
        price = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        change_pct = (price - prev) / prev * 100 if prev else 0
        currency = "USD"
        name = ticker
        try:
            info = t.info
            currency = info.get("currency", "USD")
            name = info.get("shortName", ticker)
        except Exception:
            pass
        return {"price": price, "change_pct": change_pct, "currency": currency, "name": name, "ok": True}
    except Exception as e:
        return {"price": 0, "change_pct": 0, "currency": "?", "name": ticker, "ok": False}

@st.cache_data(ttl=3600)
def get_history(ticker: str, period: str = "1y") -> pd.Series:
    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if hist.empty:
            return pd.Series(dtype=float, name=ticker)
        return hist["Close"].rename(ticker)
    except Exception:
        return pd.Series(dtype=float, name=ticker)

@st.cache_data(ttl=3600)
def get_usd_to_eur() -> float:
    try:
        rate = yf.Ticker("EURUSD=X").history(period="2d")["Close"].iloc[-1]
        return 1.0 / float(rate)
    except Exception:
        return 0.92

@st.cache_data(ttl=86400)
def get_logo_url(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        website = info.get("website", "")
        if website:
            domain = (website
                      .replace("https://", "").replace("http://", "")
                      .replace("www.", "").split("/")[0])
            return f"https://logo.clearbit.com/{domain}"
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────────────────────────────────────
# AUTO-REFRESH
# ─────────────────────────────────────────────────────────────────────────────
now = time.time()
if now - st.session_state.last_refresh >= AUTO_REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    st.session_state.refresh_count += 1
    get_live_price.clear()
    get_usd_to_eur.clear()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="app-title">Portfolio Tracker</div>'
        f'<div class="app-subtitle">'
        f'<span class="status-dot"></span>Rafraîchissement toutes les {AUTO_REFRESH_INTERVAL}s'
        f'</div>',
        unsafe_allow_html=True
    )
    st.markdown("---")

    # ADD
    st.markdown("**Ajouter une position**")
    c1, c2 = st.columns(2)
    new_ticker   = c1.text_input("Ticker", placeholder="MC.PA", label_visibility="visible").upper().strip()
    new_envelope = c2.selectbox("Enveloppe", ["PEA", "CTO"])
    c3, c4 = st.columns(2)
    new_qty       = c3.number_input("Quantité", min_value=0.001, step=1.0, value=1.0, format="%.3f")
    new_buy_price = c4.number_input("Prix achat", min_value=0.001, step=0.01, value=100.0, format="%.2f")
    new_currency  = st.selectbox("Devise achat", ["EUR", "USD", "GBP"])
    new_is_etf    = st.checkbox("ETF", value=False, help="Cochez si c'est un ETF/tracker")

    if st.button("Ajouter la position", use_container_width=True, type="primary"):
        if new_ticker:
            exists = any(
                p["ticker"] == new_ticker and p["envelope"] == new_envelope
                for p in st.session_state.portfolio
            )
            if exists:
                st.warning(f"{new_ticker} déjà présent dans {new_envelope}.")
            else:
                usd2eur = get_usd_to_eur()
                conv = {"EUR": 1.0, "USD": usd2eur, "GBP": usd2eur * 1.17}
                st.session_state.portfolio.append({
                    "ticker":        new_ticker,
                    "envelope":      new_envelope,
                    "quantity":      new_qty,
                    "buy_price_eur": round(new_buy_price * conv.get(new_currency, 1.0), 4),
                    "buy_currency":  new_currency,
                    "is_etf":        new_is_etf,
                    "added_date":    datetime.now().strftime("%Y-%m-%d"),
                })
                save_portfolio(st.session_state.portfolio)
                st.cache_data.clear()
                st.success(f"{new_ticker} ajouté.")
                st.rerun()
        else:
            st.error("Ticker requis.")

    st.markdown("---")
    st.markdown("**Supprimer une position**")
    if st.session_state.portfolio:
        options = [f"{p['ticker']} ({p['envelope']})" for p in st.session_state.portfolio]
        to_delete = st.selectbox("Position", options, label_visibility="collapsed")
        if st.button("Supprimer", use_container_width=True):
            idx = options.index(to_delete)
            removed = st.session_state.portfolio.pop(idx)
            save_portfolio(st.session_state.portfolio)
            st.cache_data.clear()
            st.success(f"{removed['ticker']} supprimé.")
            st.rerun()
    else:
        st.caption("Portefeuille vide.")

    st.markdown("---")
    st.markdown("**Options**")
    history_period = st.selectbox("Période historique", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    show_etf_section = st.checkbox("Section ETF", value=True)
    if st.button("Forcer le rafraîchissement", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Refresh #{st.session_state.refresh_count} — {datetime.now().strftime('%H:%M:%S')}")

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="app-title">Portfolio Tracker</div>'
    f'<div class="app-subtitle">Données Yahoo Finance — {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</div>',
    unsafe_allow_html=True
)

if not st.session_state.portfolio:
    st.info("Ajoutez vos premières positions dans le panneau de gauche.")
    time.sleep(AUTO_REFRESH_INTERVAL)
    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# BUILD DATAFRAME
# ─────────────────────────────────────────────────────────────────────────────
usd_to_eur = get_usd_to_eur()

rows = []
for pos in st.session_state.portfolio:
    ticker = pos["ticker"]
    live   = get_live_price(ticker)
    price  = live["price"]
    curr   = live["currency"]
    if curr in ("USD", "GBp"):
        price_eur = price * usd_to_eur
    else:
        price_eur = price

    qty       = pos["quantity"]
    buy_price = pos["buy_price_eur"]
    cur_val   = price_eur * qty
    invested  = buy_price * qty
    pnl       = cur_val - invested
    pnl_pct   = pnl / invested * 100 if invested > 0 else 0

    rows.append({
        "ticker":        ticker,
        "name":          live["name"],
        "envelope":      pos["envelope"],
        "is_etf":        pos.get("is_etf", False),
        "qty":           qty,
        "buy_price":     buy_price,
        "price_eur":     price_eur,
        "currency":      curr,
        "change_pct":    live["change_pct"],
        "current_value": cur_val,
        "invested":      invested,
        "pnl":           pnl,
        "pnl_pct":       pnl_pct,
        "data_ok":       live["ok"],
    })

df = pd.DataFrame(rows)

if df.empty:
    st.warning("Aucune donnée disponible.")
    time.sleep(AUTO_REFRESH_INTERVAL)
    st.rerun()

total_value    = df["current_value"].sum()
total_invested = df["invested"].sum()
total_pnl      = total_value - total_invested
total_pnl_pct  = total_pnl / total_invested * 100 if total_invested > 0 else 0
pea_value      = df[df["envelope"] == "PEA"]["current_value"].sum()
cto_value      = df[df["envelope"] == "CTO"]["current_value"].sum()
etf_value      = df[df["is_etf"]]["current_value"].sum()

# ─────────────────────────────────────────────────────────────────────────────
# KPI CARDS
# ─────────────────────────────────────────────────────────────────────────────
def kpi(col, label, value_str, delta=None, delta_pct=None):
    with col:
        delta_html = ""
        if delta is not None:
            sign = "+" if delta >= 0 else ""
            cls  = "kpi-delta-pos" if delta >= 0 else "kpi-delta-neg"
            delta_html = f'<div class="{cls}">{sign}{delta:,.2f} € &nbsp;({sign}{delta_pct:.2f}%)</div>'
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value_str}</div>'
            f'{delta_html}</div>',
            unsafe_allow_html=True
        )

st.markdown("<div style='margin-top:1.2rem'></div>", unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)
kpi(c1, "Valeur totale",   f"{total_value:,.2f} €",    total_pnl, total_pnl_pct)
kpi(c2, "Capital investi", f"{total_invested:,.2f} €")
kpi(c3, "Plus/Moins-value",f"{total_pnl:+,.2f} €")
kpi(c4, "PEA",             f"{pea_value:,.2f} €")
kpi(c5, "CTO",             f"{cto_value:,.2f} €")
kpi(c6, "Part ETF",        f"{etf_value:,.2f} €")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_labels = ["Positions", "Répartition", "Evolution", "Logos"]
if show_etf_section:
    tab_labels.append("ETF")

tabs = st.tabs(tab_labels)
t = {name: obj for name, obj in zip(tab_labels, tabs)}

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — POSITIONS
# ─────────────────────────────────────────────────────────────────────────────
with t["Positions"]:
    st.markdown('<div class="section-title">Détail des positions</div>', unsafe_allow_html=True)

    tbl = df.copy()
    tbl["Type"]      = tbl["is_etf"].apply(lambda x: "ETF" if x else "Action")
    tbl["Variation"] = tbl["change_pct"].apply(lambda v: f"{'+'if v>=0 else ''}{v:.2f}%")
    tbl["P&L"]       = tbl.apply(
        lambda r: f"{'+'if r['pnl']>=0 else ''}{r['pnl']:,.2f} € ({'+'if r['pnl_pct']>=0 else ''}{r['pnl_pct']:.1f}%)",
        axis=1
    )
    tbl["Prix achat (€)"]  = tbl["buy_price"].map("{:.2f}".format)
    tbl["Prix actuel (€)"] = tbl["price_eur"].map("{:.2f}".format)
    tbl["Valeur (€)"]      = tbl["current_value"].map("{:,.2f}".format)
    tbl["Quantite"]        = tbl["qty"].map("{:.4g}".format)

    display = tbl[["ticker","name","envelope","Type","Quantite",
                   "Prix achat (€)","Prix actuel (€)","Variation","Valeur (€)","P&L"]].rename(
        columns={"ticker":"Ticker","name":"Nom","envelope":"Enveloppe","Quantite":"Quantité"}
    )

    def color_col(val):
        if isinstance(val, str) and val.startswith("+"):
            return "color: #059669; font-weight:500"
        elif isinstance(val, str) and val.startswith("-"):
            return "color: #DC2626; font-weight:500"
        return ""

    st.dataframe(
        display.style.applymap(color_col, subset=["P&L","Variation"]),
        use_container_width=True,
        hide_index=True,
        height=min(520, 80 + len(display) * 45),
    )

    errors = df[~df["data_ok"]]
    if not errors.empty:
        st.warning(f"Données indisponibles pour : {', '.join(errors['ticker'].tolist())}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — REPARTITION
# ─────────────────────────────────────────────────────────────────────────────
with t["Répartition"]:
    st.markdown('<div class="section-title">Répartition du portefeuille</div>', unsafe_allow_html=True)

    col_l, col_r = st.columns(2)

    with col_l:
        fig1 = go.Figure(go.Pie(
            labels=df["ticker"], values=df["current_value"].round(2),
            hole=0.50, textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:,.2f} €<br>%{percent}<extra></extra>",
            marker=dict(colors=CHART_COLORS, line=dict(color="#FFFFFF", width=2)),
        ))
        fig1.update_layout(
            title=dict(text="Par action", font=dict(size=12, color=COLORS["text_muted"]), x=0.02),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"]),
            margin=dict(t=45,b=20,l=20,r=20),
            legend=dict(bgcolor="#F7F8FA", bordercolor=COLORS["border"]),
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_r:
        env_g = df.groupby("envelope")["current_value"].sum().reset_index()
        fig2 = go.Figure(go.Pie(
            labels=env_g["envelope"], values=env_g["current_value"].round(2),
            hole=0.50, textinfo="label+percent+value",
            hovertemplate="<b>%{label}</b><br>%{value:,.2f} €<extra></extra>",
            marker=dict(colors=[COLORS["pea"], COLORS["cto"]], line=dict(color="#FFFFFF", width=2)),
        ))
        fig2.update_layout(
            title=dict(text="PEA vs CTO", font=dict(size=12, color=COLORS["text_muted"]), x=0.02),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"]),
            margin=dict(t=45,b=20,l=20,r=20),
            legend=dict(bgcolor="#F7F8FA", bordercolor=COLORS["border"]),
        )
        st.plotly_chart(fig2, use_container_width=True)

    col_l2, col_r2 = st.columns(2)

    with col_l2:
        type_g = df.copy()
        type_g["Type"] = type_g["is_etf"].apply(lambda x: "ETF" if x else "Action")
        type_grp = type_g.groupby("Type")["current_value"].sum().reset_index()
        fig3 = go.Figure(go.Pie(
            labels=type_grp["Type"], values=type_grp["current_value"].round(2),
            hole=0.50, textinfo="label+percent+value",
            marker=dict(colors=[COLORS["accent"], COLORS["etf_tag"]], line=dict(color="#FFFFFF", width=2)),
        ))
        fig3.update_layout(
            title=dict(text="Actions vs ETF", font=dict(size=12, color=COLORS["text_muted"]), x=0.02),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"]),
            margin=dict(t=45,b=20,l=20,r=20),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_r2:
        fig4 = px.treemap(
            df, path=["envelope","ticker"], values="current_value",
            color="pnl_pct",
            color_continuous_scale=["#DC2626","#F9FAFB","#059669"],
            color_continuous_midpoint=0,
        )
        fig4.update_layout(
            title=dict(text="Treemap par valeur et performance", font=dict(size=12, color=COLORS["text_muted"]), x=0.02),
            paper_bgcolor="#FFFFFF", margin=dict(t=45,b=10,l=10,r=10),
            coloraxis_colorbar=dict(title="P&L %"),
        )
        st.plotly_chart(fig4, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — EVOLUTION
# ─────────────────────────────────────────────────────────────────────────────
with t["Evolution"]:
    st.markdown('<div class="section-title">Evolution du portefeuille</div>', unsafe_allow_html=True)

    series_list = []
    for pos in st.session_state.portfolio:
        ticker = pos["ticker"]
        hist   = get_history(ticker, history_period)
        if hist.empty:
            continue
        live = get_live_price(ticker)
        mult = usd_to_eur if live["currency"] in ("USD", "GBp") else 1.0
        series_list.append((hist * pos["quantity"] * mult).rename(ticker))

    if not series_list:
        st.info("Aucune donnée historique disponible.")
    else:
        # Concaténer et propager les valeurs manquantes
        port_df = pd.concat(series_list, axis=1)
        port_df = port_df.ffill()          # pandas moderne, pas de FutureWarning
        port_df = port_df.fillna(0)
        port_df["__total__"] = port_df.drop(columns="__total__", errors="ignore").sum(axis=1)

        fig_evo = go.Figure()

        # Lignes individuelles
        tickers_cols = [c for c in port_df.columns if c != "__total__"]
        for i, ticker in enumerate(tickers_cols):
            fig_evo.add_trace(go.Scatter(
                x=port_df.index, y=port_df[ticker].round(2),
                mode="lines", name=ticker,
                line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=1.2, dash="dot"),
                opacity=0.55,
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.2f} €<extra>" + ticker + "</extra>",
            ))

        # Courbe totale
        fig_evo.add_trace(go.Scatter(
            x=port_df.index, y=port_df["__total__"].round(2),
            mode="lines", name="Total",
            line=dict(color=COLORS["accent"], width=2.5),
            fill="tozeroy", fillcolor="rgba(37,99,235,0.07)",
            hovertemplate="%{x|%d/%m/%Y} — <b>%{y:,.2f} €</b><extra>Total</extra>",
        ))

        # Ligne capital investi
        fig_evo.add_hline(
            y=total_invested,
            line_dash="dash", line_color=COLORS["amber"], line_width=1.5,
            annotation_text=f"Investi : {total_invested:,.0f} €",
            annotation_font_color=COLORS["amber"], annotation_font_size=11,
        )

        fig_evo.update_layout(
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
            font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"], size=12),
            xaxis=dict(gridcolor=COLORS["border"], showgrid=True, zeroline=False, tickformat="%b %Y"),
            yaxis=dict(gridcolor=COLORS["border"], showgrid=True, zeroline=False, ticksuffix=" €"),
            legend=dict(bgcolor="#F7F8FA", bordercolor=COLORS["border"], borderwidth=1,
                        orientation="h", yanchor="bottom", y=1.02),
            hovermode="x unified",
            margin=dict(t=60,b=40,l=70,r=20),
            height=450,
        )
        st.plotly_chart(fig_evo, use_container_width=True)

        # Performance normalisée base 100
        st.markdown('<div class="section-title">Performance relative (base 100)</div>', unsafe_allow_html=True)
        fig_norm = go.Figure()
        for i, ticker in enumerate(tickers_cols):
            s = port_df[ticker]
            base = s[s > 0].iloc[0] if (s > 0).any() else 1.0
            norm = (s / base * 100).round(2)
            fig_norm.add_trace(go.Scatter(
                x=port_df.index, y=norm, mode="lines", name=ticker,
                line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=1.8),
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}<extra>" + ticker + "</extra>",
            ))
        fig_norm.add_hline(y=100, line_dash="dash", line_color="#9CA3AF", line_width=1)
        fig_norm.update_layout(
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
            font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"], size=12),
            xaxis=dict(gridcolor=COLORS["border"], tickformat="%b %Y"),
            yaxis=dict(gridcolor=COLORS["border"], title="Base 100"),
            legend=dict(bgcolor="#F7F8FA", bordercolor=COLORS["border"], borderwidth=1,
                        orientation="h", yanchor="bottom", y=1.02),
            hovermode="x unified",
            margin=dict(t=60,b=40,l=60,r=20),
            height=360,
        )
        st.plotly_chart(fig_norm, use_container_width=True)

    # Barre P&L par position
    st.markdown('<div class="section-title">Performance par position</div>', unsafe_allow_html=True)
    df_s = df.sort_values("pnl_pct", ascending=True)
    fig_bar = go.Figure(go.Bar(
        x=df_s["pnl_pct"].round(2), y=df_s["ticker"], orientation="h",
        marker_color=["#059669" if v >= 0 else "#DC2626" for v in df_s["pnl_pct"]],
        text=[f"{v:+.1f}%" for v in df_s["pnl_pct"]],
        textposition="outside", textfont=dict(size=11),
        hovertemplate="<b>%{y}</b><br>P&L : %{x:.2f}%<extra></extra>",
    ))
    fig_bar.add_vline(x=0, line_color="#9CA3AF", line_width=1)
    fig_bar.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
        font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"], size=12),
        xaxis=dict(gridcolor=COLORS["border"], ticksuffix="%"),
        yaxis=dict(gridcolor="#FFFFFF"),
        margin=dict(t=10,b=40,l=80,r=80),
        height=max(250, len(df) * 44),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — LOGOS
# ─────────────────────────────────────────────────────────────────────────────
with t["Logos"]:
    st.markdown('<div class="section-title">Entreprises en portefeuille</div>', unsafe_allow_html=True)

    n_cols = min(len(df), 5)
    cols   = st.columns(n_cols)

    for i, row in enumerate(df.itertuples()):
        with cols[i % n_cols]:
            logo_url = get_logo_url(row.ticker)
            tag_env  = "tag-pea" if row.envelope == "PEA" else "tag-cto"
            perf_cls = "kpi-delta-pos" if row.pnl_pct >= 0 else "kpi-delta-neg"
            sign     = "+" if row.pnl_pct >= 0 else ""
            etf_badge = '<br><span class="tag tag-etf">ETF</span>' if row.is_etf else ""

            if logo_url:
                img_html = (
                    f'<img src="{logo_url}" '
                    f'style="height:34px;max-width:80px;object-fit:contain;" '
                    f'onerror="this.parentNode.querySelector(\'.fb\').style.display=\'block\';this.style.display=\'none\'">'
                    f'<div class="fb" style="display:none;font-size:22px;color:#9CA3AF;">&#9673;</div>'
                )
            else:
                img_html = '<div style="font-size:22px;color:#9CA3AF;">&#9673;</div>'

            st.markdown(
                f'<div class="logo-card">'
                f'{img_html}'
                f'<div class="logo-ticker">{row.ticker}</div>'
                f'<div style="font-size:10px;color:{COLORS["text_muted"]};margin:3px 0;">'
                f'{row.name[:22]}</div>'
                f'<span class="tag {tag_env}">{row.envelope}</span>'
                f'{etf_badge}'
                f'<div class="{perf_cls}" style="margin-top:6px;">{sign}{row.pnl_pct:.1f}%</div>'
                f'<div style="font-size:11px;color:{COLORS["text_muted"]};">{row.current_value:,.2f} €</div>'
                f'</div>',
                unsafe_allow_html=True
            )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — ETF
# ─────────────────────────────────────────────────────────────────────────────
if show_etf_section and "ETF" in t:
    with t["ETF"]:
        etf_df = df[df["is_etf"]].copy()

        if etf_df.empty:
            st.info("Aucun ETF dans le portefeuille. Ajoutez une position en cochant 'ETF' dans le formulaire.")
        else:
            st.markdown('<div class="section-title">Vue consolidée ETF</div>', unsafe_allow_html=True)

            etf_tot = etf_df["current_value"].sum()
            etf_inv = etf_df["invested"].sum()
            etf_pnl = etf_tot - etf_inv
            etf_pct = etf_pnl / etf_inv * 100 if etf_inv > 0 else 0

            e1, e2, e3, e4 = st.columns(4)
            kpi(e1, "Valeur ETF",      f"{etf_tot:,.2f} €", etf_pnl, etf_pct)
            kpi(e2, "Investi ETF",     f"{etf_inv:,.2f} €")
            kpi(e3, "P&L ETF",         f"{etf_pnl:+,.2f} €")
            kpi(e4, "Part portefeuille",f"{etf_tot/total_value*100:.1f} %")

            st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

            el, er = st.columns(2)

            with el:
                fig_etf_pie = go.Figure(go.Pie(
                    labels=etf_df["ticker"], values=etf_df["current_value"].round(2),
                    hole=0.50, textinfo="label+percent",
                    marker=dict(colors=CHART_COLORS, line=dict(color="#FFFFFF", width=2)),
                    hovertemplate="<b>%{label}</b><br>%{value:,.2f} €<br>%{percent}<extra></extra>",
                ))
                fig_etf_pie.update_layout(
                    title=dict(text="Répartition des ETF", font=dict(size=12, color=COLORS["text_muted"]), x=0.02),
                    paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                    font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"]),
                    margin=dict(t=45,b=20,l=20,r=20),
                )
                st.plotly_chart(fig_etf_pie, use_container_width=True)

            with er:
                etf_s = etf_df.sort_values("pnl_pct", ascending=True)
                fig_etf_bar = go.Figure(go.Bar(
                    x=etf_s["pnl_pct"].round(2), y=etf_s["ticker"], orientation="h",
                    marker_color=["#059669" if v >= 0 else "#DC2626" for v in etf_s["pnl_pct"]],
                    text=[f"{v:+.1f}%" for v in etf_s["pnl_pct"]],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>P&L : %{x:.2f}%<extra></extra>",
                ))
                fig_etf_bar.add_vline(x=0, line_color="#9CA3AF", line_width=1)
                fig_etf_bar.update_layout(
                    title=dict(text="Comparaison performance ETF", font=dict(size=12, color=COLORS["text_muted"]), x=0.02),
                    paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
                    font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"]),
                    xaxis=dict(gridcolor=COLORS["border"], ticksuffix="%"),
                    yaxis=dict(gridcolor="#FFFFFF"),
                    margin=dict(t=45,b=40,l=80,r=80),
                    height=max(250, len(etf_df) * 50),
                    showlegend=False,
                )
                st.plotly_chart(fig_etf_bar, use_container_width=True)

            # Evolution ETF
            st.markdown('<div class="section-title">Evolution historique ETF (base 100)</div>', unsafe_allow_html=True)
            etf_series = []
            for pos in st.session_state.portfolio:
                if not pos.get("is_etf"):
                    continue
                hist = get_history(pos["ticker"], history_period)
                if hist.empty:
                    continue
                live = get_live_price(pos["ticker"])
                mult = usd_to_eur if live["currency"] in ("USD", "GBp") else 1.0
                etf_series.append((hist * pos["quantity"] * mult).rename(pos["ticker"]))

            if etf_series:
                etf_h = pd.concat(etf_series, axis=1).ffill().fillna(0)
                fig_etf_evo = go.Figure()
                for i, col in enumerate(etf_h.columns):
                    s    = etf_h[col]
                    base = s[s > 0].iloc[0] if (s > 0).any() else 1.0
                    fig_etf_evo.add_trace(go.Scatter(
                        x=etf_h.index, y=(s / base * 100).round(2),
                        mode="lines", name=col,
                        line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}<extra>" + col + "</extra>",
                    ))
                fig_etf_evo.add_hline(y=100, line_dash="dash", line_color="#9CA3AF", line_width=1,
                                      annotation_text="Base 100", annotation_font_color="#9CA3AF")
                fig_etf_evo.update_layout(
                    paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
                    font=dict(family="Inter, Segoe UI", color=COLORS["text_primary"]),
                    xaxis=dict(gridcolor=COLORS["border"], tickformat="%b %Y"),
                    yaxis=dict(gridcolor=COLORS["border"], title="Base 100"),
                    legend=dict(bgcolor="#F7F8FA", bordercolor=COLORS["border"], borderwidth=1,
                                orientation="h", yanchor="bottom", y=1.02),
                    hovermode="x unified",
                    margin=dict(t=60,b=40,l=60,r=20),
                    height=380,
                )
                st.plotly_chart(fig_etf_evo, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER + AUTO-REFRESH
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="text-align:right;font-size:11px;color:{COLORS["text_muted"]};'
    f'margin-top:2rem;padding-top:1rem;border-top:1px solid {COLORS["border"]};">'
    f'Données Yahoo Finance — Rafraîchissement automatique toutes les {AUTO_REFRESH_INTERVAL}s — '
    f'A titre informatif uniquement, ne constitue pas un conseil en investissement.'
    f'</div>',
    unsafe_allow_html=True
)

time.sleep(AUTO_REFRESH_INTERVAL)
st.rerun()
