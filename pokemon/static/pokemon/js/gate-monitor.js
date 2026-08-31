(function () {
  const bootEl = document.getElementById('gate-monitor-boot');
  const cardsEl = document.getElementById('gate-cards');
  const feedEl = document.getElementById('gate-feed-body');
  if (!bootEl || !cardsEl || !feedEl) return;

  const boot = JSON.parse(bootEl.textContent);
  const filtersEl = document.getElementById('gate-feed-filters');
  const liveEl = document.getElementById('gate-live-indicator');

  const FEED_MAX_ROWS = 200;
  const cardNodes = new Map();
  const seenScanIds = new Set();
  let lastSeenScanId = 0;
  let deviceFilter = null;

  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function buildCard(device) {
    const card = document.createElement('a');
    card.className = 'gate-card';
    card.href = boot.detailUrlTemplate.replace('__ID__', device.id);
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
    return card;
  }

  function updateCard(card, device) {
    card.querySelector('.gate-card__name').textContent = device.name;
    card.querySelector('.gate-card__dot').classList.toggle('is-online', device.online);

    const ticketEl = card.querySelector('.gate-card__ticket');
    const message = device.last_scan ? device.last_scan.message : '';
    ticketEl.textContent = message || 'Wachten op scan…';
    ticketEl.classList.toggle('is-empty', !message);

    card.querySelector('[data-role="count"]').textContent =
      `${device.today_total} scans`;
    card.querySelector('[data-role="time"]').textContent = device.last_scan
      ? device.last_scan.time
      : (device.online ? 'Online' : 'Offline');
  }

  function renderCards(devices) {
    devices.forEach(function (device) {
      let card = cardNodes.get(device.id);
      if (!card) {
        card = buildCard(device);
        cardNodes.set(device.id, card);
        cardsEl.appendChild(card);
      }
      updateCard(card, device);
    });

    cardNodes.forEach(function (card, id) {
      if (!devices.some((d) => d.id === id)) {
        card.remove();
        cardNodes.delete(id);
      }
    });

    if (!devices.length) {
      cardsEl.innerHTML =
        '<p class="gate-hint">Nog geen gate-toestellen aangemaakt.</p>';
    }
  }

  function flashCard(deviceId, success) {
    const card = cardNodes.get(deviceId);
    if (!card) return;
    const className = success ? 'flash-success' : 'flash-fail';
    card.classList.remove('flash-success', 'flash-fail');
    // Force a reflow so the animation restarts on rapid consecutive scans.
    void card.offsetWidth;
    card.classList.add(className);
  }

  function renderKpis(aggregate) {
    document.querySelectorAll('[data-kpi]').forEach(function (el) {
      const key = el.dataset.kpi;
      if (key === 'online') {
        el.textContent = `${aggregate.online_count}/${aggregate.total_count}`;
      } else if (aggregate[key] != null) {
        el.textContent = aggregate[key];
      }
    });
  }

  function buildFeedRow(scan) {
    const row = document.createElement('tr');
    row.dataset.deviceId = scan.device_id;
    row.innerHTML = `
      <td class="gate-feed__time">${escapeHtml(scan.time)}</td>
      <td>${escapeHtml(scan.device_name)}</td>
      <td class="gate-feed__outcome ${scan.success ? 'is-success' : 'is-fail'}">
        ${scan.success ? 'Toegelaten' : 'Geweigerd'}
      </td>
      <td>${escapeHtml(scan.message)}</td>
      <td>${scan.participant_id ? escapeHtml(scan.participant_id) : '—'}</td>`;
    applyFilterToRow(row);
    return row;
  }

  function applyFilterToRow(row) {
    const visible =
      deviceFilter === null || Number(row.dataset.deviceId) === deviceFilter;
    row.style.display = visible ? '' : 'none';
  }

  function prependScan(scan) {
    feedEl.insertBefore(buildFeedRow(scan), feedEl.firstChild);
    while (feedEl.children.length > FEED_MAX_ROWS) {
      feedEl.removeChild(feedEl.lastChild);
    }
  }

  function renderEmptyFeedIfNeeded() {
    const hasRows = feedEl.querySelector('tr[data-device-id]');
    const placeholder = feedEl.querySelector('.gate-feed__placeholder');
    if (!hasRows && !placeholder) {
      const row = document.createElement('tr');
      row.className = 'gate-feed__placeholder';
      row.innerHTML =
        '<td colspan="5" class="gate-feed__empty">Nog geen scans vandaag.</td>';
      feedEl.appendChild(row);
    } else if (hasRows && placeholder) {
      placeholder.remove();
    }
  }

  function renderFilters(devices) {
    if (!filtersEl || filtersEl.dataset.count === String(devices.length)) return;
    filtersEl.dataset.count = String(devices.length);
    filtersEl.innerHTML = '';

    const options = [{ id: null, name: 'Alle ingangen' }].concat(devices);
    options.forEach(function (option) {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'gate-chip';
      chip.textContent = option.name;
      chip.classList.toggle('is-active', deviceFilter === option.id);
      chip.addEventListener('click', function () {
        deviceFilter = option.id;
        filtersEl.querySelectorAll('.gate-chip').forEach(function (el) {
          el.classList.remove('is-active');
        });
        chip.classList.add('is-active');
        feedEl.querySelectorAll('tr[data-device-id]').forEach(applyFilterToRow);
      });
      filtersEl.appendChild(chip);
    });
  }

  function handleScans(scans, flash) {
    // Server sends newest first; replay oldest first so cards end on the latest scan.
    scans
      .slice()
      .reverse()
      .forEach(function (scan) {
        if (seenScanIds.has(scan.id)) return;
        seenScanIds.add(scan.id);
        lastSeenScanId = Math.max(lastSeenScanId, scan.id);
        prependScan(scan);
        if (flash) flashCard(scan.device_id, scan.success);
      });
  }

  function apply(payload, flash) {
    renderCards(payload.devices);
    renderFilters(payload.devices);
    renderKpis(payload.aggregate);
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
