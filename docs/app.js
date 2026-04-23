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
  renderMiniList("#previewTrend", state.stocks.trend, "trend");
  renderMiniList("#previewSetup", state.stocks.setup, "setup");
  renderMiniList("#previewReversal", state.stocks.reversal, "reversal");
}

function renderMiniList(selector, rows, type) {
  const el = $(selector);
  const list = (rows || []).slice(0, 5);

  if (!list.length) {
    el.innerHTML = '<div class="empty-state">目前沒有資料</div>';
    return;
  }

  const badgeText = {
    trend: "趨勢穩健",
    setup: "蓄勢待發",
    reversal: "反轉雷達",
  }[type];

  const badgeClass = {
    trend: "pill-trend",
    setup: "pill-setup",
    reversal: "pill-reversal",
  }[type];

  el.innerHTML = list.map((row) => `
    <div class="mini-item stock-card">
      <div class="stock-top">
        <div>
          <div class="stock-code">${row.StockID || row.Stock || "-"}</div>
          <div class="stock-name">${row.Name || ""}</div>
        </div>
        <span class="pill ${badgeClass}">${badgeText}</span>
      </div>

      <div class="stock-price-line">
        <span class="stock-price">${safeNum(row.Close)}</span>
        <span class="stock-change ${getChangeClass(row.Change)}">
          ${formatSigned(row.Change)} (${formatSigned(row.ChangePct)}%)
        </span>
      </div>

      <div class="stock-meta">
        <span>成交量：${safeNum(row.Volume)}</span>
      </div>
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
      const html = `
        <div class="notice-card">
          <div class="notice-title">法人資料目前不可用</div>
          <div class="notice-text">${state.funds.message}</div>
        </div>
      `;
      $("#tableForeign").innerHTML = html;
      $("#tableInvest").innerHTML = html;
    } else {
      $("#tableForeign").innerHTML = createFundTable(foreign, "外資");
      $("#tableInvest").innerHTML = createFundTable(invest, "投信");
    }
  } else if (state.currentView === "strong") {
    const rows = buildStrongRows();
    $("#resultBadge").textContent = `${rows.length} 筆`;
    $("#tableStrong").innerHTML = createStrongTable(rows);
  } else {
    const total =
      (state.stocks.trend?.length || 0) +
      (state.stocks.setup?.length || 0) +
      (state.stocks.reversal?.length || 0);

    $("#resultBadge").textContent = `${total} 筆`;
  }
}

function buildStrongRows() {
  const trendRows = state.stocks.trend || [];
  const foreignIds = new Set((state.funds.foreign || []).map(x => String(x.stock_id)));
  const investIds = new Set((state.funds.invest || []).map(x => String(x.stock_id)));

  let rows = trendRows.filter(row => {
    const id = String(row.StockID || "");
    return foreignIds.has(id) || investIds.has(id);
  }).map(row => {
    const id = String(row.StockID || "");
    return {
      ...row,
      hasForeign: foreignIds.has(id),
      hasInvest: investIds.has(id),
    };
  });

  if (state.search) {
    rows = rows.filter((row) =>
      String(row.StockID || row.Stock || "").toUpperCase().includes(state.search)
    );
  }

  rows.sort((a, b) => Number(b.ChangePct || 0) - Number(a.ChangePct || 0));
  return rows;
}

function processRows(rows) {
  let result = [...(rows || [])];

  if (state.search) {
    result = result.filter((row) =>
      String(row.StockID || row.Stock || "").toUpperCase().includes(state.search)
    );
  }

  result.sort((a, b) => {
    const stockA = String(a.StockID || a.Stock || "");
    const stockB = String(b.StockID || b.Stock || "");
    const closeA = Number(a.Close || 0);
    const closeB = Number(b.Close || 0);
    const volA = Number(a.Volume || 0);
    const volB = Number(b.Volume || 0);
    const pctA = Number(a.ChangePct || 0);
    const pctB = Number(b.ChangePct || 0);

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
      case "change-desc":
        return pctB - pctA;
      case "change-asc":
        return pctA - pctB;
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
            <th>漲跌</th>
            <th>漲跌幅</th>
            <th>成交量</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${row.StockID || row.Stock || "-"}</td>
              <td>${row.Name || "-"}</td>
              <td><span class="pill ${pillClass}">${pillText}</span></td>
              <td>${safeNum(row.Close)}</td>
              <td class="${getChangeClass(row.Change)}">${formatSigned(row.Change)}</td>
              <td class="${getChangeClass(row.ChangePct)}">${formatSigned(row.ChangePct)}%</td>
              <td>${safeNum(row.Volume)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function createStrongTable(rows) {
  if (!rows.length) {
    return '<div class="empty-state">目前沒有「主力＋趨勢」交集資料</div>';
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>股票代碼</th>
            <th>名稱</th>
            <th>收盤價</th>
            <th>漲跌幅</th>
            <th>外資</th>
            <th>投信</th>
            <th>成交量</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${row.StockID || "-"}</td>
              <td>${row.Name || "-"}</td>
              <td>${safeNum(row.Close)}</td>
              <td class="${getChangeClass(row.ChangePct)}">${formatSigned(row.ChangePct)}%</td>
              <td>${row.hasForeign ? "✓" : "-"}</td>
              <td>${row.hasInvest ? "✓" : "-"}</td>
              <td>${safeNum(row.Volume)}</td>
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
          ${rows.map((row, index) => `
            <tr>
              <td>#${index + 1}　${row.stock_id || "-"}</td>
              <td>${safeNum(row.buy_sell)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function getChangeClass(v) {
  const n = Number(v || 0);
  if (n > 0) return "up";
  if (n < 0) return "down";
  return "flat";
}

function formatSigned(v) {
  if (v === null || v === undefined || v === "") return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  if (n > 0) return `+${n.toLocaleString("zh-TW")}`;
  return n.toLocaleString("zh-TW");
}

function safeNum(v) {
  if (v === null || v === undefined || v === "") return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("zh-TW");
}