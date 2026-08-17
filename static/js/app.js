(function () {
  "use strict";

  function populateEvents(yearSelect, eventSelect, submitBtn, preselectRound) {
    const year = yearSelect.value;
    eventSelect.disabled = true;
    eventSelect.innerHTML = "<option value=\"\">Loading…</option>";
    if (submitBtn) submitBtn.disabled = true;

    fetch("/api/events/" + year)
      .then(function (res) {
        if (!res.ok) throw new Error("Failed to load events (" + res.status + ")");
        return res.json();
      })
      .then(function (events) {
        eventSelect.innerHTML = "";

        if (!events.length) {
          eventSelect.innerHTML = "<option value=\"\">No races yet this season</option>";
          return;
        }

        events.forEach(function (ev) {
          const opt = document.createElement("option");
          opt.value = ev.round;
          opt.textContent = ev.name;
          eventSelect.appendChild(opt);
        });

        if (preselectRound) {
          eventSelect.value = String(preselectRound);
        }

        eventSelect.disabled = false;
        if (submitBtn) submitBtn.disabled = false;
      })
      .catch(function () {
        eventSelect.innerHTML = "<option value=\"\">Couldn't load races</option>";
      });
  }

  function showLoadingOverlay() {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) overlay.hidden = false;
  }

  document.querySelectorAll("[data-race-picker]").forEach(function (form) {
    const yearSelect = form.querySelector("[data-year-select]");
    const eventSelect = form.querySelector("[data-event-select]");
    const submitBtn = form.querySelector("[data-submit]");
    const preselectRound = eventSelect.value || null;

    populateEvents(yearSelect, eventSelect, submitBtn, preselectRound);

    yearSelect.addEventListener("change", function () {
      populateEvents(yearSelect, eventSelect, submitBtn, null);
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const year = yearSelect.value;
      const round = eventSelect.value;
      if (!year || !round) return;
      showLoadingOverlay();
      window.location.href = "/race/" + year + "/" + round;
    });
  });
})();
