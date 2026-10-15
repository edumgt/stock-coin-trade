/* Member ledger cards. External paper accounts are read-only and never added to personal totals. */
(() => {
 const defs=[['cash','공유 모의 현금','fa-wallet'],['stocks','국내주식 모의투자','fa-chart-line'],['crypto','코인 모의투자','fa-coins'],['alternatives','대체자산 모의투자','fa-layer-group'],['practice','KIS 스타일 가상 연습','fa-graduation-cap'],['kis','KIS Testbed 공용계좌','fa-building-columns'],['alpaca','Alpaca Paper 공용계좌','fa-globe']];
 const external=new Set(['kis','alpaca']),snapshots={},busy=new Set();
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const n=v=>v==null?'—':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:2});
 const at=v=>v?new Date(v).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' KST':'미조회';
 const labels={complete:'조회 완료',estimated:'교육용 시세 포함',partial:'일부 평가 실패',provider_snapshot:'브로커 조회값'};
 function metric(label,value,currency=''){return `<div><dt>${label}</dt><dd>${n(value)}${value==null?'':currency}</dd></div>`;}
 function render(id){const d=snapshots[id],def=defs.find(x=>x[0]===id),card=document.getElementById('sim-'+id);if(!card)return;
  const ext=external.has(id);let body='';
  if(!d)body=`<p class="sim-message">${ext?'공용 모의계좌입니다. 조회 버튼을 누르면 잔고를 읽습니다.':'회원 원장을 조회하고 있습니다…'}</p>`;
  else if(d.error)body=`<p class="sim-message sim-error">${esc(d.error)}</p>`;
  else if(id==='cash')body=`<strong class="sim-value">${n(d.cash)}원</strong><p class="sim-message">주식·코인·대체자산이 공유하는 현금입니다. 아래 각 투자 카드에 중복 배분하지 않습니다.</p>`;
  else{const unit=d.currency==='USD'?' USD':'원';body=`<strong class="sim-value">${n(d.value)}${d.value==null?'':unit}</strong><span class="sim-subtitle">현재 보유자산 평가액 · 현금 제외</span><dl class="sim-metrics">${metric('보유 자산',d.positions,'종')}${metric('보유 원가',d.cost,unit)}${metric('평가손익',d.pnl,unit)}${metric('평가수익률',d.pnl_pct,'%')}${metric('전체 체결',d.fills,'건')}${metric('거래한 자산',d.traded_assets,'종')}${metric('누적 매수',d.buy_amount,unit)}${metric('누적 매도',d.sell_amount,unit)}${d.cash!=null?metric('별도 예수금',d.cash,unit):''}${d.account_total!=null?metric('계좌 총자산',d.account_total,unit):''}</dl><p class="sim-message">${esc(d.history_scope||'')}${d.account_opened===false?' · 연습계좌 미개설':''}</p>${d.last_trade?`<p class="sim-message">마지막 거래 ${esc(d.last_trade.replace('T',' '))} (서버 기록시각)</p>`:''}<details><summary>집계 범위·주의사항</summary><p>${esc(d.coverage_note||'')}</p>${d.assets?.length?`<p>현재 보유: ${d.assets.map(x=>esc(x.symbol)).join(', ')}</p>`:''}</details>`;}
  card.innerHTML=`<header><h3><i class="fa-solid ${def[2]}" aria-hidden="true"></i> ${def[1]}</h3><span class="sim-badge">${ext?'공용·별도':id==='practice'?'내 별도 원장':'내 공유 원장'}</span></header>${body}<div class="sim-card-meta"><small>${esc(d?.source||'')}${d&&!d.error?' · '+at(d.as_of):''}${d?.status?' · '+(labels[d.status]||d.status):''}</small><button type="button" data-sim-refresh="${id}" ${busy.has(id)?'disabled':''}>${busy.has(id)?'조회 중…':ext?'계좌 조회':'새로고침'}</button></div>`;
 }
 function totals(){const out=document.getElementById('simulationTotal');const keys=['cash','stocks','crypto','alternatives'];const valid=keys.every(k=>snapshots[k]&&!snapshots[k].error&&(k==='cash'||snapshots[k].value!=null));
  out.textContent=valid?`내 공유 모의자산 총액 ${n(snapshots.cash.cash+keys.slice(1).reduce((v,k)=>v+snapshots[k].value,0))}원`: '내 공유 모의자산 총액: 모든 원장의 평가 완료 후 표시';
  out.title='공유 현금 + 국내주식 + 코인 + 대체자산 평가액. KIS 스타일 연습·외부 공용계좌 제외.';
 }
 async function load(id){if(busy.has(id))return;busy.add(id);render(id);try{const path=external.has(id)?'external/'+id:id;const r=await apiFetch('/api/trade/simulation-summary/'+path,{signal:AbortSignal.timeout(external.has(id)?45000:30000)});const d=await r.json();if(!r.ok)throw Error(d.message||d.error||'조회 실패');snapshots[id]=d;}catch(e){snapshots[id]={error:e.name==='TimeoutError'?'조회 시간이 초과되었습니다. 다시 조회하세요.':e.message};}finally{busy.delete(id);render(id);totals();}}
 window.addEventListener('hold-ready',()=>{const mount=document.getElementById('simulationCards');if(!mount)return;mount.innerHTML=defs.map(([id])=>`<article class="simulation-card" id="sim-${id}"></article>`).join('');defs.forEach(([id])=>render(id));mount.addEventListener('click',e=>{const button=e.target.closest('[data-sim-refresh]');if(button)load(button.dataset.simRefresh);});document.getElementById('simulationRefresh').onclick=()=>Promise.allSettled(defs.filter(([id])=>!external.has(id)).map(([id])=>load(id)));Promise.allSettled(defs.filter(([id])=>!external.has(id)).map(([id])=>load(id)));},{once:true});
})();
