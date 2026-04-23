import os
import time
import random
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

DATA_DIR = "data"
MAX_STOCKS = 150   # 建議先測試，穩了改 None
SLEEP_SECONDS = 0.15


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# =========================
# 🔥 抓「股票 + ETF」
# =========================
def get_twse_stock_list():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = "big5"

    tables = pd.read_html(StringIO(resp.text), flavor="lxml")

    df = tables[0].copy()
    df.columns = df.iloc[0]
    df = df[1:].copy()
    df.columns = [str(c).strip() for c in df.columns]

    # 找欄位
    type_col = None
    code_col = None

    for col in df.columns:
        if "有價證券別" in col:
            type_col = col
        if "有價證券代號及名稱" in col:
            code_col = col

    if code_col is None:
        raise Exception("找不到代號欄位")

    # 🔥 關鍵：同時抓 股票 + ETF
    if type_col:
        df = df[
            df[type_col].astype(str).str.contains("股票|ETF", na=False)
        ].copy()

    raw = df[code_col].astype(str).str.strip()

    split_col = raw.str.split("　", n=1, expand=True)
    if split_col.shape[1] < 2:
        split_col = raw.str.split(" ", n=1, expand=True)

    df["stock_id"] = split_col[0].astype(str).str.strip()
    df["stock_name"] = split_col[1].astype(str).str.strip() if split_col.shape[1] > 1 else ""

    # 🔥 股票 + ETF 編碼規則
    df = df[df["stock_id"].str.match(r"^\d{4,5}$", na=False)].copy()

    df["yf_symbol"] = df["stock_id"] + ".TW"

    result = df[["stock_id", "stock_name", "yf_symbol"]].drop_duplicates().reset_index(drop=True)

    print("抓到股票+ETF數量:", len(result))
    return result


# =========================
# 🔥 修正 yfinance 欄位
# =========================
def flatten_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []

        for col in df.columns:
            parts = [str(x) for x in col if x]

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


# =========================
# 🔥 抓價格
# =========================
def download_stock_data(symbol):
    try:
        df = yf.download(
            symbol,
            period="6mo",
            interval="1d",
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        df = flatten_yfinance_columns(df)

        need = ["Open", "High", "Low", "Close", "Volume"]
        if not all(c in df.columns for c in need):
            return None

        df = df.dropna()

        if len(df) < 25:
            return None

        return df

    except:
        return None


# =========================
# 技術指標
# =========================
def add_indicators(df):
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["VOL5"] = df["Volume"].rolling(5).mean()
    df["VOL20"] = df["Volume"].rolling(20).mean()
    return df


# =========================
# 分類
# =========================
def classify(df):
    if len(df) < 25:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = last["Close"]
    ma5 = last["MA5"]
    ma10 = last["MA10"]
    ma20 = last["MA20"]

    vol = last["Volume"]
    vol5 = last["VOL5"]
    vol20 = last["VOL20"]

    if any(pd.isna(x) for x in [ma5, ma10, ma20, vol5, vol20]):
        return None

    # 🔥 趨勢
    if close > ma5 > ma10 > ma20 and vol >= vol20 * 0.9:
        return "trend"

    # 🔥 蓄勢
    high = df["High"].tail(10).max()
    low = df["Low"].tail(10).min()

    if abs(close - ma20) / ma20 < 0.03 and (high - low) / close < 0.08 and vol > vol5 * 1.2:
        return "setup"

    # 🔥 反轉
    if prev["Close"] < prev["MA20"] and close > ma20 and vol > vol5 * 1.1:
        return "reversal"

    return None


# =========================
# 產出資料
# =========================
def make_row(stock_id, name, symbol, df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(last["Close"])
    prev_close = float(prev["Close"])

    change = close - prev_close
    pct = change / prev_close * 100

    return {
        "Stock": symbol,
        "StockID": stock_id,
        "Name": name,
        "Close": round(close, 2),
        "Change": round(change, 2),
        "ChangePct": round(pct, 2),
        "Volume": int(last["Volume"])
    }


def save_csv(name, rows):
    path = os.path.join(DATA_DIR, name)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")


# =========================
# 主掃描
# =========================
def run():
    ensure_data_dir()

    stocks = get_twse_stock_list()

    if MAX_STOCKS:
        stocks = stocks.head(MAX_STOCKS)

    trend, setup, reversal = [], [], []

    total = len(stocks)
    print("開始掃描:", total)

    for i, row in stocks.iterrows():
        print(f"[{i+1}/{total}] {row['stock_id']} {row['stock_name']}")

        df = download_stock_data(row["yf_symbol"])
        if df is None:
            continue

        df = add_indicators(df)
        c = classify(df)

        if c:
            r = make_row(row["stock_id"], row["stock_name"], row["yf_symbol"], df)

            if c == "trend":
                trend.append(r)
            elif c == "setup":
                setup.append(r)
            elif c == "reversal":
                reversal.append(r)

        time.sleep(SLEEP_SECONDS + random.random() * 0.05)

    save_csv("trend.csv", trend)
    save_csv("setup.csv", setup)
    save_csv("reversal.csv", reversal)

    print("完成")
    print("trend:", len(trend))
    print("setup:", len(setup))
    print("reversal:", len(reversal))


if __name__ == "__main__":
    run()