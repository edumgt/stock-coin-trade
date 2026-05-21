/* ── DOM refs ─────────────────────────────────────────────────────────────── */
const stockSymbol    = document.getElementById("stockSymbol");
const orderQty       = document.getElementById("orderQty");
const quotePrice     = document.getElementById("quotePrice");
const quoteChange    = document.getElementById("quoteChange");
const quoteChangeRate = document.getElementById("quoteChangeRate");
const quoteVolume    = document.getElementById("quoteVolume");
const quoteMarket    = document.getElementById("quoteMarket");
const accountCash    = document.getElementById("accountCash");
const accountAsset   = document.getElementById("accountAsset");
const accountPnlRate = document.getElementById("accountPnlRate");
const positionsBody  = document.getElementById("positionsBody");
const stockMessage   = document.getElementById("stockMessage");
const chartStockName = document.getElementById("chartStockName");
const dataSourceBadge = document.getElementById("dataSourceBadge");

/* ── State ─────────────────────────────────────────────────────────────────── */
let currentPeriod = "1m";
let candleChart   = null;
let volumeChart   = null;

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

/* ── API helpers ──────────────────────────────────────────────────────────── */
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

/* ── ApexCharts initialisation ────────────────────────────────────────────── */
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
            labels: {
                style: { fontSize: "11px", colors: "#94a3b8" },
                datetimeUTC: false,
            },
            axisBorder: { show: false },
            axisTicks: { show: false },
        },
        yaxis: {
            tooltip: { enabled: true },
            labels: {
                formatter: (v) => Number(v).toLocaleString("ko-KR"),
                style: { fontSize: "11px", colors: "#94a3b8" },
            },
        },
        plotOptions: {
            candlestick: {
                colors: { upward: "#e11d48", downward: "#2563eb" },
                wick:   { useFillColor: true },
            },
        },
        grid: { borderColor: "#f1f5f9", strokeDashArray: 4 },
        tooltip: {
            custom({ seriesIndex, dataPointIndex, w }) {
                const d = w.globals.initialSeries[seriesIndex].data[dataPointIndex];
                if (!d) return "";
                const dt = new Date(d.x).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
                const [o, h, l, c] = [d.o, d.h, d.l, d.c].map(v => Number(v).toLocaleString("ko-KR"));
                const color = d.c >= d.o ? "#e11d48" : "#2563eb";
                return `<div style="padding:8px 12px;font-size:12px;line-height:1.8;">
                    <div style="color:#64748b;margin-bottom:4px;">${dt}</div>
                    <div>시가 <b>${o}</b></div>
                    <div>고가 <b style="color:#e11d48">${h}</b></div>
                    <div>저가 <b style="color:#2563eb">${l}</b></div>
                    <div>종가 <b style="color:${color}">${c}</b></div>
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
            labels: {
                style: { fontSize: "10px", colors: "#94a3b8" },
                datetimeUTC: false,
            },
            axisBorder: { show: false },
            axisTicks: { show: false },
        },
        yaxis: {
            labels: {
                formatter: (v) => {
                    if (v >= 1_000_000) return (v / 1_000_000).toFixed(0) + "M";
                    if (v >= 1_000)    return (v / 1_000).toFixed(0) + "K";
                    return v;
                },
                style: { fontSize: "10px", colors: "#94a3b8" },
            },
        },
        fill: { opacity: 0.6 },
        colors: ["#818cf8"],
        grid: { borderColor: "#f1f5f9", strokeDashArray: 4 },
        tooltip: {
            x: { format: "yyyy-MM-dd HH:mm" },
            y: { formatter: (v) => Number(v).toLocaleString("ko-KR") + "주" },
        },
    };

    candleChart = new ApexCharts(document.getElementById("candleChart"), candleOptions);
    volumeChart = new ApexCharts(document.getElementById("volumeChart"), volumeOptions);
    candleChart.render();
    volumeChart.render();
}

/* ── Data loaders ─────────────────────────────────────────────────────────── */
async function loadStockList() {
    const data = await requestJson("/api/stocks/list");
    stockSymbol.innerHTML = "";
    const markets = ["KOSPI", "KOSDAQ"];
    markets.forEach(market => {
        const group = document.createElement("optgroup");
        group.label = market;
        data.stocks
            .filter(s => s.market === market)
            .forEach(s => {
                const opt = document.createElement("option");
                opt.value = s.symbol;
                opt.textContent = `${s.name} (${s.symbol})`;
                group.appendChild(opt);
            });
        stockSymbol.appendChild(group);
    });
}

async function loadMarket() {
    try {
        const data = await requestJson("/api/stocks/market");
        const indices = { KOSPI: data.KOSPI, KOSDAQ: data.KOSDAQ };
        for (const [key, val] of Object.entries(indices)) {
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
        const data = await requestJson(`/api/stocks/chart?symbol=${encodeURIComponent(symbol)}&period=${encodeURIComponent(period)}`);
        const candleData = data.data.map(d => ({ x: d.x, y: [d.o, d.h, d.l, d.c] }));
        const volumeData = data.data.map(d => ({ x: d.x, y: d.v }));
        candleChart.updateSeries([{ name: "Price", data: candleData }]);
        volumeChart.updateSeries([{ name: "Volume", data: volumeData }]);
    } catch (e) {
        console.warn("차트 로딩 실패:", e.message);
    }
}

async function loadQuote() {
    const symbol = stockSymbol.value;
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
    chartStockName.textContent = data.name || "";

    if (data.simulated) {
        dataSourceBadge.classList.remove("hidden");
    } else {
        dataSourceBadge.classList.add("hidden");
    }
}

async function loadAccount() {
    const data = await requestJson("/api/stocks/account");
    accountCash.textContent  = formatKrw(data.cash);
    accountAsset.textContent = formatKrw(data.totalAsset);
    const pnl = Number(data.totalPnlRate);
    accountPnlRate.textContent = `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}%`;
    accountPnlRate.style.color = colorClass(pnl);
}

async function loadPositions() {
    const data = await requestJson("/api/stocks/positions");
    positionsBody.innerHTML = "";
    if (!data.positions || data.positions.length === 0) {
        positionsBody.innerHTML = `
            <tr><td colspan="7" class="px-3 py-4 text-center text-slate-500">보유 포지션이 없습니다.</td></tr>`;
        return;
    }
    data.positions.forEach(pos => {
        const pnl   = Number(pos.pnl || 0);
        const color = colorClass(pnl);
        const tr    = document.createElement("tr");
        tr.innerHTML = `
            <td class="px-3 py-2 font-semibold text-slate-800">${pos.name || pos.symbol}<br><span class="text-xs text-slate-400">${pos.symbol}</span></td>
            <td class="px-3 py-2"><span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">${pos.market || "-"}</span></td>
            <td class="px-3 py-2 text-right">${pos.quantity}</td>
            <td class="px-3 py-2 text-right">${formatKrw(pos.avgPrice)}</td>
            <td class="px-3 py-2 text-right">${formatKrw(pos.currentPrice)}</td>
            <td class="px-3 py-2 text-right">${formatKrw(pos.evalAmount)}</td>
            <td class="px-3 py-2 text-right font-semibold" style="color:${color}">${pnl >= 0 ? "+" : ""}${formatKrw(pnl)}</td>`;
        positionsBody.appendChild(tr);
    });
}

/* ── Order ────────────────────────────────────────────────────────────────── */
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
        await Promise.all([loadAccount(), loadPositions(), loadQuote()]);
    } catch (e) {
        showMessage(e.message, true);
    }
}

/* ── Period buttons ───────────────────────────────────────────────────────── */
function updatePeriodBtns(active) {
    document.querySelectorAll(".period-btn").forEach(btn => {
        const isActive = btn.dataset.period === active;
        btn.className = [
            "period-btn rounded-lg px-3 py-1.5 text-xs font-semibold transition",
            isActive
                ? "bg-indigo-600 text-white shadow"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200",
        ].join(" ");
    });
}

document.getElementById("periodBtns").addEventListener("click", async (e) => {
    const btn = e.target.closest(".period-btn");
    if (!btn) return;
    currentPeriod = btn.dataset.period;
    updatePeriodBtns(currentPeriod);
    await loadChart(stockSymbol.value, currentPeriod);
});

/* ── Symbol change ────────────────────────────────────────────────────────── */
stockSymbol.addEventListener("change", async () => {
    await Promise.all([loadQuote(), loadChart(stockSymbol.value, currentPeriod)]);
});

/* ── Buy / Sell ───────────────────────────────────────────────────────────── */
document.getElementById("buyBtn").addEventListener("click",  () => submitOrder("buy"));
document.getElementById("sellBtn").addEventListener("click", () => submitOrder("sell"));

/* ── Refresh all ──────────────────────────────────────────────────────────── */
async function refreshAll({ silent = false } = {}) {
    try {
        await Promise.all([loadMarket(), loadQuote(), loadAccount(), loadPositions()]);
        if (!silent) showMessage("");
    } catch (e) {
        showMessage(e.message, true);
    }
}

/* ── Boot ─────────────────────────────────────────────────────────────────── */
(async () => {
    initCharts();
    updatePeriodBtns(currentPeriod);
    await loadStockList();
    await refreshAll();
    await loadChart(stockSymbol.value, currentPeriod);
    setInterval(refreshAll, 15000);
    setInterval(() => loadChart(stockSymbol.value, currentPeriod), 60000);
})();
