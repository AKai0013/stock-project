from datetime import datetime, timedelta
from FinMind.data import DataLoader
import pandas as pd
import os

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")

api = None

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
except Exception as e:
    print("FinMind DataLoader init failed:", e)
    api = None


def _normalize_name(name):
    if not isinstance(name, str):
        return ""
    return name.strip().lower()


def _pick_buy_sell_column(df):
    candidates = [
        "buy_sell",
        "buy_sell_difference",
        "buy_sell_diff",
        "net_buy_sell",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _pick_date_column(df):
    for col in ["date", "Date"]:
        if col in df.columns:
            return col
    return None


def get_funds_rank(days=1, top_n=20):
    if api is None:
        return {"foreign": [], "invest": []}

    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=max(days * 3, 7))

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

    date_col = _pick_date_column(df)
    buy_sell_col = _pick_buy_sell_column(df)

    if date_col is None or buy_sell_col is None:
        print("Unexpected columns:", df.columns.tolist())
        return {"foreign": [], "invest": []}

    if "stock_id" not in df.columns or "name" not in df.columns:
        print("Missing expected columns:", df.columns.tolist())
        return {"foreign": [], "invest": []}

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    latest_dates = sorted(df[date_col].dt.date.unique())[-days:]
    df = df[df[date_col].dt.date.isin(latest_dates)].copy()
    df["name_norm"] = df["name"].map(_normalize_name)

    foreign_df = df[df["name_norm"].str.contains("foreign", na=False)].copy()
    invest_df = df[df["name_norm"].str.contains("investment", na=False)].copy()

    def build_rank(sub_df):
        if sub_df.empty:
            return []

        rank = (
            sub_df.groupby("stock_id", as_index=False)[buy_sell_col]
            .sum()
            .sort_values(buy_sell_col, ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

        result = []
        for _, row in rank.iterrows():
            result.append({
                "stock_id": str(row["stock_id"]),
                "buy_sell": int(row[buy_sell_col]) if pd.notna(row[buy_sell_col]) else 0
            })
        return result

    return {
        "foreign": build_rank(foreign_df),
        "invest": build_rank(invest_df),
    }