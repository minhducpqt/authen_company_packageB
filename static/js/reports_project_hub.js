(function (global) {
  "use strict";

  var LS_KEY = "reports:last_project_code";

  function safeGet(key) {
    try {
      return (localStorage.getItem(key) || "").trim();
    } catch (e) {
      return "";
    }
  }

  function safeSet(key, value) {
    try {
      if (value) localStorage.setItem(key, value);
      else localStorage.removeItem(key);
    } catch (e) {}
  }

  function findProject(projects, code) {
    var c = (code || "").trim().toUpperCase();
    if (!c) return null;
    for (var i = 0; i < projects.length; i++) {
      var p = projects[i];
      var pc = (p.project_code || p.code || "").trim().toUpperCase();
      if (pc === c) return p;
    }
    return null;
  }

  function isGroupMode(project) {
    return String(project.registration_mode || "NORMAL").toUpperCase() === "GROUP_AUCTION";
  }

  function applyLinks(root, project) {
    if (!root || !project) return;
    var pid = project.id || project.project_id;
    var code = project.project_code || project.code || "";
    var isGroup = isGroupMode(project);

    root.querySelectorAll("[data-hub-href]").forEach(function (el) {
      var tpl = el.getAttribute("data-hub-href") || "";
      var mode = (el.getAttribute("data-hub-mode") || "both").toLowerCase();
      var disabled =
        (mode === "normal" && isGroup) || (mode === "group" && !isGroup);

      if (disabled) {
        el.setAttribute("href", "#");
        el.classList.add("is-disabled");
        return;
      }

      el.classList.remove("is-disabled");
      el.setAttribute(
        "href",
        tpl
          .replace(/__PID__/g, encodeURIComponent(String(pid)))
          .replace(/__CODE__/g, encodeURIComponent(String(code)))
      );
    });
  }

  function renderHub(root, project) {
    var emptyEl = root.querySelector("[data-hub-empty]");
    var panelEl = root.querySelector("[data-hub-panel]");
    var metaEl = root.querySelector("[data-hub-meta]");
    var badgeEl = root.querySelector("[data-hub-mode-badge]");
    var nameEl = root.querySelector("[data-hub-project-name]");
    var codeEl = root.querySelector("[data-hub-project-code]");
    var normalSec = root.querySelector("[data-hub-section-normal]");
    var groupSec = root.querySelector("[data-hub-section-group]");

    if (!project) {
      if (emptyEl) emptyEl.classList.remove("hidden");
      if (panelEl) panelEl.classList.add("hidden");
      if (metaEl) metaEl.classList.add("hidden");
      root.querySelectorAll("[data-hub-project-row]").forEach(function (row) {
        row.classList.remove("is-selected");
      });
      return;
    }

    if (emptyEl) emptyEl.classList.add("hidden");
    if (panelEl) panelEl.classList.remove("hidden");
    if (metaEl) metaEl.classList.remove("hidden");

    var isGroup = isGroupMode(project);

    if (badgeEl) {
      badgeEl.textContent = isGroup ? "Đấu nhóm" : "Đấu lô";
      badgeEl.className =
        "rph-badge " + (isGroup ? "rph-badge-group" : "rph-badge-normal");
    }
    if (nameEl) nameEl.textContent = project.name || "";
    if (codeEl) codeEl.textContent = project.project_code || project.code || "";

    if (normalSec) normalSec.classList.toggle("hidden", isGroup);
    if (groupSec) groupSec.classList.toggle("hidden", !isGroup);

    applyLinks(root, project);

    var cur = (project.project_code || project.code || "").trim().toUpperCase();
    root.querySelectorAll("[data-hub-project-row]").forEach(function (row) {
      var rc = (row.getAttribute("data-project-code") || "").trim().toUpperCase();
      row.classList.toggle("is-selected", rc === cur);
    });
  }

  function pickInitialCode(projects, urlCode, initCode) {
    var fromUrl = (urlCode || "").trim().toUpperCase();
    if (fromUrl && findProject(projects, fromUrl)) return fromUrl;

    var fromInit = (initCode || "").trim().toUpperCase();
    if (fromInit && findProject(projects, fromInit)) return fromInit;

    var saved = safeGet(LS_KEY).toUpperCase();
    if (saved && findProject(projects, saved)) return saved;

    if (saved) safeSet(LS_KEY, "");
    if (projects.length === 1) {
      return (projects[0].project_code || projects[0].code || "").trim().toUpperCase();
    }
    return "";
  }

  function init(root) {
    if (!root) return;

    var projects = [];
    try {
      projects = JSON.parse(root.getAttribute("data-projects") || "[]");
    } catch (e) {
      projects = [];
    }

    var selectEl = root.querySelector("[data-hub-project-select]");
    var urlCode = root.getAttribute("data-url-project") || "";
    var initCode = root.getAttribute("data-init-project") || "";

    var initialCode = pickInitialCode(projects, urlCode, initCode);
    if (selectEl && initialCode) selectEl.value = initialCode;

    function onSelect(code) {
      var p = findProject(projects, code);
      if (p) safeSet(LS_KEY, (p.project_code || p.code || "").trim());
      else safeSet(LS_KEY, "");
      renderHub(root, p);
    }

    if (selectEl) {
      selectEl.addEventListener("change", function () {
        onSelect(selectEl.value);
      });
    }

    root.querySelectorAll("[data-hub-pick-project]").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        var code = btn.getAttribute("data-hub-pick-project") || "";
        if (selectEl) selectEl.value = code;
        onSelect(code);
      });
    });

    onSelect(selectEl ? selectEl.value : initialCode);
  }

  global.ReportsProjectHub = { init: init, LS_KEY: LS_KEY };
})(window);
