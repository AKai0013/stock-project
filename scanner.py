import yfinance as yf
import pandas as pd

# 台股清單（先用幾檔測試）
stocks = [
    "2330.TW",
    "2317.TW",
    "2454.TW",
    "2308.TW",
    "2603.TW",
    "3481.TW",
    "2382.TW"
]

trend = []
setup = []
reversal = []

for s in stocks:
    try:
        df = yf.download(s, period="3mo", interval="1d")

        if len(df) < 20:
            continue

        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA20"] = df["Close"].rolling(20).mean()

        latest = df.iloc[-1]

        close = float(latest["Close"])
        volume = int(latest["Volume"])

        ma5 = float(latest["MA5"])
        ma20 = float(latest["MA20"])

        # 趨勢股（多頭）
        if close > ma5 > ma20:
            trend.append({
                "Stock": s,
                "Close": round(close, 2),
                "Volume": volume
            })

        # 蓄勢股（接近均線）
        elif abs(close - ma20) / ma20 < 0.03:
            setup.append({
                "Stock": s,
                "Close": round(close, 2),
                "Volume": volume
            })

        # 反轉股（剛站上）
        elif close > ma20:
            reversal.append({
                "Stock": s,
                "Close": round(close, 2),
                "Volume": volume
            })

    except Exception as e:
        print("error:", s, e)

# 輸出 CSV
pd.DataFrame(trend).to_csv("data/trend.csv", index=False)
pd.DataFrame(setup).to_csv("data/setup.csv", index=False)
pd.DataFrame(reversal).to_csv("data/reversal.csv", index=False)

print("完成掃描")