/**
 * Participant admin: unlock/populate ticket filter as soon as an evenement is chosen.
 */
(function () {
  function loadTicketsByEvent() {
    var el = document.getElementById("participant-tickets-by-event");
    if (!el) {
      return {};
    }
    try {
      return JSON.parse(el.textContent || "{}") || {};
    } catch (err) {
      return {};
    }
  }

  function ticketsForEvent(ticketsByEvent, eventId) {
    if (!eventId) {
      return [];
    }
    return ticketsByEvent[eventId] || ticketsByEvent[String(eventId)] || [];
  }

  function populateTicketOptions(ticketSelect, tickets, selectedId, allLabel) {
    ticketSelect.innerHTML = "";
    var allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = allLabel;
    ticketSelect.appendChild(allOpt);

    tickets.forEach(function (ticket) {
      var opt = document.createElement("option");
      opt.value = String(ticket.id);
      opt.textContent = ticket.label;
      if (selectedId && String(ticket.id) === String(selectedId)) {
        opt.selected = true;
      }
      ticketSelect.appendChild(opt);
    });
  }

  function syncTicketFilter(eventSelect, ticketSelect, ticketsByEvent, allLabel) {
    if (!eventSelect || !ticketSelect) {
      return;
    }

    var eventId = eventSelect.value;
    var previousTicketId = ticketSelect.value;

    if (!eventId) {
      populateTicketOptions(ticketSelect, [], null, allLabel);
      ticketSelect.disabled = true;
      return;
    }

    var tickets = ticketsForEvent(ticketsByEvent, eventId);
    var keepSelection = tickets.some(function (ticket) {
      return String(ticket.id) === String(previousTicketId);
    });
    populateTicketOptions(
      ticketSelect,
      tickets,
      keepSelection ? previousTicketId : null,
      allLabel
    );
    ticketSelect.disabled = false;
  }

  function init() {
    var eventSelect = document.getElementById("id_evenement");
    var ticketSelect = document.getElementById("id_ticket");
    if (!eventSelect || !ticketSelect) {
      return;
    }

    var ticketsByEvent = loadTicketsByEvent();
    var allLabel = "All";
    var emptyOption = ticketSelect.querySelector('option[value=""]');
    if (emptyOption && emptyOption.textContent) {
      allLabel = emptyOption.textContent;
    }

    syncTicketFilter(eventSelect, ticketSelect, ticketsByEvent, allLabel);

    eventSelect.addEventListener("change", function () {
      ticketSelect.value = "";
      syncTicketFilter(eventSelect, ticketSelect, ticketsByEvent, allLabel);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
