import os
import time
import random
import pandas as pd
import yfinance as yf

DATA_DIR = "data"
MAX_STOCKS = 100   # 先測試 100 檔，穩了再改成 None
SLEEP_SECONDS = 0.15


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def get_twse_stock_list():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    tables = pd.read_html(url)
    df = tables[0]

    df.columns = df.iloc[0]
    df = df[1:].copy()

    df = df[df["有價證券別"] == "股票"].copy()

    split_col = df["有價證券代號及名稱"].astype(str).str.split("　", n=1, expand=True)

    if split_col.shape[1] < 2:
        split_col = df["有價證券代號及名稱"].astype(str).str.split(" ", n=1, expand=True)

    df["stock_id"] = split_col[0].astype(str).str.strip()
    df["stock_name"] = split_col[1].astype(str).str.strip() if split_col.shape[1] > 1 else ""

    df = df[df["stock_id"].str.match(r"^\d{4}$", na=False)].copy()
    df["yf_symbol"] = df["stock_id"] + ".TW"

    return df[["stock_id", "stock_name", "yf_symbol"]].drop_duplicates().reset_index(drop=True)


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
            return None

        df = df.dropna().copy()
        if len(df) < 25:
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


def classify_stock(df: pd.DataFrame):
    if df is None or len(df) < 25:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    recent_10 = df.iloc[-10:].copy()

    close = float(latest["Close"])
    ma5 = float(latest["MA5"]) if pd.notna(latest["MA5"]) else None
    ma10 = float(latest["MA10"]) if pd.notna(latest["MA10"]) else None
    ma20 = float(latest["MA20"]) if pd.notna(latest["MA20"]) else None
    volume = float(latest["Volume"])
    vol_ma5 = float(latest["VOL_MA5"]) if pd.notna(latest["VOL_MA5"]) else None
    vol_ma20 = float(latest["VOL_MA20"]) if pd.notna(latest["VOL_MA20"]) else None

    if None in [ma5, ma10, ma20, vol_ma5, vol_ma20]:
        return None

    if close > ma5 > ma10 > ma20 and volume >= vol_ma20 * 0.9:
        return "trend"

    recent_high = recent_10["High"].max()
    recent_low = recent_10["Low"].min()
    volatility_ratio = (recent_high - recent_low) / close if close > 0 else 999
    near_ma20 = abs(close - ma20) / ma20 < 0.03
    volume_expand = volume > vol_ma5 * 1.2

    if near_ma20 and volatility_ratio < 0.08 and volume_expand:
        return "setup"

    prev_close = float(prev["Close"])
    prev_ma20 = float(prev["MA20"]) if pd.notna(prev["MA20"]) else None
    if prev_ma20 is not None:
        if prev_close < prev_ma20 and close > ma20 and volume > vol_ma5 * 1.1:
            return "reversal"

    return None


def make_row(stock_id: str, stock_name: str, symbol: str, df: pd.DataFrame):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(latest["Close"])
    prev_close = float(prev["Close"])
    change = close - prev_close
    change_pct = (change / prev_close * 100) if prev_close != 0 else 0
    volume = int(latest["Volume"])

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