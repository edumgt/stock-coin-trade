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
        grid: { borderColor: "rgba(255,255,255,0.06)", strokeDashArray: 4 },
        tooltip: {
            theme: "dark",
            custom({ seriesIndex, dataPointIndex, w }) {
                const d = w.globals.initialSeries[seriesIndex].data[dataPointIndex];
                if (!d) return "";
                const dt = new Date(d.x).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
                const [o, h, l, c] = [d.o, d.h, d.l, d.c].map(v => Number(v).toLocaleString("ko-KR"));
                const color = d.c >= d.o ? "#22c55e" : "#f43f5e";
                return `<div style="padding:10px 14px;font-size:13px;line-height:1.9;background:#161616;border:1px solid rgba(255,255,255,0.10);border-radius:10px;font-family:'Pretendard',sans-serif;">
                    <div style="color:#888;margin-bottom:6px;font-size:12px;">${dt}</div>
                    <div style="color:#F2F2F2;">시가 <b>${o}</b></div>
                    <div style="color:#22c55e;">고가 <b>${h}</b></div>
                    <div style="color:#f43f5e;">저가 <b>${l}</b></div>
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
        fill: { opacity: 0.5 },
        colors: ["rgba(255,204,0,0.7)"],
        grid: { borderColor: "rgba(255,255,255,0.06)", strokeDashArray: 4 },
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
        const color = pnl > 0 ? "#22c55e" : pnl < 0 ? "#f43f5e" : "#888";
        const tr    = document.createElement("tr");
        tr.innerHTML = `
            <td style="padding:10px 12px;font-weight:700;color:#F2F2F2;">${pos.name || pos.symbol}<br><span style="font-size:12px;color:#FFCC00;">${pos.symbol}</span></td>
            <td style="padding:10px 12px;"><span style="background:rgba(255,255,255,0.06);color:#888;border:1px solid rgba(255,255,255,0.10);border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;">${pos.market || "-"}</span></td>
            <td style="padding:10px 12px;text-align:right;color:#F2F2F2;font-weight:600;">${pos.quantity}</td>
            <td style="padding:10px 12px;text-align:right;color:#F2F2F2;font-weight:600;">${formatKrw(pos.avgPrice)}</td>
            <td style="padding:10px 12px;text-align:right;color:#F2F2F2;font-weight:600;">${formatKrw(pos.currentPrice)}</td>
            <td style="padding:10px 12px;text-align:right;color:#FFCC00;font-weight:700;">${formatKrw(pos.evalAmount)}</td>
            <td style="padding:10px 12px;text-align:right;font-weight:800;font-size:15px;color:${color};">${pnl >= 0 ? "+" : ""}${formatKrw(pnl)}</td>`;
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
        if (btn.dataset.period === active) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
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
