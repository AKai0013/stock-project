from datetime import datetime, timedelta
import requests


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


def _fetch_twse_t86(date_str):
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"

    params = {
        "date": date_str,
        "selectType": "ALLBUT0999",
        "response": "json"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        # 🔥 關鍵：timeout 改很短
        resp = requests.get(url, params=params, headers=headers, timeout=5)

        if resp.status_code != 200:
            return []

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

    except Exception as e:
        print("TWSE fetch failed:", e)
        return []


def _find_latest_available_rows(lookback_days=3):
    today = datetime.today().date()

    for i in range(lookback_days):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y%m%d")

        rows = _fetch_twse_t86(date_str)

        if rows:
            return rows, d.strftime("%Y-%m-%d"), ""

    return [], None, "TWSE 連線逾時或暫時無法取得資料"


def _build_twse_rank(rows, top_n=20):
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


def get_funds_rank(top_n=20):
    try:
        rows, latest_date, err = _find_latest_available_rows(lookback_days=10)

        if err:
            return {
                "foreign": [],
                "invest": [],
                "message": err
            }

        if not rows:
            return {
                "foreign": [],
                "invest": [],
                "message": "目前查無官方法人資料"
            }

        foreign, invest = _build_twse_rank(rows, top_n=top_n)

        return {
            "foreign": foreign,
            "invest": invest,
            "message": f"資料來源：TWSE 官方三大法人買賣超日報，最新交易日 {latest_date}"
        }

    except Exception as e:
        print("get_funds_rank error:", e)
        return {
            "foreign": [],
            "invest": [],
            "message": f"法人資料處理失敗：{str(e)}"
        }