(function () {
  var canvas = document.getElementById("event-map");
  var wrap = document.querySelector(".event-map__frame");
  var button = document.querySelector(".event-map__fullscreen");
  if (!canvas || typeof L === "undefined") return;

  var pins = [];
  var pinsEl = document.getElementById("event-map-pins");
  if (pinsEl) {
    try {
      pins = JSON.parse(pinsEl.textContent) || [];
    } catch (error) {
      pins = [];
    }
  }

  var icon = L.divIcon({
    className: "event-map__pin",
    html: '<svg class="event-map__pin-icon" viewBox="0 0 32 42" aria-hidden="true"><path fill="currentColor" d="M16 41S2 26.2 2 16a14 14 0 1 1 28 0C30 26.2 16 41 16 41z"/><circle cx="16" cy="16" r="5.5" fill="#fff"/></svg>',
    iconSize: [32, 42],
    iconAnchor: [16, 42],
    popupAnchor: [0, -38],
  });

  var map = L.map(canvas, { scrollWheelZoom: false });
  // The site Referrer-Policy is same-origin, which strips Referer on these
  // cross-origin requests. OSM requires that header and blocks tiles without it.
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    referrerPolicy: "strict-origin-when-cross-origin",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  var moreLabel = canvas.getAttribute("data-more") || "Meer info";
  var groups = {};

  pins.forEach(function (pin) {
    var lat = Number(pin.lat);
    var lng = Number(pin.lng);
    if (!isFinite(lat) || !isFinite(lng)) return;
    pin.lat = lat;
    pin.lng = lng;
    var key = lat.toFixed(5) + "," + lng.toFixed(5);
    if (!groups[key]) groups[key] = [];
    groups[key].push(pin);
  });

  var markers = Object.keys(groups).map(function (key) {
    var group = groups[key];
    var marker = L.marker([group[0].lat, group[0].lng], { icon: icon }).addTo(map);
    var popup = document.createElement("div");

    group.forEach(function (pin) {
      var block = document.createElement("div");
      block.className = "event-map__popup";

      var title = document.createElement("p");
      title.className = "event-map__popup-title";
      title.textContent = pin.titel || "";
      block.appendChild(title);

      if (pin.datum) {
        var when = document.createElement("p");
        when.className = "event-map__popup-when";
        var dateIcon = document.createElement("span");
        dateIcon.className = "event-map__popup-icon";
        dateIcon.setAttribute("aria-hidden", "true");
        var calendar = document.createElement("i");
        calendar.className = "bi bi-calendar-event";
        dateIcon.appendChild(calendar);
        var dateText = document.createElement("span");
        dateText.textContent = pin.datum;
        when.appendChild(dateIcon);
        when.appendChild(dateText);
        block.appendChild(when);
      }

      if (pin.locatie) {
        var where = document.createElement("p");
        where.className = "event-map__popup-where";
        var placeIcon = document.createElement("span");
        placeIcon.className = "event-map__popup-icon";
        placeIcon.setAttribute("aria-hidden", "true");
        var geo = document.createElement("i");
        geo.className = "bi bi-geo-alt-fill";
        placeIcon.appendChild(geo);
        var place = document.createElement("span");
        place.textContent = pin.locatie;
        where.appendChild(placeIcon);
        where.appendChild(place);
        block.appendChild(where);
      }

      if (pin.url) {
        var link = document.createElement("a");
        link.className = "event-map__popup-link";
        link.href = pin.url;
        link.textContent = moreLabel;
        block.appendChild(link);
      }

      popup.appendChild(block);
    });

    marker.bindPopup(popup, {
      className: "event-map__leaflet-popup",
      maxWidth: 280,
      minWidth: 220,
    });
    return marker;
  });

  var flanders = L.latLngBounds([50.68, 2.54], [51.51, 5.92]);
  if (markers.length === 1) {
    map.setView(markers[0].getLatLng(), 12);
  } else if (markers.length > 1) {
    map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [36, 36], maxZoom: 12 });
  } else {
    map.fitBounds(flanders);
  }

  if (!wrap || !button) return;

  function isFullscreen() {
    return document.fullscreenElement === wrap || document.webkitFullscreenElement === wrap;
  }

  function syncIcon() {
    var iconEl = button.querySelector("i");
    if (!iconEl) return;
    if (isFullscreen()) {
      iconEl.className = "bi bi-fullscreen-exit";
      button.setAttribute("aria-label", button.getAttribute("data-label-exit") || "Exit fullscreen");
    } else {
      iconEl.className = "bi bi-fullscreen";
      button.setAttribute("aria-label", button.getAttribute("data-label-enter") || "Fullscreen");
    }
  }

  function refreshMap() {
    var active = isFullscreen();
    wrap.classList.toggle("is-fullscreen", active);
    if (active) {
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
    } else {
      canvas.style.width = "";
      canvas.style.height = "";
    }
    map.invalidateSize();
  }

  button.addEventListener("click", function () {
    if (isFullscreen()) {
      (document.exitFullscreen || document.webkitExitFullscreen).call(document);
      return;
    }
    var req = wrap.requestFullscreen || wrap.webkitRequestFullscreen;
    if (req) req.call(wrap);
  });

  function onFullscreenChange() {
    syncIcon();
    window.requestAnimationFrame(refreshMap);
  }

  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("webkitfullscreenchange", onFullscreenChange);
  window.addEventListener("resize", function () {
    if (isFullscreen()) refreshMap();
  });
})();
