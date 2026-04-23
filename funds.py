from FinMind.data import DataLoader
from datetime import datetime

api = DataLoader()

def get_top_buyers():
    today = datetime.today().strftime("%Y-%m-%d")

    df = api.taiwan_stock_institutional_investors(
        start_date=today,
        end_date=today
    )

    foreign = df[df["name"] == "Foreign_Investor"]
    invest = df[df["name"] == "Investment_Trust"]

    foreign_rank = foreign.groupby("stock_id")["buy_sell"].sum().nlargest(20).reset_index()
    invest_rank = invest.groupby("stock_id")["buy_sell"].sum().nlargest(20).reset_index()

    return foreign_rank.to_dict("records"), invest_rank.to_dict("records")