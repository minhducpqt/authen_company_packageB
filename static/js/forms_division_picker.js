/**
 * Searchable province / commune picker for Biểu mẫu module (pattern from Service C register).
 */
(function (global) {
  const MODAL_ID = 'fmDivPickModal';
  let modalEl = null;
  let titleEl = null;
  let searchEl = null;
  let listEl = null;
  let closeEl = null;
  let backdropEl = null;
  let currentItems = [];
  let currentOnSelect = null;
  let escHandler = null;

  function normVI(s) {
    const str = String(s || '').toLowerCase();
    return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
  }

  function escHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function ensureModal() {
    if (modalEl) return;
    modalEl = document.getElementById(MODAL_ID);
    if (!modalEl) return;
    titleEl = modalEl.querySelector('[data-fm-div-pick-title]');
    searchEl = modalEl.querySelector('[data-fm-div-pick-search]');
    listEl = modalEl.querySelector('[data-fm-div-pick-list]');
    closeEl = modalEl.querySelector('[data-fm-div-pick-close]');
    backdropEl = modalEl.querySelector('[data-fm-div-pick-backdrop]');

    closeEl?.addEventListener('click', closeModal);
    backdropEl?.addEventListener('click', closeModal);
    searchEl?.addEventListener('input', applyFilter);
    searchEl?.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeModal();
      }
    });
  }

  function openModal() {
    ensureModal();
    if (!modalEl) return;
    modalEl.classList.add('is-open');
    modalEl.setAttribute('aria-hidden', 'false');
    document.body.classList.add('fm-div-pick-open');
    escHandler = (e) => {
      if (e.key === 'Escape') closeModal();
    };
    document.addEventListener('keydown', escHandler);
    setTimeout(() => searchEl?.focus(), 30);
  }

  function closeModal() {
    if (!modalEl) return;
    modalEl.classList.remove('is-open');
    modalEl.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('fm-div-pick-open');
    if (escHandler) {
      document.removeEventListener('keydown', escHandler);
      escHandler = null;
    }
    currentOnSelect = null;
  }

  function renderList(items) {
    if (!listEl) return;
    if (!items || !items.length) {
      listEl.innerHTML = '<div class="fm-div-pick-empty">Không tìm thấy kết quả.</div>';
      return;
    }
    listEl.innerHTML = items
      .map((it) => {
        const code = String(it.code ?? '');
        const name = String(it.label || it.name || '');
        return (
          '<button type="button" class="fm-div-pick-item" data-code="' +
          escHtml(code) +
          '" data-name="' +
          escHtml(name) +
          '">' +
          '<span class="n">' +
          escHtml(name) +
          '</span>' +
          (code ? '<span class="c">' + escHtml(code) + '</span>' : '') +
          '</button>'
        );
      })
      .join('');

    listEl.querySelectorAll('.fm-div-pick-item').forEach((node) => {
      node.addEventListener('click', () => {
        const code = node.getAttribute('data-code') || '';
        const name = node.getAttribute('data-name') || '';
        const cb = currentOnSelect;
        closeModal();
        if (typeof cb === 'function') cb({ code, name });
      });
    });
  }

  function applyFilter() {
    const q = normVI(searchEl?.value || '');
    if (!q) {
      renderList(currentItems);
      return;
    }
    const filtered = currentItems.filter((it) => {
      const label = it.label || it.name || '';
      return normVI(label).includes(q) || String(it.code || '').includes(q);
    });
    renderList(filtered);
  }

  function openPicker(title, items, onSelect) {
    ensureModal();
    if (!modalEl) return;
    currentItems = items || [];
    currentOnSelect = onSelect;
    if (titleEl) titleEl.textContent = title || 'Chọn';
    if (searchEl) searchEl.value = '';
    renderList(currentItems);
    openModal();
  }

  function setBtnLabel(btn, textEl, text, placeholder) {
    if (!textEl) return;
    if (!text) {
      textEl.textContent = placeholder;
      textEl.classList.add('is-placeholder');
      btn?.classList.remove('has-value');
    } else {
      textEl.textContent = text;
      textEl.classList.remove('is-placeholder');
      btn?.classList.add('has-value');
    }
  }

  function normalizeProvince(p) {
    const name = p.name_with_type || p.name || String(p.code || '');
    return { code: String(p.code), name, label: name, norm: normVI(name) };
  }

  function normalizeCommune(w) {
    const name = w.name_with_type || w.name || String(w.code || '');
    return { code: String(w.code), name, label: name, norm: normVI(name) };
  }

  /**
   * @param {object} opts
   * @param {string} opts.rootId - id of .fm-div-picker root
   * @param {Array} opts.provinces
   * @param {string} [opts.communesUrl='/bieu-mau/api/communes']
   * @param {string} [opts.initialProvinceCode]
   * @param {string} [opts.initialWardCode]
   * @param {string} [opts.initialWardName] - label when ward not in loaded list
   * @param {Function} [opts.onChange]
   */
  function mount(opts) {
    const root = document.getElementById(opts.rootId);
    if (!root) return null;

    const provinceBtn = root.querySelector('[data-role="province-btn"]');
    const wardBtn = root.querySelector('[data-role="ward-btn"]');
    const provinceText = root.querySelector('[data-role="province-text"]');
    const wardText = root.querySelector('[data-role="ward-text"]');
    const provinceCodeEl = root.querySelector('[data-role="province-code"]');
    const wardCodeEl = root.querySelector('[data-role="ward-code"]');

    const provinces = (opts.provinces || []).map(normalizeProvince);
    let wards = [];
    let provinceCode = String(opts.initialProvinceCode || '');
    let wardCode = String(opts.initialWardCode || '');

    const communesUrl = opts.communesUrl || '/bieu-mau/api/communes';

    function emitChange() {
      if (typeof opts.onChange === 'function') {
        opts.onChange({
          provinceCode: provinceCodeEl?.value || '',
          wardCode: wardCodeEl?.value || '',
          provinceName: provinceText?.classList.contains('is-placeholder') ? '' : provinceText?.textContent || '',
          wardName: wardText?.classList.contains('is-placeholder') ? '' : wardText?.textContent || '',
        });
      }
    }

    function resetWard() {
      wards = [];
      wardCode = '';
      if (wardCodeEl) wardCodeEl.value = '';
      setBtnLabel(wardBtn, wardText, '', opts.wardPlaceholder || 'Chọn Xã/Phường');
      if (wardBtn) wardBtn.disabled = true;
    }

    function setProvince(code, name) {
      provinceCode = String(code || '');
      if (provinceCodeEl) provinceCodeEl.value = provinceCode;
      setBtnLabel(provinceBtn, provinceText, name || '', opts.provincePlaceholder || 'Chọn Tỉnh/Thành');
      resetWard();
      if (provinceCode) {
        if (wardBtn) wardBtn.disabled = false;
        loadWards(provinceCode).then(() => emitChange());
      } else {
        emitChange();
      }
    }

    function setWard(code, name) {
      wardCode = String(code || '');
      if (wardCodeEl) wardCodeEl.value = wardCode;
      setBtnLabel(wardBtn, wardText, name || '', opts.wardPlaceholder || 'Chọn Xã/Phường');
      emitChange();
    }

    async function loadWards(pc) {
      if (!pc) {
        wards = [];
        return wards;
      }
      try {
        const r = await fetch(communesUrl + '?province_code=' + encodeURIComponent(pc));
        const data = await r.json();
        wards = (data.items || []).map(normalizeCommune);
      } catch (_e) {
        wards = [];
      }
      return wards;
    }

    provinceBtn?.addEventListener('click', () => {
      openPicker(opts.provincePlaceholder || 'Chọn Tỉnh/Thành', provinces, ({ code, name }) => {
        setProvince(code, name);
      });
    });

    wardBtn?.addEventListener('click', async () => {
      if (!provinceCode) return;
      if (!wards.length) await loadWards(provinceCode);
      openPicker(opts.wardPlaceholder || 'Chọn Xã/Phường', wards, ({ code, name }) => {
        setWard(code, name);
      });
    });

    if (provinceCode) {
      const p = provinces.find((x) => String(x.code) === provinceCode);
      setBtnLabel(provinceBtn, provinceText, p?.label || '', opts.provincePlaceholder || 'Chọn Tỉnh/Thành');
      if (wardBtn) wardBtn.disabled = false;
      loadWards(provinceCode).then(() => {
        if (wardCode) {
          const w = wards.find((x) => String(x.code) === wardCode);
          if (w) setWard(w.code, w.label);
          else if (opts.initialWardName) setWard(wardCode, opts.initialWardName);
          else if (wardCodeEl) wardCodeEl.value = wardCode;
        }
        emitChange();
      });
    } else {
      resetWard();
      setBtnLabel(provinceBtn, provinceText, '', opts.provincePlaceholder || 'Chọn Tỉnh/Thành');
    }

    return {
      getWardCode: () => wardCodeEl?.value || '',
      setProvince,
      setWard,
      loadWards,
    };
  }

  global.FmDivisionPicker = { mount, openPicker, normVI };
})(window);
