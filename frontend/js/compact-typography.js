/* Shared title/description scale: preserve each page's existing type hierarchy. */
(() => {
  if (window.__edumgtCompactTypography) return;
  const selector = 'h1,h2,h3,h4,h5,h6,[role="heading"],.page-title,.section-title,.card-title,.content-title,.lesson-title,p,.description,.subtitle,.content-lead,.content-kicker,.help-text,.hint,.text-muted,.text-mute,.text-xs,.text-sm,.lesson-content li,.lesson-body li';
  const excluded = 'nav,button,input,select,textarea,pre,code,footer,[role="navigation"],.ag-root,.ag-root-wrapper,svg,canvas';
  const originals = new Map();
  let frame = 0;
  function apply() {
    frame = 0;
    // Restore all baselines before measuring: nested descriptions never shrink twice.
    for (const [el, original] of originals) {
      if (!el.isConnected) { originals.delete(el); continue; }
      if (original.value) el.style.setProperty('font-size', original.value, original.priority);
      else el.style.removeProperty('font-size');
    }
    const sizes = [];
    document.querySelectorAll(selector).forEach(el => {
      if (el.closest(excluded)) return;
      // Utility classes also occur on layout containers. Only scale actual text.
      if (!el.matches('h1,h2,h3,h4,h5,h6,p,[role="heading"]') && !Array.from(el.childNodes).some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim())) return;
      if (!originals.has(el)) originals.set(el, {value:el.style.getPropertyValue('font-size'),priority:el.style.getPropertyPriority('font-size')});
      const size = parseFloat(getComputedStyle(el).fontSize);
      if (Number.isFinite(size)) sizes.push([el,size]);
    });
    for (const [el,size] of sizes) el.style.setProperty('font-size', `${size * 0.92}px`, 'important');
  }
  function schedule() { if (!frame) frame = requestAnimationFrame(apply); }
  window.__edumgtCompactTypography = { refresh:schedule, scale:0.92 };
  function start() {
    apply();
    new MutationObserver(records => {
      if (records.some(r => !(r.target instanceof SVGElement) && (r.type === 'attributes' || r.addedNodes.length || r.removedNodes.length))) schedule();
    }).observe(document.body, {subtree:true,childList:true,attributes:true,attributeFilter:['class']});
    window.addEventListener('resize',schedule,{passive:true});
    window.addEventListener('load',schedule,{once:true});
    document.fonts?.ready.then(schedule);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();
