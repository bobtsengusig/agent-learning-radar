(() => {
  'use strict';
  const key = 'agent-learning-radar:personal:v1';
  const week = Number(document.body.dataset.week);
  const complete = document.getElementById('lesson-complete');
  const status = document.getElementById('lesson-progress');
  const empty = () => ({ schema_version: 1, completed_weeks: [], bookmarks: [] });
  function read() {
    const raw = localStorage.getItem(key);
    if (!raw) return empty();
    const data = JSON.parse(raw);
    if (!data || data.schema_version !== 1 || !Array.isArray(data.completed_weeks) || !Array.isArray(data.bookmarks)
        || data.completed_weeks.length > 12 || data.bookmarks.length > 20000
        || data.completed_weeks.some(n => !Number.isInteger(n) || n < 1 || n > 12)
        || data.bookmarks.some(id => typeof id !== 'string' || id.length > 1000)) throw new Error('invalid progress');
    return { schema_version: 1, completed_weeks: [...new Set(data.completed_weeks)], bookmarks: [...new Set(data.bookmarks)] };
  }
  function refresh() {
    try {
      const data = read();
      complete.checked = data.completed_weeks.includes(week);
      complete.disabled = false;
      status.textContent = `已完成 ${data.completed_weeks.length} / 12 週。進度與首頁共用，僅保存在這個瀏覽器。`;
    } catch {
      complete.disabled = true;
      status.textContent = '無法讀取瀏覽器進度；請回總覽檢查或匯出備份。教材仍可閱讀。';
    }
  }
  complete.addEventListener('change', () => {
    try {
      const data = read(); // Re-read to preserve bookmarks and changes from another tab.
      data.completed_weeks = complete.checked ? [...new Set([...data.completed_weeks, week])]
        : data.completed_weeks.filter(n => n !== week);
      localStorage.setItem(key, JSON.stringify(data));
      refresh();
    } catch {
      complete.checked = !complete.checked;
      status.textContent = '無法保存進度；請回總覽匯出備份後再試。';
    }
  });
  window.addEventListener('storage', event => { if (event.key === key || event.key === null) refresh(); });
  window.addEventListener('pageshow', refresh);
  refresh();
  if (navigator.clipboard && window.isSecureContext) {
    document.querySelectorAll('[data-copy]').forEach(button => {
      button.hidden = false;
      button.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(document.getElementById(button.dataset.copy).textContent);
          button.textContent = '已複製 ✓';
          document.getElementById('copy-status').textContent = '程式碼已複製。';
          setTimeout(() => { button.textContent = '複製程式碼'; }, 2000);
        } catch {
          document.getElementById('copy-status').textContent = '瀏覽器未允許複製，請直接選取程式碼或下載檔案。';
        }
      });
    });
  }
})();
