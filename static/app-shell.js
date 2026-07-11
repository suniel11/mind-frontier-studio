(() => {
  const VIEW_DEFINITIONS = [
    {
      id: "overview",
      label: "Overview",
      icon: "◫",
      title: "Studio Overview",
      subtitle: "Channel health, recommendations, and current priorities.",
      selectors: [
        ".producer-panel",
        ".planner-panel",
        ".operations-panel"
      ]
    },
    {
      id: "create",
      label: "Create",
      icon: "＋",
      title: "Create & Plan",
      subtitle: "Generate videos and build evidence-backed production plans.",
      selectors: [
        "#project-form",
        ".orchestrator-panel",
        ".producer-workspace-panel"
      ]
    },
    {
      id: "youtube",
      label: "YouTube",
      icon: "▶",
      title: "YouTube Intelligence",
      subtitle: "Sync your channel, inspect performance, and connect projects.",
      selectors: [".youtube-sync-panel"]
    },
    {
      id: "atlas",
      label: "Atlas",
      icon: "✦",
      title: "Atlas Intelligence",
      subtitle: "Conversation, memory, agents, and performance prediction.",
      selectors: [
        ".atlas-chat-panel",
        ".atlas-memory-panel",
        ".atlas-agents-panel",
        ".prediction-panel",
        ".atlas-panel"
      ]
    },
    {
      id: "automation",
      label: "Automation",
      icon: "⚙",
      title: "Automation",
      subtitle: "Batch queues and autonomous production missions.",
      selectors: [
        ".apollo-panel",
        ".orion-panel"
      ]
    },
    {
      id: "projects",
      label: "Projects",
      icon: "▣",
      title: "Projects",
      subtitle: "Browse project history, outputs, and production status.",
      selectors: [
        ".dashboard-panel",
        ".project-dashboard-panel",
        ".projects-panel"
      ]
    }
  ];

  const STORAGE_KEY = "mind-frontier-active-view";

  function sectionMatches(section, selectors) {
    return selectors.some((selector) => {
      try {
        return section.matches(selector);
      } catch {
        return false;
      }
    });
  }

  function createElement(tag, className, html = "") {
    const node = document.createElement(tag);
    node.className = className;
    node.innerHTML = html;
    return node;
  }

  function buildShell() {
    const originalShell = document.querySelector("main.shell");
    if (!originalShell || document.querySelector(".mf-app-shell")) return;

    const originalHeader = originalShell.querySelector(":scope > header");
    const directChildren = [...originalShell.children];
    const dialogs = directChildren.filter((node) => node.tagName === "DIALOG");
    const contentNodes = directChildren.filter(
      (node) =>
        node !== originalHeader &&
        node.tagName !== "DIALOG" &&
        node.tagName !== "SCRIPT"
    );

    document.body.classList.add("mf-redesigned");

    const app = createElement("div", "mf-app-shell");
    const sidebar = createElement("aside", "mf-sidebar");
    const main = createElement("div", "mf-main");
    const topbar = createElement("header", "mf-topbar");
    const viewport = createElement("div", "mf-viewport");

    sidebar.innerHTML = `
      <div class="mf-brand">
        <div class="mf-brand-mark">MF</div>
        <div>
          <strong>Mind Frontier</strong>
          <span>Creator OS</span>
        </div>
      </div>
      <nav class="mf-nav" aria-label="Studio navigation"></nav>
      <div class="mf-sidebar-footer">
        <span class="mf-status-dot"></span>
        <div>
          <strong>Studio local</strong>
          <span>v27 platform</span>
        </div>
      </div>
    `;

    topbar.innerHTML = `
      <div>
        <button class="mf-mobile-menu" type="button" aria-label="Toggle navigation">☰</button>
        <p class="mf-kicker">MIND FRONTIER STUDIO</p>
        <h1 id="mf-view-title">Studio Overview</h1>
        <p id="mf-view-subtitle">Channel health, recommendations, and current priorities.</p>
      </div>
      <div class="mf-topbar-actions">
        <button id="mf-command-button" type="button" class="mf-command-button">
          <span>⌘</span> Quick navigation
        </button>
      </div>
    `;

    const nav = sidebar.querySelector(".mf-nav");
    VIEW_DEFINITIONS.forEach((view) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mf-nav-item";
      button.dataset.view = view.id;
      button.innerHTML = `
        <span class="mf-nav-icon">${view.icon}</span>
        <span>${view.label}</span>
      `;
      nav.appendChild(button);
    });

    const assigned = new Set();
    VIEW_DEFINITIONS.forEach((view) => {
      const page = createElement("section", "mf-page");
      page.dataset.viewPage = view.id;

      const pageGrid = createElement("div", "mf-page-grid");
      contentNodes.forEach((node) => {
        if (assigned.has(node)) return;
        if (sectionMatches(node, view.selectors)) {
          node.classList.add("mf-module");
          pageGrid.appendChild(node);
          assigned.add(node);
        }
      });

      if (!pageGrid.children.length) {
        pageGrid.innerHTML = `
          <div class="mf-empty-state panel">
            <strong>${view.label}</strong>
            <p>This area is ready for the next module.</p>
          </div>
        `;
      }

      page.appendChild(pageGrid);
      viewport.appendChild(page);
    });

    const remaining = contentNodes.filter((node) => !assigned.has(node));
    if (remaining.length) {
      const moreView = {
        id: "more",
        label: "More",
        icon: "•••",
        title: "More Tools",
        subtitle: "Additional Studio modules and utilities."
      };

      const button = document.createElement("button");
      button.type = "button";
      button.className = "mf-nav-item";
      button.dataset.view = moreView.id;
      button.innerHTML = `
        <span class="mf-nav-icon">${moreView.icon}</span>
        <span>${moreView.label}</span>
      `;
      nav.appendChild(button);
      VIEW_DEFINITIONS.push(moreView);

      const page = createElement("section", "mf-page");
      page.dataset.viewPage = moreView.id;
      const pageGrid = createElement("div", "mf-page-grid");
      remaining.forEach((node) => {
        node.classList.add("mf-module");
        pageGrid.appendChild(node);
      });
      page.appendChild(pageGrid);
      viewport.appendChild(page);
    }

    main.appendChild(topbar);
    main.appendChild(viewport);
    app.appendChild(sidebar);
    app.appendChild(main);

    originalShell.innerHTML = "";
    originalShell.appendChild(app);
    dialogs.forEach((dialog) => originalShell.appendChild(dialog));

    bindNavigation();
    bindShortcuts();
    activateInitialView();
  }

  function activateView(viewId, updateHash = true) {
    const definition =
      VIEW_DEFINITIONS.find((view) => view.id === viewId) ||
      VIEW_DEFINITIONS[0];

    document.querySelectorAll(".mf-nav-item").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === definition.id);
    });

    document.querySelectorAll(".mf-page").forEach((page) => {
      page.classList.toggle(
        "active",
        page.dataset.viewPage === definition.id
      );
    });

    const title = document.querySelector("#mf-view-title");
    const subtitle = document.querySelector("#mf-view-subtitle");
    if (title) title.textContent = definition.title;
    if (subtitle) subtitle.textContent = definition.subtitle;

    localStorage.setItem(STORAGE_KEY, definition.id);
    if (updateHash) {
      history.replaceState(null, "", `#${definition.id}`);
    }

    document.querySelector(".mf-sidebar")?.classList.remove("mobile-open");
    window.scrollTo({top: 0, behavior: "smooth"});
  }

  function activateInitialView() {
    const hashView = location.hash.replace("#", "");
    const savedView = localStorage.getItem(STORAGE_KEY);
    const valid = (value) =>
      VIEW_DEFINITIONS.some((view) => view.id === value);

    activateView(
      valid(hashView)
        ? hashView
        : valid(savedView)
        ? savedView
        : "overview",
      false
    );
  }

  function bindNavigation() {
    document.querySelectorAll(".mf-nav-item").forEach((button) => {
      button.addEventListener("click", () => {
        activateView(button.dataset.view);
      });
    });

    document.querySelector(".mf-mobile-menu")?.addEventListener("click", () => {
      document.querySelector(".mf-sidebar")?.classList.toggle("mobile-open");
    });

    window.addEventListener("hashchange", () => {
      const next = location.hash.replace("#", "");
      if (VIEW_DEFINITIONS.some((view) => view.id === next)) {
        activateView(next, false);
      }
    });
  }

  function bindShortcuts() {
    const commandButton = document.querySelector("#mf-command-button");

    function showQuickNavigation() {
      const labels = VIEW_DEFINITIONS.map(
        (view, index) => `${index + 1}. ${view.label}`
      ).join("\n");
      const answer = prompt(`Open a Studio area:\n\n${labels}`);
      const index = Number(answer) - 1;
      if (Number.isInteger(index) && VIEW_DEFINITIONS[index]) {
        activateView(VIEW_DEFINITIONS[index].id);
      }
    }

    commandButton?.addEventListener("click", showQuickNavigation);

    document.addEventListener("keydown", (event) => {
      const modifier = event.ctrlKey || event.metaKey;
      if (modifier && event.key.toLowerCase() === "k") {
        event.preventDefault();
        showQuickNavigation();
      }

      if (
        event.altKey &&
        /^[1-9]$/.test(event.key) &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
      ) {
        const index = Number(event.key) - 1;
        if (VIEW_DEFINITIONS[index]) {
          activateView(VIEW_DEFINITIONS[index].id);
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildShell);
  } else {
    buildShell();
  }
})();
