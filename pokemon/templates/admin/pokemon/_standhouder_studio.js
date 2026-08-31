(function () {
  var bootEl = document.getElementById("sh-studio-boot");
  if (!bootEl) return;
  var boot = JSON.parse(bootEl.textContent);

  var vragen = boot.vragen || [];
  var currentStep = (boot.previewSteps && boot.previewSteps[0]) || "gegevens";
  var typeLabels = {};
  (boot.vraagTypes || []).forEach(function (t) {
    typeLabels[t.value] = t.label;
  });

  var listEl = document.getElementById("sh-vragen-list");
  var stepsEl = document.getElementById("sh-preview-steps");
  var frame = document.getElementById("sh-preview-frame");
  var dialog = document.getElementById("sh-vraag-dialog");
  var form = document.getElementById("sh-vraag-form");
  var typeSelect = document.getElementById("sh-vraag-type");

  function csrfHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRFToken": boot.csrfToken,
    };
  }

  function api(url, body) {
    return fetch(url, {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify(body || {}),
      credentials: "same-origin",
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok || !data.success) {
          throw new Error((data && data.error) || "Request failed");
        }
        return data;
      });
    });
  }

  function previewSrc(step) {
    var url = boot.previewUrl + "?step=" + encodeURIComponent(step || currentStep);
    return url + "&_=" + Date.now();
  }

  function refreshPreview() {
    if (!frame) return;
    frame.src = previewSrc(currentStep);
    Array.prototype.forEach.call(stepsEl.querySelectorAll(".sh-preview-step"), function (btn) {
      btn.classList.toggle("is-active", btn.dataset.step === currentStep);
    });
  }

  function renderSteps() {
    stepsEl.innerHTML = "";
    (boot.previewSteps || []).forEach(function (step) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sh-preview-step" + (step === currentStep ? " is-active" : "");
      btn.dataset.step = step;
      btn.textContent = step.charAt(0).toUpperCase() + step.slice(1);
      btn.addEventListener("click", function () {
        currentStep = step;
        refreshPreview();
      });
      stepsEl.appendChild(btn);
    });
  }

  function fillCopyFields() {
    var c = boot.copy || {};
    var prijzen = document.getElementById("sh-copy-prijzen");
    var inbegrepen = document.getElementById("sh-copy-inbegrepen");
    var maxTafels = document.getElementById("sh-copy-max-tafels");
    if (prijzen) prijzen.value = c.standhouder_prijzen || "";
    if (inbegrepen) inbegrepen.value = c.standhouder_inbegrepen || "";
    if (maxTafels) maxTafels.value = c.standhouder_max_tafels || 1;
    var prijs = document.getElementById("sh-copy-prijs");
    var btw = document.getElementById("sh-copy-btw");
    var excl = document.getElementById("sh-copy-excl-btw");
    if (prijs) prijs.value = c.standhouder_prijs_per_tafel || "";
    if (btw) btw.value = c.standhouder_prijs_btw_percentage || "21";
    if (excl) excl.checked = !!c.standhouder_prijs_excl_btw;
  }

  var sortable = null;

  function initSortable() {
    if (!window.Sortable || !listEl) return;
    if (sortable) {
      sortable.destroy();
      sortable = null;
    }
    sortable = Sortable.create(listEl, {
      animation: 150,
      draggable: ".sh-vraag-card",
      onStart: function (evt) {
        evt.item.classList.add("is-dragging");
      },
      onEnd: function (evt) {
        evt.item.classList.remove("is-dragging");
        var order = Array.prototype.map.call(
          listEl.querySelectorAll(".sh-vraag-card"),
          function (el) {
            return parseInt(el.dataset.id, 10);
          }
        );
        api(boot.api.vragenReorder, { order: order })
          .then(function (data) {
            vragen = data.vragen || vragen;
            renderVragen();
            refreshPreview();
          })
          .catch(function (err) {
            alert(err.message);
            renderVragen();
          });
      },
    });
  }

  function renderVragen() {
    listEl.innerHTML = "";
    if (!vragen.length) {
      var empty = document.createElement("p");
      empty.className = "sh-empty";
      empty.textContent = "Nog geen vragen. Voeg er een toe.";
      listEl.appendChild(empty);
      initSortable();
      return;
    }
    vragen.forEach(function (v) {
      var card = document.createElement("div");
      card.className = "sh-vraag-card";
      card.dataset.id = v.id;

      var top = document.createElement("div");
      top.className = "sh-vraag-card__top";

      var left = document.createElement("div");
      var title = document.createElement("p");
      title.className = "sh-vraag-card__tekst";
      title.textContent = v.tekst;
      left.appendChild(title);

      var meta = document.createElement("div");
      meta.className = "sh-vraag-card__meta";
      meta.innerHTML =
        '<span class="sh-badge">' +
        (typeLabels[v.vraag_type] || v.vraag_type) +
        "</span>" +
        (v.verplicht ? '<span class="sh-badge">Verplicht</span>' : "") +
        (v.prijs_toeslag
          ? '<span class="sh-badge">€' + v.prijs_toeslag + "</span>"
          : "") +
        (v.is_borg ? '<span class="sh-badge sh-badge--warn">Borg</span>' : "") +
        (v.min_tafels || v.max_tafels
          ? '<span class="sh-badge">Tafels ' +
            (v.min_tafels || "…") +
            "–" +
            (v.max_tafels || "…") +
            "</span>"
          : "");
      left.appendChild(meta);

      var actions = document.createElement("div");
      actions.className = "sh-vraag-card__actions";
      var editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "sh-btn sh-btn--ghost";
      editBtn.textContent = "Bewerk";
      editBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        openVraagDialog(v);
      });
      var delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "sh-btn sh-btn--ghost";
      delBtn.textContent = "Verwijder";
      delBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (!confirm("Deze vraag verwijderen?")) return;
        api(boot.api.vraagDelete, { id: v.id })
          .then(function () {
            vragen = vragen.filter(function (x) {
              return x.id !== v.id;
            });
            renderVragen();
            refreshPreview();
          })
          .catch(function (err) {
            alert(err.message);
          });
      });
      actions.appendChild(editBtn);
      actions.appendChild(delBtn);

      top.appendChild(left);
      top.appendChild(actions);
      card.appendChild(top);
      listEl.appendChild(card);
    });
    initSortable();
  }

  function fillTypeSelect() {
    typeSelect.innerHTML = "";
    (boot.vraagTypes || []).forEach(function (t) {
      var opt = document.createElement("option");
      opt.value = t.value;
      opt.textContent = t.label;
      typeSelect.appendChild(opt);
    });
  }

  function openVraagDialog(vraag) {
    document.getElementById("sh-vraag-id").value = vraag && vraag.id ? vraag.id : "";
    document.getElementById("sh-vraag-tekst").value = (vraag && vraag.tekst) || "";
    document.getElementById("sh-vraag-type").value =
      (vraag && vraag.vraag_type) || "boolean";
    document.getElementById("sh-vraag-opties").value = (vraag && vraag.opties) || "";
    document.getElementById("sh-vraag-verplicht").checked = !!(vraag && vraag.verplicht);
    document.getElementById("sh-vraag-toeslag").value =
      (vraag && vraag.prijs_toeslag) || "";
    document.getElementById("sh-vraag-btw").value =
      (vraag && vraag.prijs_toeslag_btw_percentage) || "21";
    document.getElementById("sh-vraag-excl-btw").checked = !!(
      vraag && vraag.prijs_toeslag_excl_btw
    );
    document.getElementById("sh-vraag-borg").checked = !!(vraag && vraag.is_borg);
    document.getElementById("sh-vraag-min").value =
      (vraag && vraag.min_tafels) || "";
    document.getElementById("sh-vraag-max").value =
      (vraag && vraag.max_tafels) || "";
    document.getElementById("sh-vraag-dialog-title").textContent = vraag && vraag.id
      ? "Vraag bewerken"
      : "Vraag toevoegen";
    if (typeof dialog.showModal === "function") dialog.showModal();
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var payload = {
      id: document.getElementById("sh-vraag-id").value || null,
      tekst: document.getElementById("sh-vraag-tekst").value,
      vraag_type: document.getElementById("sh-vraag-type").value,
      opties: document.getElementById("sh-vraag-opties").value,
      verplicht: document.getElementById("sh-vraag-verplicht").checked,
      prijs_toeslag: document.getElementById("sh-vraag-toeslag").value,
      prijs_toeslag_btw_percentage: document.getElementById("sh-vraag-btw").value,
      prijs_toeslag_excl_btw: document.getElementById("sh-vraag-excl-btw").checked,
      is_borg: document.getElementById("sh-vraag-borg").checked,
      min_tafels: document.getElementById("sh-vraag-min").value,
      max_tafels: document.getElementById("sh-vraag-max").value,
    };
    if (payload.id) payload.id = parseInt(payload.id, 10);
    else delete payload.id;

    api(boot.api.vraagSave, payload)
      .then(function (data) {
        var saved = data.vraag;
        var idx = vragen.findIndex(function (v) {
          return v.id === saved.id;
        });
        if (idx >= 0) vragen[idx] = saved;
        else vragen.push(saved);
        renderVragen();
        dialog.close();
        currentStep = "vragen";
        refreshPreview();
      })
      .catch(function (err) {
        alert(err.message);
      });
  });

  function showToast(message, isError) {
    var toast = document.getElementById("sh-toast");
    if (!toast) return;
    toast.hidden = false;
    toast.textContent = message;
    toast.classList.toggle("is-error", !!isError);
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () {
      toast.hidden = true;
    }, 2800);
  }

  function saveCopyPayload() {
    var payload = {
      standhouder_prijzen: document.getElementById("sh-copy-prijzen").value,
      standhouder_inbegrepen: document.getElementById("sh-copy-inbegrepen").value,
      standhouder_max_tafels: document.getElementById("sh-copy-max-tafels").value,
    };
    var prijs = document.getElementById("sh-copy-prijs");
    if (prijs) {
      payload.standhouder_prijs_per_tafel = prijs.value;
      payload.standhouder_prijs_btw_percentage = document.getElementById("sh-copy-btw").value;
      payload.standhouder_prijs_excl_btw = document.getElementById("sh-copy-excl-btw").checked;
    }
    return api(boot.api.copy, payload);
  }

  function syncStepFromFrameUrl() {
    try {
      var href = frame.contentWindow.location.href;
      var match = href.match(/[?&]step=([a-z]+)/i);
      if (match && match[1] && match[1] !== currentStep) {
        currentStep = match[1];
        Array.prototype.forEach.call(stepsEl.querySelectorAll(".sh-preview-step"), function (btn) {
          btn.classList.toggle("is-active", btn.dataset.step === currentStep);
        });
      }
    } catch (e) {
      /* ignore cross-origin */
    }
  }

  document.getElementById("sh-vraag-cancel").addEventListener("click", function () {
    dialog.close();
  });

  document.getElementById("sh-vraag-add").addEventListener("click", function () {
    openVraagDialog(null);
  });

  document.getElementById("sh-save-all").addEventListener("click", function () {
    var btn = document.getElementById("sh-save-all");
    btn.disabled = true;
    saveCopyPayload()
      .then(function () {
        showToast("Opgeslagen. Vragen stonden al bijgewerkt; teksten/instellingen zijn bewaard.");
        refreshPreview();
      })
      .catch(function (err) {
        showToast(err.message || "Opslaan mislukt", true);
      })
      .finally(function () {
        btn.disabled = false;
      });
  });

  document.getElementById("sh-preview-refresh").addEventListener("click", refreshPreview);

  frame.addEventListener("load", syncStepFromFrameUrl);

  fillTypeSelect();
  fillCopyFields();
  renderSteps();
  renderVragen();
  refreshPreview();
})();
