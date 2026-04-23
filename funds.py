from datetime import datetime, timedelta
import requests


def _to_int(value):
    """
    把字串數字轉成 int，處理:
    - 1,234
    - --
    - X0.00
    - 空字串
    """
    if value is None:
        return 0

    s = str(value).strip().replace(",", "")

    if s in ["", "--", "---", "None", "nan"]:
        return 0

    # 去掉可能的特殊符號
    s = s.replace("X", "").replace("x", "")

    try:
        return int(float(s))
    except Exception:
        return 0


def _safe_get(row, keys):
    """
    從 row 裡用多個可能欄位名找值
    """
    for k in keys:
        if k in row:
            return row[k]
    return ""


def _fetch_twse_t86(date_str):
    """
    抓 TWSE 官方三大法人買賣超日報
    date_str: YYYYMMDD
    使用 ALLBUT0999，會包含一般上市股票與 ETF，
    並排除權證等衍生性商品。
    """
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"

    params = {
        "date": date_str,
        "selectType": "ALLBUT0999",
        "response": "json"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()

    data = resp.json()

    # 常見成功格式會有 data 欄
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


def _find_latest_available_rows(lookback_days=10):
    """
    往前回找最近有資料的交易日
    """
    today = datetime.today().date()

    for i in range(lookback_days):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y%m%d")

        try:
            rows = _fetch_twse_t86(date_str)
            if rows:
                return rows, d.strftime("%Y-%m-%d"), ""
        except Exception as e:
            last_error = str(e)

    return [], None, f"官方法人資料抓取失敗：{last_error if 'last_error' in locals() else '查無資料'}"


def _build_twse_rank(rows, top_n=20):
    """
    從 TWSE T86 資料中產生:
    - foreign 外資排行
    - invest 投信排行
    """
    foreign_result = []
    invest_result = []

    for row in rows:
        stock_id = _safe_get(row, ["證券代號", "代號"])
        name = _safe_get(row, ["證券名稱", "名稱"])

        if not stock_id:
            continue

        # 外資（不含外資自營商）淨買賣超
        foreign_net = _to_int(_safe_get(row, [
            "外陸資買賣超股數(不含外資自營商)",
            "外資及陸資(不含外資自營商)買賣超股數",
            "外資及陸資買賣超股數(不含外資自營商)",
        ]))

        # 投信淨買賣超
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

    # 只保留淨買超 > 0
    foreign_result = [x for x in foreign_result if x["buy_sell"] > 0]
    invest_result = [x for x in invest_result if x["buy_sell"] > 0]

    # 排序
    foreign_result.sort(key=lambda x: x["buy_sell"], reverse=True)
    invest_result.sort(key=lambda x: x["buy_sell"], reverse=True)

    return foreign_result[:top_n], invest_result[:top_n]


def get_funds_rank(top_n=20):
    """
    回傳格式保持與你目前前端相容:
    {
      "foreign": [...],
      "invest": [...],
      "message": ""
    }
    """
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