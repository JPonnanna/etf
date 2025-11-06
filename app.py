import streamlit as st
import pandas as pd
import time
import random
import json
import cloudscraper

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
NSE_HOME = "https://www.nseindia.com/"
NSE_QUOTE = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"

UA_LIST = [
    # rotate a few realistic UAs
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

def safe_float(x):
    try: return float(x)
    except: return None

@st.cache_resource(show_spinner=False)
def make_scraper():
    ua = random.choice(UA_LIST)
    s = cloudscraper.create_scraper(
        browser={"custom": ua},
        delay=5,           # politeness delay on challenges
    )
    # baseline headers
    s.headers.update({
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
        "Connection": "keep-alive",
    })
    # warm the cookies
    r = s.get(NSE_HOME, timeout=12)
    r.raise_for_status()
    return s

def fetch_quote(scraper, symbol, retries=4, base_delay=1.2):
    url = NSE_QUOTE.format(symbol=symbol)
    last_err = None
    for i in range(retries):
        try:
            resp = scraper.get(url, timeout=12)
            # if we got HTML instead of JSON, re-warm and retry
            if not resp.headers.get("Content-Type","").startswith("application/json"):
                scraper.get(NSE_HOME, timeout=12)
                time.sleep(base_delay*(i+1))
                raise ValueError("Blocked/HTML response")
            return resp.json()
        except Exception as e:
            last_err = e
            # small backoff + random jitter
            time.sleep(base_delay*(i+1) + random.uniform(0,0.6))
    raise last_err

@st.cache_data(ttl=120, show_spinner=True)
def fetch_snapshot(symbols):
    s = make_scraper()
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
            # brief pause after an error to avoid rapid-fire blocks
            time.sleep(0.8)
    return pd.DataFrame(rows)

st.title("Gold ETFs — LTP vs iNAV (NSE)")
st.caption("Auto-refresh ~120s • Unofficial NSE JSON via cloudscraper")

# optional page-level refresh
st.markdown('<meta http-equiv="refresh" content="120">', unsafe_allow_html=True)

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
        st.write(df[["Ticker","Error"]])
