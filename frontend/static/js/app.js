// ── Unsaved-changes tracking ──────────────────────────────────────────────────

function _content() { return document.getElementById('section-content'); }

// Mark dirty when any input inside section-content changes
document.addEventListener('input', function (e) {
  const c = _content();
  if (c && c.contains(e.target)) {
    c.dataset.dirty = 'true';
    const hint = c.querySelector('#unsaved-hint');
    if (hint) hint.style.display = 'inline';
  }
});

// Clear dirty after any HTMX swap into section-content (save or navigation)
document.body.addEventListener('htmx:afterSwap', function (e) {
  if (e.detail.target && e.detail.target.id === 'section-content') {
    const c = _content();
    if (c) c.dataset.dirty = '';
  }
  // If a new entry was appended (target is an inner list), mark dirty
  const c = _content();
  if (c && e.detail.target && e.detail.target.id !== 'section-content' && c.contains(e.detail.target)) {
    c.dataset.dirty = 'true';
    const hint = c.querySelector('#unsaved-hint');
    if (hint) hint.style.display = 'inline';
  }
});

// Warn before browser navigation away (reload, close)
window.addEventListener('beforeunload', function (e) {
  const c = _content();
  if (c && c.dataset.dirty === 'true') {
    e.preventDefault();
    e.returnValue = '';
  }
});

// ── Sidebar navigation with unsaved-changes gate ─────────────────────────────

function navigateTo(url, section) {
  const c = _content();
  if (c && c.dataset.dirty === 'true') {
    if (!confirm('You have unsaved changes. Leave this section?')) return;
  }
  // Update active link
  document.querySelectorAll('.section-link').forEach(function (a) {
    a.classList.toggle('active', a.dataset.section === section);
  });
  htmx.ajax('GET', url, { target: '#section-content', swap: 'innerHTML' });
}

// ── Dynamic link rows (Personal Info) ────────────────────────────────────────

function addLinkRow() {
  const c = document.getElementById('links-container');
  if (!c) return;
  const row = document.createElement('div');
  row.className = 'link-row';
  row.innerHTML =
    '<input type="text" name="link_label" placeholder="Label (e.g. LinkedIn)">' +
    '<input type="url"  name="link_url"   placeholder="https://…">' +
    '<button type="button" class="btn-icon" onclick="this.closest(\'.link-row\').remove()">✕</button>';
  c.appendChild(row);
  // Mark dirty
  const content = _content();
  if (content) {
    content.dataset.dirty = 'true';
    const hint = content.querySelector('#unsaved-hint');
    if (hint) hint.style.display = 'inline';
  }
}

// Mark active sidebar link on initial load
document.addEventListener('htmx:load', function () {
  const first = document.querySelector('.section-link[data-section="personal"]');
  if (first) first.classList.add('active');
});
