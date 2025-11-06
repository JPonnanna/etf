import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Gold ETFs — LTP vs iNAV", layout="wide")

# ✅ Correct NSE symbols (trimmed to widely-traded ones)
GOLD_ETF_TICKERS = [
    "GOLDBEES",      # Nippon India ETF Gold BeES
    "SETFGOLD",      # SBI Gold ETF
    "KOTAKGOLD",     # Kotak Gold ETF
    "ICICIGOLD",     # ICICI Prudential Gold ETF
    "HDFCMFGETF",    # HDFC Gold ETF
    "GOLDSHARE",     # UTI Gold ETF
    "BSLGOLDETF",    # Aditya Birla Sun Life Gold ETF
    "AXISGOLD",      # Axis Gold ETF
    "DSPGOLDETF",    # DSP Gold ETF
    "QGOLDHALF",     # Quantum Gold ETF
    "LICMFGOLD",     # LIC MF Gold ETF
    "IVZINGOLD",     # Invesco India Gold ETF
    "UNIONGOLD",     # Union Gold ETF
    "TATAGOLD",      # Tata Gold ETF
    "EGOLD",         # Edelweiss Gold ETF
]

NSE_HOME = "https://www.nseindia.com/"
NSE_QUOTE = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

@st.cache_resource(show_spinner=False)
def make_nse_session():
    s = requests.Session()
    # Must look like a real browser
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
        "Connection": "keep-alive",
    })
    # Warm up: fetch homepage to get cookies
    r = s.get(NSE_HOME, timeout=10)
    r.raise_for_status()
    return s

def fetch_quote(session: requests.Session, symbol: str, retries: int = 3, delay: float = 1.5):
    """Fetch NSE equity quote JSON with retries and 403/HTML handling."""
    url = NSE_QUOTE.format(symbol=symbol)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=10)
            # If we got HTML (blocked), try to re-warm and retry
            if resp.headers.get("Content-Type", "").startswith("text/html"):
                # Re-warm cookies
                session.get(NSE_HOME, timeout=10)
                time.sleep(delay)
                raise ValueError("HTML/blocked response; rewarming cookies")
            data = resp.json()  # will raise if not JSON
            return data
        except Exception as e:
            last_err = e
            time.sleep(delay * attempt)
    raise last_err

@st.cache_data(ttl=120, show_spinner=True)  # 2-minute cache
def fetch_snapshot(symbols):
    s = make_nse_session()
    rows = []
    for sym in symbols:
        try:
            q = fetch_quote(s, sym)
            pi = (q or {}).get("priceInfo", {}) or {}
            ltp = safe_float(pi.get("lastPrice"))
            inav_ok = bool(pi.get("checkINAV"))
            inav = safe_float(pi.get("iNavValue")) if inav_ok else None
            disc = (ltp - inav) / inav * 100 if (ltp is not None and inav) else None
            rows.append({
                "Ticker": sym,
                "LTP": ltp,
                "iNAV ok?": inav_ok,
                "iNAV": inav,
                "Disc/Prem %": None if disc is None else round(disc, 3),
            })
        except Exception as e:
            rows.append({
                "Ticker": sym,
                "LTP": None,
                "iNAV ok?": False,
                "iNAV": None,
                "Disc/Prem %": None,
                "Error": str(e),
            })
    return pd.DataFrame(rows)

st.title("Gold ETFs — LTP vs iNAV (NSE)")
st.caption("Auto-refresh every ~2 minutes · Data via NSE website JSON (unofficial)")

# Simple page refresh (optional)
st.markdown('<meta http-equiv="refresh" content="120">', unsafe_allow_html=True)

df = fetch_snapshot(GOLD_ETF_TICKERS)
st.dataframe(
    df,
    use_container_width=True,
    column_config={
        "LTP": st.column_config.NumberColumn(format="%.2f"),
        "iNAV": st.column_config.NumberColumn(format="%.2f"),
        "Disc/Prem %": st.column_config.NumberColumn(format="%.3f"),
    }
)
# Show any errors compactly
errs = df[df["Error"].notna()] if "Error" in df.columns else pd.DataFrame()
if not errs.empty:
    with st.expander("Errors / blocked symbols"):
        st.write(errs[["Ticker", "Error"]])
