(async () => {
  await initPage({ requireAuth: true });
  await loadKeys();
})();

function fmtDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('ko-KR', { hour12: false });
}

async function loadKeys() {
  const tbody = document.getElementById('keysTableBody');
  try {
    const res = await apiFetch('/api/member/api-keys');
    const data = await res.json();
    const keys = data.keys ?? [];
    if (!keys.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center" style="color:var(--muted);">발급된 키가 없습니다.</td></tr>';
      return;
    }
    tbody.innerHTML = keys.map(k => `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
        <td class="px-4 py-3" style="font-weight:700;color:var(--fg);font-size:13px;">${k.label}</td>
        <td class="px-4 py-3" style="font-family:monospace;font-size:12px;color:var(--muted);">${k.keyPrefix}••••••••</td>
        <td class="px-4 py-3" style="font-size:12px;color:var(--muted);">${fmtDate(k.createdAt)}</td>
        <td class="px-4 py-3" style="font-size:12px;color:var(--muted);">${fmtDate(k.lastUsedAt)}</td>
        <td class="px-4 py-3 text-center">
          ${k.isActive
            ? '<span class="badge" style="background:rgba(5,150,105,0.12);color:#059669;font-size:11px;">활성</span>'
            : '<span class="badge" style="background:rgba(156,163,175,0.15);color:#9CA3AF;font-size:11px;">폐기됨</span>'}
        </td>
        <td class="px-4 py-3 text-center">
          ${k.isActive
            ? `<button onclick="revokeKey(${k.id})" style="background:rgba(225,29,72,0.08);color:#E11D48;border:1px solid rgba(225,29,72,0.2);border-radius:6px;padding:.3rem .8rem;font-size:12px;font-weight:700;cursor:pointer;">폐기</button>`
            : '-'}
        </td>
      </tr>`).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center" style="color:#F87171;">불러오기 실패: ${err.message}</td></tr>`;
  }
}

async function createKey() {
  const btn = document.getElementById('createKeyBtn');
  const label = prompt('키 라벨을 입력하세요 (예: 트레이딩봇 서버)', 'My API Key');
  if (label === null) return;

  btn.disabled = true;
  btn.textContent = '발급 중...';
  try {
    const res = await apiFetch('/api/member/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.message ?? '발급에 실패했습니다.');
      return;
    }
    document.getElementById('newKeyValue').value = data.apiKey;
    document.getElementById('keyModalOverlay').style.display = 'flex';
    await loadKeys();
  } catch (err) {
    alert('오류: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '+ 새 키 발급';
  }
}

async function revokeKey(id) {
  if (!confirm('이 API 키를 폐기하시겠습니까? 폐기 후에는 되돌릴 수 없습니다.')) return;
  try {
    const res = await apiFetch(`/api/member/api-keys/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.message ?? '폐기에 실패했습니다.');
      return;
    }
    await loadKeys();
  } catch (err) {
    alert('오류: ' + err.message);
  }
}

function closeKeyModal() {
  document.getElementById('keyModalOverlay').style.display = 'none';
  document.getElementById('newKeyValue').value = '';
}

function copyNewKey() {
  const input = document.getElementById('newKeyValue');
  input.select();
  navigator.clipboard?.writeText(input.value).catch(() => {});
}
