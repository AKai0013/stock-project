from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import json

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
    try:
        foreign = load_csv("data/foreign.csv")
        invest = load_csv("data/invest.csv")
        meta = load_json("data/funds_meta.json", default={})

        return jsonify({
            "foreign": foreign,
            "invest": invest,
            "message": meta.get("message", "法人資料尚未建立")
        })
    except Exception as e:
        print("Funds route failed:", e)
        return jsonify({
            "foreign": [],
            "invest": [],
            "message": f"/api/funds 路由錯誤：{str(e)}"
        }), 200


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
                    "AssetType": row.get("AssetType", ""),
                    "IsETF": bool(row.get("IsETF", False)),
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

        def to_float(v, default=0):
            try:
                if v is None or v == "":
                    return default
                return float(v)
            except Exception:
                return default

        def score_stock(row, category):
            stock_id = str(row.get("StockID", ""))
            is_etf = str(row.get("IsETF", "False")).lower() in ["true", "1", "yes"]

            change_pct = to_float(row.get("ChangePct", 0))
            volume = to_float(row.get("Volume", 0))
            rsi = to_float(row.get("RSI14", 50))
            near_high20 = to_float(row.get("NearHigh20Pct", 0))
            near_high120 = to_float(row.get("NearHigh120Pct", 0))

            score = 0.0

            # 1. 類別基礎分
            if category == "trend":
                score += 40
            elif category == "setup":
                score += 26
            elif category == "reversal":
                score += 18

            # 2. 漲幅分
            if change_pct > 0:
                score += min(change_pct * 2.5, 20)
            else:
                score += max(change_pct * 1.2, -10)

            # 3. 量能分
            if volume >= 3000000:
                score += 18
            elif volume >= 1500000:
                score += 14
            elif volume >= 800000:
                score += 10
            elif volume >= 300000:
                score += 6
            else:
                score += 0

            # 4. 接近高點強度
            if near_high20 >= 99:
                score += 14
            elif near_high20 >= 97:
                score += 10
            elif near_high20 >= 95:
                score += 6

            if near_high120 >= 90:
                score += 10
            elif near_high120 >= 85:
                score += 6

            # 5. RSI 強度
            if 55 <= rsi <= 72:
                score += 10
            elif 50 <= rsi < 55:
                score += 5
            elif rsi > 80:
                score -= 4

            # 6. 法人加分
            if stock_id in foreign_ids:
                score += 10
            if stock_id in invest_ids:
                score += 8

            # 7. ETF 調整
            # ETF波動通常較穩，適度扣一點，避免全部被ETF吃榜
            if is_etf:
                score -= 4

            # 8. 弱勢股扣分
            if change_pct < -3:
                score -= 8

            return round(score, 2)

        def add_rows(rows, category):
            for row in rows:
                item = dict(row)
                stock_id = str(item.get("StockID", ""))

                item["category"] = category
                item["hasForeign"] = stock_id in foreign_ids
                item["hasInvest"] = stock_id in invest_ids
                item["score"] = score_stock(item, category)

                all_rows.append(item)

        add_rows(trend, "trend")
        add_rows(setup, "setup")
        add_rows(reversal, "reversal")

        # 同一檔只留最高分
        best_map = {}
        for row in all_rows:
            stock_id = str(row.get("StockID", ""))
            if stock_id not in best_map or row["score"] > best_map[stock_id]["score"]:
                best_map[stock_id] = row

        final_rows = list(best_map.values())
        final_rows.sort(key=lambda x: x["score"], reverse=True)

        stock_top10 = [x for x in final_rows if str(x.get("IsETF", "False")).lower() not in ["true", "1", "yes"]][:10]
        etf_top10 = [x for x in final_rows if str(x.get("IsETF", "False")).lower() in ["true", "1", "yes"]][:10]

        return jsonify({
            "top10": final_rows[:10],
            "stock_top10": stock_top10,
            "etf_top10": etf_top10,
            "message": meta.get("message", "")
        })

    except Exception as e:
        print("Top10 API failed:", e)
        return jsonify({
            "top10": [],
            "stock_top10": [],
            "etf_top10": [],
            "message": f"最強10檔 API 錯誤：{str(e)}"
        }), 200


if __name__ == "__main__":
    app.run()