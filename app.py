from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import json
import os

app = Flask(__name__)
app.json.ensure_ascii = False
CORS(app)


def load_csv(file):
    try:
        return pd.read_csv(file).to_dict("records")
    except Exception as e:
        print("CSV load failed:", file, e)
        return []


def load_json(file, default=None):
    if default is None:
        default = {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("JSON load failed:", file, e)
        return default


@app.route("/")
def home():
    return "API is running"


@app.route("/api/stocks")
def stocks():
    return jsonify({
        "trend": load_csv("data/trend.csv"),
        "setup": load_csv("data/setup.csv"),
        "reversal": load_csv("data/reversal.csv")
    })


@app.route("/api/funds")
def funds():
    foreign = load_csv("data/foreign.csv")
    invest = load_csv("data/invest.csv")
    meta = load_json("data/funds_meta.json", default={})

    return jsonify({
        "foreign": foreign,
        "invest": invest,
        "message": meta.get("message", "法人資料尚未建立")
    })


@app.route("/api/strong")
def strong():
    try:
        trend_rows = load_csv("data/trend.csv")
        foreign_rows = load_csv("data/foreign.csv")
        invest_rows = load_csv("data/invest.csv")
        meta = load_json("data/funds_meta.json", default={})

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
            "message": meta.get("message", "")
        })

    except Exception as e:
        print("Strong route failed:", e)
        return jsonify({
            "strong": [],
            "message": f"/api/strong 路由錯誤：{str(e)}"
        }), 200


@app.route("/api/top10")
def top10():
    try:
        trend = load_csv("data/trend.csv")
        setup = load_csv("data/setup.csv")
        reversal = load_csv("data/reversal.csv")
        foreign_rows = load_csv("data/foreign.csv")
        invest_rows = load_csv("data/invest.csv")
        meta = load_json("data/funds_meta.json", default={})

        foreign_ids = set(str(row.get("stock_id", "")) for row in foreign_rows)
        invest_ids = set(str(row.get("stock_id", "")) for row in invest_rows)

        all_rows = []

        def score_stock(row, category):
            score = 0.0

            change_pct = float(row.get("ChangePct", 0) or 0)
            volume = float(row.get("Volume", 0) or 0)
            stock_id = str(row.get("StockID", ""))

            if category == "trend":
                score += 40
            elif category == "setup":
                score += 28
            elif category == "reversal":
                score += 20

            score += change_pct * 2.2
            score += min(volume / 100000, 20)

            if stock_id in foreign_ids:
                score += 12
            if stock_id in invest_ids:
                score += 10

            if change_pct < -3:
                score -= 8

            return round(score, 2)

        for row in trend:
            row = dict(row)
            row["score"] = score_stock(row, "trend")
            row["category"] = "trend"
            row["hasForeign"] = str(row.get("StockID", "")) in foreign_ids
            row["hasInvest"] = str(row.get("StockID", "")) in invest_ids
            all_rows.append(row)

        for row in setup:
            row = dict(row)
            row["score"] = score_stock(row, "setup")
            row["category"] = "setup"
            row["hasForeign"] = str(row.get("StockID", "")) in foreign_ids
            row["hasInvest"] = str(row.get("StockID", "")) in invest_ids
            all_rows.append(row)

        for row in reversal:
            row = dict(row)
            row["score"] = score_stock(row, "reversal")
            row["category"] = "reversal"
            row["hasForeign"] = str(row.get("StockID", "")) in foreign_ids
            row["hasInvest"] = str(row.get("StockID", "")) in invest_ids
            all_rows.append(row)

        best_map = {}
        for row in all_rows:
            stock_id = str(row.get("StockID", ""))
            if stock_id not in best_map or row["score"] > best_map[stock_id]["score"]:
                best_map[stock_id] = row

        final_rows = list(best_map.values())
        final_rows.sort(key=lambda x: x["score"], reverse=True)

        return jsonify({
            "top10": final_rows[:10],
            "message": meta.get("message", "")
        })

    except Exception as e:
        print("Top10 API failed:", e)
        return jsonify({
            "top10": [],
            "message": f"最強10檔 API 錯誤：{str(e)}"
        }), 200


if __name__ == "__main__":
    app.run()