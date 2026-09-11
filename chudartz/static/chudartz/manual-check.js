(function () {
  var activeController = null;

  function clampToViewport(top, left, right, bottom) {
    var viewTop = 0;
    var viewLeft = 0;
    var viewRight = window.innerWidth;
    var viewBottom = window.innerHeight;
    var clampedTop = Math.max(top, viewTop);
    var clampedLeft = Math.max(left, viewLeft);
    var clampedRight = Math.min(right, viewRight);
    var clampedBottom = Math.min(bottom, viewBottom);
    return {
      top: clampedTop,
      left: clampedLeft,
      width: Math.max(0, clampedRight - clampedLeft),
      height: Math.max(0, clampedBottom - clampedTop),
    };
  }

  function getContentAreaRect() {
    var main = document.getElementById('main');
    if (main) {
      var mainRect = main.getBoundingClientRect();
      var top = mainRect.top;
      var header =
        main.querySelector('header') ||
        main.querySelector('[data-header]') ||
        main.firstElementChild;
      if (header && header !== main) {
        var headerRect = header.getBoundingClientRect();
        if (headerRect.bottom > mainRect.top && headerRect.top < mainRect.top + 120) {
          top = Math.max(top, headerRect.bottom);
        }
      }
      // Intersect with the viewport so the modal centers in the visible area,
      // not the middle of a tall scrolled #main.
      return clampToViewport(top, mainRect.left, mainRect.right, mainRect.bottom);
    }

    var content = document.getElementById('content');
    if (content) {
      var contentRect = content.getBoundingClientRect();
      return clampToViewport(
        contentRect.top,
        contentRect.left,
        contentRect.right,
        contentRect.bottom
      );
    }

    return {
      top: 0,
      left: 0,
      width: window.innerWidth,
      height: window.innerHeight,
    };
  }

  function initScanCard(card) {
    var input = card.querySelector('input[type="text"]');
    if (!card || !input || card.dataset.manualCheckBound === '1') {
      return;
    }
    card.dataset.manualCheckBound = '1';

    var mode = card.dataset.mode || 'lookup';
    var endpoint = card.dataset.endpoint || '/pokemon/manual-check/';
    var csrfToken = card.dataset.csrf || '';
    var titleLabel =
      (card.querySelector('.dash-card__title, .gate-manual-check__title') || {}).textContent ||
      (mode === 'checkin' ? 'Scan ticket' : 'Bekijk deelnemer');
    titleLabel = String(titleLabel).trim() || (mode === 'checkin' ? 'Scan ticket' : 'Bekijk deelnemer');

    var listening = false;
    var busy = false;
    var modalOpen = false;
    var successResetTimer = null;

    var titleId = (card.id || 'scan-card') + '-modal-title';

    var modalRoot = document.createElement('div');
    modalRoot.className = 'manual-check-modal';
    modalRoot.hidden = true;
    modalRoot.setAttribute('aria-hidden', 'true');
    modalRoot.innerHTML =
      '<div class="manual-check-modal__backdrop" data-role="backdrop"></div>' +
      '<div class="manual-check-modal__panel" role="dialog" aria-modal="true" aria-labelledby="' +
      titleId +
      '">' +
      '<h2 class="manual-check-modal__title" id="' +
      titleId +
      '" data-role="title"></h2>' +
      '<p class="manual-check-modal__message" data-role="message"></p>' +
      '<pre class="manual-check-modal__raw" data-role="raw" hidden></pre>' +
      '<a class="manual-check-modal__link" data-role="link" hidden target="_blank" rel="noopener noreferrer"></a>' +
      '<p class="manual-check-modal__hint" data-role="hint"></p>' +
      '</div>';
    document.body.appendChild(modalRoot);

    var backdropEl = modalRoot.querySelector('[data-role="backdrop"]');
    var titleEl = modalRoot.querySelector('[data-role="title"]');
    var messageEl = modalRoot.querySelector('[data-role="message"]');
    var rawEl = modalRoot.querySelector('[data-role="raw"]');
    var linkEl = modalRoot.querySelector('[data-role="link"]');
    var hintEl = modalRoot.querySelector('[data-role="hint"]');

    function clearSuccessTimer() {
      if (successResetTimer !== null) {
        window.clearTimeout(successResetTimer);
        successResetTimer = null;
      }
    }

    function positionModal() {
      if (!modalOpen) {
        return;
      }
      var rect = getContentAreaRect();
      modalRoot.style.top = rect.top + 'px';
      modalRoot.style.left = rect.left + 'px';
      modalRoot.style.width = rect.width + 'px';
      modalRoot.style.height = rect.height + 'px';
    }

    function onViewportChange() {
      positionModal();
    }

    function showModal() {
      if (!modalOpen) {
        modalOpen = true;
        modalRoot.hidden = false;
        modalRoot.setAttribute('aria-hidden', 'false');
        window.addEventListener('resize', onViewportChange);
        window.addEventListener('scroll', onViewportChange, true);
      }
      positionModal();
    }

    function hideModal() {
      if (!modalOpen) {
        return;
      }
      modalOpen = false;
      modalRoot.hidden = true;
      modalRoot.setAttribute('aria-hidden', 'true');
      modalRoot.classList.remove('is-error', 'is-success');
      window.removeEventListener('resize', onViewportChange);
      window.removeEventListener('scroll', onViewportChange, true);
      if (titleEl) {
        titleEl.textContent = '';
      }
      if (messageEl) {
        messageEl.textContent = '';
        messageEl.removeAttribute('role');
      }
      if (rawEl) {
        rawEl.textContent = '';
        rawEl.hidden = true;
      }
      if (linkEl) {
        linkEl.textContent = '';
        linkEl.removeAttribute('href');
        linkEl.hidden = true;
      }
      if (hintEl) {
        hintEl.textContent = '';
      }
    }

    function setParticipantLink(adminUrl) {
      if (!linkEl) {
        return;
      }
      if (adminUrl) {
        linkEl.href = adminUrl;
        linkEl.textContent = 'Open deelnemer';
        linkEl.hidden = false;
      } else {
        linkEl.textContent = '';
        linkEl.removeAttribute('href');
        linkEl.hidden = true;
      }
    }

    function setStatus(title, message, hint) {
      card.classList.remove('is-error', 'is-success');
      modalRoot.classList.remove('is-error', 'is-success');
      showModal();
      if (titleEl) {
        titleEl.textContent = title || '';
      }
      if (messageEl) {
        messageEl.textContent = message || '';
        messageEl.setAttribute('role', 'status');
      }
      if (rawEl) {
        rawEl.textContent = '';
        rawEl.hidden = true;
      }
      setParticipantLink(null);
      if (hintEl) {
        hintEl.textContent = hint || '';
      }
    }

    function setSuccess(message, adminUrl) {
      clearSuccessTimer();
      card.classList.remove('is-error');
      card.classList.add('is-success');
      modalRoot.classList.remove('is-error');
      modalRoot.classList.add('is-success');
      showModal();
      if (titleEl) {
        titleEl.textContent = 'Toegelaten';
      }
      if (messageEl) {
        messageEl.textContent = message || 'Ticket geregistreerd.';
        messageEl.setAttribute('role', 'status');
      }
      if (rawEl) {
        rawEl.textContent = '';
        rawEl.hidden = true;
      }
      setParticipantLink(adminUrl);
      if (hintEl) {
        hintEl.textContent = adminUrl
          ? 'Klik om deelnemer te openen, of scan de volgende. Esc om te stoppen.'
          : 'Klaar voor volgende scan. Esc om te stoppen.';
      }
    }

    function setError(message, raw, adminUrl) {
      clearSuccessTimer();
      card.classList.remove('is-success');
      card.classList.add('is-error');
      modalRoot.classList.remove('is-success');
      modalRoot.classList.add('is-error');
      showModal();
      if (titleEl) {
        titleEl.textContent = 'Fout';
      }
      if (messageEl) {
        messageEl.textContent = message || 'Opzoeken mislukt.';
        messageEl.setAttribute('role', 'alert');
      }
      if (rawEl) {
        if (raw) {
          rawEl.textContent = 'Ruwe data: ' + raw;
          rawEl.hidden = false;
        } else {
          rawEl.textContent = '';
          rawEl.hidden = true;
        }
      }
      setParticipantLink(adminUrl || null);
      if (hintEl) {
        hintEl.textContent = adminUrl
          ? 'Klik om deelnemer te openen, of scan opnieuw. Esc om te sluiten.'
          : 'Scan opnieuw of druk Esc om te sluiten.';
      }
    }

    function clearError() {
      card.classList.remove('is-error', 'is-success');
      modalRoot.classList.remove('is-error', 'is-success');
    }

    function startListening() {
      if (activeController && activeController !== controller) {
        activeController.stopListening();
      }
      activeController = controller;
      clearSuccessTimer();
      listening = true;
      busy = false;
      input.value = '';
      clearError();
      card.classList.add('is-listening');
      card.setAttribute('aria-pressed', 'true');
      setStatus(titleLabel, 'Aan het wachten op scanner…', 'Esc om te annuleren.');
      input.focus();
    }

    function stopListening() {
      clearSuccessTimer();
      listening = false;
      busy = false;
      input.value = '';
      card.classList.remove('is-listening', 'is-error', 'is-success');
      card.setAttribute('aria-pressed', 'false');
      clearError();
      hideModal();
      input.blur();
      if (activeController === controller) {
        activeController = null;
      }
    }

    function handleScan(raw) {
      if (busy) {
        return;
      }
      busy = true;
      clearSuccessTimer();
      clearError();
      setStatus(titleLabel, mode === 'checkin' ? 'Controleren…' : 'Opzoeken…', '');

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
          var contentType = response.headers.get('content-type') || '';
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
          if (mode === 'checkin') {
            if (!result.ok || !result.data.success) {
              setError(
                (result.data && result.data.message) || 'Check-in mislukt.',
                raw,
                result.data && result.data.admin_url
              );
              busy = false;
              input.value = '';
              input.focus();
              return;
            }
            setSuccess(
              result.data.message || result.data.ticket || 'Ticket geregistreerd.',
              result.data.admin_url
            );
            busy = false;
            input.value = '';
            input.focus();
            return;
          }

          if (!result.ok || !result.data.success || !result.data.redirect_url) {
            setError(
              (result.data && result.data.message) || 'Opzoeken mislukt.',
              raw
            );
            busy = false;
            input.value = '';
            input.focus();
            return;
          }
          setStatus(titleLabel, 'Doorsturen…', '');
          window.location.href = result.data.redirect_url;
        })
        .catch(function (err) {
          setError(err.message || 'Netwerkfout.', raw);
          busy = false;
          input.value = '';
          input.focus();
        });
    }

    var controller = {
      stopListening: stopListening,
    };

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

    backdropEl.addEventListener('click', function () {
      if (listening) {
        stopListening();
      } else {
        hideModal();
        clearError();
      }
    });

    input.addEventListener('keydown', function (event) {
      if (!listening || busy) {
        if (event.key === 'Escape' && modalOpen) {
          event.preventDefault();
          stopListening();
        }
        return;
      }

      if (event.key === 'Escape') {
        event.preventDefault();
        stopListening();
        return;
      }

      if (event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        var raw = input.value.trim();
        input.value = '';
        if (raw) {
          handleScan(raw);
        }
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape' || !modalOpen) {
        return;
      }
      if (listening || card.classList.contains('is-error') || card.classList.contains('is-success')) {
        event.preventDefault();
        stopListening();
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

  function initManualCheck() {
    var cards = document.querySelectorAll(
      '#manual-check-card, #scan-ticket-card, [data-mode][data-endpoint]'
    );
    for (var i = 0; i < cards.length; i++) {
      initScanCard(cards[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initManualCheck);
  } else {
    initManualCheck();
  }
})();
