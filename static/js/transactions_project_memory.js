(function (global) {
  const KEYS = {
    CODE: "transactions:last_project_code",
    ID: "transactions:last_project_id",
    STATUS: "transactions:last_project_status",
  };

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

  function rememberByCode(projectSelect, statusSelect) {
    if (!projectSelect) return;
    const code = (projectSelect.value || "").trim();
    const st = (statusSelect?.value || "ACTIVE").trim();
    safeSet(KEYS.CODE, code);
    safeSet(KEYS.STATUS, st);
    safeSet(KEYS.ID, "");
  }

  function rememberById(projectSelect, statusSelect) {
    if (!projectSelect) return;
    const id = (projectSelect.value || "").trim();
    const st = (statusSelect?.value || "ACTIVE").trim();
    const opt = projectSelect.selectedOptions?.[0];
    const code = (opt?.dataset?.projectCode || "").trim();
    safeSet(KEYS.ID, id);
    safeSet(KEYS.STATUS, st);
    if (code) safeSet(KEYS.CODE, code);
  }

  function restoreStatusFilter(statusSelect, skipIfInit) {
    if (!statusSelect || skipIfInit) return;
    const st = safeGet(KEYS.STATUS);
    if (st && statusSelect.querySelector(`option[value="${CSS.escape(st)}"]`)) {
      statusSelect.value = st;
    }
  }

  function pickProjectCode(projectSelect, prev, initCode) {
    if (!projectSelect) return "";
    if (prev && projectSelect.querySelector(`option[value="${CSS.escape(prev)}"]`)) {
      return prev;
    }
    const fromInit = (initCode || "").trim();
    if (fromInit && projectSelect.querySelector(`option[value="${CSS.escape(fromInit)}"]`)) {
      return fromInit;
    }
    const saved = safeGet(KEYS.CODE);
    if (saved && projectSelect.querySelector(`option[value="${CSS.escape(saved)}"]`)) {
      return saved;
    }
    if (saved) safeSet(KEYS.CODE, "");
    return "";
  }

  function pickProjectId(projectSelect, prev, initId) {
    if (!projectSelect) return "";
    if (prev && projectSelect.querySelector(`option[value="${CSS.escape(prev)}"]`)) {
      return prev;
    }
    const fromInit = (initId || "").trim();
    if (fromInit && projectSelect.querySelector(`option[value="${CSS.escape(fromInit)}"]`)) {
      return fromInit;
    }
    const savedId = safeGet(KEYS.ID);
    if (savedId && projectSelect.querySelector(`option[value="${CSS.escape(savedId)}"]`)) {
      return savedId;
    }
    const savedCode = safeGet(KEYS.CODE);
    if (savedCode) {
      const opt = Array.from(projectSelect.options).find(
        (o) => (o.dataset?.projectCode || "").trim() === savedCode
      );
      if (opt) return opt.value;
    }
    if (savedId) safeSet(KEYS.ID, "");
    return "";
  }

  global.TxProjectMemory = {
    KEYS,
    rememberByCode,
    rememberById,
    restoreStatusFilter,
    pickProjectCode,
    pickProjectId,
  };
})(window);
