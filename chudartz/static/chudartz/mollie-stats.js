(function () {
  function formatAmount(value) {
    var amount = Number(value);
    if (!Number.isFinite(amount)) {
      amount = 0;
    }
    return '€' + amount.toFixed(2);
  }

  function setField(card, name, value) {
    var el = card.querySelector('[data-field="' + name + '"]');
    if (!el || !el.parentElement) {
      return;
    }
    el.parentElement.textContent = value;
  }

  function showError(card, message) {
    var errorEl = card.querySelector('[data-role="mollie-error"]');
    if (!errorEl) {
      return;
    }
    errorEl.hidden = false;
    errorEl.textContent = message;
  }

  function initMollieStats() {
    var card = document.getElementById('mollie-stats-card');
    if (!card || card.dataset.bound === '1') {
      return;
    }
    card.dataset.bound = '1';

    var endpoint = card.dataset.endpoint;
    if (!endpoint) {
      return;
    }

    var kpis = card.querySelector('[data-role="mollie-kpis"]');

    fetch(endpoint, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Mollie stats konden niet geladen worden');
        }
        return response.json();
      })
      .then(function (data) {
        if (data.error) {
          showError(card, data.error + '.');
        }

        var totals = data.totals || {};
        setField(card, 'paid_amount', formatAmount(totals.paid_amount));
        setField(card, 'paid', String(totals.paid != null ? totals.paid : 0));
        setField(card, 'open', String(totals.open != null ? totals.open : 0));
        setField(card, 'failed', String(totals.failed != null ? totals.failed : 0));

        if (kpis) {
          kpis.setAttribute('aria-busy', 'false');
        }
      })
      .catch(function (err) {
        showError(
          card,
          (err && err.message) || 'Mollie stats konden niet geladen worden.'
        );
        setField(card, 'paid_amount', '€0.00');
        setField(card, 'paid', '0');
        setField(card, 'open', '0');
        setField(card, 'failed', '0');
        if (kpis) {
          kpis.setAttribute('aria-busy', 'false');
        }
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMollieStats);
  } else {
    initMollieStats();
  }
})();
