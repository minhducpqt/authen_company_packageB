(function (global) {
  "use strict";

  var KIND = {
    NORMAL: "NORMAL",
    GROUP_BLIND: "GROUP_BLIND",
    GROUP_PRE_SESSION: "GROUP_PRE_SESSION",
  };

  var STYLES = {
    NORMAL: {
      label: "Đấu thường",
      lineCls: "project-type-line--normal",
    },
    GROUP_BLIND: {
      label: "Đấu nhóm (khách chọn lô trong phiên)",
      lineCls: "project-type-line--group-in-session",
    },
    GROUP_PRE_SESSION: {
      label: "Đấu nhóm (khách chọn lô trước phiên)",
      lineCls: "project-type-line--group-pre-session",
    },
  };

  var EXPLICIT_SELECTORS = [
    "[data-project-type-badge]",
    "[data-hub-project-select]",
    "#projectSelect",
    "#projectSelectLocal",
    "#projectSelectV2",
    "#laProjectSelect",
    "#fProject",
    "#fProjectShared",
    "#projectSel",
    "#csProject",
    "#project_id",
    'select[name="project"]',
    'select[name="project_id"]',
    'select[name="project_code"]',
  ];

  var EXCLUDE_IDS = {
    projectstatusselect: true,
  };

  var _metaCache = Object.create(null);
  var _fetchInflight = Object.create(null);

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeKind(raw) {
    var k = String(raw || "").trim().toUpperCase();
    if (k === KIND.GROUP_PRE_SESSION || k === KIND.GROUP_BLIND || k === KIND.NORMAL) {
      return k;
    }
    return KIND.NORMAL;
  }

  function resolveKind(registrationMode, lotPolicy) {
    var mode = String(registrationMode || "NORMAL").trim().toUpperCase();
    if (mode !== "GROUP_AUCTION") return KIND.NORMAL;
    var policy = String(lotPolicy || "IN_SESSION_R1").trim().toUpperCase();
    return policy === "PRE_SESSION" ? KIND.GROUP_PRE_SESSION : KIND.GROUP_BLIND;
  }

  function styleForKind(kind) {
    return STYLES[normalizeKind(kind)] || STYLES.NORMAL;
  }

  function isProjectSelect(el) {
    if (!el || el.tagName !== "SELECT") return false;
    if (el.hasAttribute("data-project-type-skip")) return false;
    if (el.hasAttribute("data-project-type-badge")) return true;
    if (el.matches("[data-hub-project-select]")) return true;

    var id = (el.id || "").trim().toLowerCase();
    var name = (el.name || "").trim().toLowerCase();
    if (id && EXCLUDE_IDS[id]) return false;

    if (name === "project" || name === "project_id" || name === "project_code") {
      return true;
    }
    if (
      id === "projectselect" ||
      id === "projectselectlocal" ||
      id === "projectselectv2" ||
      id === "laprojectselect" ||
      id === "fproject" ||
      id === "fprojectshared" ||
      id === "projectsel" ||
      id === "csproject" ||
      id === "project_id"
    ) {
      return true;
    }
    if (/projectselect/i.test(id)) return true;
    if (/^project(_?sel)?$/i.test(id)) return true;
    return false;
  }

  function discoverSelects(scope) {
    scope = scope && scope.querySelectorAll ? scope : document;
    var seen = typeof WeakSet !== "undefined" ? new WeakSet() : null;
    var out = [];

    function push(el) {
      if (!el || !isProjectSelect(el)) return;
      if (seen) {
        if (seen.has(el)) return;
        seen.add(el);
      }
      out.push(el);
    }

    EXPLICIT_SELECTORS.forEach(function (sel) {
      try {
        scope.querySelectorAll(sel).forEach(push);
      } catch (e) {}
    });

    scope.querySelectorAll("select").forEach(push);
    return out;
  }

  function readMetaFromOption(opt) {
    if (!opt || !opt.dataset) return null;
    var kind = opt.dataset.auctionTypeKind;
    if (kind) {
      return {
        auction_type_kind: normalizeKind(kind),
        auction_type_label:
          opt.dataset.auctionTypeLabel || styleForKind(kind).label,
        registration_mode: opt.dataset.registrationMode || "",
        lot_policy: opt.dataset.lotPolicy || "",
      };
    }
    if (opt.dataset.registrationMode) {
      var resolved = resolveKind(opt.dataset.registrationMode, opt.dataset.lotPolicy);
      return {
        auction_type_kind: resolved,
        auction_type_label: styleForKind(resolved).label,
        registration_mode: opt.dataset.registrationMode,
        lot_policy: opt.dataset.lotPolicy || "",
      };
    }
    return null;
  }

  function applyOptionMeta(opt, project) {
    if (!opt || !project) return;
    var kind =
      project.auction_type_kind ||
      resolveKind(project.registration_mode, project.lot_policy);
    var style = styleForKind(kind);
    opt.dataset.registrationMode = project.registration_mode || "NORMAL";
    opt.dataset.lotPolicy = project.lot_policy || "";
    opt.dataset.auctionTypeKind = kind;
    opt.dataset.auctionTypeLabel = project.auction_type_label || style.label;
    var code = (project.project_code || project.code || "").trim();
    if (code) opt.dataset.projectCode = code;
  }

  function inferValueMode(selectEl) {
    if (selectEl.dataset.projectTypeValueMode) {
      return selectEl.dataset.projectTypeValueMode;
    }
    var opt = selectEl.selectedOptions && selectEl.selectedOptions[0];
    if (opt && opt.dataset && opt.dataset.projectCode) return "id";
    var name = (selectEl.name || "").toLowerCase();
    var id = (selectEl.id || "").toLowerCase();
    if (name === "project_id" || id === "project_id") return "id";
    return "code";
  }

  function cacheKeyForSelect(selectEl) {
    var opt = selectEl && selectEl.selectedOptions && selectEl.selectedOptions[0];
    if (!opt) return "";
    var code = (opt.dataset.projectCode || "").trim();
    var id = (opt.value || "").trim();
    if (inferValueMode(selectEl) === "id") {
      return id ? "id:" + id : code ? "code:" + code.toUpperCase() : "";
    }
    return code ? "code:" + code.toUpperCase() : id ? "id:" + id : "";
  }

  function fetchMeta(selectEl) {
    var opt = selectEl.selectedOptions && selectEl.selectedOptions[0];
    if (!opt || !opt.value) return Promise.resolve(null);

    var key = cacheKeyForSelect(selectEl);
    if (key && _metaCache[key]) return Promise.resolve(_metaCache[key]);
    if (key && _fetchInflight[key]) return _fetchInflight[key];

    var params = new URLSearchParams();
    var code = (opt.dataset.projectCode || "").trim();
    if (inferValueMode(selectEl) === "id") {
      params.set("project_id", opt.value);
      if (code) params.set("project_code", code);
    } else {
      var pc = code || (opt.value || "").trim();
      if (pc && !/^\d+$/.test(pc)) params.set("project_code", pc);
      else params.set("project_id", opt.value);
    }

    var p = fetch("/projects/api/auction-type?" + params.toString(), {
      credentials: "same-origin",
    })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (js) {
        if (js && js.auction_type_kind) {
          if (key) _metaCache[key] = js;
          applyOptionMeta(opt, js);
          return js;
        }
        return null;
      })
      .catch(function () {
        return null;
      })
      .finally(function () {
        if (key) delete _fetchInflight[key];
      });

    if (key) _fetchInflight[key] = p;
    return p;
  }

  function ensureFieldWrapper(selectEl) {
    if (!selectEl || selectEl.closest("[data-project-type-field]")) return;
    var parent = selectEl.parentElement;
    if (!parent || parent.closest(".rph-select-inner")) return;
    if (parent.querySelector(":scope > label") && parent.querySelector(":scope > select") === selectEl) {
      parent.setAttribute("data-project-type-field", "");
      parent.classList.add("min-w-0");
    }
  }

  function ensureHost(selectEl) {
    if (!selectEl) return null;
    if (selectEl._ptbHost && selectEl._ptbHost.isConnected) {
      return selectEl._ptbHost;
    }

    ensureFieldWrapper(selectEl);

    var host = null;
    var hubBar = selectEl.closest(".rph-select-bar");
    if (hubBar && hubBar.parentElement) {
      var head = hubBar.parentElement;
      host = head.querySelector(":scope > [data-project-type-badge-host]");
      if (!host) {
        host = document.createElement("div");
        host.className = "project-type-badge-wrap project-type-badge-wrap--full";
        host.setAttribute("data-project-type-badge-host", "");
        hubBar.insertAdjacentElement("afterend", host);
      }
    } else if (selectEl.closest(".rph-select-inner")) {
      var bar = selectEl.closest(".rph-select-bar");
      if (bar && bar.parentElement) {
        var wrap = bar.parentElement;
        host = wrap.querySelector(":scope > [data-project-type-badge-host]");
        if (!host) {
          host = document.createElement("div");
          host.className = "project-type-badge-wrap project-type-badge-wrap--full";
          host.setAttribute("data-project-type-badge-host", "");
          bar.insertAdjacentElement("afterend", host);
        }
      }
    } else {
      var field = selectEl.closest("[data-project-type-field]");
      var container = field || selectEl.parentElement;
      if (container) {
        host = container.querySelector("[data-project-type-badge-host]");
        if (!host) {
          host = document.createElement("div");
          host.className = "project-type-badge-wrap";
          host.setAttribute("data-project-type-badge-host", "");
          var after = selectEl;
          var next = selectEl.nextElementSibling;
          while (next && next.tagName === "INPUT" && next.type === "hidden") {
            after = next;
            next = next.nextElementSibling;
          }
          after.insertAdjacentElement("afterend", host);
        }
      }
    }

    if (host) selectEl._ptbHost = host;
    return host;
  }

  function renderHost(host, meta) {
    if (!host) return;
    if (!meta || !meta.auction_type_kind) {
      host.innerHTML = "";
      host.classList.add("is-empty");
      host.hidden = true;
      return;
    }

    host.hidden = false;
    host.classList.remove("is-empty");
    var kind = normalizeKind(meta.auction_type_kind);
    var style = styleForKind(kind);
    var label = meta.auction_type_label || style.label;
    var loading = !label || label === "…";

    host.innerHTML =
      '<div class="project-type-line ' +
      style.lineCls +
      (loading ? " is-loading" : "") +
      '" role="status" aria-live="polite">' +
      '<span class="project-type-line-dot" aria-hidden="true"></span>' +
      '<span class="project-type-line-label">' +
      escapeHtml(loading ? "Đang xác định loại dự án…" : label) +
      "</span></div>";
  }

  function syncSelect(selectEl) {
    if (!selectEl) return Promise.resolve();
    var host = ensureHost(selectEl);
    var opt = selectEl.selectedOptions && selectEl.selectedOptions[0];
    if (!opt || !opt.value) {
      renderHost(host, null);
      return Promise.resolve();
    }

    var meta = readMetaFromOption(opt);
    if (meta) {
      renderHost(host, meta);
      return Promise.resolve();
    }

    renderHost(host, { auction_type_kind: "NORMAL", auction_type_label: "…" });
    return fetchMeta(selectEl).then(function (remote) {
      renderHost(host, remote || null);
    });
  }

  function bindSelect(selectEl) {
    if (!selectEl || selectEl._ptbBound) return;
    selectEl._ptbBound = true;
    selectEl.setAttribute("data-project-type-badge", "1");
    ensureHost(selectEl);
    selectEl.addEventListener("change", function () {
      syncSelect(selectEl);
    });
    syncSelect(selectEl);
  }

  function initAll(root) {
    discoverSelects(root || document).forEach(bindSelect);
  }

  function resolveFromProject(project) {
    if (!project) return null;
    var kind =
      project.auction_type_kind ||
      resolveKind(project.registration_mode, project.lot_policy);
    var style = styleForKind(kind);
    return {
      registration_mode: project.registration_mode || "NORMAL",
      lot_policy: project.lot_policy || null,
      auction_type_kind: kind,
      auction_type_label: project.auction_type_label || style.label,
    };
  }

  function updateFromProject(selectEl, project) {
    if (!project) {
      renderHost(selectEl ? ensureHost(selectEl) : null, null);
      return;
    }
    var meta = resolveFromProject(project);
    var opt = selectEl && selectEl.selectedOptions && selectEl.selectedOptions[0];
    if (opt && meta) applyOptionMeta(opt, meta);
    renderHost(selectEl ? ensureHost(selectEl) : null, meta);
  }

  function createProjectOption(project, config) {
    config = config || {};
    var valueMode = config.valueMode || "code";
    var opt = document.createElement("option");
    var code = (project.project_code || project.code || "").trim();
    var name = (project.name || project.project_name || code).trim();
    if (!code && valueMode !== "id") return null;
    if (valueMode === "id") {
      if (project.id == null && project.project_id == null) return null;
      opt.value = String(project.id != null ? project.id : project.project_id);
      opt.dataset.projectCode = code;
    } else {
      opt.value = code;
    }
    var labelFn = config.labelFormat;
    opt.textContent = labelFn
      ? labelFn(code, name, project)
      : code + " — " + name;
    applyOptionMeta(opt, project);
    return opt;
  }

  function fillSelect(selectEl, projects, opts) {
    if (!selectEl) return;
    opts = opts || {};
    var placeholder = opts.placeholder;
    if (placeholder === undefined) placeholder = "Chọn dự án…";
    var valueMode = opts.valueMode || "code";
    if (valueMode === "id") {
      selectEl.dataset.projectTypeValueMode = "id";
    }
    selectEl.innerHTML = "";
    if (placeholder !== false && placeholder !== null && placeholder !== "") {
      var empty = document.createElement("option");
      empty.value = "";
      empty.textContent = placeholder;
      selectEl.appendChild(empty);
    }
    (projects || []).forEach(function (p) {
      var opt = createProjectOption(p, {
        valueMode: valueMode,
        labelFormat: opts.labelFormat,
      });
      if (opt) selectEl.appendChild(opt);
    });
    if (opts.selectedValue != null && opts.selectedValue !== "") {
      selectEl.value = String(opts.selectedValue);
    }
    syncSelect(selectEl);
  }

  global.ProjectTypeBadge = {
    KIND: KIND,
    initAll: initAll,
    discoverSelects: discoverSelects,
    bindSelect: bindSelect,
    syncSelect: syncSelect,
    applyOptionMeta: applyOptionMeta,
    createProjectOption: createProjectOption,
    fillSelect: fillSelect,
    resolveFromProject: resolveFromProject,
    updateFromProject: updateFromProject,
    resolveKind: resolveKind,
    styleForKind: styleForKind,
  };

  function boot() {
    initAll(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  // Các trang load option bằng fetch sau DOMContentLoaded
  global.addEventListener("load", function () {
    initAll(document);
  });
})(window);
