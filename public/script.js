document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".nav-tab");
  const panels = document.querySelectorAll(".tab-panel");
  const searchForm = document.querySelector(".search-form");
  const searchInput = searchForm?.querySelector("input");
  const projectSummary = document.getElementById("project-summary");
  const contactGrid = document.getElementById("contact-grid");
  const requiredActionsList = document.getElementById("required-actions");
  const projectNotes = document.getElementById("project-notes");
  const docGrid = document.getElementById("doc-grid");
  const emailList = document.getElementById("email-list");
  const flightList = document.getElementById("flight-list");
  const hotelCard = document.getElementById("hotel-card");
  const carpoolList = document.getElementById("carpool-list");
  const policyGrid = document.getElementById("policy-grid");
  const downloadManifestBtn = document.getElementById("download-manifest");

  const state = {
    project: null,
    policies: [],
    attachments: [],
    docFilter: "",
  };

  const activateTab = (tabId) => {
    tabs.forEach((tab) => {
      const active = tab.dataset.tab === tabId;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active);
    });

    panels.forEach((panel) => {
      const active = panel.id === tabId;
      panel.classList.toggle("active", active);
    });
  };

  const humanize = (value = "") =>
    value
      .split(/[_\s-]+/)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");

  const formatDateTime = (value, options = {}) => {
    if (!value) return "TBD";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    const formatter = new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      ...options,
    });
    return formatter.format(date);
  };

  const formatDate = (value) => {
    if (!value) return "TBD";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    const formatter = new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    return formatter.format(date);
  };

  const createElement = (tag, { className, text } = {}) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (typeof text === "string") el.textContent = text;
    return el;
  };

  const renderSummary = (project) => {
    if (!projectSummary) return;
    projectSummary.innerHTML = "";

    const store = project.store || {};
    const storeCard = createElement("article", { className: "info-card" });
    storeCard.appendChild(createElement("h3", { text: project.title }));
    storeCard.appendChild(
      createElement("p", {
        text: `Store ${store.number || "TBD"} · ${store.name || "Name coming soon"}`,
      })
    );
    storeCard.appendChild(
      createElement("p", {
        text: store.address || "Add the store address to the manifest.",
      })
    );
    storeCard.appendChild(
      createElement("p", {
        text: `Report Time: ${formatDateTime(store.report_time)}`,
      })
    );

    if (Array.isArray(store.notes) && store.notes.length) {
      const noteList = createElement("ul");
      store.notes.forEach((note) => {
        const item = createElement("li", { text: note });
        noteList.appendChild(item);
      });
      storeCard.appendChild(noteList);
    }

    projectSummary.appendChild(storeCard);
  };

  const renderContacts = (project) => {
    if (!contactGrid) return;
    contactGrid.innerHTML = "";

    const contacts = Object.entries(project.contacts || {});
    if (!contacts.length) {
      contactGrid.appendChild(
        createElement("div", {
          className: "empty-state",
          text: "No contacts have been added yet.",
        })
      );
      return;
    }

    contacts.forEach(([role, details]) => {
      const card = createElement("article", { className: "info-card" });
      card.appendChild(createElement("h3", { text: humanize(role) }));
      card.appendChild(createElement("p", { text: details.name || "TBD" }));
      if (details.phone) {
        card.appendChild(createElement("p", { text: details.phone }));
      }
      if (details.email) {
        const emailLink = createElement("a", { text: details.email });
        emailLink.href = `mailto:${details.email}`;
        emailLink.className = "ghost-button";
        card.appendChild(emailLink);
      }
      contactGrid.appendChild(card);
    });
  };

  const checklistKey = (projectId) => `sas-retail-actions-${projectId}`;

  const getChecklistState = (projectId) => {
    try {
      return JSON.parse(localStorage.getItem(checklistKey(projectId))) || {};
    } catch (error) {
      console.warn("Unable to read checklist preferences", error);
      return {};
    }
  };

  const setChecklistState = (projectId, value) => {
    try {
      localStorage.setItem(checklistKey(projectId), JSON.stringify(value));
    } catch (error) {
      console.warn("Unable to persist checklist preferences", error);
    }
  };

  const renderChecklist = (project) => {
    if (!requiredActionsList) return;
    requiredActionsList.innerHTML = "";

    const tasks = project.required_actions || [];
    const stateMap = getChecklistState(project.id);

    if (!tasks.length) {
      requiredActionsList.appendChild(
        createElement("li", { text: "No actions at this time." })
      );
      return;
    }

    tasks.forEach((task, index) => {
      const item = createElement("li");
      const checkbox = createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(stateMap[index]);
      checkbox.addEventListener("change", () => {
        stateMap[index] = checkbox.checked;
        setChecklistState(project.id, stateMap);
      });
      const label = createElement("span", { text: task });
      item.append(checkbox, label);
      requiredActionsList.appendChild(item);
    });
  };

  const renderNotes = (project) => {
    if (!projectNotes) return;
    projectNotes.innerHTML = "";
    const notes = project.notes || [];
    if (!notes.length) {
      projectNotes.appendChild(createElement("li", { text: "No notes yet." }));
      return;
    }
    notes.forEach((note) => {
      projectNotes.appendChild(createElement("li", { text: note }));
    });
  };

  const iconForType = (type = "") => {
    const normalized = type.toLowerCase();
    if (normalized.includes("pdf")) return "📄";
    if (normalized.includes("ppt")) return "📊";
    if (normalized.includes("xls")) return "📈";
    if (normalized.includes("email")) return "✉️";
    return "📁";
  };

  const renderDocs = (project) => {
    state.attachments = project.attachments || [];
    updateDocGrid();
  };

  const updateDocGrid = (filterValue = state.docFilter) => {
    if (!docGrid) return;
    docGrid.innerHTML = "";
    state.docFilter = filterValue;
    const normalized = filterValue.trim().toLowerCase();

    const attachments = !normalized
      ? state.attachments
      : state.attachments.filter((item) =>
          [item.title, item.type]
            .filter(Boolean)
            .some((field) => field.toLowerCase().includes(normalized))
        );

    if (!attachments.length) {
      docGrid.appendChild(
        createElement("div", {
          className: "empty-state",
          text: normalized
            ? `No documents match "${filterValue}".`
            : "No documents have been linked yet.",
        })
      );
      return;
    }

    const fragment = document.createDocumentFragment();
    attachments.forEach((attachment) => {
      const card = createElement("article", { className: "resource-card" });
      const icon = createElement("div", {
        className: "card-icon",
        text: iconForType(attachment.type),
      });
      card.appendChild(icon);
      card.appendChild(createElement("h3", { text: attachment.title }));
      const meta = createElement("div", { className: "doc-meta" });
      meta.appendChild(
        createElement("span", {
          className: "badge",
          text: (attachment.type || "doc").toUpperCase(),
        })
      );
      meta.appendChild(
        createElement("span", {
          text: attachment.mandatory ? "Mandatory" : "Optional",
        })
      );
      card.appendChild(meta);

      const button = createElement("button", {
        className: "ghost-button",
        text: "Copy Repo Path",
      });
      button.type = "button";
      button.dataset.path = attachment.path;
      card.appendChild(button);
      fragment.appendChild(card);
    });

    docGrid.appendChild(fragment);
  };

  const renderSourceEmails = (project) => {
    if (!emailList) return;
    emailList.innerHTML = "";
    const sources = project.source_emails || [];
    if (!sources.length) {
      emailList.appendChild(
        createElement("li", { text: "No source emails archived yet." })
      );
      return;
    }
    sources.forEach((email) => {
      const item = createElement("li");
      const details = createElement("div");
      details.appendChild(
        createElement("strong", {
          text: humanize(email.type || "reference"),
        })
      );
      details.appendChild(createElement("p", { text: email.path }));
      const button = createElement("button", {
        className: "ghost-button",
        text: "Copy Repo Path",
      });
      button.type = "button";
      button.dataset.path = email.path;
      item.append(details, button);
      emailList.appendChild(item);
    });
  };

  const renderTravel = (project) => {
    if (flightList) {
      flightList.innerHTML = "";
      const flights = project.travel?.flights || [];
      if (!flights.length) {
        flightList.appendChild(
          createElement("div", {
            className: "empty-state",
            text: "Flight information is not yet available.",
          })
        );
      } else {
        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        ["Traveler", "Segment", "Departure", "Arrival"].forEach((label) => {
          headerRow.appendChild(createElement("th", { text: label }));
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        flights.forEach((flight) => {
          (flight.legs || []).forEach((leg, index) => {
            const row = document.createElement("tr");
            row.appendChild(createElement("td", { text: flight.traveler }));
            row.appendChild(
              createElement("td", {
                text: `Leg ${index + 1} (${leg.depart_airport} → ${leg.arrive_airport})`,
              })
            );
            row.appendChild(
              createElement("td", { text: formatDateTime(leg.depart_time) })
            );
            row.appendChild(
              createElement("td", { text: formatDateTime(leg.arrive_time) })
            );
            tbody.appendChild(row);
          });
        });
        table.appendChild(tbody);
        flightList.appendChild(table);
      }
    }

    if (hotelCard) {
      hotelCard.innerHTML = "";
      const hotel = project.travel?.hotel;
      if (!hotel) {
        hotelCard.appendChild(
          createElement("p", { text: "Hotel assignments pending." })
        );
      } else {
        hotelCard.appendChild(createElement("h3", { text: hotel.name || "Hotel" }));
        hotelCard.appendChild(
          createElement("p", { text: hotel.address || "Address coming soon." })
        );
        hotelCard.appendChild(
          createElement("p", {
            text: `Check-in ${formatDate(hotel.check_in)} · Check-out ${formatDate(
              hotel.check_out
            )}`,
          })
        );
        if (Array.isArray(hotel.reservations) && hotel.reservations.length) {
          const list = createElement("ul");
          hotel.reservations.forEach((reservation) => {
            list.appendChild(
              createElement("li", {
                text: `${reservation.guest} · Confirmation ${reservation.confirmation}`,
              })
            );
          });
          hotelCard.appendChild(list);
        }
      }
    }

    if (carpoolList) {
      carpoolList.innerHTML = "";
      const carpools = project.travel?.carpool || [];
      if (!carpools.length) {
        carpoolList.appendChild(
          createElement("p", { text: "No carpool assignments yet." })
        );
      } else {
        const list = createElement("ul");
        carpools.forEach((entry) => {
          list.appendChild(
            createElement("li", {
              text: `${entry.driver} (${entry.vehicle || "Vehicle"}) → ${
                (entry.riders || []).join(", ") || "No riders"
              } · Arrival ${formatDateTime(entry.arrival_time)}`,
            })
          );
        });
        carpoolList.appendChild(list);
      }
    }
  };

  const renderPolicies = (project) => {
    if (!policyGrid) return;
    policyGrid.innerHTML = "";
    const references = project.policies?.references || [];

    if (!references.length) {
      policyGrid.appendChild(
        createElement("div", {
          className: "empty-state",
          text: "No policy references linked to this project.",
        })
      );
      return;
    }

    references.forEach((policyId) => {
      const policy = state.policies.find((item) => item.id === policyId);
      const card = createElement("article", { className: "resource-card" });
      card.appendChild(
        createElement("div", {
          className: "card-icon",
          text: iconForType(policy?.type || "policy"),
        })
      );
      card.appendChild(
        createElement("h3", { text: policy?.title || humanize(policyId) })
      );
      card.appendChild(
        createElement("p", {
          text:
            policy?.description ||
            "Update policy metadata in data/policies.yaml to show more details.",
        })
      );
      const meta = createElement("div", { className: "doc-meta" });
      meta.appendChild(
        createElement("span", {
          className: "badge",
          text: policy?.type ? policy.type.toUpperCase() : "POLICY",
        })
      );
      if (policy?.last_updated) {
        meta.appendChild(
          createElement("span", {
            text: `Updated ${formatDate(policy.last_updated)}`,
          })
        );
      }
      card.appendChild(meta);
      const button = createElement("button", {
        className: "ghost-button",
        text: "Copy Repo Path",
      });
      button.type = "button";
      button.dataset.path = policy?.path || `data/policies/${policyId}.yaml`;
      card.appendChild(button);
      policyGrid.appendChild(card);
    });
  };

  const renderProject = (project) => {
    state.project = project;
    renderSummary(project);
    renderContacts(project);
    renderChecklist(project);
    renderNotes(project);
    renderDocs(project);
    renderSourceEmails(project);
    renderTravel(project);
    renderPolicies(project);
  };

  const handleCopyClick = async (event) => {
    const target = event.target.closest("button[data-path]");
    if (!target) return;
    event.preventDefault();
    const original = target.textContent;
    const value = target.dataset.path;
    if (!value) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        throw new Error("Clipboard API unavailable");
      }
      target.textContent = "Copied!";
      setTimeout(() => {
        target.textContent = original;
      }, 1600);
    } catch (error) {
      window.prompt("Copy this path", value);
    }
  };

  const handleSearch = (event) => {
    event?.preventDefault();
    if (!searchInput) return;
    updateDocGrid(searchInput.value);
  };

  const initialise = async () => {
    try {
      const [projectResp, policyResp] = await Promise.all([
        fetch("data/projects.example.json"),
        fetch("data/policies.example.json"),
      ]);

      if (!projectResp.ok || !policyResp.ok) {
        throw new Error("Unable to load example data");
      }

      const projectData = await projectResp.json();
      const policyData = await policyResp.json();
      state.policies = policyData.policies || [];
      const project = projectData.projects?.[0];
      if (project) {
        renderProject(project);
      }
    } catch (error) {
      console.error(error);
      if (projectSummary) {
        projectSummary.innerHTML = "";
        projectSummary.appendChild(
          createElement("div", {
            className: "empty-state",
            text: "Unable to load example manifest. Check the developer console for details.",
          })
        );
      }
    }
  };

  tabs.forEach((tab) => {
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", tab.dataset.tab);
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
    tab.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateTab(tab.dataset.tab);
      }
    });
  });

  panels.forEach((panel) => {
    panel.setAttribute("role", "tabpanel");
  });

  if (searchForm) {
    searchForm.addEventListener("submit", handleSearch);
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => updateDocGrid(searchInput.value));
  }

  if (downloadManifestBtn) {
    downloadManifestBtn.addEventListener("click", () => {
      if (!state.project) return;
      const blob = new Blob([JSON.stringify(state.project, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${state.project.id.toLowerCase()}-example.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    });
  }

  document.addEventListener("click", handleCopyClick);
  initialise();
});
