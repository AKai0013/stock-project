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


def fetch_raw_funds_df(lookback_days=10):
    api = get_api()
    if api is None:
        return None, "FinMind 初始化失敗"

    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=lookback_days)

    try:
        df = api.taiwan_stock_institutional_investors(
            start_date=str(start_date),
            end_date=str(end_date)
        )
    except Exception as e:
        err_msg = str(e)

        if "Your level is register" in err_msg:
            return None, "目前 FinMind 帳號等級不足，法人資料尚未開通"

        return None, f"FinMind 抓取失敗：{err_msg}"

    if df is None or df.empty:
        return None, "目前查無法人資料"

    return df.copy(), None


def find_buy_col(df):
    candidates = [
        "buy_sell",
        "buy_sell_difference",
        "buy_sell_diff",
        "net_buy_sell",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    for col in df.columns:
        if "buy" in str(col).lower():
            return col

    return None


def get_funds_rank(top_n=20):
    df, err = fetch_raw_funds_df(lookback_days=10)

    if err:
        return {
            "foreign": [],
            "invest": [],
            "message": err
        }

    if "date" not in df.columns or "name" not in df.columns or "stock_id" not in df.columns:
        return {
            "foreign": [],
            "invest": [],
            "message": "法人資料格式不符，缺少必要欄位"
        }

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if df.empty:
        return {
            "foreign": [],
            "invest": [],
            "message": "法人資料為空"
        }

    latest_date = df["date"].max()
    df = df[df["date"] == latest_date].copy()

    buy_col = find_buy_col(df)
    if buy_col is None:
        return {
            "foreign": [],
            "invest": [],
            "message": "找不到法人買賣超欄位"
        }

    foreign_df = df[df["name"].astype(str).str.contains("外資|陸資|foreign", case=False, na=False)].copy()
    invest_df = df[df["name"].astype(str).str.contains("投信|investment", case=False, na=False)].copy()

    def build_rank(sub_df):
        if sub_df.empty:
            return []

        grouped = (
            sub_df.groupby("stock_id", as_index=False)[buy_col]
            .sum()
            .sort_values(buy_col, ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

        result = []
        for _, row in grouped.iterrows():
            result.append({
                "stock_id": str(row["stock_id"]),
                "buy_sell": int(row[buy_col]) if pd.notna(row[buy_col]) else 0
            })
        return result

    return {
        "foreign": build_rank(foreign_df),
        "invest": build_rank(invest_df),
        "message": ""
    }