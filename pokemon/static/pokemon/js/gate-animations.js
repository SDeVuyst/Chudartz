(function () {
  const prefersReducedMotion = window.matchMedia(
    '(prefers-reduced-motion: reduce)'
  ).matches;

  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function animateKpiNumber(el, nextValue) {
    if (!el || nextValue == null) return;

    const next = String(nextValue);
    const prev =
      el.dataset.animValue != null ? el.dataset.animValue : el.textContent.trim();

    if (prev === next) return;
    el.dataset.animValue = next;

    if (prefersReducedMotion) {
      el.textContent = next;
      return;
    }

    const inner = document.createElement('span');
    inner.className = 'gate-kpi-roll__inner';
    inner.innerHTML =
      `<span class="gate-kpi-roll__val">${escapeHtml(prev)}</span>` +
      `<span class="gate-kpi-roll__val">${escapeHtml(next)}</span>`;

    el.textContent = '';
    el.classList.add('gate-kpi-roll');
    el.appendChild(inner);

    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        inner.classList.add('is-rolling');
      });
    });

    inner.addEventListener(
      'transitionend',
      function () {
        el.classList.remove('gate-kpi-roll');
        el.textContent = next;
      },
      { once: true }
    );
  }

  function animateFeedRow(row, success) {
    if (!row || prefersReducedMotion) return;

    row.classList.add('gate-feed__row--enter');
    row.classList.add(success ? 'gate-feed__row--success' : 'gate-feed__row--fail');
    row.addEventListener(
      'animationend',
      function () {
        row.classList.remove(
          'gate-feed__row--enter',
          'gate-feed__row--success',
          'gate-feed__row--fail'
        );
      },
      { once: true }
    );
  }

  function animateListItem(item, success) {
    if (!item || prefersReducedMotion) return;

    item.classList.add('gate-recent-scan--enter');
    if (success != null) {
      item.classList.add(success ? 'gate-recent-scan--success' : 'gate-recent-scan--fail');
    }
    item.addEventListener(
      'animationend',
      function () {
        item.classList.remove(
          'gate-recent-scan--enter',
          'gate-recent-scan--success',
          'gate-recent-scan--fail'
        );
      },
      { once: true }
    );
  }

  function updateStatusDot(dotEl, online, isLive) {
    if (!dotEl) return;
    dotEl.classList.toggle('is-online', Boolean(online));
    dotEl.classList.toggle('is-polling', Boolean(isLive));
  }

  function updateAllStatusDots(root, isLive) {
    if (!root) return;
    root.querySelectorAll('.gate-card__dot').forEach(function (dot) {
      dot.classList.toggle('is-polling', Boolean(isLive));
    });
  }

  window.GateAnimations = {
    animateKpiNumber: animateKpiNumber,
    animateFeedRow: animateFeedRow,
    animateListItem: animateListItem,
    updateStatusDot: updateStatusDot,
    updateAllStatusDots: updateAllStatusDots,
  };
})();
