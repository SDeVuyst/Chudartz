(function () {
  const bootEl = document.getElementById('gate-dashboard-boot');
  const cardsEl = document.getElementById('gate-cards');
  const feedEl = document.getElementById('gate-feed-body');
  if (!bootEl || !cardsEl || !feedEl) return;

  const boot = JSON.parse(bootEl.textContent);
  const liveEl = document.getElementById('gate-live-indicator');
  const filterForm = document.getElementById('gate-scans-filter-form');
  const clearBtn = document.getElementById('gate-scans-clear');
  const paginationEl = document.getElementById('gate-scans-pagination');
  const prevBtn = document.getElementById('gate-scans-prev');
  const nextBtn = document.getElementById('gate-scans-next');
  const pageLabel = document.getElementById('gate-scans-page-label');
  const liveHint = document.getElementById('gate-scans-live-hint');

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
    offline_pending: 'Offline — wijziging wacht',
    unmanaged: 'Niet beheerd vanuit admin',
  };

  const seenScanIds = new Set();
  let lastSeenScanId = 0;
  let cardEl = null;
  let currentFilters = boot.filters || { outcome: '', datum: '', q: '', page: 1 };
  let configOptions = boot.configOptions || { events: [], tickets_by_event: {} };

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
    void cardEl.offsetWidth;
    cardEl.classList.add(className);
  }

  function renderKpis(device) {
    document.querySelectorAll('[data-kpi]').forEach(function (el) {
      const value = device[el.dataset.kpi];
      if (value != null) el.textContent = value;
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

  function prependScan(scan) {
    feedEl.insertBefore(buildFeedRow(scan), feedEl.firstChild);
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

    if (liveHint) {
      liveHint.hidden = page <= 1;
    }
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

  function handleScansDelta(scans, flash) {
    if (!scans || !scans.is_delta) return;
    scans.items
      .slice()
      .reverse()
      .forEach(function (scan) {
        if (seenScanIds.has(scan.id)) return;
        seenScanIds.add(scan.id);
        lastSeenScanId = Math.max(lastSeenScanId, scan.id);
        const placeholder = feedEl.querySelector('.gate-feed__placeholder');
        if (placeholder) placeholder.remove();
        prependScan(scan);
        if (flash) flashCard(scan.success);
      });
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

    populateEventOptions(config.remote_event_id);
    populateTicketOptions(config.remote_event_id, config.remote_ticket_id);
  }

  function apply(payload, flash) {
    renderCard(payload.device);
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

  function setLive(isLive) {
    if (liveEl) liveEl.style.opacity = isLive ? '1' : '0.4';
  }

  function poll() {
    const canDelta = currentFilters.page <= 1;
    const extra = {};
    if (canDelta && lastSeenScanId) {
      extra.since_scan_id = lastSeenScanId;
    }
    const url = `${boot.statusUrl}${filtersQueryString(extra)}`;

    fetch(url, { credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(function (payload) {
        const liveActive = currentFilters.page <= 1;
        setLive(liveActive);
        apply(payload, liveActive);
      })
      .catch(function () {
        setLive(false);
      })
      .finally(function () {
        setTimeout(poll, boot.pollMs);
      });
  }

  function reloadWithFilters(page) {
    currentFilters.page = page || 1;
    const url = `${boot.statusUrl}${filtersQueryString()}`;

    fetch(url, { credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(function (payload) {
        apply(payload, false);
        setLive(currentFilters.page <= 1);
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
      reloadWithFilters(1);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      currentFilters = { outcome: '', datum: '', q: '', page: 1 };
      syncFilterForm();
      reloadWithFilters(1);
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      if (currentFilters.page > 1) {
        reloadWithFilters(currentFilters.page - 1);
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      reloadWithFilters(currentFilters.page + 1);
    });
  }

  if (configEvent) {
    configEvent.addEventListener('change', function () {
      const eventId = configEvent.value ? parseInt(configEvent.value, 10) : null;
      populateTicketOptions(eventId, null);
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
  setTimeout(poll, boot.pollMs);
})();
