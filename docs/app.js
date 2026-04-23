const API_BASE = "https://stock-project-bnio.onrender.com";

const state = {
  stocks: { trend: [], setup: [], reversal: [] },
  funds: { foreign: [], invest: [], message: "" },
  currentView: "dashboard",
  search: "",
  sort: "stock-asc",
};

const $ = (sel) => document.querySelector(sel);

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadAll();
});

function bindEvents() {
  document.querySelectorAll(".nav-link").forEach((btn) => {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  });

  $("#refreshBtn").addEventListener("click", loadAll);

  $("#searchInput").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toUpperCase();
    renderCurrentView();
  });

  $("#sortSelect").addEventListener("change", (e) => {
    state.sort = e.target.value;
    renderCurrentView();
  });
}

async function loadAll() {
  setStatus(false, "連線中...");

  try {
    const [stocksRes, fundsRes] = await Promise.all([
      fetch(`${API_BASE}/api/stocks`),
      fetch(`${API_BASE}/api/funds`).catch(() => null),
    ]);

    if (!stocksRes.ok) throw new Error("股票 API 讀取失敗");

    state.stocks = await stocksRes.json();

    if (fundsRes && fundsRes.ok) {
      state.funds = await fundsRes.json();
    } else {
      state.funds = { foreign: [], invest: [], message: "法人 API 讀取失敗" };
    }

    updateSummary();
    renderDashboard();
    renderCurrentView();
    setStatus(true, "API 已連線");
    $("#lastUpdated").textContent = new Date().toLocaleString("zh-TW");
  } catch (err) {
    console.error(err);
    setStatus(false, "API 連線失敗");
    alert("資料讀取失敗，請檢查 API_BASE 是否正確，或 Render 是否仍在喚醒中。");
  }
}

function setStatus(ok, text) {
  const dot = document.querySelector(".dot");
  dot.classList.toggle("online", ok);
  $("#apiStatusText").textContent = text;
}

function updateSummary() {
  const t = state.stocks.trend?.length || 0;
  const s = state.stocks.setup?.length || 0;
  const r = state.stocks.reversal?.length || 0;

  $("#countTrend").textContent = t;
  $("#countSetup").textContent = s;
  $("#countReversal").textContent = r;

  $("#dashTrend").textContent = t;
  $("#dashSetup").textContent = s;
  $("#dashReversal").textContent = r;

  const total = Math.max(t + s + r, 1);
  $("#barTrend").style.width = `${(t / total) * 100}%`;
  $("#barSetup").style.width = `${(s / total) * 100}%`;
  $("#barReversal").style.width = `${(r / total) * 100}%`;
}

function renderDashboard() {
  renderMiniList("#previewTrend", state.stocks.trend);
  renderMiniList("#previewSetup", state.stocks.setup);
  renderMiniList("#previewReversal", state.stocks.reversal);
}

function renderMiniList(selector, rows) {
  const el = $(selector);
  const list = (rows || []).slice(0, 5);

  if (!list.length) {
    el.innerHTML = '<div class="empty-state">目前沒有資料</div>';
    return;
  }

  el.innerHTML = list.map((row) => `
    <div class="mini-item">
      <strong>${row.StockID || row.Stock || row.stock_id || "-"} ${row.Name || ""}</strong>
      <span>價格：${safeNum(row.Close || row.close)}　成交量：${safeNum(row.Volume || row.volume)}</span>
    </div>
  `).join("");
}

function setView(view) {
  state.currentView = view;

  document.querySelectorAll(".nav-link").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });

  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active-view", section.id === `view-${view}`);
  });

  renderCurrentView();
}

function renderCurrentView() {
  if (state.currentView === "trend") {
    const rows = processRows(state.stocks.trend);
    $("#resultBadge").textContent = `${rows.length} 筆`;
    $("#tableTrend").innerHTML = createStockTable(rows, "trend");
  } else if (state.currentView === "setup") {
    const rows = processRows(state.stocks.setup);
    $("#resultBadge").textContent = `${rows.length} 筆`;
    $("#tableSetup").innerHTML = createStockTable(rows, "setup");
  } else if (state.currentView === "reversal") {
    const rows = processRows(state.stocks.reversal);
    $("#resultBadge").textContent = `${rows.length} 筆`;
    $("#tableReversal").innerHTML = createStockTable(rows, "reversal");
  } else if (state.currentView === "funds") {
    const foreign = processFundRows(state.funds.foreign);
    const invest = processFundRows(state.funds.invest);
    $("#resultBadge").textContent = `${foreign.length + invest.length} 筆`;

    if (state.funds.message && foreign.length === 0 && invest.length === 0) {
      $("#tableForeign").innerHTML = `<div class="empty-state">${state.funds.message}</div>`;
      $("#tableInvest").innerHTML = `<div class="empty-state">${state.funds.message}</div>`;
    } else {
      $("#tableForeign").innerHTML = createFundTable(foreign, "外資");
      $("#tableInvest").innerHTML = createFundTable(invest, "投信");
    }
  } else {
    const total =
      (state.stocks.trend?.length || 0) +
      (state.stocks.setup?.length || 0) +
      (state.stocks.reversal?.length || 0);

    $("#resultBadge").textContent = `${total} 筆`;
  }
}

function processRows(rows) {
  let result = [...(rows || [])];

  if (state.search) {
    result = result.filter((row) =>
      String(row.Stock || row.StockID || row.stock_id || "").toUpperCase().includes(state.search)
    );
  }

  result.sort((a, b) => {
    const stockA = String(a.StockID || a.Stock || a.stock_id || "");
    const stockB = String(b.StockID || b.Stock || b.stock_id || "");
    const closeA = Number(a.Close || a.close || 0);
    const closeB = Number(b.Close || b.close || 0);
    const volA = Number(a.Volume || a.volume || 0);
    const volB = Number(b.Volume || b.volume || 0);

    switch (state.sort) {
      case "stock-desc":
        return stockB.localeCompare(stockA);
      case "close-desc":
        return closeB - closeA;
      case "close-asc":
        return closeA - closeB;
      case "volume-desc":
        return volB - volA;
      case "volume-asc":
        return volA - volB;
      default:
        return stockA.localeCompare(stockB);
    }
  });

  return result;
}

function processFundRows(rows) {
  let result = [...(rows || [])];

  if (state.search) {
    result = result.filter((row) =>
      String(row.stock_id || "").toUpperCase().includes(state.search)
    );
  }

  result.sort((a, b) => Number(b.buy_sell || 0) - Number(a.buy_sell || 0));
  return result;
}

function createStockTable(rows, type) {
  if (!rows.length) return '<div class="empty-state">沒有符合條件的股票</div>';

  const pillClass = {
    trend: "pill-trend",
    setup: "pill-setup",
    reversal: "pill-reversal",
  }[type];

  const pillText = {
    trend: "趨勢穩健",
    setup: "蓄勢待發",
    reversal: "反轉雷達",
  }[type];

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>股票代碼</th>
            <th>名稱</th>
            <th>分類</th>
            <th>收盤價</th>
            <th>成交量</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${row.StockID || row.Stock || row.stock_id || "-"}</td>
              <td>${row.Name || "-"}</td>
              <td><span class="pill ${pillClass}">${pillText}</span></td>
              <td>${safeNum(row.Close || row.close)}</td>
              <td>${safeNum(row.Volume || row.volume)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function createFundTable(rows, label) {
  if (!rows.length) {
    return '<div class="empty-state">目前沒有法人資料</div>';
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>股票代碼</th>
            <th>${label}買賣超</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${row.stock_id || "-"}</td>
              <td>${safeNum(row.buy_sell)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function safeNum(v) {
  if (v === null || v === undefined || v === "") return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("zh-TW");
}