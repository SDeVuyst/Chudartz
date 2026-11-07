(function () {
  var data = document.getElementById("mark-texture-data");
  if (!data) return;

  var marks;
  try {
    marks = JSON.parse(data.textContent);
  } catch (err) {
    return;
  }
  if (!marks || !marks.length) return;

  function isUpright(src) {
    var name = decodeURIComponent(src.split("/").pop() || "").toLowerCase();
    return /puzzle|goku|demon|kanji|metsu|millennium|悟|滅/.test(name);
  }

  function place(el) {
    if (el.querySelector(":scope > .mark-field")) return;
    var height = el.offsetHeight;
    var width = el.offsetWidth || 1;
    if (height < 80) return;

    var rand = Math.random;
    var pool = marks.slice();
    for (var i = pool.length - 1; i > 0; i--) {
      var j = Math.floor(rand() * (i + 1));
      var swap = pool[i];
      pool[i] = pool[j];
      pool[j] = swap;
    }

    var gap = 4;
    var target = Math.round((width * height) / (210 * 150));
    if (target < 8) target = 8;
    if (target > 34) target = 34;

    function bounds(cx, cy, size, rot) {
      var rad = (rot * Math.PI) / 180;
      var factor = Math.abs(Math.cos(rad)) + Math.abs(Math.sin(rad));
      var box = size * factor;
      return { l: cx - box / 2, t: cy - box / 2, r: cx + box / 2, b: cy + box / 2 };
    }

    function collides(candidate) {
      for (var p = 0; p < placed.length; p++) {
        var other = placed[p];
        if (
          candidate.l < other.r + gap &&
          candidate.r + gap > other.l &&
          candidate.t < other.b + gap &&
          candidate.b + gap > other.t
        ) {
          return true;
        }
      }
      return false;
    }

    var maxEach = Math.max(1, Math.ceil(target / pool.length));

    function usedCount(src) {
      var count = 0;
      for (var p = 0; p < placed.length; p++) {
        if (placed[p].src === src) count++;
      }
      return count;
    }

    function sameIsClose(src, cx, cy, reach) {
      for (var p = 0; p < placed.length; p++) {
        if (placed[p].src !== src) continue;
        var dx = placed[p].cx - cx;
        var dy = placed[p].cy - cy;
        if (dx * dx + dy * dy < reach * reach) return true;
      }
      return false;
    }

    var placed = [];
    var tries = 0;
    while (placed.length < target && tries < 500) {
      tries++;
      var size = 180 + rand() * 120;
      if (size > height * 0.78) size = height * 0.78;
      var span = size * 1.28;
      var cx = -span * 0.28 + rand() * (width + span * 0.56);
      var cy = -span * 0.22 + rand() * (height + span * 0.44);
      var reach = tries > 340 ? Math.max(size * 2.2, 260) : Math.max(size * 3, Math.min(width * 0.42, 720));
      var start = Math.floor(rand() * pool.length);
      for (var s = 0; s < pool.length; s++) {
        var src = pool[(start + s) % pool.length];
        if (usedCount(src) >= maxEach) continue;
        if (sameIsClose(src, cx, cy, reach)) continue;
        var rot = (rand() * 2 - 1) * (isUpright(src) ? 6 : 20);
        var candidate = bounds(cx, cy, size, rot);
        if (collides(candidate)) continue;
        candidate.src = src;
        candidate.size = size;
        candidate.rot = rot;
        candidate.cx = cx;
        candidate.cy = cy;
        placed.push(candidate);
        break;
      }
    }

    var field = document.createElement("div");
    field.className = "mark-field";
    field.setAttribute("aria-hidden", "true");

    for (var n = 0; n < placed.length; n++) {
      var mark = placed[n];
      var img = document.createElement("img");
      img.src = mark.src;
      img.alt = "";
      img.style.width = mark.size.toFixed(0) + "px";
      img.style.height = mark.size.toFixed(0) + "px";
      img.style.objectFit = "contain";
      img.style.left = (((mark.cx - mark.size / 2) / width) * 100).toFixed(1) + "%";
      img.style.top = (((mark.cy - mark.size / 2) / height) * 100).toFixed(1) + "%";
      img.style.transform = "rotate(" + mark.rot.toFixed(1) + "deg)";
      field.appendChild(img);
    }

    el.insertBefore(field, el.firstChild);
  }

  function run() {
    var bands = document.querySelectorAll(".light-background");
    for (var i = 0; i < bands.length; i++) place(bands[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
