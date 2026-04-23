def fetch_twse_t86(date_str):
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.twse.com.tw/"
    }

    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code != 200:
        print("HTTP錯誤:", resp.status_code)
        return []

    data = resp.json()

    if "data" not in data:
        print("沒有 data 欄位:", data)
        return []

    rows = data["data"]
    fields = data["fields"]

    result = []
    for r in rows:
        row = {}
        for i, field in enumerate(fields):
            row[field] = r[i] if i < len(r) else ""
        result.append(row)

    print("抓到筆數:", len(result))

    return result