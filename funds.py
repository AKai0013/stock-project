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


def get_latest_trading_day_df(api, lookback_days=10):
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=lookback_days)

    try:
        df = api.taiwan_stock_institutional_investors(
            start_date=str(start_date),
            end_date=str(end_date)
        )
    except Exception as e:
        print("FinMind fetch failed:", e)
        return None

    if df is None or df.empty:
        print("NO DATA FROM FINMIND")
        return None

    print("FUNDS COLUMNS:", df.columns.tolist())

    if "date" not in df.columns or "stock_id" not in df.columns or "name" not in df.columns:
        print("Missing required columns")
        return None

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if df.empty:
        return None

    latest_date = df["date"].max()
    print("LATEST DATE:", latest_date)

    df = df[df["date"] == latest_date].copy()
    return df


def pick_buy_sell_column(df):
    candidates = [
        "buy_sell",
        "buy_sell_difference",
        "buy_sell_diff",
        "net_buy_sell",
    ]
    for col in candidates:
        if col in df.columns:
            return col

    # 保底：找欄位名含 buy 的
    for col in df.columns:
        if "buy" in str(col).lower():
            return col

    return None


def filter_foreign(df):
    # 盡量包更多可能名稱
    keys = [
        "foreign",
        "foreign investor",
        "foreign_investor",
        "foreign dealer",
        "foreign_dealer",
    ]

    mask = pd.Series(False, index=df.index)
    for k in keys:
        mask = mask | df["name"].astype(str).str.contains(k, case=False, na=False)

    return df[mask].copy()


def filter_invest(df):
    keys = [
        "investment",
        "investment trust",
        "investment_trust",
    ]

    mask = pd.Series(False, index=df.index)
    for k in keys:
        mask = mask | df["name"].astype(str).str.contains(k, case=False, na=False)

    return df[mask].copy()


def build_rank(df, buy_col, top_n=20):
    if df is None or df.empty or buy_col is None:
        return []

    rank = (
        df.groupby("stock_id", as_index=False)[buy_col]
        .sum()
        .sort_values(buy_col, ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    result = []
    for _, row in rank.iterrows():
        result.append({
            "stock_id": str(row["stock_id"]),
            "buy_sell": int(row[buy_col]) if pd.notna(row[buy_col]) else 0
        })
    return result


def get_funds_rank(days=3, top_n=20):
    api = get_api()
    if api is None:
        return {"foreign": [], "invest": []}

    df = get_latest_trading_day_df(api, lookback_days=10)
    if df is None or df.empty:
        return {"foreign": [], "invest": []}

    buy_col = pick_buy_sell_column(df)
    print("BUY COL:", buy_col)

    if buy_col is None:
        return {"foreign": [], "invest": []}

    foreign_df = filter_foreign(df)
    invest_df = filter_invest(df)

    print("FOREIGN ROWS:", len(foreign_df))
    print("INVEST ROWS:", len(invest_df))

    return {
        "foreign": build_rank(foreign_df, buy_col, top_n=top_n),
        "invest": build_rank(invest_df, buy_col, top_n=top_n),
    }