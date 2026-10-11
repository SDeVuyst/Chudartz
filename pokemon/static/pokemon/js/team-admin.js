(function () {
  const STEPS = [
    { key: "lid", next: "Kaart", inlines: [] },
    { key: "kaart", next: "Stats", inlines: ["#aanvallen-group"] },
    { key: "stats", next: "Slab", inlines: [] },
    { key: "slab", next: "Detail", inlines: [] },
    { key: "detail", next: null, inlines: ["#weetjes-group", "#socials-group"] },
  ];

  const INLINE_IDS = ["#aanvallen-group", "#weetjes-group", "#socials-group"];

  function boot() {
    const root = document.getElementById("te-editor");
    if (!root) return;

    const form = root.querySelector("#teamlid_form") || root.querySelector("form");
    const iframe = root.querySelector(".te-preview-frame");
    const previewUrl = root.dataset.previewUrl;
    const objectId = root.dataset.objectId || "";
    let timer = null;
    let controller = null;
    let currentStep = 0;

    function csrfToken() {
      const field = form && form.querySelector("[name=csrfmiddlewaretoken]");
      return field ? field.value : "";
    }

    function selectedTypes(value) {
      return String(value || "")
        .split(",")
        .map(function (item) { return item.trim(); })
        .filter(Boolean);
    }

    const ENERGY_ICONS = {
      dart: "bi-bullseye",
      electric: "bi-lightning-charge-fill",
      fire: "bi-fire",
      water: "bi-droplet-fill",
      grass: "bi-tree-fill",
      psychic: "bi-eye-fill",
      fighting: "bi-hammer",
      darkness: "bi-moon-fill",
      metal: "bi-gem",
      colorless: "bi-star-fill",
    };

    function refreshEnergy(widget) {
      const input = widget.querySelector(".te-energy-value");
      const selected = widget.querySelector(".te-energy-selected");
      if (!input || !selected) return;

      selected.innerHTML = selectedTypes(input.value).map(function (type) {
        const swatch = widget.querySelector('[data-energy="' + type + '"]');
        const label = swatch ? swatch.getAttribute("title") : type;
        const icon = ENERGY_ICONS[type] || "bi-star-fill";
        return (
          '<button type="button" class="te-energy-chip te-energy--' + type +
          '" data-energy-remove="' + type + '" title="' + label +
          '"><i class="bi ' + icon + '"></i></button>'
        );
      }).join("");
    }

    function refreshAllEnergy() {
      root.querySelectorAll("[data-energy-widget]").forEach(refreshEnergy);
    }

    function schedulePreview() {
      window.clearTimeout(timer);
      timer = window.setTimeout(renderPreview, 280);
    }

    async function renderPreview() {
      if (!form || !iframe || !previewUrl) return;
      const data = new FormData(form);
      if (objectId) data.set("object_id", objectId);
      if (controller) controller.abort();
      controller = new AbortController();

      try {
        const response = await fetch(previewUrl, {
          method: "POST",
          body: data,
          headers: {
            "X-CSRFToken": csrfToken(),
            "X-Requested-With": "XMLHttpRequest",
          },
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!response.ok) {
          iframe.srcdoc = "<p style='padding:1rem;font:14px sans-serif'>Voorbeeld kon niet worden geladen.</p>";
          return;
        }
        iframe.srcdoc = await response.text();
      } catch (error) {
        if (error.name !== "AbortError") {
          iframe.srcdoc = "<p style='padding:1rem;font:14px sans-serif'>Voorbeeld kon niet worden geladen.</p>";
        }
      }
    }

    function tabLinks() {
      return Array.from(root.querySelectorAll('[x-on\\:click*="openTab"]'));
    }

    function showStep(index) {
      currentStep = Math.max(0, Math.min(STEPS.length - 1, index));
      const step = STEPS[currentStep];
      const allowed = new Set(step.inlines);

      INLINE_IDS.forEach(function (sel) {
        const node = root.querySelector(sel);
        if (!node) return;
        node.classList.toggle("te-step-show", allowed.has(sel));
      });

      if (prevBtn) prevBtn.hidden = currentStep === 0;
      if (nextBtn) {
        if (step.next) {
          nextBtn.hidden = false;
          nextBtn.textContent = "Volgende: " + step.next;
        } else {
          nextBtn.hidden = true;
        }
      }
    }

    function goToStep(index) {
      const links = tabLinks();
      if (links[index]) links[index].click();
      showStep(index);
    }

    root.addEventListener("click", function (event) {
      const add = event.target.closest("[data-energy]");
      if (add && add.closest("[data-energy-widget]")) {
        event.preventDefault();
        const widget = add.closest("[data-energy-widget]");
        const input = widget.querySelector(".te-energy-value");
        const next = selectedTypes(input.value);
        next.push(add.dataset.energy);
        input.value = next.join(",");
        refreshEnergy(widget);
        schedulePreview();
        return;
      }

      const remove = event.target.closest("[data-energy-remove]");
      if (remove) {
        event.preventDefault();
        const widget = remove.closest("[data-energy-widget]");
        const input = widget.querySelector(".te-energy-value");
        const next = selectedTypes(input.value);
        const pos = next.indexOf(remove.dataset.energyRemove);
        if (pos >= 0) next.splice(pos, 1);
        input.value = next.join(",");
        refreshEnergy(widget);
        schedulePreview();
        return;
      }

      const tab = event.target.closest('[x-on\\:click*="openTab"]');
      if (tab) {
        const expr = tab.getAttribute("x-on:click") || "";
        const match = expr.match(/openTab = '(\d+)-/);
        if (match) showStep(Number(match[1]));
      }
    });

    if (form) {
      form.addEventListener("input", schedulePreview);
      form.addEventListener("change", schedulePreview);
    }

    root.addEventListener("click", function (event) {
      if (event.target.closest(".add-row a, .add-row button, .inline-deletelink")) {
        window.setTimeout(function () {
          refreshAllEnergy();
          schedulePreview();
        }, 30);
      }
    });

    const bar = document.createElement("div");
    bar.className = "te-step-bar";
    bar.innerHTML =
      '<div class="te-step-actions">' +
      '<button type="button" class="te-step-prev">Vorige</button>' +
      '<button type="button" class="te-step-next">Volgende: Kaart</button>' +
      "</div>";

    const submit = form && (form.querySelector(".submit-row") || form.querySelector("[class*='submit']"));
    if (form && submit) form.insertBefore(bar, submit);
    else if (form) form.appendChild(bar);

    const prevBtn = bar.querySelector(".te-step-prev");
    const nextBtn = bar.querySelector(".te-step-next");

    prevBtn.addEventListener("click", function () { goToStep(currentStep - 1); });
    nextBtn.addEventListener("click", function () { goToStep(currentStep + 1); });

    showStep(0);
    refreshAllEnergy();
    renderPreview();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
