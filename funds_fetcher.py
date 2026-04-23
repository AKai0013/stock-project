from datetime import datetime, timedelta
import os
import json
import requests
import pandas as pd

DATA_DIR = "data"


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _to_int(value):
    if value is None:
        return 0

    s = str(value).strip().replace(",", "")

    if s in ["", "--", "---", "None", "nan"]:
        return 0

    s = s.replace("X", "").replace("x", "")

    try:
        return int(float(s))
    except Exception:
        return 0


def _safe_get(row, keys):
    for k in keys:
        if k in row:
            return row[k]
    return ""


def fetch_twse_t86(date_str):
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"
    params = {
        "date": date_str,
        "selectType": "ALLBUT0999",
        "response": "json"
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()

    data = resp.json()

    rows = data.get("data", [])
    fields = data.get("fields", [])

    if not rows or not fields:
        return []

    result = []
    for r in rows:
        row = {}
        for i, field in enumerate(fields):
            row[field] = r[i] if i < len(r) else ""
        result.append(row)

    return result


def find_latest_rows(lookback_days=10):
    today = datetime.today().date()
    last_error = ""

    for i in range(lookback_days):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y%m%d")

        try:
            rows = fetch_twse_t86(date_str)
            if rows:
                return rows, d.strftime("%Y-%m-%d"), ""
        except Exception as e:
            last_error = str(e)

    return [], None, last_error or "查無資料"


def build_rank(rows, top_n=50):
    foreign_result = []
    invest_result = []

    for row in rows:
        stock_id = _safe_get(row, ["證券代號", "代號"])
        name = _safe_get(row, ["證券名稱", "名稱"])

        if not stock_id:
            continue

        foreign_net = _to_int(_safe_get(row, [
            "外陸資買賣超股數(不含外資自營商)",
            "外資及陸資(不含外資自營商)買賣超股數",
            "外資及陸資買賣超股數(不含外資自營商)",
        ]))

        invest_net = _to_int(_safe_get(row, [
            "投信買賣超股數",
            "投信買賣超股數(總)",
        ]))

        foreign_result.append({
            "stock_id": str(stock_id),
            "name": str(name),
            "buy_sell": foreign_net
        })

        invest_result.append({
            "stock_id": str(stock_id),
            "name": str(name),
            "buy_sell": invest_net
        })

    foreign_result = [x for x in foreign_result if x["buy_sell"] > 0]
    invest_result = [x for x in invest_result if x["buy_sell"] > 0]

    foreign_result.sort(key=lambda x: x["buy_sell"], reverse=True)
    invest_result.sort(key=lambda x: x["buy_sell"], reverse=True)

    return foreign_result[:top_n], invest_result[:top_n]


def save_outputs(foreign, invest, message, latest_date):
    ensure_data_dir()

    pd.DataFrame(foreign).to_csv(
        os.path.join(DATA_DIR, "foreign.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    pd.DataFrame(invest).to_csv(
        os.path.join(DATA_DIR, "invest.csv"),
        index=False,
        encoding="utf-8-sig"
    )

    meta = {
        "message": message,
        "latest_date": latest_date or ""
    }

    with open(os.path.join(DATA_DIR, "funds_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main():
    rows, latest_date, err = find_latest_rows(lookback_days=10)

    if not rows:
        print("法人資料抓取失敗:", err)
        save_outputs([], [], f"TWSE 官方暫時無法取得法人資料：{err}", latest_date)
        return

    foreign, invest = build_rank(rows, top_n=50)
    message = f"資料來源：TWSE 官方三大法人買賣超日報，最新交易日 {latest_date}"
    save_outputs(foreign, invest, message, latest_date)

    print("法人資料完成")
    print("foreign:", len(foreign))
    print("invest:", len(invest))


if __name__ == "__main__":
    main()