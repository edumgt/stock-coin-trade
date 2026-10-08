(() => {
  const exchange=document.body.dataset.exchange;
  const panel=document.getElementById('exchange-chart-panel');
  const testPanel=document.getElementById('exchange-test-panel');
  const host=document.getElementById('exchange-candle-chart');
  const status=document.getElementById('chart-status');
  const detail=document.getElementById('chart-candle-detail');
  const symbol=document.getElementById('chart-symbol');
  const interval=document.getElementById('chart-interval');
  const reload=document.getElementById('chart-reload');
  const kst=(time)=>new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(Number(time)*1000));
  const number=(v)=>Number(v).toLocaleString('ko-KR',{maximumFractionDigits:8});
  let chart,candles,volume,rows=[],controller,sequence=0;
  const clear=()=>{rows=[];candles?.setData([]);volume?.setData([]);detail.textContent='';};
  function ensureChart() {
    if(chart)return;
    const L=window.LightweightCharts;
    if(!L)throw new Error('차트 라이브러리를 불러오지 못했습니다. 새로고침해 주세요.');
    chart=L.createChart(host,{autoSize:true,height:460,layout:{background:{color:'#ffffff'},textColor:'#334155',attributionLogo:true},grid:{vertLines:{color:'#f1f5f9'},horzLines:{color:'#f1f5f9'}},localization:{locale:'ko-KR',timeFormatter:kst},timeScale:{timeVisible:true,secondsVisible:false,tickMarkFormatter:kst},rightPriceScale:{scaleMargins:{top:.08,bottom:.25}}});
    candles=chart.addSeries(L.CandlestickSeries,{upColor:'#16a34a',downColor:'#dc2626',borderVisible:false,wickUpColor:'#16a34a',wickDownColor:'#dc2626',priceFormat:{type:'price',precision:exchange==='korbit'?0:2,minMove:exchange==='korbit'?1:.01}});
    volume=chart.addSeries(L.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume'});
    chart.priceScale('volume').applyOptions({scaleMargins:{top:.8,bottom:0}});
    chart.subscribeCrosshairMove(p=>{const r=p.seriesData.get(candles);if(r)showDetail(r,p.seriesData.get(volume)?.value);else if(rows.length)showDetail(rows.at(-1),rows.at(-1).volume);});
  }
  function showDetail(r,v){detail.textContent=`${kst(r.time)} KST · 시가 ${number(r.open)} · 고가 ${number(r.high)} · 저가 ${number(r.low)} · 종가 ${number(r.close)} · 거래량 ${number(v??0)}`;}
  async function load() {
    const run=++sequence;controller?.abort();controller=new AbortController();reload.disabled=true;clear();status.textContent='거래소 공개 캔들 API 조회 중…';
    try {
      ensureChart();
      symbol.value=exchange==='binance'?symbol.value.trim().toUpperCase().replace(/[\s/_-]/g,''):symbol.value.trim().toLowerCase();
      if(!symbol.value)throw new Error('거래쌍을 입력하세요.');
      const params=new URLSearchParams({symbol:symbol.value,interval:interval.value,limit:'200'});
      const response=await fetch(`${window.APP_CONFIG?.apiBase||''}/api/crypto-exchange-test/${exchange}/candles?${params}`,{signal:controller.signal});
      const data=await response.json();if(run!==sequence)return;
      if(!response.ok||!data.ok)throw new Error(data.message||'캔들 조회에 실패했습니다.');
      rows=data.result.candles||[];
      if(!rows.length){status.textContent='선택한 거래쌍·주기의 캔들 데이터가 없습니다.';return;}
      const smallest=Math.min(...rows.map(r=>r.low).filter(v=>v>0));const precision=exchange==='korbit'?0:smallest<1?8:smallest<100?4:2;
      candles.applyOptions({priceFormat:{type:'price',precision,minMove:10**-precision}});
      candles.setData(rows.map(({time,open,high,low,close})=>({time,open,high,low,close})));
      volume.setData(rows.map(r=>({time:r.time,value:r.volume,color:r.close>=r.open?'#16a34a66':'#dc262666'})));
      chart.timeScale().fitContent();showDetail(rows.at(-1),rows.at(-1).volume);
      status.textContent=`${data.result.exchange} · ${data.result.symbol} · ${interval.selectedOptions[0].textContent} · ${rows.length}개 봉 · 조회 ${kst(data.result.fetchedAt/1000)} KST`;
    }catch(e){if(run===sequence&&e.name!=='AbortError'){clear();status.textContent=`조회 실패: ${e.message}`;}}
    finally{if(run===sequence)reload.disabled=false;}
  }
  function selectTab(name){
    const show=name==='chart';panel.hidden=!show;testPanel.hidden=show;
    document.querySelectorAll('[data-exchange-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.exchangeTab===name)));
    if(show){symbol.value=document.getElementById('symbol')?.value||symbol.value;load();}
    else{sequence++;controller?.abort();reload.disabled=false;}
    history.replaceState(null,'',show?'#chart':'#api-test');
  }
  document.querySelectorAll('[data-exchange-tab]').forEach(b=>b.addEventListener('click',()=>selectTab(b.dataset.exchangeTab)));
  reload.addEventListener('click',load);interval.addEventListener('change',load);symbol.addEventListener('keydown',e=>{if(e.key==='Enter')load();});
  document.getElementById('chart-fit').addEventListener('click',()=>chart?.timeScale().fitContent());
  if(location.hash==='#chart')selectTab('chart');
})();
