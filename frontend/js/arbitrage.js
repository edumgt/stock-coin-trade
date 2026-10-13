(() => {
  'use strict';
  const names = [['UPBIT','업비트'],['BITHUMB','빗썸'],['COINONE','코인원'],['KORBIT','코빗']];
  const canvas = document.getElementById('arbitrageCanvas'), ctx = canvas.getContext('2d');
  const money = value => Math.round(value).toLocaleString('ko-KR') + ' 원';
  const cards = document.getElementById('exchangeCards');
  const status = document.getElementById('quoteStatus');
  const button = document.getElementById('refreshPrices');
  let quotes = [], fetchedAt = 0, receivedAt = 0, failed = false, loading = false, pairs = [], selected = null, refreshTimer;
  const fresh = () => !failed && receivedAt > 0 && Date.now() - receivedAt < 45000 && Date.now() - fetchedAt < 45000;
  for (const [code,name] of names) {
    const card = document.createElement('article'); card.className = 'arb-exchange';
    card.innerHTML = `<h2>${name} <span class="arb-tag">BTC / KRW</span></h2><p class="arb-price" id="price-${code}">조회 중</p><p class="arb-tag" id="state-${code}">공식 공개 시세</p>`;
    cards.append(card);
  }
  function update() {
    const usable = fresh();
    pairs = [];
    const valid = quotes.filter(q => Number.isFinite(q.tradePriceKrw) && q.tradePriceKrw > 0);
    for (let i=0;i<valid.length;i++) for (let j=i+1;j<valid.length;j++) {
      const [buy,sell] = [valid[i],valid[j]].sort((a,b)=>a.tradePriceKrw-b.tradePriceKrw);
      pairs.push({buy,sell,spread:(sell.tradePriceKrw-buy.tradePriceKrw)/buy.tradePriceKrw*100});
    }
    pairs.sort((a,b)=>b.spread-a.spread);
    selected = usable ? pairs[0] || null : null;
    for (const [code] of names) {
      const quote=valid.find(q=>q.exchangeCode===code);
      document.getElementById('price-'+code).textContent = quote ? money(quote.tradePriceKrw) : '조회 불가';
      document.getElementById('state-'+code).textContent = !quote ? '추천 비교에서 제외' : !usable ? '지연 시세 · 추천 중단' : '최근 체결가 · 조회 완료';
    }
    cards.classList.toggle('arb-stale',!usable);
    const count = valid.length;
    status.textContent = !usable ? '시세 지연/조회 실패 · 추천 중단' : count===4 ? '4개 거래소 정상 · 실시간 조회' : `일부 조회 실패 · ${count}/4개 비교`;
    document.getElementById('quoteTime').textContent = fetchedAt ? 'API 조회 시각: '+new Date(fetchedAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' KST' : '조회 시각 없음';
    const recommendation=document.getElementById('recommendation');
    recommendation.textContent = !usable ? '새 시세가 확인될 때까지 매매 추천을 중단합니다.' : !selected ? '비교 가능한 거래소가 2개 미만입니다.' : selected.spread>=0.5 ? `매매 검토 추천: ${selected.buy.exchangeName} 매수 → ${selected.sell.exchangeName} 매도 · 차이 ${selected.spread.toFixed(3)}% (비용 차감 전)` : `대기: 최대 차이 ${selected.spread.toFixed(3)}% · 추천 기준 0.5% 미만`;
    recommendation.classList.toggle('arb-signal',!!selected && selected.spread>=0.5);
    const list=document.getElementById('pairList'); list.replaceChildren();
    for(const pair of pairs) {
      const row=document.createElement('div');row.className='arb-pair';
      const direction=document.createElement('span');direction.textContent=pair.buy.exchangeName+' 매수 → '+pair.sell.exchangeName+' 매도';
      const value=document.createElement('strong'); value.textContent=pair.spread.toFixed(3)+'% · '+(!usable?'중단':pair.spread>=0.5?'추천':'대기');
      if(usable && pair.spread>=0.5)value.className='arb-signal';
      row.append(direction,value);list.append(row);
    }
    if(!pairs.length)list.textContent='비교 가능한 시세를 기다리는 중입니다.';
    calculate();
    canvas.setAttribute('aria-label',recommendation.textContent+' · '+valid.map(q=>q.exchangeName+' '+money(q.tradePriceKrw)).join(', '));
  }
  function calculate(event) {
    event?.preventDefault();
    const result=document.getElementById('arbitrageResult'),error=document.getElementById('calculationError');
    result.replaceChildren();error.textContent='';
    document.getElementById('selectedPair').textContent=selected ? selected.buy.exchangeName+' 매수 → '+selected.sell.exchangeName+' 매도 · '+(selected.spread>=0.5?'추천 기준 충족':'기준 미달 · 비교 계산') : '최신 시세가 확인되면 예상 차익을 계산합니다.';
    if(!selected)return;
    const ids=['quantity','buyFee','sellFee','transferCost'];
    const values=ids.map(id=>Number(document.getElementById(id).value));
    const [quantity,buyFee,sellFee,transfer]=values;
    if(values.some((v,i)=>!Number.isFinite(v)||v<0||document.getElementById(ids[i]).value.trim()==='')||quantity<=0||buyFee>100||sellFee>100){error.textContent='수량은 0보다 크게, 수수료는 0~100%로 입력하세요.';return;}
    const cost=selected.buy.tradePriceKrw*quantity,revenue=selected.sell.tradePriceKrw*quantity,fees=cost*buyFee/100+revenue*sellFee/100+transfer,net=revenue-cost-fees;
    if(!Number.isFinite(net)){error.textContent='계산 가능한 범위의 수량을 입력하세요.';return;}
    for(const [label,value] of [['매수 금액',cost],['매도 금액',revenue],['수수료 · 기타 비용',fees],['예상 순차익',net]]){
      const row=document.createElement('div');row.className='result-row';
      const title=document.createElement('span');title.className='result-label';title.textContent=label;
      const amount=document.createElement('span');amount.className='result-value';amount.textContent=money(value);if(label==='예상 순차익')amount.id='netProfit';
      row.append(title,amount);result.append(row);
    }
    const note=document.createElement('p');note.className='arb-help';note.textContent=net>0?'입력 비용 기준 예상 순차익이 양수입니다.':'입력 비용 기준 예상 순차익이 0 이하이므로 매매를 권장하지 않습니다.';result.append(note);
  }
  async function refresh() {
    if(loading)return;clearTimeout(refreshTimer);loading=true;button.disabled=true;
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),25000);
    status.textContent='4개 거래소 실제 BTC 시세 조회 중';
    try {
      const response=await fetch('/api/crypto/KRW-BTC/domestic-prices',{cache:'no-store',signal:controller.signal});
      if(!response.ok)throw new Error('시세 응답 오류');
      const data=await response.json();
      if(data.symbol!=='BTC'||!Array.isArray(data.prices)||!Number.isFinite(data.fetchedAt))throw new Error('시세 형식 오류');
      quotes=names.map(([code,name])=>({exchangeCode:code,exchangeName:name,tradePriceKrw:data.prices.find(q=>q.exchangeCode===code)?.tradePriceKrw ?? null}));
      fetchedAt=data.fetchedAt;receivedAt=Date.now();failed=false;
    } catch {failed=true;} finally {
      clearTimeout(timeout);loading=false;button.disabled=false;update();
      if(!document.hidden)refreshTimer=setTimeout(refresh,10000);
    }
  }
  let width=0,height=0;
  new ResizeObserver(()=>{
    const rect=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1;
    width=rect.width;height=rect.height;canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);
  }).observe(canvas);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function draw(time) {
    if(!document.hidden && width && height){
      ctx.clearRect(0,0,width,height);
      const narrow=width<600,positions=narrow?[[width*.25,height*.27],[width*.75,height*.27],[width*.25,height*.77],[width*.75,height*.77]]:[[width*.13,height*.52],[width*.38,height*.52],[width*.63,height*.52],[width*.88,height*.52]];
      const active=selected&&selected.spread>=0.5&&fresh();
      if(active){
        const from=positions[names.findIndex(([c])=>c===selected.buy.exchangeCode)],to=positions[names.findIndex(([c])=>c===selected.sell.exchangeCode)];
        ctx.strokeStyle='#16a34a';ctx.lineWidth=3;ctx.setLineDash([8,7]);ctx.lineDashOffset=reduced.matches?0:-time/35;ctx.beginPath();ctx.moveTo(...from);ctx.lineTo(...to);ctx.stroke();ctx.setLineDash([]);
        const progress=reduced.matches?.5:(time%2400)/2400;ctx.beginPath();ctx.arc(from[0]+(to[0]-from[0])*progress,from[1]+(to[1]-from[1])*progress,6,0,Math.PI*2);ctx.fillStyle='#16a34a';ctx.fill();
      }
      const colors=['#2563eb','#f97316','#7c3aed','#0d9488'];
      names.forEach(([code,name],i)=>{
        const [x,y]=positions[i],q=quotes.find(v=>v.exchangeCode===code),price=q?.tradePriceKrw;
        ctx.fillStyle='#f1f5f9';ctx.beginPath();ctx.arc(x,y,44+(reduced.matches||!fresh()?0:Math.sin(time/800+i)*2),0,Math.PI*2);ctx.fill();ctx.strokeStyle=colors[i];ctx.lineWidth=3;ctx.stroke();ctx.textAlign='center';ctx.fillStyle=colors[i];ctx.font='bold 16px Pretendard, sans-serif';ctx.fillText(name,x,y+6);
        ctx.fillStyle='#0f172a';ctx.font='bold '+(narrow?13:17)+'px Pretendard, sans-serif';ctx.fillText(Number.isFinite(price)&&price>0?money(price):'조회 불가',x,y+72);
        ctx.font='12px Pretendard, sans-serif';ctx.fillStyle='#64748b';ctx.fillText(!fresh()?'추천 중단':active?(code===selected.buy.exchangeCode?'매수 추천':code===selected.sell.exchangeCode?'매도 추천':'비교 거래소'):'가격 비교',x,y-59);
      });
      ctx.fillStyle=active?'#15803d':'#64748b';ctx.font='bold 14px Pretendard, sans-serif';ctx.textAlign='center';ctx.fillText(active?'0.5% 이상 · 매수 → 매도 흐름':'BTC / KRW · 최신 체결가 비교',width/2,24);
    }
    requestAnimationFrame(draw);
  }
  document.getElementById('arbitrageForm').addEventListener('submit',calculate);
  button.addEventListener('click',refresh);
  document.addEventListener('visibilitychange',()=>{clearTimeout(refreshTimer);if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden && receivedAt && !fresh())update();},1000);
  requestAnimationFrame(draw);refresh();initPage().catch(()=>{});
})();
