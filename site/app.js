(() => {
  'use strict';
  const payload = JSON.parse(document.getElementById('app-data').textContent);
  const { settings, sources, radar } = payload;
  const $ = (selector) => document.querySelector(selector);
  const key = 'agent-learning-radar:personal:v1';
  const empty = () => ({ schema_version: 1, completed_weeks: [], bookmarks: [] });
  const dateTime = (value) => value ? new Date(value).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei', hour12: false }) : '尚無紀錄';
  const dateOnly = (value) => value ? new Date(value).toLocaleDateString('sv-SE', { timeZone: 'Asia/Taipei' }) : '日期未提供';
  function validateBackup(value) {
    if (!value || value.schema_version !== 1 || !Array.isArray(value.completed_weeks) || !Array.isArray(value.bookmarks)) throw new Error('備份格式不正確，需使用版本 1 的本站備份。');
    if (value.completed_weeks.length > 12 || value.bookmarks.length > 20000 || value.completed_weeks.some(n => !Number.isInteger(n) || n < 1 || n > 12) || value.bookmarks.some(id => typeof id !== 'string' || id.length > 1000)) throw new Error('備份含有無效的進度或收藏。');
    return { schema_version: 1, completed_weeks: [...new Set(value.completed_weeks)], bookmarks: [...new Set(value.bookmarks)] };
  }
  let personal = empty();
  let storageAvailable = true;
  try {
    const saved = localStorage.getItem(key);
    if (saved) personal = validateBackup(JSON.parse(saved));
  } catch { storageAvailable = false; }
  function announce(message) { $('#backup-status').textContent = message; }
  function save() {
    try { localStorage.setItem(key, JSON.stringify(personal)); storageAvailable = true; }
    catch { storageAvailable = false; announce('瀏覽器無法保存資料。目前進度僅保留於此頁，請使用匯出備份。'); }
  }
  if (!storageAvailable) announce('無法讀取瀏覽器儲存空間。請匯出備份，以免關閉後遺失進度。');
  function updateProgress() {
    $('#progress').value = personal.completed_weeks.length;
    $('#progress-label').textContent = `${personal.completed_weeks.length} / 12 週`;
    document.querySelectorAll('[data-complete]').forEach(input => {
      const checked = personal.completed_weeks.includes(Number(input.dataset.complete));
      input.checked = checked;
      input.closest('.week-card').classList.toggle('is-complete', checked);
    });
  }
  document.querySelectorAll('[data-complete]').forEach(input => input.addEventListener('change', () => {
    const week = Number(input.dataset.complete);
    personal.completed_weeks = input.checked ? [...new Set([...personal.completed_weeks, week])] : personal.completed_weeks.filter(n => n !== week);
    save(); updateProgress();
  }));
  updateProgress();

  // Anchor navigation remains fully usable without JS; enhance it into focused panels.
  const panels = new Set(['roadmap', 'radar', 'frameworks', 'weekly', 'sources']);
  function showPanel() {
    const fragment = location.hash.slice(1);
    if (fragment === 'main') return;
    const selected = fragment.startsWith('week-') || !panels.has(fragment) ? 'roadmap' : fragment;
    document.querySelectorAll('[data-panel]').forEach(panel => { panel.hidden = panel.dataset.panel !== selected; });
    document.querySelectorAll('[data-nav]').forEach(anchor => {
      const active = anchor.dataset.nav === selected;
      anchor.classList.toggle('active', active);
      if (active) anchor.setAttribute('aria-current', 'page'); else anchor.removeAttribute('aria-current');
    });
    if (fragment.startsWith('week-')) requestAnimationFrame(() => document.getElementById(fragment)?.scrollIntoView({ block: 'start' }));
  }
  window.addEventListener('hashchange', showPanel);
  showPanel();

  function freshness() {
    const node = $('#freshness');
    const last = radar.last_success_at ? new Date(radar.last_success_at) : null;
    const stale = !last || Date.now() - last.getTime() > 48 * 3600000;
    const failed = sources.filter(s => radar.sources[s.id]?.status === 'error').length;
    node.classList.toggle('is-stale', stale || failed > 0);
    node.textContent = !last ? '尚未完成首次自動收集。請先在 GitHub Actions 執行更新工作流程。' :
      stale ? `資料更新已超過 48 小時。最近成功：${dateTime(radar.last_success_at)}（台北）。請檢查 GitHub Actions。` :
      `最近收集成功：${dateTime(radar.last_success_at)}（台北） · ${sources.length - failed}/${sources.length} 個來源成功${failed ? '，部分來源需處理' : ''}`;
  }
  freshness();
  setInterval(freshness, 60000);

  function element(tag, text, cls) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }
  function externalLink(url, text) {
    const anchor = element('a', text);
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== 'https:' || parsed.username || parsed.password) throw new Error('Unsafe URL');
      anchor.href = parsed.href;
    } catch { return element('span', text); }
    anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
    return anchor;
  }
  const categoryNames = { '': '全部消息', ...settings.categories };
  let category = '';
  let limit = 24;
  Object.entries(categoryNames).forEach(([id, title]) => {
    const button = element('button', title, 'chip');
    button.type = 'button'; button.dataset.category = id; button.setAttribute('aria-pressed', String(id === category));
    button.addEventListener('click', () => { category = id; limit = 24; renderNews(); });
    $('#category-filters').append(button);
  });
  [...sources].sort((a, b) => a.product.localeCompare(b.product)).forEach(source => {
    const option = element('option', source.product); option.value = source.id; $('#product-filter').append(option);
  });
  Object.entries(settings.release_types).forEach(([id, title]) => {
    const option = element('option', title); option.value = id; $('#type-filter').append(option);
  });
  const knownIds = new Set(radar.items.map(x => x.id));
  function newsCard(item) {
    const card = element('article', undefined, 'news-card');
    const meta = element('div', undefined, 'card-meta');
    meta.append(element('span', `${settings.categories[item.category]} · ${item.product}`), element('time', dateOnly(item.published_at)));
    const heading = element('h3'); heading.append(externalLink(item.url, item.title + ' ↗'));
    const foot = element('div', undefined, 'card-foot');
    const tags = element('div', undefined, 'tag-row');
    tags.append(element('span', settings.release_types[item.release_type]));
    if (item.version) tags.append(element('span', item.version));
    if (item.revision_count) tags.append(element('span', `已修訂 ${item.revision_count} 次`));
    const button = element('button', personal.bookmarks.includes(item.id) ? '★ 已收藏' : '☆ 收藏', 'bookmark-button');
    button.type = 'button'; button.setAttribute('aria-pressed', String(personal.bookmarks.includes(item.id))); button.setAttribute('aria-label', `收藏：${item.title}`);
    button.addEventListener('click', () => {
      personal.bookmarks = personal.bookmarks.includes(item.id) ? personal.bookmarks.filter(id => id !== item.id) : [...personal.bookmarks, item.id];
      save(); renderNews();
    });
    foot.append(tags, button);
    card.append(meta, heading, element('p', item.excerpt || '請至官方來源閱讀完整發布內容。'), foot,
      element('small', `首次發現 ${dateOnly(item.first_seen_at)} · 最近變更 ${dateOnly(item.updated_at)}`, 'item-provenance'));
    return card;
  }
  function renderNews() {
    const query = $('#search').value.trim().toLocaleLowerCase();
    const product = $('#product-filter').value;
    const type = $('#type-filter').value;
    const range = $('#date-filter').value;
    const bookmarks = $('#bookmarks-only').checked;
    const cutoff = Date.now() - Number(range) * 86400000;
    const matches = radar.items.filter(item => (!category || item.category === category) && (!product || item.source_id === product) && (!type || item.release_type === type) &&
      (!bookmarks || personal.bookmarks.includes(item.id)) && (!query || `${item.product} ${item.title} ${item.excerpt} ${item.version || ''}`.toLocaleLowerCase().includes(query)) &&
      (range === 'all' || (range === 'undated' ? !item.published_at : item.published_at && new Date(item.published_at).getTime() >= cutoff)));
    $('#news-list').replaceChildren(...matches.slice(0, limit).map(newsCard));
    if (!matches.length) $('#news-list').append(element('p', '沒有符合條件的消息。可調整篩選，或查看來源健康狀態。', 'empty-state'));
    $('#result-count').textContent = `${matches.length} 則消息${bookmarks ? ' · 已收藏' : ''}`;
    $('#load-more').hidden = limit >= matches.length;
    $('#load-more').textContent = `載入更多（還有 ${Math.max(0, matches.length - limit)} 則）`;
    document.querySelectorAll('[data-category]').forEach(button => { button.setAttribute('aria-pressed', String(button.dataset.category === category)); });
  }
  ['search', 'product-filter', 'type-filter', 'date-filter', 'bookmarks-only'].forEach(id => $('#' + id).addEventListener(id === 'search' ? 'input' : 'change', () => { limit = 24; renderNews(); }));
  $('#load-more').addEventListener('click', () => { limit += 24; renderNews(); });
  renderNews();

  const lookup = new Map(radar.items.map(x => [x.id, x]));
  if (!radar.digests.length) $('#weekly-list').append(element('p', '尚未產生週報。首次成功更新時會建立前一個完整週的彙整。', 'empty-state'));
  radar.digests.forEach((digest, index) => {
    const box = element('details', undefined, 'digest'); box.open = index === 0;
    box.id = 'digest-' + digest.id;
    box.append(element('summary', `${digest.id}　${digest.item_ids.length} 則官方更新`));
    box.append(element('p', `${digest.start} 至 ${digest.end_exclusive} 前 · 台北時間 · 產生於 ${dateTime(digest.generated_at)}`, 'muted'));
    Object.entries(settings.categories).forEach(([id, name]) => {
      const chosen = digest.item_ids.map(itemId => lookup.get(itemId)).filter(item => item?.category === id);
      if (!chosen.length) return;
      box.append(element('h3', name));
      const list = element('ul', undefined, 'digest-links');
      chosen.forEach(item => { const li = element('li'); li.append(externalLink(item.url, item.product + ' · ' + item.title), element('small', item.published_at ? dateOnly(item.published_at) : '日期未提供，依首次發現時間歸週')); list.append(li); });
      box.append(list);
    });
    if (!digest.item_ids.length) box.append(element('p', '本週沒有收集到新消息。請同時查看來源健康狀態。'));
    $('#weekly-list').append(box);
  });

  let successful = 0;
  sources.forEach(source => {
    const health = radar.sources[source.id] || {};
    if (health.status === 'ok') successful += 1;
    const row = element('tr');
    const identity = element('td');
    identity.append(externalLink(source.homepage || source.url || `https://github.com/${source.repo}/releases`, source.product), element('small', settings.categories[source.category]));
    const status = element('td');
    status.append(element('span', health.status === 'ok' ? '● 成功' : health.status === 'error' ? '● 異常' : '○ 待收集', 'health ' + (health.status || 'pending')));
    const note = element('td', health.error || health.coverage || '等待首次收集');
    if (health.items_in_window !== undefined) note.append(element('small', `本次 90 日視窗 ${health.items_in_window} 則`));
    row.append(identity, status, element('td', dateTime(health.last_attempt_at)), element('td', dateTime(health.last_success_at)), note);
    $('#sources-body').append(row);
  });
  $('#source-summary').append(element('b', `${successful} / ${sources.length}`), element('span', '個來源最近檢查成功'), element('small', `最近嘗試：${dateTime(radar.last_attempt_at)}（台北）`));

  $('#export').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify({ ...personal, exported_at: new Date().toISOString() }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a');
    a.href = url; a.download = `agent-learning-radar-backup-${dateOnly(new Date().toISOString())}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000); announce('已匯出學習進度與收藏備份。');
  });
  $('#import').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error('備份檔案超過 2 MB。');
      const next = validateBackup(JSON.parse(await file.text()));
      try { localStorage.setItem(key + ':before-import', JSON.stringify(personal)); } catch { /* Export remains available when storage is unavailable. */ }
      personal = next; save(); updateProgress(); renderNews();
      const missing = personal.bookmarks.filter(id => !knownIds.has(id)).length;
      announce(`已匯入 ${personal.completed_weeks.length} 週進度、${personal.bookmarks.length} 筆收藏。${missing ? `其中 ${missing} 筆尚未出現在目前公開資料中，已保留識別碼。` : ''}${storageAvailable ? '' : '請匯出備份；目前瀏覽器無法持久保存。'}`);
    } catch (error) { announce(`匯入失敗：${error.message} 原有進度未變更。`); }
    event.target.value = '';
  });
})();
