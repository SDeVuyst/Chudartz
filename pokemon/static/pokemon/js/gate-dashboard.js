(function () {
  const bootEl = document.getElementById('gate-dashboard-boot');
  const cardsEl = document.getElementById('gate-cards');
  const feedEl = document.getElementById('gate-feed-body');
  if (!bootEl || !cardsEl || !feedEl) return;

  const boot = JSON.parse(bootEl.textContent);
  const liveEl = document.getElementById('gate-live-indicator');

  const FEED_MAX_ROWS = 200;
  const seenScanIds = new Set();
  let lastSeenScanId = 0;
  let cardEl = null;

  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function buildCard() {
    const card = document.createElement('div');
    card.className = 'gate-card';
    card.innerHTML = `
      <div class="gate-card__head">
        <span class="gate-card__dot"></span>
        <span class="gate-card__name"></span>
      </div>
      <div class="gate-card__ticket"></div>
      <div class="gate-card__meta">
        <span data-role="count"></span>
        <span data-role="time"></span>
      </div>`;
    cardsEl.appendChild(card);
    return card;
  }

  function renderCard(device) {
    if (!cardEl) cardEl = buildCard();

    cardEl.querySelector('.gate-card__name').textContent = device.name;
    cardEl.querySelector('.gate-card__dot').classList.toggle('is-online', device.online);

    const ticketEl = cardEl.querySelector('.gate-card__ticket');
    const message = device.last_scan ? device.last_scan.message : '';
    ticketEl.textContent = message || 'Wachten op scan…';
    ticketEl.classList.toggle('is-empty', !message);

    cardEl.querySelector('[data-role="count"]').textContent =
      `${device.today_total} scans`;
    cardEl.querySelector('[data-role="time"]').textContent = device.last_scan
      ? device.last_scan.time
      : (device.online ? 'Online' : 'Offline');
  }

  function flashCard(success) {
    if (!cardEl) return;
    const className = success ? 'flash-success' : 'flash-fail';
    cardEl.classList.remove('flash-success', 'flash-fail');
    // Force a reflow so the animation restarts on rapid consecutive scans.
    void cardEl.offsetWidth;
    cardEl.classList.add(className);
  }

  function renderKpis(device) {
    document.querySelectorAll('[data-kpi]').forEach(function (el) {
      const value = device[el.dataset.kpi];
      if (value != null) el.textContent = value;
    });
  }

  function prependScan(scan) {
    const row = document.createElement('tr');
    row.dataset.scanId = scan.id;
    row.innerHTML = `
      <td class="gate-feed__time">${escapeHtml(scan.time)}</td>
      <td class="gate-feed__outcome ${scan.success ? 'is-success' : 'is-fail'}">
        ${scan.success ? 'Toegelaten' : 'Geweigerd'}
      </td>
      <td>${escapeHtml(scan.message)}</td>
      <td>${scan.participant_id ? escapeHtml(scan.participant_id) : '—'}</td>`;

    feedEl.insertBefore(row, feedEl.firstChild);
    while (feedEl.children.length > FEED_MAX_ROWS) {
      feedEl.removeChild(feedEl.lastChild);
    }
  }

  function renderEmptyFeedIfNeeded() {
    const hasRows = feedEl.querySelector('tr[data-scan-id]');
    const placeholder = feedEl.querySelector('.gate-feed__placeholder');
    if (!hasRows && !placeholder) {
      const row = document.createElement('tr');
      row.className = 'gate-feed__placeholder';
      row.innerHTML =
        '<td colspan="4" class="gate-feed__empty">Nog geen scans.</td>';
      feedEl.appendChild(row);
    } else if (hasRows && placeholder) {
      placeholder.remove();
    }
  }

  function handleScans(scans, flash) {
    // Server sends newest first; replay oldest first so the card ends on the latest scan.
    scans
      .slice()
      .reverse()
      .forEach(function (scan) {
        if (seenScanIds.has(scan.id)) return;
        seenScanIds.add(scan.id);
        lastSeenScanId = Math.max(lastSeenScanId, scan.id);
        prependScan(scan);
        if (flash) flashCard(scan.success);
      });
  }

  function apply(payload, flash) {
    renderCard(payload.device);
    renderKpis(payload.device);
    handleScans(payload.recent_scans || [], flash);
    renderEmptyFeedIfNeeded();
  }

  function setLive(isLive) {
    if (liveEl) liveEl.style.opacity = isLive ? '1' : '0.4';
  }

  function poll() {
    const url = lastSeenScanId
      ? `${boot.statusUrl}?since_scan_id=${lastSeenScanId}`
      : boot.statusUrl;

    fetch(url, { credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(function (payload) {
        setLive(true);
        apply(payload, true);
      })
      .catch(function () {
        setLive(false);
      })
      .finally(function () {
        setTimeout(poll, boot.pollMs);
      });
  }

  apply(boot, false);
  setTimeout(poll, boot.pollMs);
})();
