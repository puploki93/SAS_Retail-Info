document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".nav-tab");
  const panels = document.querySelectorAll(".tab-panel");
  const searchForm = document.querySelector(".search-form");

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
    searchForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const query = searchForm.querySelector("input").value.trim();
      if (query) {
        window.alert(`Search demo: results for "${query}" coming soon.`);
      }
    });
  }
});
