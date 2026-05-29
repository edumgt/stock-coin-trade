/* ── DOM refs ──────────────────────────────────────────────────────────────── */
const stockSymbol     = document.getElementById("stockSymbol");
const orderQty        = document.getElementById("orderQty");
const quotePrice      = document.getElementById("quotePrice");
const quoteChange     = document.getElementById("quoteChange");
const quoteChangeRate = document.getElementById("quoteChangeRate");
const quoteVolume     = document.getElementById("quoteVolume");
const quoteMarket     = document.getElementById("quoteMarket");
const accountCash     = document.getElementById("accountCash");
const accountAsset    = document.getElementById("accountAsset");
const accountPnlRate  = document.getElementById("accountPnlRate");
const positionsBody   = document.getElementById("positionsBody");
const stockMessage    = document.getElementById("stockMessage");
const chartStockName  = document.getElementById("chartStockName");
const dataSourceBadge = document.getElementById("dataSourceBadge");

/* ── State ─────────────────────────────────────────────────────────────────── */
let currentPeriod       = "1m";
let candleChart         = null;
let volumeChart         = null;
let portfolioChart      = null;
let currentMarketFilter = "ALL";
let allStocks           = [];
let lastPositions       = [];
let lastCash            = 10_000_000;
let watchlist           = new Set(JSON.parse(localStorage.getItem("stockWatchlist") || "[]"));

/* ── Formatters ────────────────────────────────────────────────────────────── */
function formatKrw(value) {
    return Number(value).toLocaleString("ko-KR") + "원";
}
function formatVolume(v) {
    if (v >= 100_000_000) return (v / 100_000_000).toFixed(1) + "억주";
    if (v >= 10_000)      return (v / 10_000).toFixed(1) + "만주";
    return Number(v).toLocaleString("ko-KR") + "주";
}
function colorClass(val) {
    return val > 0 ? "#e11d48" : val < 0 ? "#2563eb" : "#64748b";
}

/* ── API helpers ───────────────────────────────────────────────────────────── */
async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const raw = await response.text();
    let data = null;
    try { data = raw.trim() ? JSON.parse(raw) : null; }
    catch (e) { throw new Error("응답 형식이 올바르지 않습니다."); }
    if (!response.ok) throw new Error(data?.message || "요청에 실패했습니다.");
    if (data === null) throw new Error("서버 응답이 비어 있습니다.");
    return data;
}

function showMessage(msg, isError = false) {
    stockMessage.textContent = msg;
    stockMessage.className = isError ? "text-xs text-rose-600" : "text-xs text-emerald-600";
}

/* ── Watchlist (토스증권·Robinhood 참고) ──────────────────────────────────── */
function saveWatchlist() {
    localStorage.setItem("stockWatchlist", JSON.stringify([...watchlist]));
}

function updateWatchlistBtn(symbol) {
    const btn = document.getElementById("watchlistBtn");
    if (!btn) return;
    const inList = watchlist.has(symbol);
    btn.textContent = inList ? "⭐" : "☆";
    btn.title  = inList ? "관심종목 해제" : "관심종목 추가";
    btn.style.color = inList ? "#FFCC00" : "#888";
}

document.getElementById("watchlistBtn").addEventListener("click", () => {
    const sym = stockSymbol.value;
    if (!sym) return;
    if (watchlist.has(sym)) {
        watchlist.delete(sym);
    } else {
        watchlist.add(sym);
    }
    saveWatchlist();
    updateWatchlistBtn(sym);
    if (currentMarketFilter === "WATCH") rebuildSelectOptions();
});

/* ── Stock list + filtering (eToro·키움증권 참고) ──────────────────────────── */
async function loadStockList() {
    const data = await requestJson("/api/stocks/list");
    allStocks = data.stocks;
    rebuildSelectOptions();
}

function getFilteredStocks() {
    const search = (document.getElementById("stockSearch")?.value || "").toLowerCase().trim();
    return allStocks.filter(s => {
        if (currentMarketFilter === "KOSPI"  && s.market !== "KOSPI")  return false;
        if (currentMarketFilter === "KOSDAQ" && s.market !== "KOSDAQ") return false;
        if (currentMarketFilter === "WATCH"  && !watchlist.has(s.symbol)) return false;
        if (search && !s.name.toLowerCase().includes(search) && !s.symbol.toLowerCase().includes(search)) return false;
        return true;
    });
}

function rebuildSelectOptions() {
    const filtered = getFilteredStocks();
    const prevVal  = stockSymbol.value;
    stockSymbol.innerHTML = "";

    if (filtered.length === 0) {
        const opt = document.createElement("option");
        opt.textContent = currentMarketFilter === "WATCH"
            ? "관심종목을 추가해 주세요 (☆ 버튼)" : "검색 결과 없음";
        opt.disabled = true;
        stockSymbol.appendChild(opt);
        return;
    }

    const markets = [...new Set(filtered.map(s => s.market))];
    markets.forEach(market => {
        const group = document.createElement("optgroup");
        group.label = market;
        filtered.filter(s => s.market === market).forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.symbol;
            opt.textContent = `${s.name} (${s.symbol})`;
            if (s.symbol === prevVal) opt.selected = true;
            group.appendChild(opt);
        });
        stockSymbol.appendChild(group);
    });

    if (!filtered.some(s => s.symbol === prevVal) && filtered.length > 0) {
        stockSymbol.value = filtered[0].symbol;
        Promise.all([loadQuote(), loadChart(stockSymbol.value, currentPeriod)]).catch(console.warn);
    }
}

/* Market tab click */
document.getElementById("marketTabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".market-tab");
    if (!btn) return;
    currentMarketFilter = btn.dataset.market;
    document.querySelectorAll(".market-tab").forEach(t =>
        t.classList.toggle("active", t === btn)
    );
    rebuildSelectOptions();
});

/* Search input */
document.getElementById("stockSearch").addEventListener("input", () => {
    rebuildSelectOptions();
});

/* ── Market Movers (키움증권 참고) ─────────────────────────────────────────── */
async function loadMovers() {
    try {
        const data = await requestJson("/api/stocks/movers");
        renderMoverList("gainers", data.gainers, true);
        renderMoverList("losers",  data.losers,  false);
    } catch (e) {
        console.warn("모버스 로딩 실패:", e.message);
    }
}

function renderMoverList(id, items, isGainer) {
    const el = document.getElementById(id);
    if (!el || !items?.length) return;
    const color = isGainer ? "#e11d48" : "#2563eb";
    el.innerHTML = items.map(item => {
        const rate = Number(item.changeRate);
        const sign = rate >= 0 ? "+" : "";
        return `<div onclick="selectStock('${item.symbol}')"
                     style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border);cursor:pointer;transition:opacity .15s;"
                     onmouseenter="this.style.opacity='.7'" onmouseleave="this.style.opacity='1'">
            <div>
                <span style="font-size:13px;font-weight:700;color:#111827;">${item.name}</span>
                <span style="font-size:11px;color:#6B7280;margin-left:4px;">${item.symbol}</span>
            </div>
            <div style="text-align:right;margin-left:12px;flex-shrink:0;">
                <div style="font-weight:900;font-size:13px;color:${color};">${sign}${rate.toFixed(2)}%</div>
                <div style="font-size:11px;color:#888;">${Number(item.price).toLocaleString("ko-KR")}</div>
            </div>
        </div>`;
    }).join("");
}

async function selectStock(symbol) {
    currentMarketFilter = "ALL";
    document.querySelectorAll(".market-tab").forEach(t =>
        t.classList.toggle("active", t.dataset.market === "ALL")
    );
    rebuildSelectOptions();
    stockSymbol.value = symbol;
    await Promise.all([loadQuote(), loadChart(symbol, currentPeriod)]);
}

/* ── ApexCharts: candle + volume ───────────────────────────────────────────── */
function initCharts() {
    const candleOptions = {
        chart: {
            id: "candle",
            type: "candlestick",
            height: 300,
            toolbar: { show: true, tools: { download: false, pan: true, zoom: true, reset: true } },
            animations: { enabled: false },
            background: "transparent",
        },
        series: [{ name: "Price", data: [] }],
        xaxis: {
            type: "datetime",
            labels: { style: { fontSize: "11px", colors: "#9CA3AF" }, datetimeUTC: false },
            axisBorder: { show: false },
            axisTicks:  { show: false },
        },
        yaxis: {
            tooltip: { enabled: true },
            labels: {
                formatter: (v) => Number(v).toLocaleString("ko-KR"),
                style: { fontSize: "11px", colors: "#9CA3AF" },
            },
        },
        plotOptions: {
            candlestick: {
                colors: { upward: "#e11d48", downward: "#2563eb" },
                wick:   { useFillColor: true },
            },
        },
        grid: { borderColor: "#E5E7EB", strokeDashArray: 4 },
        tooltip: {
            theme: "light",
            custom({ seriesIndex, dataPointIndex, w }) {
                const d = w.globals.initialSeries[seriesIndex].data[dataPointIndex];
                if (!d) return "";
                const dt = new Date(d.x).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
                const [o, h, l, c] = [d.o, d.h, d.l, d.c].map(v => Number(v).toLocaleString("ko-KR"));
                const color = d.c >= d.o ? "#E11D48" : "#2563EB";
                return `<div style="padding:10px 14px;font-size:13px;line-height:1.9;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.10);font-family:'Pretendard',sans-serif;">
                    <div style="color:#6B7280;margin-bottom:6px;font-size:12px;">${dt}</div>
                    <div style="color:#111827;">시가 <b>${o}</b></div>
                    <div style="color:#E11D48;">고가 <b>${h}</b></div>
                    <div style="color:#2563EB;">저가 <b>${l}</b></div>
                    <div style="color:${color};">종가 <b>${c}</b></div>
                </div>`;
            },
        },
    };

    const volumeOptions = {
        chart: {
            id: "volume",
            type: "bar",
            height: 110,
            brush: { target: "candle", enabled: true },
            selection: { enabled: true },
            toolbar: { show: false },
            animations: { enabled: false },
            background: "transparent",
        },
        series: [{ name: "Volume", data: [] }],
        dataLabels: { enabled: false },
        xaxis: {
            type: "datetime",
            labels: { style: { fontSize: "10px", colors: "#9CA3AF" }, datetimeUTC: false },
            axisBorder: { show: false },
            axisTicks:  { show: false },
        },
        yaxis: {
            labels: {
                formatter: (v) => {
                    if (v >= 1_000_000) return (v / 1_000_000).toFixed(0) + "M";
                    if (v >= 1_000)    return (v / 1_000).toFixed(0) + "K";
                    return v;
                },
                style: { fontSize: "10px", colors: "#9CA3AF" },
            },
        },
        fill: { opacity: 0.6 },
        colors: ["rgba(124,92,252,0.65)"],
        grid: { borderColor: "#E5E7EB", strokeDashArray: 4 },
        tooltip: {
            theme: "light",
            x: { format: "yyyy-MM-dd HH:mm" },
            y: { formatter: (v) => Number(v).toLocaleString("ko-KR") + "주" },
        },
    };

    candleChart = new ApexCharts(document.getElementById("candleChart"), candleOptions);
    volumeChart = new ApexCharts(document.getElementById("volumeChart"), volumeOptions);
    candleChart.render();
    volumeChart.render();
}

/* ── Portfolio donut chart (삼성증권 POP 참고) ─────────────────────────────── */
function initPortfolioChart() {
    const options = {
        chart:  { type: "donut", height: 200, background: "transparent" },
        series: [100],
        labels: ["현금 KRW"],
        colors: ["#7C5CFC","#E11D48","#2563EB","#059669","#F59E0B","#8B5CF6","#06B6D4","#EC4899","#14B8A6"],
        plotOptions: {
            pie: { donut: { size: "62%",
                labels: {
                    show: true,
                    total: {
                        show: true, label: "포트폴리오", color: "#888",
                        fontSize: "11px", formatter: () => "보유 비중",
                    },
                },
            }},
        },
        legend: {
            show: true, position: "bottom", fontSize: "12px",
            labels: { colors: "#6B7280" },
            itemMargin: { horizontal: 4, vertical: 2 },
        },
        dataLabels: { enabled: false },
        tooltip:    { theme: "light", y: { formatter: (v) => v.toFixed(1) + "%" } },
        stroke:     { width: 0 },
        theme:      { mode: "dark" },
    };
    portfolioChart = new ApexCharts(document.getElementById("portfolioChart"), options);
    portfolioChart.render();
}

function updatePortfolioChart(positions, cash) {
    if (!portfolioChart) return;
    if (!positions?.length) {
        portfolioChart.updateOptions({ labels: ["현금 KRW"] });
        portfolioChart.updateSeries([100]);
        return;
    }
    const labels = ["현금 KRW", ...positions.map(p => p.name)];
    const raw    = [cash, ...positions.map(p => p.evalAmount)];
    const total  = raw.reduce((a, b) => a + b, 0);
    const series = raw.map(v => total > 0 ? parseFloat((v / total * 100).toFixed(1)) : 0);
    portfolioChart.updateOptions({ labels });
    portfolioChart.updateSeries(series);
}

/* ── Order Book / 호가창 (키움증권 참고) ───────────────────────────────────── */
function renderOrderBook(price) {
    if (!price || price <= 0) return;
    const askBody = document.getElementById("askBody");
    const bidBody = document.getElementById("bidBody");
    if (!askBody || !bidBody) return;

    let tick = 1;
    if      (price >= 500_000) tick = 1000;
    else if (price >= 100_000) tick = 500;
    else if (price >=  50_000) tick = 100;
    else if (price >=  10_000) tick = 50;
    else if (price >=   1_000) tick = 10;

    const qty = (p, offset) => Math.max(50, ((p * 7 + offset) % 2_900) + 100);

    const LEVELS = 5;
    const askRows = [];
    for (let i = LEVELS; i >= 1; i--) {
        const p = price + tick * i;
        askRows.push({ price: p, qty: qty(p, 13) });
    }
    const bidRows = [];
    for (let i = 1; i <= LEVELS; i++) {
        const p = price - tick * i;
        bidRows.push({ price: p, qty: qty(p, 31) });
    }

    askBody.innerHTML = askRows.map(r => `
        <tr style="background:rgba(37,99,235,0.03);">
            <td style="padding:5px 16px;text-align:right;color:#2563EB;font-weight:700;">${Number(r.price).toLocaleString("ko-KR")}</td>
            <td style="padding:5px 16px;text-align:right;color:#6B7280;">${Number(r.qty).toLocaleString("ko-KR")}</td>
        </tr>`).join("");

    bidBody.innerHTML = bidRows.map(r => `
        <tr style="background:rgba(225,29,72,0.03);">
            <td style="padding:5px 16px;text-align:right;color:#E11D48;font-weight:700;">${Number(r.price).toLocaleString("ko-KR")}</td>
            <td style="padding:5px 16px;text-align:right;color:#6B7280;">${Number(r.qty).toLocaleString("ko-KR")}</td>
        </tr>`).join("");

    const obCur    = document.getElementById("obCurrentPrice");
    const obSpread = document.getElementById("obSpread");
    if (obCur)    obCur.textContent = Number(price).toLocaleString("ko-KR");
    if (obSpread) {
        const spread = tick * 2;
        obSpread.textContent = `${Number(spread).toLocaleString("ko-KR")} (${((spread / price) * 100).toFixed(3)}%)`;
    }
}

/* ── Break-even / 손익분기가 (토스증권 참고) ──────────────────────────────── */
function updateBreakEven(positions, symbol) {
    const el  = document.getElementById("quoteBreakEven");
    if (!el) return;
    const pos = positions?.find(p => p.symbol === symbol);
    if (pos) {
        el.textContent = `${Number(pos.avgPrice).toLocaleString("ko-KR")}원 (매입단가)`;
        el.style.color = "#FFCC00";
    } else {
        el.textContent = "-";
        el.style.color = "#888";
    }
}

/* ── Trade History (키움증권·Robinhood 참고) ──────────────────────────────── */
async function loadHistory() {
    try {
        const data = await requestJson("/api/stocks/orders/history");
        renderHistory(data.history || []);
    } catch (e) {
        console.warn("거래 내역 로딩 실패:", e.message);
    }
}

function renderHistory(history) {
    const tbody = document.getElementById("historyBody");
    if (!tbody) return;
    if (!history.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="px-3 py-4 text-center text-slate-500">거래 내역이 없습니다.</td></tr>`;
        return;
    }
    tbody.innerHTML = history.slice(0, 30).map(h => {
        const isBuy = h.type === "BUY";
        const color = isBuy ? "#e11d48" : "#2563eb";
        const bg    = isBuy ? "rgba(225,29,72,0.04)" : "rgba(37,99,235,0.04)";
        const label = isBuy ? "매수" : "매도";
        const dt    = new Date(h.ts).toLocaleTimeString("ko-KR",
            { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        return `<tr style="background:${bg};">
            <td style="padding:8px 12px;color:#6B7280;font-size:12px;">${dt}</td>
            <td style="padding:8px 12px;font-weight:700;color:#111827;">${h.name}<br>
                <span style="color:#7C5CFC;font-size:11px;">${h.symbol}</span></td>
            <td style="padding:8px 12px;"><span style="color:${color};font-weight:800;font-size:13px;">${label}</span></td>
            <td style="padding:8px 12px;text-align:right;color:#111827;font-weight:600;">${Number(h.quantity).toLocaleString("ko-KR")}주</td>
            <td style="padding:8px 12px;text-align:right;color:#374151;">${Number(h.price).toLocaleString("ko-KR")}원</td>
            <td style="padding:8px 12px;text-align:right;color:#7C5CFC;font-weight:700;">${Number(h.amount).toLocaleString("ko-KR")}원</td>
        </tr>`;
    }).join("");
}

/* ── Account Reset (Trading212 참고) ──────────────────────────────────────── */
document.getElementById("resetBtn").addEventListener("click", async () => {
    if (!confirm("모의투자 계좌를 초기화하시겠습니까?\n보유 포지션과 거래 내역이 모두 삭제됩니다.")) return;
    try {
        await requestJson("/api/stocks/account/reset", { method: "POST" });
        showMessage("계좌가 초기화되었습니다.");
        await Promise.all([loadAccount(), loadPositions(), loadHistory()]);
    } catch (e) {
        showMessage(e.message, true);
    }
});

/* ── Data loaders ──────────────────────────────────────────────────────────── */
async function loadMarket() {
    try {
        const data = await requestJson("/api/stocks/market");
        for (const [key, val] of Object.entries({ KOSPI: data.KOSPI, KOSDAQ: data.KOSDAQ })) {
            const prefix = key.toLowerCase();
            document.getElementById(prefix + "Price").textContent =
                Number(val.price).toLocaleString("ko-KR", { minimumFractionDigits: 2 });
            const rate  = Number(val.changeRate);
            const amt   = Number(val.change);
            const color = colorClass(rate);
            document.getElementById(prefix + "Change").textContent =
                `${rate >= 0 ? "▲" : "▼"} ${Math.abs(rate).toFixed(2)}%`;
            document.getElementById(prefix + "Change").style.color = color;
            document.getElementById(prefix + "ChangeAmt").textContent =
                `${amt >= 0 ? "+" : ""}${Number(amt).toLocaleString("ko-KR", { minimumFractionDigits: 2 })}`;
            document.getElementById(prefix + "ChangeAmt").style.color = color;
        }
    } catch (e) {
        console.warn("시장지수 로딩 실패:", e.message);
    }
}

async function loadChart(symbol, period) {
    try {
        const data = await requestJson(
            `/api/stocks/chart?symbol=${encodeURIComponent(symbol)}&period=${encodeURIComponent(period)}`
        );
        const candleData = data.data.map(d => ({ x: d.x, y: [d.o, d.h, d.l, d.c] }));
        const volumeData = data.data.map(d => ({ x: d.x, y: d.v }));
        candleChart.updateSeries([{ name: "Price",  data: candleData }]);
        volumeChart.updateSeries([{ name: "Volume", data: volumeData }]);
    } catch (e) {
        console.warn("차트 로딩 실패:", e.message);
    }
}

async function loadQuote() {
    const symbol = stockSymbol.value;
    if (!symbol) return;
    const data = await requestJson(`/api/stocks/quote?symbol=${encodeURIComponent(symbol)}`);

    quotePrice.textContent = formatKrw(data.price);
    const change = Number(data.change || 0);
    const rate   = Number(data.changeRate || 0);
    const color  = colorClass(rate);

    quoteChange.textContent = `${change >= 0 ? "+" : ""}${formatKrw(change)}`;
    quoteChange.style.color = color;
    quoteChangeRate.textContent = `${rate >= 0 ? "+" : ""}${rate.toFixed(2)}%`;
    quoteChangeRate.style.color = color;
    quoteVolume.textContent = data.volume ? formatVolume(data.volume) : "-";
    quoteMarket.textContent = data.market || "-";
    chartStockName.textContent  = data.name || "";

    if (data.simulated) {
        dataSourceBadge.classList.remove("hidden");
    } else {
        dataSourceBadge.classList.add("hidden");
    }

    renderOrderBook(data.price);
    updateWatchlistBtn(symbol);
    updateBreakEven(lastPositions, symbol);
}

async function loadAccount() {
    const data = await requestJson("/api/stocks/account");
    lastCash = data.cash;
    accountCash.textContent  = formatKrw(data.cash);
    accountAsset.textContent = formatKrw(data.totalAsset);
    const pnl = Number(data.totalPnlRate);
    accountPnlRate.textContent = `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}%`;
    accountPnlRate.style.color = colorClass(pnl);
    updatePortfolioChart(lastPositions, data.cash);
}

async function loadPositions() {
    const data = await requestJson("/api/stocks/positions");
    lastPositions = data.positions || [];
    positionsBody.innerHTML = "";
    if (!lastPositions.length) {
        positionsBody.innerHTML =
            `<tr><td colspan="7" class="px-3 py-4 text-center text-slate-500">보유 포지션이 없습니다.</td></tr>`;
        updatePortfolioChart([], lastCash);
        updateBreakEven([], stockSymbol.value);
        return;
    }
    lastPositions.forEach(pos => {
        const pnl   = Number(pos.pnl || 0);
        const color = pnl > 0 ? "#E11D48" : pnl < 0 ? "#2563EB" : "#6B7280";
        const tr    = document.createElement("tr");
        tr.innerHTML = `
            <td style="padding:10px 12px;font-weight:700;color:#111827;">${pos.name || pos.symbol}<br>
                <span style="font-size:12px;color:#7C5CFC;">${pos.symbol}</span></td>
            <td style="padding:10px 12px;">
                <span style="background:#EDE9FF;color:#6548E8;border:1px solid rgba(124,92,252,0.20);border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;">${pos.market || "-"}</span>
            </td>
            <td style="padding:10px 12px;text-align:right;color:#111827;font-weight:600;">${pos.quantity}</td>
            <td style="padding:10px 12px;text-align:right;color:#111827;font-weight:600;">${formatKrw(pos.avgPrice)}</td>
            <td style="padding:10px 12px;text-align:right;color:#111827;font-weight:600;">${formatKrw(pos.currentPrice)}</td>
            <td style="padding:10px 12px;text-align:right;color:#7C5CFC;font-weight:700;">${formatKrw(pos.evalAmount)}</td>
            <td style="padding:10px 12px;text-align:right;font-weight:800;font-size:15px;color:${color};">${pnl >= 0 ? "+" : ""}${formatKrw(pnl)}</td>`;
        positionsBody.appendChild(tr);
    });
    updatePortfolioChart(lastPositions, lastCash);
    updateBreakEven(lastPositions, stockSymbol.value);
}

/* ── Order ─────────────────────────────────────────────────────────────────── */
async function submitOrder(type) {
    const qty = Number(orderQty.value);
    if (!Number.isFinite(qty) || qty <= 0) {
        showMessage("수량은 1 이상이어야 합니다.", true);
        return;
    }
    try {
        const payload = { symbol: stockSymbol.value, quantity: qty };
        await requestJson(`/api/stocks/orders/${type}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        showMessage(`${type === "buy" ? "매수" : "매도"} 주문이 완료되었습니다.`);
        await Promise.all([loadAccount(), loadPositions(), loadQuote(), loadHistory()]);
    } catch (e) {
        showMessage(e.message, true);
    }
}

/* ── Period buttons ────────────────────────────────────────────────────────── */
function updatePeriodBtns(active) {
    document.querySelectorAll(".period-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.period === active);
    });
}

document.getElementById("periodBtns").addEventListener("click", async (e) => {
    const btn = e.target.closest(".period-btn");
    if (!btn) return;
    currentPeriod = btn.dataset.period;
    updatePeriodBtns(currentPeriod);
    await loadChart(stockSymbol.value, currentPeriod);
});

/* ── Symbol change ─────────────────────────────────────────────────────────── */
stockSymbol.addEventListener("change", async () => {
    await Promise.all([loadQuote(), loadChart(stockSymbol.value, currentPeriod)]);
});

/* ── Buy / Sell ────────────────────────────────────────────────────────────── */
document.getElementById("buyBtn").addEventListener("click",  () => submitOrder("buy"));
document.getElementById("sellBtn").addEventListener("click", () => submitOrder("sell"));

/* ── Refresh all ───────────────────────────────────────────────────────────── */
async function refreshAll({ silent = false } = {}) {
    try {
        await Promise.all([loadMarket(), loadQuote(), loadAccount(), loadPositions()]);
        if (!silent) showMessage("");
    } catch (e) {
        showMessage(e.message, true);
    }
}

/* ── Boot ──────────────────────────────────────────────────────────────────── */
(async () => {
    initCharts();
    initPortfolioChart();
    updatePeriodBtns(currentPeriod);
    await loadStockList();
    await refreshAll();
    await loadChart(stockSymbol.value, currentPeriod);
    await Promise.all([loadMovers(), loadHistory()]);
    setInterval(refreshAll, 15_000);
    setInterval(() => loadChart(stockSymbol.value, currentPeriod), 60_000);
    setInterval(loadMovers, 60_000);
})();
