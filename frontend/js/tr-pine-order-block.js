// 17단계 · 오더 블록과 SMC 차트 읽기 — 읽기형 페이지. GNB/LNB는 common.js의 initPage()가 그린다.
document.addEventListener('DOMContentLoaded',async()=>{
  if(typeof initPage==='function')await initPage();
  const modal=document.getElementById('tpobGlossaryModal'),opener=document.getElementById('tpobGlossary');
  if(!modal||!opener)return;
  const open=()=>{modal.classList.add('open');modal.setAttribute('aria-hidden','false');document.body.style.overflow='hidden'};
  const close=()=>{modal.classList.remove('open');modal.setAttribute('aria-hidden','true');document.body.style.overflow=''};
  opener.addEventListener('click',open);
  modal.querySelectorAll('[data-tpob-close]').forEach(item=>item.addEventListener('click',close));
  document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});
});
