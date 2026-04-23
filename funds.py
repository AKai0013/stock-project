from datetime import datetime, timedelta
from FinMind.data import DataLoader
import pandas as pd
import os

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")

_api = None
_api_ready = False


def get_api():
    global _api, _api_ready

    if _api_ready and _api is not None:
        return _api

    try:
        api = DataLoader()

        if FINMIND_TOKEN:
            try:
                api.login_by_token(api_token=FINMIND_TOKEN)
                print("FinMind token login success")
            except Exception as e:
                print("FinMind token login failed:", e)
        else:
            print("FINMIND_TOKEN is empty")

        _api = api
        _api_ready = True
        return _api

    except Exception as e:
        print("FinMind DataLoader init failed:", e)
        return None


def get_funds_rank(days=3, top_n=20):
    api = get_api()
    if api is None:
        return {"foreign": [], "invest": []}

    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=10)

    try:
        df = api.taiwan_stock_institutional_investors(
            start_date=str(start_date),
            end_date=str(end_date)
        )
    except Exception as e:
        print("FinMind fetch failed:", e)
        return {"foreign": [], "invest": []}

    if df is None or df.empty:
        return {"foreign": [], "invest": []}

    # 👉 轉時間
    df["date"] = pd.to_datetime(df["date"])
    latest_date = df["date"].max()

    # 👉 只抓最新一天
    df = df[df["date"] == latest_date].copy()

    # 👉 找買賣超欄位
    buy_col = None
    for col in df.columns:
        if "buy" in col.lower():
            buy_col = col

    if buy_col is None:
        print("找不到買賣超欄位")
        return {"foreign": [], "invest": []}

    # 🔥🔥🔥 關鍵：用中文抓法人
    foreign_df = df[df["name"].astype(str).str.contains("外資|陸資", na=False)]
    invest_df = df[df["name"].astype(str).str.contains("投信", na=False)]

    def build_rank(d):
        if d.empty:
            return []

        r = (
            d.groupby("stock_id")[buy_col]
            .sum()
            .sort_values(ascending=False)
            .head(top_n)
        )

        return [
            {"stock_id": i, "buy_sell": int(v)}
            for i, v in r.items()
        ]

    return {
        "foreign": build_rank(foreign_df),
        "invest": build_rank(invest_df),
    }