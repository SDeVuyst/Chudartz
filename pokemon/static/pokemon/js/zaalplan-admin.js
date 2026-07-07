(function () {
  const gridEl = document.getElementById('zaalplan-grid');
  const emptyEl = document.getElementById('zaalplan-empty');
  if (!gridEl) return;

  const saveUrl = gridEl.dataset.saveUrl;
  const settingsUrl = gridEl.dataset.settingsUrl;
  const generateUrl = gridEl.dataset.generateUrl;
  const mergeUrl = gridEl.dataset.mergeUrl;
  const splitUrl = gridEl.dataset.splitUrl;
  let gridData = window.ZAALPLAN_DATA || { rijen: 0, kolommen: 0, cellen: [] };

  let currentMode = 'tafel';
  let isPainting = false;
  const paintedInDrag = new Set();
  const mergeSelection = new Set();
  let mergeDragging = false;

  const detailEl = document.getElementById('cel-detail');
  const hintEl = document.getElementById('zp-mode-hint');

  const MODE_HINTS = {
    tafel: 'Klik of sleep om tafels te plaatsen. Rechtermuisklik maakt een vakje leeg.',
    geblokkeerd: 'Klik of sleep om cellen te blokkeren (gang/geen plaats). Rechtermuisklik maakt leeg.',
    leeg: 'Klik of sleep om cellen leeg te maken.',
    reserveren: 'Klik op een tafel om ze als "reeds gereserveerd" te markeren (of opnieuw vrij te geven).',
    samenvoegen: 'Sleep over de cellen (elke vorm mag, ook een hoek of L-vorm) en laat los om samen te voegen.',
    splitsen: 'Klik op een samengevoegde cel om ze weer op te splitsen.',
    bewerken: 'Klik op een cel om tekst (bv. Gang, Ingang) of een tafelprijs in te stellen.',
  };

  function getCsrf() {
    const input = document.querySelector('#csrf-form input[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    }).then(async (r) => {
      const data = await r.json().catch(() => null);
      if (!r.ok || !data) throw new Error((data && data.error) || `Request mislukt (${r.status})`);
      return data;
    });
  }

  function cellSize() {
    if (gridData.kolommen > 24) return 28;
    if (gridData.kolommen > 18) return 32;
    if (gridData.kolommen > 12) return 36;
    return 42;
  }

  function findCel(id) {
    return gridData.cellen.find((c) => c.id === id);
  }

  function elFor(id) {
    return gridEl.querySelector(`[data-id="${id}"]`);
  }

  function isDonkerType(type) {
    return type !== 'tafel';
  }

  // Bepaal de langste aaneengesloten strook (horizontaal of verticaal) van een groep,
  // zodat het label altijd op gevulde cellen staat (ook bij L-vormen).
  function bestLabelArea(leden) {
    let best = { len: 0, r1: leden[0].rij, r2: leden[0].rij, c1: leden[0].kolom, c2: leden[0].kolom };

    const rows = {};
    leden.forEach((c) => { (rows[c.rij] = rows[c.rij] || []).push(c.kolom); });
    Object.keys(rows).forEach((r) => {
      const cols = rows[r].sort((a, b) => a - b);
      let start = cols[0], prev = cols[0];
      for (let i = 1; i <= cols.length; i++) {
        if (i < cols.length && cols[i] === prev + 1) { prev = cols[i]; continue; }
        const len = prev - start + 1;
        if (len > best.len) best = { len, r1: +r, r2: +r, c1: start, c2: prev };
        if (i < cols.length) { start = cols[i]; prev = cols[i]; }
      }
    });

    const colsMap = {};
    leden.forEach((c) => { (colsMap[c.kolom] = colsMap[c.kolom] || []).push(c.rij); });
    Object.keys(colsMap).forEach((k) => {
      const rr = colsMap[k].sort((a, b) => a - b);
      let start = rr[0], prev = rr[0];
      for (let i = 1; i <= rr.length; i++) {
        if (i < rr.length && rr[i] === prev + 1) { prev = rr[i]; continue; }
        const len = prev - start + 1;
        if (len > best.len) best = { len, r1: start, r2: prev, c1: +k, c2: +k };
        if (i < rr.length) { start = rr[i]; prev = rr[i]; }
      }
    });

    return best;
  }

  function renderGrid() {
    const size = cellSize();
    gridEl.style.gridTemplateColumns = `repeat(${gridData.kolommen}, ${size}px)`;
    gridEl.style.gridAutoRows = `${size}px`;
    gridEl.innerHTML = '';

    if (!gridData.cellen || gridData.cellen.length === 0) {
      if (emptyEl) emptyEl.classList.remove('hidden');
      return;
    }
    if (emptyEl) emptyEl.classList.add('hidden');

    gridData.cellen.forEach((cel) => {
      const div = document.createElement('div');
      let cls = `zaalplan-cel ${cel.type}`;
      if (cel.bezet) cls += ' bezet';
      if (cel.gereserveerd) cls += ' gereserveerd';
      if (cel.groep) {
        cls += ' grouped';
        if (cel.buren.boven) cls += ' nb-top';
        if (cel.buren.onder) cls += ' nb-bottom';
        if (cel.buren.links) cls += ' nb-left';
        if (cel.buren.rechts) cls += ' nb-right';
      } else if (cel.type !== 'tafel' && cel.tekst) {
        cls += ' heeft-tekst';
      }
      div.className = cls;
      div.dataset.id = cel.id;
      div.style.gridColumn = `${cel.kolom + 1}`;
      div.style.gridRow = `${cel.rij + 1}`;

      // Losse cellen tonen hun eigen tekst; groepen krijgen een centraal label
      if (!cel.groep) {
        if (cel.type === 'tafel') {
          div.textContent = cel.label;
          div.title = `${cel.label} (€${cel.prijs})`;
        } else if (cel.tekst) {
          div.textContent = cel.tekst;
          div.title = cel.tekst;
        }
      }

      div.addEventListener('mousedown', (e) => {
        if (e.button === 2) return; // rechtermuisklik apart afgehandeld
        e.preventDefault();
        onCellMouseDown(cel);
      });
      div.addEventListener('contextmenu', (e) => { e.preventDefault(); emptyCell(cel); });
      div.addEventListener('mouseenter', () => onCellEnter(cel));
      gridEl.appendChild(div);
    });

    renderGroupLabels(size);
  }

  function renderGroupLabels(size) {
    const groepen = {};
    gridData.cellen.forEach((cel) => {
      if (!cel.groep) return;
      (groepen[cel.groep] = groepen[cel.groep] || []).push(cel);
    });

    Object.values(groepen).forEach((leden) => {
      const primary = leden.find((c) => c.is_primary) || leden[0];
      const area = bestLabelArea(leden);

      const label = document.createElement('div');
      label.className = 'zaalplan-groep-label' + (isDonkerType(primary.type) ? ' op-donker' : '');
      label.style.gridColumn = `${area.c1 + 1} / ${area.c2 + 2}`;
      label.style.gridRow = `${area.r1 + 1} / ${area.r2 + 2}`;
      label.textContent = primary.type === 'tafel' ? primary.label : (primary.tekst || '');
      gridEl.appendChild(label);
    });
  }

  function applyTypeLocally(cel, newType) {
    cel.type = newType;
    const el = elFor(cel.id);
    if (!el) return;
    el.classList.remove('leeg', 'tafel', 'geblokkeerd');
    el.classList.add(newType);
    if (!cel.groep) el.textContent = newType === 'tafel' ? cel.label : (cel.tekst || '');
  }

  function paintType(cel, newType) {
    if (cel.bezet) return;
    if (cel.type === newType && !cel.groep) return;
    postJson(saveUrl, { cel_id: cel.id, cel_type: newType })
      .then((data) => { gridData = data.grid; renderGrid(); })
      .catch((err) => { alert(err.message); });
  }

  function emptyCell(cel) {
    if (cel.bezet) { alert('Deze cel heeft een echte boeking en kan niet leeggemaakt worden.'); return; }
    postJson(saveUrl, { cel_id: cel.id, leegmaken: true })
      .then((data) => { gridData = data.grid; renderGrid(); })
      .catch((err) => alert(err.message));
  }

  function onCellMouseDown(cel) {
    if (currentMode === 'bewerken') {
      if (cel.bezet) { alert('Deze cel heeft een echte boeking en kan niet gewijzigd worden.'); return; }
      showCelDetail(cel);
      return;
    }
    if (currentMode === 'reserveren') {
      if (cel.bezet) { alert('Deze cel heeft al een echte boeking.'); return; }
      if (cel.type !== 'tafel') { alert('Alleen tafels kunnen gereserveerd worden.'); return; }
      postJson(saveUrl, { cel_id: cel.id, gereserveerd: !cel.gereserveerd })
        .then((data) => { gridData = data.grid; renderGrid(); })
        .catch((err) => alert(err.message));
      return;
    }
    if (currentMode === 'splitsen') {
      if (!cel.groep) return;
      postJson(splitUrl, { cel_id: cel.id })
        .then((data) => { gridData = data.grid; renderGrid(); })
        .catch((err) => alert(err.message));
      return;
    }
    if (currentMode === 'samenvoegen') {
      mergeDragging = true;
      mergeSelection.clear();
      toggleMergeCel(cel);
      return;
    }
    isPainting = true;
    paintedInDrag.clear();
    onCellPaint(cel);
  }

  function onCellEnter(cel) {
    if (currentMode === 'samenvoegen' && mergeDragging) {
      toggleMergeCel(cel, true);
    } else if (isPainting && ['tafel', 'geblokkeerd', 'leeg'].includes(currentMode)) {
      onCellPaint(cel);
    }
  }

  function onCellPaint(cel) {
    if (paintedInDrag.has(cel.id)) return;
    paintedInDrag.add(cel.id);
    paintType(cel, currentMode);
  }

  function toggleMergeCel(cel, addOnly) {
    const el = elFor(cel.id);
    if (mergeSelection.has(cel.id)) {
      if (addOnly) return;
      mergeSelection.delete(cel.id);
      if (el) el.classList.remove('merge-preview');
    } else {
      mergeSelection.add(cel.id);
      if (el) el.classList.add('merge-preview');
    }
  }

  function finishMerge() {
    mergeDragging = false;
    const ids = Array.from(mergeSelection);
    mergeSelection.clear();
    if (ids.length < 2) { renderGrid(); return; }
    postJson(mergeUrl, { cel_ids: ids })
      .then((data) => { gridData = data.grid; renderGrid(); })
      .catch((err) => { alert(err.message); renderGrid(); });
  }

  function showCelDetail(cel) {
    detailEl.classList.remove('hidden');
    document.getElementById('cel-id').value = cel.id;
    document.getElementById('cel-label').textContent = cel.label;
    document.getElementById('cel-label-input').value = cel.tekst || '';
    document.getElementById('cel-prijs-input').value = '';
    document.getElementById('cel-prijs-wrap').style.display = cel.type === 'tafel' ? '' : 'none';
    detailEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  document.addEventListener('mouseup', () => {
    if (currentMode === 'samenvoegen' && mergeDragging) {
      finishMerge();
    }
    isPainting = false;
    paintedInDrag.clear();
  });

  document.querySelectorAll('.zaalplan-mode-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      currentMode = btn.dataset.mode;
      document.querySelectorAll('.zaalplan-mode-btn').forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      if (currentMode !== 'bewerken') detailEl.classList.add('hidden');
      if (hintEl) hintEl.textContent = MODE_HINTS[currentMode] || '';
    });
  });

  document.getElementById('btn-cel-opslaan').addEventListener('click', () => {
    const celId = parseInt(document.getElementById('cel-id').value, 10);
    const label = document.getElementById('cel-label-input').value;
    const prijs = document.getElementById('cel-prijs-input').value;
    postJson(saveUrl, { cel_id: celId, label: label, prijs: prijs || null })
      .then((data) => { gridData = data.grid; renderGrid(); detailEl.classList.add('hidden'); })
      .catch((err) => alert(err.message));
  });

  document.getElementById('btn-cel-annuleren').addEventListener('click', () => {
    detailEl.classList.add('hidden');
  });

  document.getElementById('btn-opslaan').addEventListener('click', () => {
    postJson(settingsUrl, {
      rijen: parseInt(document.getElementById('rijen').value, 10),
      kolommen: parseInt(document.getElementById('kolommen').value, 10),
      standaard_prijs: document.getElementById('standaard_prijs').value,
    })
      .then((data) => {
        gridData = data.grid;
        document.getElementById('rijen').value = gridData.rijen;
        document.getElementById('kolommen').value = gridData.kolommen;
        renderGrid();
      })
      .catch((err) => alert(err.message));
  });

  document.getElementById('btn-genereer').addEventListener('click', () => {
    if (!confirm('Dit genereert het rooster op basis van de ingestelde rijen en kolommen. Samengevoegde cellen buiten het bereik worden losgemaakt.')) return;
    postJson(generateUrl, {
      rijen: parseInt(document.getElementById('rijen').value, 10),
      kolommen: parseInt(document.getElementById('kolommen').value, 10),
      standaard_prijs: document.getElementById('standaard_prijs').value,
    })
      .then((data) => {
        gridData = data.grid;
        document.getElementById('rijen').value = gridData.rijen;
        document.getElementById('kolommen').value = gridData.kolommen;
        renderGrid();
      })
      .catch((err) => alert(err.message));
  });

  renderGrid();
})();
