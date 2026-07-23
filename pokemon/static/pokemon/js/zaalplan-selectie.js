(function () {
  const gridEl = document.getElementById('zaalplan-selectie-grid');
  if (!gridEl) return;

  const selected = new Set(
    (gridEl.dataset.selected || '').split(',').filter(Boolean).map(Number)
  );
  const form = document.getElementById('tafel-form');
  const summaryEl = document.getElementById('tafel-selectie-summary');
  const hiddenContainer = document.getElementById('tafel-hidden-inputs');
  const viewport = document.getElementById('zaalplan-selectie-viewport');
  const nextBtn = document.getElementById('tafel-next-btn');
  const gridData = window.ZAALPLAN_SELECTIE_DATA;
  const maxTafels = parseInt(
    gridEl.dataset.maxTafels || gridData.max_tafels || '0',
    10
  ) || Infinity;
  let limietBereikt = false;

  function tafelLabel(cel) {
    if (cel.label) return cel.label;
    return String.fromCharCode(65 + cel.rij) + (cel.kolom + 1);
  }

  function defaultSize() {
    if (gridData.kolommen > 24) return 34;
    if (gridData.kolommen > 16) return 40;
    return 46;
  }

  let cellSize = defaultSize();
  const MIN_SIZE = 22;
  const MAX_SIZE = 90;

  function renderGrid() {
    gridEl.style.gridTemplateColumns = `repeat(${gridData.kolommen}, ${cellSize}px)`;
    gridEl.style.gridAutoRows = `${cellSize}px`;
    gridEl.innerHTML = '';

    gridData.cellen.forEach((cel) => {
      const onbeschikbaar = cel.bezet || cel.gereserveerd;
      const div = document.createElement('div');
      let cls = `zaalplan-selectie-cel ${cel.type}`;
      if (onbeschikbaar) cls += ' bezet';
      if (selected.has(cel.primary_id)) cls += ' geselecteerd';
      if (cel.type !== 'tafel' && cel.tekst) cls += ' tekst';
      if (cel.groep) {
        if (cel.buren.boven) cls += ' nb-top';
        if (cel.buren.onder) cls += ' nb-bottom';
        if (cel.buren.links) cls += ' nb-left';
        if (cel.buren.rechts) cls += ' nb-right';
      }
      div.className = cls;
      div.style.gridColumn = `${cel.kolom + 1}`;
      div.style.gridRow = `${cel.rij + 1}`;

      if (!cel.groep) {
        if (cel.type === 'tafel') div.textContent = tafelLabel(cel);
        else if (cel.tekst) div.textContent = cel.tekst;
      }

      if (cel.type === 'tafel') {
        div.dataset.primaryId = cel.primary_id;
      }

      if (cel.type === 'tafel' && !onbeschikbaar) {
        div.setAttribute('role', 'button');
        div.setAttribute('tabindex', '0');
        div.setAttribute('aria-label', 'Tafel ' + tafelLabel(cel));
        div.setAttribute('aria-pressed', selected.has(cel.primary_id) ? 'true' : 'false');
        const activate = () => toggleGroep(cel.primary_id);
        div.addEventListener('click', activate);
        div.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            activate();
          }
        });
      }
      gridEl.appendChild(div);
    });

    renderGroupLabels();
    updateSummary();
    updateHiddenInputs();
  }

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

  function renderGroupLabels() {
    const groepen = {};
    gridData.cellen.forEach((cel) => {
      if (!cel.groep) return;
      (groepen[cel.groep] = groepen[cel.groep] || []).push(cel);
    });

    Object.values(groepen).forEach((leden) => {
      const primary = leden.find((c) => c.is_primary) || leden[0];
      const area = bestLabelArea(leden);

      const isTafel = primary.type === 'tafel';
      const isSelected = selected.has(primary.primary_id);
      const label = document.createElement('div');
      let cls = 'zaalplan-groep-label';
      if (isSelected) cls += ' op-geselecteerd';
      if (!isTafel) cls += ' op-tekst';
      label.className = cls;
      label.style.gridColumn = `${area.c1 + 1} / ${area.c2 + 2}`;
      label.style.gridRow = `${area.r1 + 1} / ${area.r2 + 2}`;
      label.textContent = isTafel ? tafelLabel(primary) : (primary.tekst || '');
      gridEl.appendChild(label);
    });
  }

  function toggleGroep(primaryId) {
    if (selected.has(primaryId)) {
      selected.delete(primaryId);
      limietBereikt = false;
    } else if (selected.size >= maxTafels) {
      limietBereikt = true;
      return;
    } else {
      selected.add(primaryId);
      limietBereikt = false;
    }
    renderGrid();
  }

  function updateHiddenInputs() {
    hiddenContainer.innerHTML = '';
    selected.forEach((id) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'tafels';
      input.value = id;
      hiddenContainer.appendChild(input);
    });
  }

  function updateSummary() {
    if (!summaryEl) return;
    const gezien = new Set();
    const labels = [];
    let subtotaal = 0;
    let btwTotaal = 0;
    const exclBtw = !!gridData.prijs_excl_btw;
    const btwPct = parseFloat(gridData.btw_percentage || '0') || 0;
    gridData.cellen.forEach((cel) => {
      if (selected.has(cel.primary_id) && !gezien.has(cel.primary_id)) {
        gezien.add(cel.primary_id);
        labels.push(tafelLabel(cel));
        const prijs = parseFloat(cel.prijs) || 0;
        subtotaal += prijs;
        if (exclBtw) {
          btwTotaal += Math.round(prijs * btwPct) / 100;
        }
      }
    });
    const totaal = subtotaal + btwTotaal;
    if (labels.length === 0) {
      summaryEl.textContent = 'Geen tafels geselecteerd';
    } else {
      let html =
        `<strong>Geselecteerd (${labels.length}):</strong> ${labels.join(', ')}<br>` +
        `<strong>Subtotaal${exclBtw ? ' (excl. btw)' : ''}:</strong> €${subtotaal.toFixed(2)}`;
      if (exclBtw && btwTotaal > 0) {
        html += `<br><strong>BTW ${btwPct}%:</strong> €${btwTotaal.toFixed(2)}`;
      }
      html += `<br><strong>Totaal:</strong> €${totaal.toFixed(2)}`;
      if (limietBereikt) {
        html += `<br><span class="tafel-limiet-bereikt">Maximum van ${maxTafels} tafel(s) bereikt.</span>`;
      }
      summaryEl.innerHTML = html;
    }

    if (nextBtn) nextBtn.disabled = selected.size === 0;
  }

  function setZoom(newSize) {
    cellSize = Math.max(MIN_SIZE, Math.min(MAX_SIZE, newSize));
    renderGrid();
  }

  const zoomIn = document.getElementById('zp-zoom-in');
  const zoomOut = document.getElementById('zp-zoom-out');
  if (zoomIn) zoomIn.addEventListener('click', () => setZoom(cellSize + 6));
  if (zoomOut) zoomOut.addEventListener('click', () => setZoom(cellSize - 6));

  const fsBtn = document.getElementById('zp-fullscreen-btn');
  if (fsBtn && viewport) {
    fsBtn.addEventListener('click', () => {
      const req = viewport.requestFullscreen || viewport.webkitRequestFullscreen;
      if (req) {
        if (!document.fullscreenElement) req.call(viewport);
        else (document.exitFullscreen || document.webkitExitFullscreen).call(document);
      } else {
        viewport.classList.toggle('is-fullscreen');
        renderGrid();
      }
    });

    document.addEventListener('fullscreenchange', () => {
      viewport.classList.toggle('is-fullscreen', document.fullscreenElement === viewport);
      renderGrid();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && viewport.classList.contains('is-fullscreen') && !document.fullscreenElement) {
        viewport.classList.remove('is-fullscreen');
        renderGrid();
      }
    });
  }

  if (form) {
    form.addEventListener('submit', (e) => {
      if (selected.size === 0) {
        e.preventDefault();
        alert('Selecteer minstens één tafel.');
      } else if (selected.size > maxTafels) {
        e.preventDefault();
        alert(`U kunt maximaal ${maxTafels} tafel(s) selecteren.`);
      }
    });
  }

  function clearGroupHover() {
    gridEl.querySelectorAll('.zaalplan-selectie-cel.is-hovered').forEach((el) => {
      el.classList.remove('is-hovered');
    });
  }

  function setGroupHover(primaryId) {
    clearGroupHover();
    gridEl.querySelectorAll(`[data-primary-id="${primaryId}"]`).forEach((el) => {
      el.classList.add('is-hovered');
    });
  }

  gridEl.addEventListener('mouseover', (e) => {
    const cel = e.target.closest('.zaalplan-selectie-cel.tafel:not(.bezet)');
    if (cel && gridEl.contains(cel)) {
      setGroupHover(cel.dataset.primaryId);
    } else {
      clearGroupHover();
    }
  });

  gridEl.addEventListener('mouseleave', clearGroupHover);

  renderGrid();
})();
