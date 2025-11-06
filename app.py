import streamlit as st
import pandas as pd
from jugaad_data.nse import NSELive
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(page_title="Gold ETFs — LTP vs iNAV", layout="wide")

TICKERS = [
    'GOLDBEES',      # Nippon India ETF Gold BeES
    'SETFGOLD',      # SBI Gold ETF
    'GOLD1',         # Kotak Gold ETF
    'GOLDIETF',      # ICICI Prudential Gold ETF
    'HDFCGOLD',      # HDFC Gold ETF
    'GOLDSHARE',     # UTI Gold Exchange Traded Fund
    'BSLGOLDETF',    # Aditya Birla Sun Life Gold ETF
    'AXISGOLD',      # Axis Gold ETF
    'GOLDETFADD',    # DSP Gold ETF
    'QGOLDHALF',     # Quantum Gold Fund
    'LICMFGOLD',     # LIC MF Gold ETF
    'IVZINGOLD',     # Invesco India Gold Exchange Traded Fund
    'GROWWGOLD',     # Groww Gold ETF
    'GOLDETF',       # Mirae Asset Gold ETF
    'GOLD360',       # 360 ONE Gold ETF
    'BBNPPGOLD',     # Baroda BNP Paribas Gold ETF
    'UNIONGOLD',     # Union Gold ETF
    'TATAGOLD',      # Tata Gold Exchange Traded Fund
    'EGOLD',         # Edelweiss Gold ETF
    'AONEGOLD',      # Angel One Gold ETF
    'GOLDCASE',      # Zerodha Gold ETF
    'MOGSEC'         # Motilal Oswal Gold ETF
]


def safe_float(x):
    try: return float(x)
    except: return None

@st.cache_data(ttl=120)   # keep data “hot” for 2 min
def fetch_snapshot():
    n = NSELive()
    rows = []
    for t in TICKERS:
        try:
            q = n.stock_quote(t)
            pi = (q or {}).get("priceInfo", {}) or {}
            ltp = safe_float(pi.get("lastPrice"))
            inav_ok = bool(pi.get("checkINAV"))
            inav = safe_float(pi.get("iNavValue")) if inav_ok else None
            disc = (ltp - inav) / inav * 100 if (ltp is not None and inav) else None
            rows.append({"Ticker": t, "LTP": ltp, "iNAV ok?": inav_ok,
                         "iNAV": inav, "Disc/Prem %": None if disc is None else round(disc,3)})
        except Exception as e:
            rows.append({"Ticker": t, "LTP": None, "iNAV ok?": False, "iNAV": None,
                         "Disc/Prem %": None, "Error": str(e)})
    return pd.DataFrame(rows)

# 🔁 Auto-rerun every 120,000 ms without a visible hard refresh
st_autorefresh(interval=120_000, key="etf_autorefresh")

st.title("Gold ETFs — LTP vs iNAV (NSE)")
st.caption(f"Last update: {datetime.now():%Y-%m-%d %H:%M:%S}  • auto-refresh ~120s")

# Keep layout static; only the placeholder’s content changes on reruns
table_placeholder = st.empty()
df = fetch_snapshot()
table_placeholder.dataframe(
    df, use_container_width=True,
    column_config={
        "LTP": st.column_config.NumberColumn(format="%.2f"),
        "iNAV": st.column_config.NumberColumn(format="%.2f"),
        "Disc/Prem %": st.column_config.NumberColumn(format="%.3f"),
    }
)

if "Error" in df.columns and df["Error"].notna().any():
    with st.expander("Errors / blocked symbols"):
        st.write(df[["Ticker","Error"]])
