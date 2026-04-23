from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
from funds import get_funds_rank

app = Flask(__name__)
app.json.ensure_ascii = False
CORS(app)


def load(file):
    try:
        return pd.read_csv(file).to_dict("records")
    except Exception as e:
        print("CSV load failed:", file, e)
        return []


@app.route("/")
def home():
    return "API is running"


@app.route("/api/stocks")
def stocks():
    return jsonify({
        "trend": load("data/trend.csv"),
        "setup": load("data/setup.csv"),
        "reversal": load("data/reversal.csv")
    })


@app.route("/api/funds")
def funds():
    return jsonify(get_funds_rank(top_n=20))


@app.route("/api/strong")
def strong():
    try:
        # 先讀趨勢穩健股票
        trend_rows = load("data/trend.csv")

        # 再讀法人資料
        funds_data = get_funds_rank(top_n=50)

        foreign_rows = funds_data.get("foreign", [])
        invest_rows = funds_data.get("invest", [])

        # 如果法人資料本身有提示訊息，也一起帶出去
        message = funds_data.get("message", "")

        foreign_ids = set(str(row.get("stock_id", "")) for row in foreign_rows)
        invest_ids = set(str(row.get("stock_id", "")) for row in invest_rows)

        strong_rows = []

        for row in trend_rows:
            stock_id = str(row.get("StockID", ""))

            has_foreign = stock_id in foreign_ids
            has_invest = stock_id in invest_ids

            if has_foreign or has_invest:
                strong_rows.append({
                    "Stock": row.get("Stock", ""),
                    "StockID": stock_id,
                    "Name": row.get("Name", ""),
                    "Close": row.get("Close", ""),
                    "Change": row.get("Change", ""),
                    "ChangePct": row.get("ChangePct", ""),
                    "Volume": row.get("Volume", ""),
                    "hasForeign": has_foreign,
                    "hasInvest": has_invest
                })

        return jsonify({
            "strong": strong_rows,
            "message": message
        })

    except Exception as e:
        print("Strong API failed:", e)
        return jsonify({
            "strong": [],
            "message": f"主力＋趨勢 API 錯誤：{str(e)}"
        })


if __name__ == "__main__":
    app.run()