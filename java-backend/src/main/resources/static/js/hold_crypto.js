// 웹소켓 생성
const upbitWebsocketUrl = "wss://api.upbit.com/websocket/v1";
const socket = new WebSocket(upbitWebsocketUrl);

// 커넥션이 제대로 생성되었을 때
socket.onopen = function (e) {
    console.log("웹 소켓 연결 성공")
    let jsonData = [
        {
            "ticket": "test example"
        },
        {
            "type": "ticker", // 현재가
            "codes": marketArrayList // ["KRW-BTC", "KRW-NEO" ... ]
        },
    ];

    socket.send(JSON.stringify(jsonData))
};

// 데이터를 수신 받았을 때
let object_total_evaluation_krw = {}; // 총 평가금액
let member_asset = document.getElementById('member_asset').innerText.replaceAll(',', ''); // 보유 KRW
socket.onmessage = async function (e) {
    try {
        if (e !== null && e !== undefined) {
            let result = JSON.parse(await e.data.text()); // blob to json
            // console.log(result);

            // 웹소켓 type 구분 - ticker(현재가), trade(체결)
            let type = result.type;

            // 암호화폐 마켓 코드
            let crypto_code = result.code; // ex) KRW-BTC, KRW-NEO ...

            // =============================================
            // ticker(현재가) 응답
            // =============================================
            if (type === 'ticker') {
                // 암호화폐 현재가 socket response
                let now_trade_price = result.trade_price;

                // 평가 금액 계산 (보유수량 * 현재가)
                let hold_count_string = document.getElementById(crypto_code + '-hold-count').innerText;
                let hold_count = hold_count_string.replaceAll(',', '');
                let evaluation_krw = now_trade_price * hold_count;
                evaluation_krw = Math.round(evaluation_krw); // 평가금액 (KRW)

                // 총평가금액
                object_total_evaluation_krw[crypto_code] = evaluation_krw;

                let total_evaluation_krw = 0; // 총평가금액
                for (const key in object_total_evaluation_krw) {
                    total_evaluation_krw += object_total_evaluation_krw[key];
                }
                document.getElementById('total_evaluation_krw').innerText = new Intl.NumberFormat('ko-kr').format(total_evaluation_krw);

                // 총보유자산 (보유KRW + 총평가금액)
                let total_member_asset = 0;
                total_member_asset = parseInt(member_asset) + total_evaluation_krw;
                total_member_asset = new Intl.NumberFormat('ko-kr').format(total_member_asset);
                document.getElementById('total_member_asset').innerText = total_member_asset;

                // 총평가손익 (총평가금액(KRW) - 총매수금액(KRW))
                let total_buy_krw = document.getElementById('total_buy_krw').innerText; // 총매수금액
                total_buy_krw = parseInt(total_buy_krw.replaceAll(',', ''));

                let total_krw_of_return = total_evaluation_krw - total_buy_krw; // 총평가손익

                let total_krw_of_return_dom = document.getElementById('total_krw_of_return');
                if (total_krw_of_return > 0) {
                    total_krw_of_return_dom.classList.remove('text-down');
                    total_krw_of_return_dom.classList.add('text-up');
                    total_krw_of_return_dom.innerText = '+' + new Intl.NumberFormat('ko-kr').format(total_krw_of_return);
                } else if (total_krw_of_return === 0) {
                    total_krw_of_return_dom.classList.remove('text-down');
                    total_krw_of_return_dom.classList.remove('text-up');
                    total_krw_of_return_dom.innerText = '0';
                } else if (total_krw_of_return < 0) {
                    total_krw_of_return_dom.classList.add('text-down');
                    total_krw_of_return_dom.classList.remove('text-up');
                    total_krw_of_return_dom.innerText = new Intl.NumberFormat('ko-kr').format(total_krw_of_return);
                }

                // 총평가수익률 (총평가금액 / 총매수금액) * 100 - 100
                let total_evaluation_rate_of_return = (total_evaluation_krw / total_buy_krw) * 100 - 100; // 총평가수익률
                let total_evaluation_rate_of_return_dom = document.getElementById('total_evaluation_rate_of_return');
                if (total_evaluation_rate_of_return > 0) {
                    total_evaluation_rate_of_return_dom.classList.remove('text-down');
                    total_evaluation_rate_of_return_dom.classList.add('text-up');
                    total_evaluation_rate_of_return_dom.innerText = '+' + total_evaluation_rate_of_return.toFixed(2);
                } else if (total_evaluation_rate_of_return === 0) {
                    total_evaluation_rate_of_return_dom.classList.remove('text-down');
                    total_evaluation_rate_of_return_dom.classList.remove('text-up');
                    total_evaluation_rate_of_return_dom.innerText = '0';
                } else if (total_evaluation_rate_of_return < 0) {
                    total_evaluation_rate_of_return_dom.classList.add('text-down');
                    total_evaluation_rate_of_return_dom.classList.remove('text-up');
                    total_evaluation_rate_of_return_dom.innerText = total_evaluation_rate_of_return.toFixed(2);
                }

                // 암호화폐별 평가금액 html text 변경
                document.getElementById(crypto_code + '-evaluation-krw').innerText = new Intl.NumberFormat('ko-kr').format(evaluation_krw);

                // 수익률 계산 - 수익률(%) = (평가금액 / 매수금액) * 100 - 100
                // 매수 금액 (KRW)
                let buy_total_krw = document.getElementById(crypto_code + '-buy-total-krw').innerText;
                buy_total_krw = buy_total_krw.replaceAll(',', '');

                // 수익률
                let rate_of_return_dom = document.getElementById(crypto_code + '-rate-of-return');
                let rate_of_return = (evaluation_krw / buy_total_krw) * 100 - 100;
                rate_of_return = Math.round(rate_of_return * 100) / 100;
                if (rate_of_return > 0) {
                    rate_of_return_dom.innerText = '+' + rate_of_return.toFixed(2);
                } else {
                    rate_of_return_dom.innerText = rate_of_return.toFixed(2);
                }

                // font color
                if (rate_of_return < 0) {
                    rate_of_return_dom.classList.remove('text-up');
                    rate_of_return_dom.classList.add('text-down');
                } else if (rate_of_return > 0) {
                    rate_of_return_dom.classList.remove('text-down');
                    rate_of_return_dom.classList.add('text-up');
                } else if (rate_of_return === 0) {
                    rate_of_return_dom.classList.remove('text-down');
                    rate_of_return_dom.classList.remove('text-up');
                }

                // 평가 손익 (KRW)
                let krw_of_return_dom = document.getElementById(crypto_code + '-krw-of-return');
                let krw_of_return = evaluation_krw - buy_total_krw; // 순 투자 손익 (KRW)

                if (krw_of_return > 0) {
                    krw_of_return_dom.innerText = '+' + new Intl.NumberFormat('ko-kr').format(krw_of_return);
                } else {
                    krw_of_return_dom.innerText = new Intl.NumberFormat('ko-kr').format(krw_of_return);
                }

                // font color
                if (krw_of_return < 0) {
                    krw_of_return_dom.classList.remove('text-up');
                    krw_of_return_dom.classList.add('text-down');
                } else if (krw_of_return > 0) {
                    krw_of_return_dom.classList.remove('text-down');
                    krw_of_return_dom.classList.add('text-up');
                } else if (krw_of_return === 0) {
                    krw_of_return_dom.classList.remove('text-up');
                    krw_of_return_dom.classList.remove('text-down');
                }
            }

        }
    } catch (err) {
        console.log("ERROR !!" + err);
    }
};

// 에러가 발생했을 때
socket.onerror = function (e) {
    console.log("업비트 웹소켓 연결 실패");
    console.log(e);
};

// ==========================================
// Highcharts 보유자산 포트폴리오 차트 불러오기
// ==========================================
// Chart Data - Upbit api
let marketListToString = String(marketArrayList);
let upbitTradePriceApiUrl = 'https://api.upbit.com/v1/ticker?markets=' + marketListToString;

fetch(upbitTradePriceApiUrl)
    .then((res) => {
        return res.json();
    })
    .then((jsonData) => {
        // 업비트 api -> 현재가 불러오기
        let objUpbitTradePrice = {};
        for (let i = 0; i < jsonData.length; i++) {
            let marketCode = jsonData[i].market; // market code
            let marketCodeSplit = marketCode.split("-");
            let cryptoSymbol = marketCodeSplit[1]; // ex) BTC, ETH ...

            let tradePrice = jsonData[i].trade_price; // upbit 기준 현재가

            objUpbitTradePrice[cryptoSymbol] = tradePrice;
        }

        // 보유중인 암호화폐 정보에서, 구매한 개수 가져오기
        let objHoldCryptoCount = {};
        for (let i = 0; i < holdCryptoList.length; i++) {
            let marketCode = holdCryptoList[i].marketCode;
            let marketCodeSplit = marketCode.split("-");
            let cryptoSymbol = marketCodeSplit[1]; // ex) BTC, ETH ...

            let holdCount = holdCryptoList[i].holdCount;

            objHoldCryptoCount[cryptoSymbol] = holdCount;
        }

        console.log('objUpbitTradePrice', objUpbitTradePrice);
        console.log('objHoldCryptoCount', objHoldCryptoCount);

        let totalHoldAsset = 0; // 총 보유자산 (보유KRW + 총평가금액)
        let evaluationPrices = {};
        for (let key in objUpbitTradePrice) {
            let evaluationPrice = objUpbitTradePrice[key] * objHoldCryptoCount[key];
            totalHoldAsset += evaluationPrice;

            evaluationPrices[key] = Math.round(evaluationPrice);
        }
        totalHoldAsset = Math.round(totalHoldAsset) + member_asset; // 총 보유자산 (보유KRW + 총평가금액)

        // 보유 비중 계산 -- 최종적으로 차트에 넣어줄 데이터 가공
        let chartPercentData = [];
        for (let key in evaluationPrices) {
            let holdPercent = (evaluationPrices[key] / totalHoldAsset) * 100; // 보유 비중(%)

            chartPercentData.push({name: key, y: holdPercent})
        }

        // 보유 비중에 KRW 비중 추가
        let krwHoldPercent = (member_asset / totalHoldAsset) * 100; // 보유 비중(%)
        chartPercentData.push({name: 'KRW', y: krwHoldPercent});

        return chartPercentData;
    })
    .then(chartData => {
        // Data retrieved from https://netmarketshare.com/
        // Make monochrome colors
        const colors = Highcharts.getOptions().colors.map((c, i) =>
            // Start out with a darkened base color (negative brighten), and end
            // up with a much brighter color
            Highcharts.color(Highcharts.getOptions().colors[0])
                .brighten((i - 3) / 7)
                .get()
        );

        /* Copilot purple palette */
        const accentPalette = ['#7C5CFC','#5865F2','#A78BFA','#E11D48','#2563EB','#059669','#F59E0B','#8B5CF6'];

        Highcharts.chart('hold_asset_chart', {
            chart: {
                plotBackgroundColor: 'transparent',
                backgroundColor: 'transparent',
                plotBorderWidth: null,
                plotShadow: false,
                type: 'pie',
                style: { fontFamily: "'Pretendard', sans-serif" }
            },
            title: {
                text: '보유 비중',
                align: 'center',
                style: { color: '#111827', fontSize: '15px', fontWeight: '800', fontFamily: "'Pretendard', sans-serif" }
            },
            tooltip: {
                pointFormat: '{series.name}: <b>{point.percentage:.1f}%</b>',
                backgroundColor: '#FFFFFF',
                borderColor: 'rgba(124,92,252,0.25)',
                borderRadius: 10,
                shadow: { color: 'rgba(0,0,0,0.10)', offsetX: 0, offsetY: 4, opacity: 1, width: 16 },
                style: { color: '#111827', fontSize: '14px', fontFamily: "'Pretendard', sans-serif" }
            },
            plotOptions: {
                pie: {
                    cursor: 'pointer',
                    colors: accentPalette,
                    borderWidth: 2,
                    borderColor: '#FFFFFF',
                    borderRadius: 4,
                    dataLabels: {
                        enabled: true,
                        format: '<b style="color:#111827">{point.name}</b><br><span style="color:#7C5CFC">{point.percentage:.1f}%</span>',
                        distance: -45,
                        style: { fontSize: '13px', fontWeight: '700', fontFamily: "'Pretendard', sans-serif", textOutline: 'none' },
                        filter: { property: 'percentage', operator: '>', value: 4 }
                    }
                }
            },
            legend: {
                itemStyle: { color: '#6B7280', fontFamily: "'Pretendard', sans-serif", fontSize: '13px' }
            },
            credits: { enabled: false },
            series: [{
                name: '비중',
                data: chartData
            }]
        });
    });
