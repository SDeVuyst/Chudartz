(function () {
  const bootEl = document.getElementById('gate-dashboard-boot');
  const heroEl = document.getElementById('gate-dashboard-hero');
  const feedEl = document.getElementById('gate-feed-body');
  if (!bootEl || !heroEl || !feedEl) return;

  const boot = JSON.parse(bootEl.textContent);
  const liveEl = document.getElementById('gate-live-indicator');
  const filterForm = document.getElementById('gate-scans-filter-form');
  const clearBtn = document.getElementById('gate-scans-clear');
  const paginationEl = document.getElementById('gate-scans-pagination');
  const prevBtn = document.getElementById('gate-scans-prev');
  const nextBtn = document.getElementById('gate-scans-next');
  const pageLabel = document.getElementById('gate-scans-page-label');

  const configForm = document.getElementById('gate-config-form');
  const configEvent = document.getElementById('gate-config-event');
  const configTicket = document.getElementById('gate-config-ticket');
  const configBadge = document.getElementById('gate-config-badge');
  const configError = document.getElementById('gate-config-error');
  const reportedEvent = document.getElementById('gate-reported-event');
  const reportedTicket = document.getElementById('gate-reported-ticket');

  const CONFIG_STATUS_LABELS = {
    synced: 'Actief op toestel',
    pending: 'Wacht op toestel',
    offline_pending: 'Offline - wijziging wacht',
    unmanaged: 'Niet beheerd vanuit admin',
  };

  const HERO_SCANS_MAX = 3;
  const seenScanIds = new Set();
  const heroScanIds = new Set();
  let heroScans = [];
  let lastSeenScanId = 0;
  let configFormDirty = false;
  let isLive = true;
  let lastDeviceOnline = false;
  let currentFilters = boot.filters || { outcome: '', datum: '', q: '', page: 1 };
  let configOptions = boot.configOptions || { events: [], tickets_by_event: {} };
  const anim = window.GateAnimations;

  function getCsrf() {
    const input = document.querySelector('input[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function formatDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString('nl-BE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function buildHero() {
    heroEl.innerHTML = `
      <div class="gate-dashboard-card__grid">
        <div class="gate-dashboard-card__main">
          <div class="gate-dashboard-card__status">
            <span class="gate-card__dot" data-role="dot"></span>
            <div>
              <span class="gate-dashboard-card__status-line" data-role="status-line"></span>
              <span class="gate-dashboard-card__status-meta" data-role="status-meta"></span>
            </div>
          </div>
          <h2 class="gate-dashboard-card__name" data-role="name"></h2>
          <h3 class="gate-dashboard-card__scans-title">Laatste scans</h3>
          <ul class="gate-recent-scans" id="gate-recent-scans-list"></ul>
        </div>
        <div class="gate-dashboard-card__side">
          <div class="gate-dashboard-card__kpis">
            <div class="gate-dashboard-card__kpi">
              <span class="gate-dashboard-card__kpi-label">Scans vandaag</span>
              <span class="gate-dashboard-card__kpi-value" data-kpi="today_total">0</span>
            </div>
            <div class="gate-dashboard-card__kpi">
              <span class="gate-dashboard-card__kpi-label">Toegelaten</span>
              <span class="gate-dashboard-card__kpi-value" data-kpi="today_success">0</span>
            </div>
            <div class="gate-dashboard-card__kpi">
              <span class="gate-dashboard-card__kpi-label">Geweigerd</span>
              <span class="gate-dashboard-card__kpi-value" data-kpi="today_fail">0</span>
            </div>
          </div>
          <div class="gate-dashboard-card__meta">
            <div class="gate-dashboard-card__meta-row">
              <span class="gate-dashboard-card__meta-label">API-sleutel</span>
              <span class="gate-dashboard-card__meta-value" data-role="api-key">—</span>
            </div>
            <div class="gate-dashboard-card__meta-row">
              <span class="gate-dashboard-card__meta-label">Heartbeat</span>
              <span class="gate-dashboard-card__meta-value" data-role="heartbeat">—</span>
            </div>
            <div class="gate-dashboard-card__meta-row">
              <span class="gate-dashboard-card__meta-label">Laatste geldige scan</span>
              <span class="gate-dashboard-card__meta-value" data-role="last-used">—</span>
            </div>
          </div>
        </div>
      </div>`;
  }

  function buildRecentScanItem(scan) {
    const li = document.createElement('li');
    li.className = 'gate-recent-scan';
    li.dataset.scanId = scan.id;
    li.innerHTML = `
      <span class="gate-recent-scan__time">${escapeHtml(scan.time || '')}</span>
      <span class="gate-recent-scan__outcome ${scan.success ? 'is-success' : 'is-fail'}">
        ${scan.success ? 'Toegelaten' : 'Geweigerd'}
      </span>
      <span class="gate-recent-scan__message">${escapeHtml(scan.message)}</span>`;
    return li;
  }

  function prependRecentScan(scan, animate) {
    const listEl = heroEl.querySelector('#gate-recent-scans-list');
    if (!listEl) return;

    if (listEl.querySelector(`[data-scan-id="${scan.id}"]`)) return;

    const empty = listEl.querySelector('.gate-recent-scans__empty');
    if (empty) empty.remove();

    const li = buildRecentScanItem(scan);
    listEl.insertBefore(li, listEl.firstChild);
    if (animate && anim) anim.animateListItem(li, scan.success);

    while (listEl.children.length > HERO_SCANS_MAX) {
      listEl.removeChild(listEl.lastChild);
    }
  }

  function syncHeroScanIds() {
    heroScanIds.clear();
    heroScans.forEach(function (scan) {
      heroScanIds.add(scan.id);
    });
  }

  function addHeroScans(scans, animate) {
    if (!scans || !scans.length) return;

    scans.forEach(function (scan) {
      if (heroScanIds.has(scan.id)) return;
      heroScanIds.add(scan.id);
      heroScans.unshift(scan);
    });

    heroScans.sort(function (a, b) {
      return b.id - a.id;
    });
    heroScans = heroScans.slice(0, HERO_SCANS_MAX);
    syncHeroScanIds();

    if (animate) {
      scans
        .slice()
        .sort(function (a, b) {
          return a.id - b.id;
        })
        .forEach(function (scan) {
          prependRecentScan(scan, true);
        });
    }
  }

  function renderRecentScans() {
    const listEl = heroEl.querySelector('#gate-recent-scans-list');
    if (!listEl) return;

    listEl.innerHTML = '';
    if (!heroScans.length) {
      const empty = document.createElement('p');
      empty.className = 'gate-recent-scans__empty';
      empty.textContent = 'Nog geen scans vandaag.';
      listEl.appendChild(empty);
      return;
    }

    heroScans.forEach(function (scan) {
      listEl.appendChild(buildRecentScanItem(scan));
    });
  }

  function renderHero(device) {
    if (!heroEl.querySelector('[data-role="name"]')) buildHero();

    lastDeviceOnline = Boolean(device.online);
    heroEl.querySelector('[data-role="name"]').textContent = device.name;
    if (anim) {
      anim.updateStatusDot(heroEl.querySelector('[data-role="dot"]'), device.online, isLive);
    } else {
      heroEl.querySelector('[data-role="dot"]').classList.toggle('is-online', device.online);
    }

    const statusLine = heroEl.querySelector('[data-role="status-line"]');
    statusLine.textContent = device.online ? 'Online' : 'Offline';

    const metaParts = [];
    if (device.is_active) {
      metaParts.push('Toestel geactiveerd');
    } else {
      metaParts.push('Toestel gedesactiveerd');
    }
    if (device.last_heartbeat_at) {
      metaParts.push(`Heartbeat ${formatDateTime(device.last_heartbeat_at)}`);
    } else {
      metaParts.push('Nog geen heartbeat');
    }
    heroEl.querySelector('[data-role="status-meta"]').textContent = metaParts.join(' · ');

    heroEl.querySelector('[data-role="api-key"]').textContent =
      device.api_key_prefix ? `${device.api_key_prefix}…` : '—';
    heroEl.querySelector('[data-role="heartbeat"]').textContent =
      formatDateTime(device.last_heartbeat_at);
    heroEl.querySelector('[data-role="last-used"]').textContent =
      formatDateTime(device.last_used_at);

    renderRecentScans();
  }

  function flashHero(success) {
    const className = success ? 'flash-success' : 'flash-fail';
    heroEl.classList.remove('flash-success', 'flash-fail');
    void heroEl.offsetWidth;
    heroEl.classList.add(className);
  }

  function renderKpis(device) {
    heroEl.querySelectorAll('[data-kpi]').forEach(function (el) {
      const value = device[el.dataset.kpi];
      if (value == null) return;
      if (anim) {
        anim.animateKpiNumber(el, value);
      } else {
        el.textContent = value;
      }
    });
  }

  function participantCell(scan) {
    if (scan.participant_admin_url && scan.participant_id) {
      return `<a href="${escapeHtml(scan.participant_admin_url)}">${escapeHtml(scan.participant_id)}</a>`;
    }
    if (scan.participant_id) {
      return escapeHtml(scan.participant_id);
    }
    return '—';
  }

  function buildFeedRow(scan) {
    const row = document.createElement('tr');
    row.dataset.scanId = scan.id;
    row.innerHTML = `
      <td class="gate-feed__time">${escapeHtml(scan.created_at_display || scan.time)}</td>
      <td class="gate-feed__outcome ${scan.success ? 'is-success' : 'is-fail'}">
        ${scan.success ? 'Toegelaten' : 'Geweigerd'}
      </td>
      <td>${escapeHtml(scan.message)}</td>
      <td>${participantCell(scan)}</td>`;
    return row;
  }

  function prependScan(scan, animate) {
    const row = buildFeedRow(scan);
    feedEl.insertBefore(row, feedEl.firstChild);
    if (animate && anim) anim.animateFeedRow(row, scan.success);
  }

  function renderScansTable(scans) {
    feedEl.innerHTML = '';
    seenScanIds.clear();
    lastSeenScanId = 0;

    if (!scans.items || scans.items.length === 0) {
      const row = document.createElement('tr');
      row.className = 'gate-feed__placeholder';
      row.innerHTML =
        '<td colspan="4" class="gate-feed__empty">Geen scans gevonden.</td>';
      feedEl.appendChild(row);
      return;
    }

    scans.items.forEach(function (scan) {
      seenScanIds.add(scan.id);
      lastSeenScanId = Math.max(lastSeenScanId, scan.id);
      feedEl.appendChild(buildFeedRow(scan));
    });

    if ((currentFilters.page || 1) <= 1 && !hasActiveTableFilters()) {
      addHeroScans(scans.items, false);
      renderRecentScans();
    }
  }

  function hasActiveTableFilters() {
    return Boolean(currentFilters.outcome || currentFilters.datum || currentFilters.q);
  }

  function renderPagination(scans) {
    const page = scans.page || 1;
    const total = scans.total_pages || 1;
    const show = total > 1 || scans.has_previous || scans.has_next;

    paginationEl.hidden = !show;
    if (!show) return;

    pageLabel.textContent = `Pagina ${page} van ${total}`;
    prevBtn.disabled = !scans.has_previous;
    nextBtn.disabled = !scans.has_next;
  }

  function syncFilterForm() {
    document.getElementById('gate-datum').value = currentFilters.datum || '';
    document.getElementById('gate-outcome').value = currentFilters.outcome || '';
    document.getElementById('gate-q').value = currentFilters.q || '';
  }

  function filtersQueryString(extra) {
    const params = new URLSearchParams();
    if (currentFilters.outcome) params.set('outcome', currentFilters.outcome);
    if (currentFilters.datum) params.set('datum', currentFilters.datum);
    if (currentFilters.q) params.set('q', currentFilters.q);
    if (currentFilters.page && currentFilters.page > 1) {
      params.set('page', String(currentFilters.page));
    }
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        if (extra[key] != null && extra[key] !== '') {
          params.set(key, String(extra[key]));
        }
      });
    }
    const qs = params.toString();
    return qs ? `?${qs}` : '';
  }

  function trackScanIds(scans) {
    if (!scans || !scans.items) return false;
    let hasNew = false;
    scans.items.forEach(function (scan) {
      if (!seenScanIds.has(scan.id)) {
        hasNew = true;
      }
      seenScanIds.add(scan.id);
      lastSeenScanId = Math.max(lastSeenScanId, scan.id);
    });
    return hasNew;
  }

  function handleScansDelta(scans, flash) {
    if (!scans || !scans.is_delta) return false;
    const page = currentFilters.page || 1;
    const hasNew = trackScanIds(scans);

    if (!hasNew) return false;

    addHeroScans(scans.items, flash);

    if (page <= 1) {
      scans.items
        .slice()
        .reverse()
        .forEach(function (scan) {
          if (feedEl.querySelector(`tr[data-scan-id="${scan.id}"]`)) return;
          const placeholder = feedEl.querySelector('.gate-feed__placeholder');
          if (placeholder) placeholder.remove();
          prependScan(scan, flash);
          if (flash) flashHero(scan.success);
        });
    } else {
      reloadWithFilters(page, false);
    }
    return true;
  }

  function populateEventOptions(selectedId) {
    configEvent.innerHTML = '<option value="">Alle evenementen</option>';
    configOptions.events.forEach(function (ev) {
      const opt = document.createElement('option');
      opt.value = String(ev.id);
      opt.textContent = ev.label;
      if (selectedId && ev.id === selectedId) opt.selected = true;
      configEvent.appendChild(opt);
    });
  }

  function ticketsForEvent(eventId) {
    if (!eventId) return [];
    const map = configOptions.tickets_by_event || {};
    return map[eventId] || map[String(eventId)] || [];
  }

  function populateTicketOptions(eventId, selectedId) {
    configTicket.innerHTML = '<option value="">Alle tickettypes</option>';
    if (!eventId) {
      configTicket.disabled = true;
      return;
    }
    configTicket.disabled = false;
    ticketsForEvent(eventId).forEach(function (ticket) {
      const opt = document.createElement('option');
      opt.value = String(ticket.id);
      opt.textContent = ticket.label;
      if (selectedId && ticket.id === selectedId) opt.selected = true;
      configTicket.appendChild(opt);
    });
  }

  function labelAlle(id, label) {
    if (!id) return 'Alle';
    return label || String(id);
  }

  function renderConfig(config) {
    if (!config) return;

    const status = config.status || 'unmanaged';
    configBadge.dataset.status = status;
    configBadge.textContent = CONFIG_STATUS_LABELS[status] || status;

    reportedEvent.textContent = labelAlle(
      config.reported_event_id,
      config.reported_event_label
    );
    reportedTicket.textContent = labelAlle(
      config.reported_ticket_id,
      config.reported_ticket_label
    );

    if (!configFormDirty) {
      populateEventOptions(config.remote_event_id);
      populateTicketOptions(config.remote_event_id, config.remote_ticket_id);
    }
  }

  function apply(payload, flash) {
    renderHero(payload.device);
    renderKpis(payload.device);
    renderConfig(payload.device.config);

    if (payload.scans && payload.scans.is_delta) {
      handleScansDelta(payload.scans, flash);
    } else if (payload.scans) {
      renderScansTable(payload.scans);
      renderPagination(payload.scans);
    }

    if (payload.filters) {
      currentFilters = payload.filters;
      syncFilterForm();
    }
  }

  function setLive(live) {
    isLive = live;
    if (!liveEl) return;
    liveEl.style.opacity = live ? '1' : '0.4';
    liveEl.textContent = live ? 'Live updates actief' : 'Live updates gepauzeerd';
    if (anim) {
      anim.updateStatusDot(
        heroEl.querySelector('[data-role="dot"]'),
        lastDeviceOnline,
        live
      );
      anim.updateAllStatusDots(document.getElementById('gate-admin'), live);
    }
  }

  function poll() {
    const extra = {};
    if (lastSeenScanId) {
      extra.since_scan_id = lastSeenScanId;
    }
    const url = `${boot.statusUrl}${filtersQueryString(extra)}`;

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

  function reloadWithFilters(page, flash) {
    currentFilters.page = page || 1;
    const url = `${boot.statusUrl}${filtersQueryString()}`;

    fetch(url, { credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(function (payload) {
        apply(payload, flash);
        setLive(true);
      });
  }

  if (filterForm) {
    filterForm.addEventListener('submit', function (event) {
      event.preventDefault();
      currentFilters = {
        outcome: document.getElementById('gate-outcome').value,
        datum: document.getElementById('gate-datum').value,
        q: document.getElementById('gate-q').value.trim(),
        page: 1,
      };
      reloadWithFilters(1, false);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      currentFilters = { outcome: '', datum: '', q: '', page: 1 };
      syncFilterForm();
      reloadWithFilters(1, false);
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      if (currentFilters.page > 1) {
        reloadWithFilters(currentFilters.page - 1, false);
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      reloadWithFilters(currentFilters.page + 1, false);
    });
  }

  if (configEvent) {
    configEvent.addEventListener('change', function () {
      configFormDirty = true;
      const eventId = configEvent.value ? parseInt(configEvent.value, 10) : null;
      populateTicketOptions(eventId, null);
    });
  }

  if (configTicket) {
    configTicket.addEventListener('change', function () {
      configFormDirty = true;
    });
  }

  if (configForm) {
    configForm.addEventListener('submit', function (event) {
      event.preventDefault();
      if (configError) {
        configError.hidden = true;
        configError.textContent = '';
      }

      const eventVal = configEvent.value;
      const ticketVal = configTicket.value;
      const body = {
        event_id: eventVal ? parseInt(eventVal, 10) : null,
        ticket_id: ticketVal ? parseInt(ticketVal, 10) : null,
      };

      fetch(boot.configUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify(body),
      })
        .then(function (response) {
          return response.json().then(function (data) {
            if (!response.ok) throw new Error(data.message || 'Opslaan mislukt.');
            return data;
          });
        })
        .then(function (data) {
          configFormDirty = false;
          if (data.config) {
            renderConfig(data.config);
          }
        })
        .catch(function (err) {
          if (configError) {
            configError.hidden = false;
            configError.textContent = err.message || 'Opslaan mislukt.';
          }
        });
    });
  }

  apply(boot, false);
  syncFilterForm();
  setLive(true);
  setTimeout(poll, boot.pollMs);
})();
