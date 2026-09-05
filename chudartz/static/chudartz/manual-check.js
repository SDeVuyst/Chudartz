(function () {
  function initManualCheck() {
    const card = document.getElementById('manual-check-card');
    const input = document.getElementById('manual-check-input');
    if (!card || !input || card.dataset.manualCheckBound === '1') {
      return;
    }
    card.dataset.manualCheckBound = '1';

    const statusEl = card.querySelector('[data-role="status"]');
    const errorEl = card.querySelector('[data-role="error"]');
    const endpoint = card.dataset.endpoint || '/pokemon/manual-check/';
    const csrfToken = card.dataset.csrf || '';

    let listening = false;
    let busy = false;

    function setStatus(text) {
      if (!statusEl) {
        return;
      }
      if (text) {
        statusEl.textContent = text;
        statusEl.hidden = false;
      } else {
        statusEl.textContent = '';
        statusEl.hidden = true;
      }
    }

    function setError(message, raw) {
      card.classList.add('is-error');
      if (!errorEl) {
        return;
      }
      const parts = [message];
      if (raw) {
        parts.push('Ruwe data: ' + raw);
      }
      errorEl.textContent = parts.join('\n');
      errorEl.hidden = false;
    }

    function clearError() {
      card.classList.remove('is-error');
      if (errorEl) {
        errorEl.textContent = '';
        errorEl.hidden = true;
      }
    }

    function startListening() {
      listening = true;
      busy = false;
      input.value = '';
      clearError();
      card.classList.add('is-listening');
      card.setAttribute('aria-pressed', 'true');
      setStatus('Scan QR…');
      input.focus();
    }

    function stopListening() {
      listening = false;
      busy = false;
      input.value = '';
      card.classList.remove('is-listening');
      card.setAttribute('aria-pressed', 'false');
      setStatus('');
      input.blur();
    }

    function handleScan(raw) {
      if (busy) {
        return;
      }
      busy = true;
      clearError();
      setStatus('Opzoeken…');

      fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ raw: raw }),
      })
        .then(function (response) {
          const contentType = response.headers.get('content-type') || '';
          if (contentType.indexOf('application/json') === -1) {
            return response.text().then(function () {
              throw new Error(
                'Serverantwoord was geen JSON (HTTP ' + response.status + ').'
              );
            });
          }
          return response.json().then(function (data) {
            return { ok: response.ok, status: response.status, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.data.success || !result.data.redirect_url) {
            setError(
              (result.data && result.data.message) || 'Opzoeken mislukt.',
              raw
            );
            setStatus('Fout');
            busy = false;
            input.value = '';
            input.focus();
            return;
          }
          setStatus('Doorsturen…');
          window.location.href = result.data.redirect_url;
        })
        .catch(function (err) {
          setError(err.message || 'Netwerkfout.', raw);
          setStatus('Fout');
          busy = false;
          input.value = '';
          input.focus();
        });
    }

    card.addEventListener('click', function (event) {
      if (event.target === input) {
        return;
      }
      if (listening) {
        stopListening();
      } else {
        startListening();
      }
    });

    input.addEventListener('keydown', function (event) {
      if (!listening || busy) {
        return;
      }

      if (event.key === 'Escape') {
        event.preventDefault();
        stopListening();
        clearError();
        return;
      }

      if (event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        const raw = input.value.trim();
        input.value = '';
        if (raw) {
          handleScan(raw);
        }
      }
    });

    input.addEventListener('blur', function () {
      if (listening && !busy) {
        // Keep focus on the wedge target while listening.
        setTimeout(function () {
          if (listening && !busy) {
            input.focus();
          }
        }, 0);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initManualCheck);
  } else {
    initManualCheck();
  }
})();
