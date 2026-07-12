(() => {
  "use strict";

  const VIEW_DEFINITIONS = [
    {
      id: "overview",
      label: "Overview",
      icon: "◫",
      title: "Studio Overview",
      subtitle: "Channel health, recommendations, and current priorities.",
      selectors: [".producer-panel", ".planner-panel", ".operations-panel"]
    },
    {
      id: "create",
      label: "Create",
      icon: "+",
      title: "Create Anything",
      subtitle: "Direct an idea, review the brief, and follow production to completion.",
      selectors: ["#creative-director-panel", "#creator-workspace"]
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
      selectors: [".apollo-panel", ".orion-panel"]
    },
    {
      id: "projects",
      label: "Projects",
      icon: "▣",
      title: "Projects",
      subtitle: "Browse project history, outputs, and production status.",
      selectors: [".dashboard-panel"]
    },
    {
      id: "settings",
      label: "Settings",
      icon: "●",
      title: "Settings & Readiness",
      subtitle: "Review configuration without exposing local secrets.",
      selectors: ["#studio-settings-panel"]
    },
    {
      id: "advanced",
      label: "Advanced",
      icon: "•••",
      title: "Advanced Tools",
      subtitle: "Legacy generators and planning tools kept for compatibility.",
      selectors: [
        "#project-form",
        "#status",
        "#result",
        ".orchestrator-panel",
        ".producer-workspace-panel"
      ]
    }
  ];

  const STORAGE_KEY = "mind-frontier-active-view";
  let views = [...VIEW_DEFINITIONS];

  function createElement(tag, className = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    return node;
  }

  function safeStorageGet(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  function safeStorageSet(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Navigation still works when storage is blocked.
    }
  }

  function sectionMatches(section, selectors) {
    return selectors.some((selector) => {
      try {
        return section.matches(selector);
      } catch {
        return false;
      }
    });
  }

  function appendTextElement(parent, tag, className, text) {
    const element = createElement(tag, className);
    element.textContent = text;
    parent.appendChild(element);
    return element;
  }

  function buildNavigationButton(view) {
    const button = createElement("button", "mf-nav-item");
    button.type = "button";
    button.id = `mf-nav-${view.id}`;
    button.dataset.view = view.id;
    button.setAttribute("aria-controls", `mf-page-${view.id}`);

    appendTextElement(button, "span", "mf-nav-icon", view.icon).setAttribute(
      "aria-hidden",
      "true"
    );
    appendTextElement(button, "span", "", view.label);
    return button;
  }

  function buildCommandDialog() {
    const dialog = createElement("dialog", "mf-command-dialog");
    dialog.id = "mf-command-dialog";
    dialog.setAttribute("aria-labelledby", "mf-command-title");

    const heading = appendTextElement(dialog, "h2", "", "Quick navigation");
    heading.id = "mf-command-title";
    appendTextElement(dialog, "p", "fine", "Choose a Studio area.");

    const list = createElement("div", "mf-command-list");
    views.forEach((view, index) => {
      const button = createElement("button", "mf-command-option");
      button.type = "button";
      button.dataset.commandView = view.id;
      button.textContent = `${index + 1}. ${view.label}`;
      list.appendChild(button);
    });
    dialog.appendChild(list);

    const close = createElement("button", "small-button secondary");
    close.type = "button";
    close.dataset.commandClose = "true";
    close.textContent = "Close";
    dialog.appendChild(close);
    return dialog;
  }

  function buildShell() {
    const originalShell = document.querySelector("main.shell");
    if (!originalShell || document.querySelector(".mf-app-shell")) return;

    const originalHeader = originalShell.querySelector(":scope > header");
    const readinessBanner = originalShell.querySelector(
      ":scope > #system-readiness-banner"
    );
    const directChildren = [...originalShell.children];
    const dialogs = directChildren.filter((node) => node.tagName === "DIALOG");
    const contentNodes = directChildren.filter(
      (node) =>
        node !== originalHeader &&
        node !== readinessBanner &&
        node.tagName !== "DIALOG" &&
        node.tagName !== "SCRIPT"
    );

    document.body.classList.add("mf-redesigned");

    const app = createElement("div", "mf-app-shell");
    const sidebar = createElement("aside", "mf-sidebar");
    sidebar.id = "mf-sidebar";
    const main = createElement("div", "mf-main");
    const topbar = createElement("header", "mf-topbar");
    const viewport = createElement("div", "mf-viewport");

    const brand = createElement("div", "mf-brand");
    appendTextElement(brand, "div", "mf-brand-mark", "MF");
    const brandCopy = createElement("div");
    appendTextElement(brandCopy, "strong", "", "Mind Frontier");
    appendTextElement(brandCopy, "span", "", "Creator OS");
    brand.appendChild(brandCopy);
    sidebar.appendChild(brand);

    const nav = createElement("nav", "mf-nav");
    nav.setAttribute("aria-label", "Studio navigation");
    sidebar.appendChild(nav);

    const footer = createElement("div", "mf-sidebar-footer");
    const statusDot = createElement("span", "mf-status-dot");
    statusDot.setAttribute("aria-hidden", "true");
    footer.appendChild(statusDot);
    const footerCopy = createElement("div");
    appendTextElement(footerCopy, "strong", "", "Studio local");
    appendTextElement(footerCopy, "span", "", "1.0.0-rc1");
    footer.appendChild(footerCopy);
    sidebar.appendChild(footer);

    const topbarCopy = createElement("div");
    const mobileButton = createElement("button", "mf-mobile-menu");
    mobileButton.type = "button";
    mobileButton.setAttribute("aria-label", "Open Studio navigation");
    mobileButton.setAttribute("aria-controls", "mf-sidebar");
    mobileButton.setAttribute("aria-expanded", "false");
    mobileButton.textContent = "☰";
    topbarCopy.appendChild(mobileButton);
    appendTextElement(topbarCopy, "p", "mf-kicker", "MIND FRONTIER STUDIO");
    const title = appendTextElement(topbarCopy, "h1", "", "Studio Overview");
    title.id = "mf-view-title";
    const subtitle = appendTextElement(
      topbarCopy,
      "p",
      "",
      "Channel health, recommendations, and current priorities."
    );
    subtitle.id = "mf-view-subtitle";
    topbar.appendChild(topbarCopy);

    const topbarActions = createElement("div", "mf-topbar-actions");
    const commandButton = createElement("button", "mf-command-button");
    commandButton.id = "mf-command-button";
    commandButton.type = "button";
    commandButton.textContent = "Quick navigation";
    commandButton.setAttribute("aria-haspopup", "dialog");
    topbarActions.appendChild(commandButton);
    topbar.appendChild(topbarActions);

    views.forEach((view) => nav.appendChild(buildNavigationButton(view)));

    const assigned = new Set();
    views.forEach((view) => {
      const page = createElement("section", "mf-page");
      page.id = `mf-page-${view.id}`;
      page.dataset.viewPage = view.id;
      page.setAttribute("aria-labelledby", `mf-nav-${view.id}`);
      page.hidden = true;

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
        const empty = createElement("div", "mf-empty-state panel");
        appendTextElement(empty, "strong", "", view.label);
        appendTextElement(empty, "p", "", "No modules are available in this area yet.");
        pageGrid.appendChild(empty);
      }

      page.appendChild(pageGrid);
      viewport.appendChild(page);
    });

    const remaining = contentNodes.filter((node) => !assigned.has(node));
    if (remaining.length) {
      const moreView = {
        id: "more",
        label: "More",
        icon: "…",
        title: "More Tools",
        subtitle: "Additional Studio modules and utilities."
      };
      views.push(moreView);
      nav.appendChild(buildNavigationButton(moreView));

      const page = createElement("section", "mf-page");
      page.id = "mf-page-more";
      page.dataset.viewPage = "more";
      page.setAttribute("aria-labelledby", "mf-nav-more");
      page.hidden = true;
      const pageGrid = createElement("div", "mf-page-grid");
      remaining.forEach((node) => {
        node.classList.add("mf-module");
        pageGrid.appendChild(node);
      });
      page.appendChild(pageGrid);
      viewport.appendChild(page);
    }

    const scrim = createElement("button", "mf-sidebar-scrim");
    scrim.type = "button";
    scrim.setAttribute("aria-label", "Close Studio navigation");
    scrim.hidden = true;

    main.appendChild(topbar);
    if (readinessBanner) main.appendChild(readinessBanner);
    main.appendChild(viewport);
    app.appendChild(sidebar);
    app.appendChild(scrim);
    app.appendChild(main);

    const commandDialog = buildCommandDialog();
    originalShell.replaceChildren(app, ...dialogs, commandDialog);

    bindNavigation();
    bindShortcuts();
    bindMobileNavigation();
    activateInitialView();
  }

  function definitionFor(viewId) {
    return views.find((view) => view.id === viewId) || views[0];
  }

  function activateView(viewId, updateHash = true) {
    const definition = definitionFor(viewId);

    document.querySelectorAll(".mf-nav-item").forEach((button) => {
      const active = button.dataset.view === definition.id;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });

    document.querySelectorAll(".mf-page").forEach((page) => {
      const active = page.dataset.viewPage === definition.id;
      page.classList.toggle("active", active);
      page.hidden = !active;
    });

    const title = document.querySelector("#mf-view-title");
    const subtitle = document.querySelector("#mf-view-subtitle");
    if (title) title.textContent = definition.title;
    if (subtitle) subtitle.textContent = definition.subtitle;

    safeStorageSet(STORAGE_KEY, definition.id);
    if (updateHash) history.replaceState(null, "", `#${definition.id}`);
    setMobileOpen(false);
    window.scrollTo({top: 0, behavior: "smooth"});
    document.dispatchEvent(
      new CustomEvent("mindfrontier:view-changed", {detail: {view: definition.id}})
    );
  }

  function activateInitialView() {
    const hashView = location.hash.replace(/^#/, "");
    const savedView = safeStorageGet(STORAGE_KEY);
    const valid = (value) => views.some((view) => view.id === value);
    activateView(valid(hashView) ? hashView : valid(savedView) ? savedView : "overview", false);
  }

  function bindNavigation() {
    document.querySelectorAll(".mf-nav-item").forEach((button) => {
      button.addEventListener("click", () => activateView(button.dataset.view));
    });

    window.addEventListener("hashchange", () => {
      const next = location.hash.replace(/^#/, "");
      if (views.some((view) => view.id === next)) activateView(next, false);
    });

    document.addEventListener("mindfrontier:navigate", (event) => {
      const view = event.detail?.view;
      if (views.some((item) => item.id === view)) activateView(view);
    });
  }

  function setMobileOpen(open) {
    const sidebar = document.querySelector(".mf-sidebar");
    const menu = document.querySelector(".mf-mobile-menu");
    const scrim = document.querySelector(".mf-sidebar-scrim");
    if (!sidebar || !menu || !scrim) return;

    const mobile = window.matchMedia("(max-width: 760px)").matches;
    const effectiveOpen = mobile && open;
    sidebar.classList.toggle("mobile-open", effectiveOpen);
    menu.setAttribute("aria-expanded", String(effectiveOpen));
    menu.setAttribute(
      "aria-label",
      effectiveOpen ? "Close Studio navigation" : "Open Studio navigation"
    );
    scrim.hidden = !effectiveOpen;
    if ("inert" in sidebar) sidebar.inert = mobile && !effectiveOpen;
  }

  function bindMobileNavigation() {
    document.querySelector(".mf-mobile-menu")?.addEventListener("click", (event) => {
      const open = event.currentTarget.getAttribute("aria-expanded") !== "true";
      setMobileOpen(open);
      if (open) document.querySelector(".mf-nav-item.active")?.focus();
    });
    document.querySelector(".mf-sidebar-scrim")?.addEventListener("click", () => {
      setMobileOpen(false);
      document.querySelector(".mf-mobile-menu")?.focus();
    });
    window.addEventListener("resize", () => setMobileOpen(false));
  }

  function bindShortcuts() {
    const dialog = document.querySelector("#mf-command-dialog");
    const show = () => {
      if (dialog && !dialog.open) dialog.showModal();
    };

    document.querySelector("#mf-command-button")?.addEventListener("click", show);
    dialog?.addEventListener("click", (event) => {
      const option = event.target.closest("[data-command-view]");
      if (option) {
        dialog.close();
        activateView(option.dataset.commandView);
      } else if (event.target.closest("[data-command-close]")) {
        dialog.close();
      }
    });

    document.addEventListener("keydown", (event) => {
      const modifier = event.ctrlKey || event.metaKey;
      if (modifier && event.key.toLowerCase() === "k") {
        event.preventDefault();
        show();
      }
      if (event.key === "Escape") setMobileOpen(false);
      if (
        event.altKey &&
        /^[1-9]$/.test(event.key) &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
      ) {
        const definition = views[Number(event.key) - 1];
        if (definition) activateView(definition.id);
      }
    });
  }

  window.MindFrontierShell = {activateView};

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildShell, {once: true});
  } else {
    buildShell();
  }
})();
