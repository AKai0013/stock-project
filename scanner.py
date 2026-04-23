import os
import time
import random
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

DATA_DIR = "data"

# 全掃就設 None；怕太慢先設 600
MAX_STOCKS = None

SLEEP_SECONDS = 0.08
MIN_PRICE = 20
MIN_AVG_VOLUME = 300000
PERIOD = "1y"


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def get_twse_stock_list():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = "big5"

    tables = pd.read_html(StringIO(resp.text), flavor="lxml")
    if not tables:
        raise ValueError("讀不到 TWSE 表格")

    df = tables[0].copy()
    df.columns = df.iloc[0]
    df = df[1:].copy()
    df.columns = [str(c).strip() for c in df.columns]

    type_col = None
    code_col = None

    for col in df.columns:
        if "有價證券別" in col:
            type_col = col
        if "有價證券代號及名稱" in col:
            code_col = col

    if code_col is None:
        raise ValueError("找不到『有價證券代號及名稱』欄位")

    if type_col is not None:
        df = df[df[type_col].astype(str).str.contains("股票|ETF", na=False)].copy()
    else:
        df["有價證券別"] = "未知"

    raw = df[code_col].astype(str).str.strip()

    split_col = raw.str.split("　", n=1, expand=True)
    if split_col.shape[1] < 2:
        split_col = raw.str.split(" ", n=1, expand=True)

    df["stock_id"] = split_col[0].astype(str).str.strip()
    df["stock_name"] = split_col[1].astype(str).str.strip() if split_col.shape[1] > 1 else ""

    df = df[df["stock_id"].str.match(r"^\d{4,5}$", na=False)].copy()

    df["asset_type"] = df[type_col].astype(str).str.strip() if type_col is not None else "未知"
    df["is_etf"] = df["asset_type"].astype(str).str.contains("ETF", na=False)
    df["yf_symbol"] = df["stock_id"] + ".TW"

    result = df[["stock_id", "stock_name", "asset_type", "is_etf", "yf_symbol"]].drop_duplicates().reset_index(drop=True)

    print("抓到股票+ETF數量:", len(result))
    return result


def flatten_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            parts = [str(x) for x in col if x not in [None, ""]]

            target = None
            for p in parts:
                if p in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
                    target = p
                    break

            if target is None:
                target = parts[-1]

            new_cols.append(target)

        df.columns = new_cols
    else:
        df.columns = [str(c) for c in df.columns]

    return df


def download_stock_data(symbol):
    try:
        df = yf.download(
            symbol,
            period=PERIOD,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        df = flatten_yfinance_columns(df)

        need = ["Open", "High", "Low", "Close", "Volume"]
        if not all(c in df.columns for c in need):
            return None

        df = df[need].dropna().copy()

        if len(df) < 130:
            return None

        return df

    except Exception:
        return None


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def add_indicators(df):
    df = df.copy()

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()

    df["VOL20"] = df["Volume"].rolling(20).mean()

    df["HIGH20"] = df["High"].rolling(20).max()
    df["HIGH60"] = df["High"].rolling(60).max()
    df["HIGH120"] = df["High"].rolling(120).max()

    df["LOW20"] = df["Low"].rolling(20).min()
    df["LOW60"] = df["Low"].rolling(60).min()

    df["RSI14"] = calc_rsi(df["Close"], 14)
    df["ChangePct"] = df["Close"].pct_change() * 100

    return df


def passes_basic_filters(df, is_etf):
    last = df.iloc[-1]

    close = float(last["Close"])
    vol20 = float(last["VOL20"]) if pd.notna(last["VOL20"]) else 0

    if close < MIN_PRICE:
        return False

    min_vol = 200000 if is_etf else MIN_AVG_VOLUME
    if vol20 < min_vol:
        return False

    return True


def classify(df, is_etf):
    if len(df) < 130:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(last["Close"])
    ma20 = float(last["MA20"]) if pd.notna(last["MA20"]) else None
    ma60 = float(last["MA60"]) if pd.notna(last["MA60"]) else None
    ma120 = float(last["MA120"]) if pd.notna(last["MA120"]) else None
    vol = float(last["Volume"])
    vol20 = float(last["VOL20"]) if pd.notna(last["VOL20"]) else None
    high20 = float(last["HIGH20"]) if pd.notna(last["HIGH20"]) else None
    high120 = float(last["HIGH120"]) if pd.notna(last["HIGH120"]) else None
    low20 = float(last["LOW20"]) if pd.notna(last["LOW20"]) else None
    rsi = float(last["RSI14"]) if pd.notna(last["RSI14"]) else None
    change_pct = float(last["ChangePct"]) if pd.notna(last["ChangePct"]) else 0

    prev_close = float(prev["Close"])
    prev_ma20 = float(prev["MA20"]) if pd.notna(prev["MA20"]) else None

    if None in [ma20, ma60, ma120, vol20, high20, high120, low20, rsi]:
        return None

    if not passes_basic_filters(df, is_etf):
        return None

    if (
        close > ma20 > ma60 > ma120 and
        close >= high20 * 0.98 and
        close >= high120 * 0.85 and
        vol >= vol20 * 1.1 and
        55 <= rsi <= 80
    ):
        return "trend"

    range_20 = (high20 - low20) / close if close > 0 else 999
    if (
        close > ma60 and
        ma20 > ma60 and
        ma60 >= ma120 * 0.97 and
        close >= high20 * 0.96 and
        range_20 < 0.12 and
        vol >= vol20 * 0.9 and
        45 <= rsi <= 68
    ):
        return "setup"

    if (
        prev_ma20 is not None and
        prev_close < prev_ma20 and
        close > ma20 and
        change_pct >= 3 and
        vol >= vol20 * 1.5 and
        rsi >= 50
    ):
        return "reversal"

    return None


def make_row(stock_id, name, asset_type, is_etf, symbol, df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(last["Close"])
    prev_close = float(prev["Close"])
    change = close - prev_close
    pct = (change / prev_close * 100) if prev_close != 0 else 0

    high20 = float(last["HIGH20"]) if pd.notna(last["HIGH20"]) else close
    high120 = float(last["HIGH120"]) if pd.notna(last["HIGH120"]) else close
    vol20 = float(last["VOL20"]) if pd.notna(last["VOL20"]) else 0

    return {
        "Stock": symbol,
        "StockID": stock_id,
        "Name": name,
        "AssetType": asset_type,
        "IsETF": bool(is_etf),
        "Close": round(close, 2),
        "Change": round(change, 2),
        "ChangePct": round(pct, 2),
        "Volume": int(last["Volume"]),
        "MA20": round(float(last["MA20"]), 2) if pd.notna(last["MA20"]) else None,
        "MA60": round(float(last["MA60"]), 2) if pd.notna(last["MA60"]) else None,
        "MA120": round(float(last["MA120"]), 2) if pd.notna(last["MA120"]) else None,
        "RSI14": round(float(last["RSI14"]), 2) if pd.notna(last["RSI14"]) else None,
        "High20": round(high20, 2),
        "High120": round(high120, 2),
        "Vol20": round(vol20, 2),
        "NearHigh20Pct": round((close / high20) * 100, 2) if high20 > 0 else None,
        "NearHigh120Pct": round((close / high120) * 100, 2) if high120 > 0 else None,
    }


def save_csv(name, rows):
    path = os.path.join(DATA_DIR, name)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def run():
    ensure_data_dir()

    stocks = get_twse_stock_list()

    if MAX_STOCKS:
        stocks = stocks.head(MAX_STOCKS)

    trend, setup, reversal = [], [], []

    total = len(stocks)
    print("開始掃描:", total)

    for i, row in stocks.iterrows():
        stock_id = row["stock_id"]
        stock_name = row["stock_name"]
        asset_type = row["asset_type"]
        is_etf = bool(row["is_etf"])
        symbol = row["yf_symbol"]

        print(f"[{i+1}/{total}] {stock_id} {stock_name} ({asset_type})")

        df = download_stock_data(symbol)
        if df is None:
            continue

        df = add_indicators(df)
        category = classify(df, is_etf)

        if category:
            result = make_row(stock_id, stock_name, asset_type, is_etf, symbol, df)

            if category == "trend":
                trend.append(result)
            elif category == "setup":
                setup.append(result)
            elif category == "reversal":
                reversal.append(result)

        time.sleep(SLEEP_SECONDS + random.random() * 0.03)

    save_csv("trend.csv", trend)
    save_csv("setup.csv", setup)
    save_csv("reversal.csv", reversal)

    print("完成")
    print("trend:", len(trend))
    print("setup:", len(setup))
    print("reversal:", len(reversal))


if __name__ == "__main__":
    run()