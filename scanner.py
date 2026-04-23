import yfinance as yf
import pandas as pd

def get_stock_list():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    df = pd.read_html(url)[0]
    df.columns = df.iloc[0]
    df = df[1:]
    df = df[df["有價證券別"] == "股票"]
    df["代號"] = df["有價證券代號及名稱"].str.split().str[0]
    return [s + ".TW" for s in df["代號"].tolist()]

def get_data(stock):
    try:
        df = yf.download(stock, period="6mo", progress=False)
        if len(df) < 60:
            return None
        return df
    except:
        return None

def add_indicators(df):
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    df["Vol_MA20"] = df["Volume"].rolling(20).mean()
    return df

def trend(df):
    latest = df.iloc[-1]
    last5 = df.iloc[-5:]
    return (
        latest["Close"] > latest["MA60"] and
        latest["MA20"] > latest["MA60"] and
        latest["Volume"] > latest["Vol_MA20"] and
        sum(last5["Close"].diff() > 0) >= 3
    )

def setup(df):
    recent = df.iloc[-10:]
    latest = df.iloc[-1]
    return (
        abs(latest["Close"] - latest["MA20"]) / latest["MA20"] < 0.03 and
        recent["Close"].std() < recent["Close"].mean() * 0.02 and
        latest["Volume"] > latest["Vol_MA20"] * 1.5
    )

def reversal(df):
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    return (
        yesterday["Close"] < yesterday["MA60"] and
        today["Close"] > today["MA60"] and
        today["Volume"] > today["Vol_MA20"] * 1.5
    )

def run_scan():
    stocks = get_stock_list()

    trend_list, setup_list, reversal_list = [], [], []

    for stock in stocks[:200]:
        df = get_data(stock)
        if df is None:
            continue

        df = add_indicators(df)
        latest = df.iloc[-1]

        data = {
            "Stock": stock,
            "Close": round(latest["Close"], 2),
            "Volume": int(latest["Volume"])
        }

        if trend(df): trend_list.append(data)
        if setup(df): setup_list.append(data)
        if reversal(df): reversal_list.append(data)

    pd.DataFrame(trend_list).to_csv("data/trend.csv", index=False)
    pd.DataFrame(setup_list).to_csv("data/setup.csv", index=False)
    pd.DataFrame(reversal_list).to_csv("data/reversal.csv", index=False)

if __name__ == "__main__":
    run_scan()