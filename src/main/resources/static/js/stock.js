const stockSymbol = document.getElementById("stockSymbol");
const orderQty = document.getElementById("orderQty");
const quotePrice = document.getElementById("quotePrice");
const quoteChange = document.getElementById("quoteChange");
const accountCash = document.getElementById("accountCash");
const accountAsset = document.getElementById("accountAsset");
const accountPnlRate = document.getElementById("accountPnlRate");
const positionsBody = document.getElementById("positionsBody");
const stockMessage = document.getElementById("stockMessage");

function formatKrw(value) {
    return Number(value).toLocaleString("ko-KR") + " KRW";
}

function showMessage(message, isError = false) {
    stockMessage.textContent = message;
    stockMessage.className = isError ? "text-xs text-rose-600" : "text-xs text-emerald-600";
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const raw = await response.text();
    let data = {};
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch (e) {
        throw new Error("응답 형식이 올바르지 않습니다. 잠시 후 다시 시도해주세요.");
    }
    if (!response.ok) {
        throw new Error(data.message || "요청에 실패했습니다.");
    }
    return data;
}

async function loadQuote() {
    const symbol = stockSymbol.value;
    const data = await requestJson(`/api/stocks/quote?symbol=${encodeURIComponent(symbol)}`);
    quotePrice.textContent = formatKrw(data.price);

    const rate = Number(data.changeRate || 0);
    quoteChange.textContent = `${rate.toFixed(2)}%`;
    quoteChange.style.color = rate >= 0 ? "#059669" : "#dc2626";
}

async function loadAccount() {
    const data = await requestJson("/api/stocks/account");
    accountCash.textContent = formatKrw(data.cash);
    accountAsset.textContent = formatKrw(data.totalAsset);
    accountPnlRate.textContent = `${Number(data.totalPnlRate).toFixed(2)}%`;
}

async function loadPositions() {
    const data = await requestJson("/api/stocks/positions");
    positionsBody.innerHTML = "";

    if (!data.positions || data.positions.length === 0) {
        positionsBody.innerHTML = `
            <tr>
                <td colspan="6" class="px-3 py-4 text-center text-slate-500">보유 포지션이 없습니다.</td>
            </tr>
        `;
        return;
    }

    data.positions.forEach((position) => {
        const pnl = Number(position.pnl || 0);
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="px-3 py-2 font-semibold text-slate-700">${position.symbol}</td>
            <td class="px-3 py-2 text-right">${position.quantity}</td>
            <td class="px-3 py-2 text-right">${formatKrw(position.avgPrice)}</td>
            <td class="px-3 py-2 text-right">${formatKrw(position.currentPrice)}</td>
            <td class="px-3 py-2 text-right">${formatKrw(position.evalAmount)}</td>
            <td class="px-3 py-2 text-right" style="color:${pnl >= 0 ? "#059669" : "#dc2626"}">${formatKrw(pnl)}</td>
        `;
        positionsBody.appendChild(tr);
    });
}

async function submitOrder(type) {
    const qty = Number(orderQty.value);
    if (!Number.isFinite(qty) || qty <= 0) {
        showMessage("수량은 1 이상이어야 합니다.", true);
        return;
    }

    const payload = {symbol: stockSymbol.value, quantity: qty};
    await requestJson(`/api/stocks/orders/${type}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });
    showMessage(`${type === "buy" ? "매수" : "매도"} 주문이 완료되었습니다.`);
    await refreshAll();
}

async function refreshAll() {
    try {
        await Promise.all([loadQuote(), loadAccount(), loadPositions()]);
    } catch (error) {
        showMessage(error.message, true);
    }
}

document.getElementById("buyBtn").addEventListener("click", () => submitOrder("buy"));
document.getElementById("sellBtn").addEventListener("click", () => submitOrder("sell"));
stockSymbol.addEventListener("change", refreshAll);

refreshAll();
setInterval(refreshAll, 10000);
