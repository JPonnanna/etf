# app.py
import streamlit as st
import pandas as pd
import time
import random

st.set_page_config(page_title="Gold ETFs — LTP vs iNAV", layout="wide")

# Valid NSE symbols (trim/add as needed)
TICKERS =[
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


NSE_HOME  = "https://www.nseindia.com/"
NSE_QUOTE = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

REFRESH_SEC = 120  # soft auto-refresh cadence

# ---- Soft auto-refresh without a hard page reload
now = time.time()
key = "next_refresh_at"
if key not in st.session_state:
    st.session_state[key] = now + REFRESH_SEC
elif now >= st.session_state[key]:
    st.session_state[key] = now + REFRESH_SEC
    st.experimental_rerun()

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

# ---- Cloudsraper session with cookie warm-up (cached across reruns)
@st.cache_resource(show_spinner=False)
def make_scraper():
    import cloudscraper
    ua = random.choice(UA_LIST)
    s = cloudscraper.create_scraper(browser={"custom": ua}, delay=5)
    s.headers.update({
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
        "Connection": "keep-alive",
    })
    r = s.get(NSE_HOME, timeout=12)
    r.raise_for_status()
    return s

def fetch_quote(scraper, symbol, retries=4, base_delay=1.2):
    """Fetch NSE quote JSON with re-warm and backoff if blocked."""
    last_err = None
    for i in range(retries):
        try:
            resp = scraper.get(NSE_QUOTE.format(symbol=symbol), timeout=12)
            ctype = resp.headers.get("Content-Type", "")
            if not ctype.startswith("application/json"):
                # blocked -> re-warm cookies and retry with backoff
                scraper.get(NSE_HOME, timeout=12)
                time.sleep(base_delay * (i + 1))
                raise ValueError(f"Blocked/HTML ({ctype})")
            return resp.json()
        except Exception as e:
            last_err = e
            time.sleep(base_delay * (i + 1) + random.uniform(0, 0.6))
    raise last_err

# ---- Pull a full snapshot (cached for 120s so we don't hammer NSE)
@st.cache_data(ttl=120, show_spinner=True)
def fetch_snapshot(symbols):
    s = make_scraper()
    out = []
    for sym in symbols:
        try:
            q  = fetch_quote(s, sym)
            pi = (q or {}).get("priceInfo", {}) or {}
            ltp = safe_float(pi.get("lastPrice"))
            inav_ok = bool(pi.get("checkINAV"))
            inav = safe_float(pi.get("iNavValue")) if inav_ok else None
            disc = (ltp - inav) / inav * 100 if (ltp is not None and inav) else None
            out.append({
                "Ticker": sym,
                "LTP": ltp,
                "iNAV ok?": inav_ok,
                "iNAV": inav,
                "Disc/Prem %": None if disc is None else round(disc, 3),
            })
            time.sleep(0.2)  # tiny politeness delay per symbol
        except Exception as e:
            out.append({
                "Ticker": sym,
                "LTP": None,
                "iNAV ok?": False,
                "iNAV": None,
                "Disc/Prem %": None,
                "Error": str(e),
            })
            time.sleep(0.6)
    return pd.DataFrame(out)

# ---- UI
st.title("Gold ETFs — LTP vs iNAV (NSE)")
st.caption(f"Auto-update ~{REFRESH_SEC}s • Unofficial NSE website JSON via cloudscraper")

df = fetch_snapshot(TICKERS)

st.dataframe(
    df,
    use_container_width=True,
    column_config={
        "LTP": st.column_config.NumberColumn(format="%.2f"),
        "iNAV": st.column_config.NumberColumn(format="%.2f"),
        "Disc/Prem %": st.column_config.NumberColumn(format="%.3f"),
    }
)

if "Error" in df.columns and df["Error"].notna().any():
    with st.expander("Errors / blocked symbols"):
        st.write(df[["Ticker", "Error"]])
