import os
import time
import random
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

DATA_DIR = "data"
MAX_STOCKS = 100   # 先測試 100 檔，穩了再改成 None
SLEEP_SECONDS = 0.15


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def get_twse_stock_list():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = "big5"

    html_text = resp.text
    tables = pd.read_html(StringIO(html_text), flavor="lxml")

    if not tables:
        raise ValueError("讀不到 TWSE 表格")

    df = tables[0].copy()
    df.columns = df.iloc[0]
    df = df[1:].copy()
    df.columns = [str(c).strip() for c in df.columns]

    print("TWSE columns:", df.columns.tolist())

    security_type_col = None
    for col in df.columns:
        if "有價證券別" in col:
            security_type_col = col
            break

    code_name_col = None
    for col in df.columns:
        if "有價證券代號及名稱" in col:
            code_name_col = col
            break

    if security_type_col is None:
        print("找不到『有價證券別』欄位，直接列出前幾列資料：")
        print(df.head(5).to_dict(orient="records"))
    else:
        df = df[df[security_type_col].astype(str).str.contains("股票", na=False)].copy()

    if code_name_col is None:
        raise ValueError(f"找不到『有價證券代號及名稱』欄位，現有欄位: {df.columns.tolist()}")

    raw_series = df[code_name_col].astype(str).str.strip()

    split_col = raw_series.str.split("　", n=1, expand=True)
    if split_col.shape[1] < 2:
        split_col = raw_series.str.split(" ", n=1, expand=True)

    df["stock_id"] = split_col[0].astype(str).str.strip()
    if split_col.shape[1] > 1:
        df["stock_name"] = split_col[1].astype(str).str.strip()
    else:
        df["stock_name"] = ""

    df = df[df["stock_id"].str.match(r"^\d{4}$", na=False)].copy()
    df["yf_symbol"] = df["stock_id"] + ".TW"

    result = df[["stock_id", "stock_name", "yf_symbol"]].drop_duplicates().reset_index(drop=True)

    print("抓到股票數量:", len(result))
    print(result.head(10).to_dict(orient="records"))

    return result


def flatten_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    把 yfinance 回傳欄位整理成單層欄位：
    目標一定是 Open / High / Low / Close / Adj Close / Volume
    """
    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []

        for col in df.columns:
            # col 可能像 ('Close', '2330.TW') 或 ('2330.TW', 'Close')
            parts = [str(x) for x in col if x not in [None, ""]]

            chosen = None
            for p in parts:
                if p in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
                    chosen = p
                    break

            if chosen is None:
                chosen = parts[-1]

            new_cols.append(chosen)

        df.columns = new_cols

    else:
        df.columns = [str(c) for c in df.columns]

    return df


def download_stock_data(symbol: str, period: str = "6mo"):
    try:
        df = yf.download(
            symbol,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            print(f"[無資料] {symbol}")
            return None

        df = flatten_yfinance_columns(df)

        # 只保留我們需要的欄位
        keep_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
        available_cols = [c for c in keep_cols if c in df.columns]
        df = df[available_cols].copy()

        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in df.columns for col in required_cols):
            print(f"[欄位不足] {symbol}: {df.columns.tolist()}")
            return None

        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()

        if len(df) < 25:
            print(f"[資料不足] {symbol}: {len(df)} rows")
            return None

        return df

    except Exception as e:
        print(f"[下載失敗] {symbol}: {e}")
        return None


def add_indicators(df: pd.DataFrame):
    out = df.copy()
    out["MA5"] = out["Close"].rolling(5).mean()
    out["MA10"] = out["Close"].rolling(10).mean()
    out["MA20"] = out["Close"].rolling(20).mean()
    out["VOL_MA5"] = out["Volume"].rolling(5).mean()
    out["VOL_MA20"] = out["Volume"].rolling(20).mean()
    return out


def safe_float(value):
    if isinstance(value, pd.Series):
        if len(value) == 0:
            return None
        return float(value.iloc[0])
    if pd.isna(value):
        return None
    return float(value)


def safe_int(value):
    if isinstance(value, pd.Series):
        if len(value) == 0:
            return None
        return int(value.iloc[0])
    if pd.isna(value):
        return None
    return int(value)


def classify_stock(df: pd.DataFrame):
    if df is None or len(df) < 25:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    recent_10 = df.iloc[-10:].copy()

    close = safe_float(latest["Close"])
    ma5 = safe_float(latest["MA5"])
    ma10 = safe_float(latest["MA10"])
    ma20 = safe_float(latest["MA20"])
    volume = safe_float(latest["Volume"])
    vol_ma5 = safe_float(latest["VOL_MA5"])
    vol_ma20 = safe_float(latest["VOL_MA20"])

    if None in [close, ma5, ma10, ma20, volume, vol_ma5, vol_ma20]:
        return None

    # 趨勢穩健
    if close > ma5 > ma10 > ma20 and volume >= vol_ma20 * 0.9:
        return "trend"

    # 蓄勢待發
    recent_high = safe_float(recent_10["High"].max())
    recent_low = safe_float(recent_10["Low"].min())

    if recent_high is None or recent_low is None or close <= 0:
        return None

    volatility_ratio = (recent_high - recent_low) / close
    near_ma20 = abs(close - ma20) / ma20 < 0.03
    volume_expand = volume > vol_ma5 * 1.2

    if near_ma20 and volatility_ratio < 0.08 and volume_expand:
        return "setup"

    # 反轉雷達
    prev_close = safe_float(prev["Close"])
    prev_ma20 = safe_float(prev["MA20"])

    if prev_close is not None and prev_ma20 is not None:
        if prev_close < prev_ma20 and close > ma20 and volume > vol_ma5 * 1.1:
            return "reversal"

    return None


def make_row(stock_id: str, stock_name: str, symbol: str, df: pd.DataFrame):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = safe_float(latest["Close"])
    prev_close = safe_float(prev["Close"])
    volume = safe_int(latest["Volume"])

    if close is None or prev_close is None or volume is None:
        return None

    change = close - prev_close
    change_pct = (change / prev_close * 100) if prev_close != 0 else 0

    return {
        "Stock": symbol,
        "StockID": stock_id,
        "Name": stock_name,
        "Close": round(close, 2),
        "Change": round(change, 2),
        "ChangePct": round(change_pct, 2),
        "Volume": volume
    }


def save_csv(filename: str, rows: list):
    path = os.path.join(DATA_DIR, filename)
    columns = ["Stock", "StockID", "Name", "Close", "Change", "ChangePct", "Volume"]

    if rows:
        df = pd.DataFrame(rows)
        for col in columns:
            if col not in df.columns:
                df[col] = None
        df = df[columns]
    else:
        df = pd.DataFrame(columns=columns)

    df.to_csv(path, index=False, encoding="utf-8-sig")


def run_scan():
    ensure_data_dir()

    stock_df = get_twse_stock_list()
    if MAX_STOCKS is not None:
        stock_df = stock_df.head(MAX_STOCKS).copy()

    total = len(stock_df)
    print(f"開始掃描，共 {total} 檔")

    trend_rows = []
    setup_rows = []
    reversal_rows = []

    for idx, row in stock_df.iterrows():
        stock_id = row["stock_id"]
        stock_name = row["stock_name"]
        symbol = row["yf_symbol"]

        print(f"[{idx + 1}/{total}] 掃描 {stock_id} {stock_name}")

        df = download_stock_data(symbol, period="6mo")
        if df is None:
            continue

        df = add_indicators(df)
        category = classify_stock(df)

        if category is not None:
            item = make_row(stock_id, stock_name, symbol, df)
            if item is not None:
                if category == "trend":
                    trend_rows.append(item)
                elif category == "setup":
                    setup_rows.append(item)
                elif category == "reversal":
                    reversal_rows.append(item)

        time.sleep(SLEEP_SECONDS + random.uniform(0, 0.05))

    save_csv("trend.csv", trend_rows)
    save_csv("setup.csv", setup_rows)
    save_csv("reversal.csv", reversal_rows)

    print("掃描完成")
    print("趨勢穩健:", len(trend_rows))
    print("蓄勢待發:", len(setup_rows))
    print("反轉雷達:", len(reversal_rows))


if __name__ == "__main__":
    run_scan()