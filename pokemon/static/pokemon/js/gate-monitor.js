(function () {
  const bootEl = document.getElementById('gate-monitor-boot');
  const cardsEl = document.getElementById('gate-cards');
  const feedEl = document.getElementById('gate-feed-body');
  if (!bootEl || !cardsEl || !feedEl) return;

  const boot = JSON.parse(bootEl.textContent);
  const filtersEl = document.getElementById('gate-feed-filters');
  const liveEl = document.getElementById('gate-live-indicator');
  const filterForm = document.getElementById('gate-scans-filter-form');
  const clearBtn = document.getElementById('gate-scans-clear');

  const FEED_MAX_ROWS = 200;
  const cardNodes = new Map();
  const seenScanIds = new Set();
  let lastSeenScanId = 0;
  let deviceFilter = boot.filters && boot.filters.device_id != null
    ? boot.filters.device_id
    : null;
  let currentFilters = boot.filters || { outcome: '', datum: '', q: '' };
  let isLive = true;
  const anim = window.GateAnimations;

  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
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

  function filterSubtitle(device) {
    const config = device.config || {};
    const parts = [];
    if (config.remote_event_label) parts.push(config.remote_event_label);
    if (config.remote_ticket_label) parts.push(config.remote_ticket_label);
    return parts.length ? parts.join(' · ') : 'Alle evenementen';
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
      <div class="gate-card__filter" data-role="filter"></div>
      <div class="gate-card__meta">
        <span data-role="count"><span class="gate-anim-count" data-role="count-num">0</span> scans</span>
        <span data-role="time"></span>
      </div>`;
    return card;
  }

  function updateCard(card, device) {
    card.querySelector('.gate-card__name').textContent = device.name;
    const filterEl = card.querySelector('[data-role="filter"]');
    if (filterEl) {
      filterEl.textContent = filterSubtitle(device);
      filterEl.title = filterEl.textContent;
    }
    const dot = card.querySelector('.gate-card__dot');
    if (anim) {
      anim.updateStatusDot(dot, device.online, isLive);
    } else {
      dot.classList.toggle('is-online', device.online);
    }

    const countNum = card.querySelector('[data-role="count-num"]');
    if (countNum && anim) {
      anim.animateKpiNumber(countNum, device.today_total);
    } else if (countNum) {
      countNum.textContent = device.today_total;
    }

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
    void card.offsetWidth;
    card.classList.add(className);
  }

  function renderKpis(aggregate) {
    document.querySelectorAll('[data-kpi]').forEach(function (el) {
      const key = el.dataset.kpi;
      if (key === 'online') {
        const parts = el.querySelectorAll('[data-role="online-num"], [data-role="total-num"]');
        if (parts.length === 2 && anim) {
          anim.animateKpiNumber(parts[0], aggregate.online_count);
          anim.animateKpiNumber(parts[1], aggregate.total_count);
        } else {
          el.textContent = `${aggregate.online_count}/${aggregate.total_count}`;
        }
      } else if (aggregate[key] != null) {
        if (anim) {
          anim.animateKpiNumber(el, aggregate[key]);
        } else {
          el.textContent = aggregate[key];
        }
      }
    });
  }

  function buildFeedRow(scan) {
    const row = document.createElement('tr');
    row.dataset.scanId = scan.id;
    row.innerHTML = `
      <td class="gate-feed__time">${escapeHtml(scan.created_at_display || scan.time)}</td>
      <td>${escapeHtml(scan.device_name)}</td>
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
    while (feedEl.children.length > FEED_MAX_ROWS) {
      feedEl.removeChild(feedEl.lastChild);
    }
  }

  function renderScansTable(scans) {
    feedEl.innerHTML = '';
    seenScanIds.clear();
    lastSeenScanId = 0;

    if (!scans.items || scans.items.length === 0) {
      renderEmptyFeedIfNeeded();
      return;
    }

    scans.items.forEach(function (scan) {
      seenScanIds.add(scan.id);
      lastSeenScanId = Math.max(lastSeenScanId, scan.id);
      feedEl.appendChild(buildFeedRow(scan));
    });
  }

  function renderEmptyFeedIfNeeded() {
    const hasRows = feedEl.querySelector('tr[data-scan-id]');
    const placeholder = feedEl.querySelector('.gate-feed__placeholder');
    if (!hasRows && !placeholder) {
      const row = document.createElement('tr');
      row.className = 'gate-feed__placeholder';
      row.innerHTML =
        '<td colspan="5" class="gate-feed__empty">Geen scans gevonden.</td>';
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
        reloadWithFilters(false);
      });
      filtersEl.appendChild(chip);
    });
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
    if (deviceFilter != null) params.set('device_id', String(deviceFilter));
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

  function handleScans(scans, flash) {
    if (!scans) return;

    if (scans.is_delta) {
      scans.items
        .slice()
        .reverse()
        .forEach(function (scan) {
          if (seenScanIds.has(scan.id)) return;
          seenScanIds.add(scan.id);
          lastSeenScanId = Math.max(lastSeenScanId, scan.id);
          const placeholder = feedEl.querySelector('.gate-feed__placeholder');
          if (placeholder) placeholder.remove();
          prependScan(scan, flash);
          if (flash) flashCard(scan.device_id, scan.success);
        });
    } else {
      renderScansTable(scans);
    }
    renderEmptyFeedIfNeeded();
  }

  function apply(payload, flash) {
    renderCards(payload.devices);
    renderFilters(payload.devices);
    renderKpis(payload.aggregate);
    handleScans(payload.recent_scans || { items: [], is_delta: false }, flash);

    if (payload.filters) {
      currentFilters = {
        outcome: payload.filters.outcome || '',
        datum: payload.filters.datum || '',
        q: payload.filters.q || '',
      };
      if (payload.filters.device_id !== undefined) {
        deviceFilter = payload.filters.device_id;
      }
      syncFilterForm();
    }
  }

  function setLive(live) {
    isLive = live;
    if (!liveEl) return;
    liveEl.style.opacity = live ? '1' : '0.4';
    liveEl.textContent = live ? 'Live updates actief' : 'Live updates gepauzeerd';
    if (anim) {
      anim.updateAllStatusDots(document.getElementById('gate-admin'), live);
    }
  }

  function reloadWithFilters(flash) {
    seenScanIds.clear();
    lastSeenScanId = 0;
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

  if (filterForm) {
    filterForm.addEventListener('submit', function (event) {
      event.preventDefault();
      currentFilters = {
        outcome: document.getElementById('gate-outcome').value,
        datum: document.getElementById('gate-datum').value,
        q: document.getElementById('gate-q').value.trim(),
      };
      reloadWithFilters(false);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      currentFilters = { outcome: '', datum: '', q: '' };
      syncFilterForm();
      reloadWithFilters(false);
    });
  }

  apply(boot, false);
  syncFilterForm();
  setLive(true);
  setTimeout(poll, boot.pollMs);
})();
