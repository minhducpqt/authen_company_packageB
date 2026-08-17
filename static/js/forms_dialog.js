/**
 * Custom alert / confirm for Biểu mẫu module (replaces native browser dialogs).
 */
(function (global) {
  const root = document.getElementById('fmDialogRoot');
  if (!root) {
    global.FmDialog = {
      alert: (opts) => Promise.resolve(window.alert(typeof opts === 'string' ? opts : opts?.message)),
      confirm: (opts) => Promise.resolve(window.confirm(typeof opts === 'string' ? opts : opts?.message)),
      confirmTyped: (opts) => Promise.resolve(window.confirm(typeof opts === 'string' ? opts : opts?.message)),
    };
    return;
  }

  const backdrop = root.querySelector('[data-fm-dialog-backdrop]');
  const titleEl = root.querySelector('[data-fm-dialog-title]');
  const messageEl = root.querySelector('[data-fm-dialog-message]');
  const iconEl = root.querySelector('[data-fm-dialog-icon]');
  const btnOk = root.querySelector('[data-fm-dialog-ok]');
  const btnCancel = root.querySelector('[data-fm-dialog-cancel]');
  const btnClose = root.querySelector('[data-fm-dialog-close]');
  const typedWrap = root.querySelector('[data-fm-dialog-typed]');
  const typedHintEl = root.querySelector('[data-fm-dialog-typed-hint]');
  const typedInput = root.querySelector('[data-fm-dialog-typed-input]');
  const typedErrEl = root.querySelector('[data-fm-dialog-typed-err]');

  let resolveFn = null;
  let mode = 'alert';
  let requiredPhrase = '';

  const ICONS = {
    info: 'ri-information-line',
    warn: 'ri-error-warning-line',
    danger: 'ri-close-circle-line',
    success: 'ri-checkbox-circle-line',
  };

  const DEFAULT_TYPED_PHRASE = 'tôi xác nhận';

  function normalizeOpts(opts, fallbackTitle) {
    if (typeof opts === 'string') {
      return { title: fallbackTitle, message: opts };
    }
    return {
      title: opts?.title || fallbackTitle,
      message: opts?.message || '',
      sub: opts?.sub || '',
      variant: opts?.variant || 'info',
      okText: opts?.okText || 'OK',
      cancelText: opts?.cancelText || 'Huỷ',
      requiredPhrase: opts?.requiredPhrase || DEFAULT_TYPED_PHRASE,
    };
  }

  function normPhrase(s) {
    return (s || '').trim().toLowerCase().replace(/\s+/g, ' ');
  }

  function phraseMatchesInput(inputVal, phrase) {
    return normPhrase(inputVal) === normPhrase(phrase);
  }

  function setOkEnabled(enabled) {
    btnOk.disabled = !enabled;
    btnOk.setAttribute('aria-disabled', enabled ? 'false' : 'true');
    btnOk.classList.toggle('is-disabled', !enabled);
  }

  function setVariant(variant) {
    iconEl.className = 'fm-dialog-icon fm-dialog-icon--' + (variant || 'info');
    const ico = ICONS[variant] || ICONS.info;
    iconEl.innerHTML = '<i class="' + ico + '" aria-hidden="true"></i>';
    btnOk.classList.remove('fm-dialog-btn--primary', 'fm-dialog-btn--warn', 'fm-dialog-btn--danger');
    if (variant === 'warn') btnOk.classList.add('fm-dialog-btn--warn');
    else if (variant === 'danger') btnOk.classList.add('fm-dialog-btn--danger');
    else btnOk.classList.add('fm-dialog-btn--primary');
  }

  function resetTypedSection() {
    requiredPhrase = '';
    if (!typedWrap) return;
    typedWrap.hidden = true;
    if (typedInput) typedInput.value = '';
    if (typedErrEl) {
      typedErrEl.textContent = '';
      typedErrEl.style.display = 'none';
    }
    if (typedHintEl) typedHintEl.innerHTML = '';
  }

  function syncTypedOkButton() {
    if (mode !== 'confirmTyped') return;
    const matched = phraseMatchesInput(typedInput?.value, requiredPhrase);
    setOkEnabled(matched);
    if (typedErrEl) {
      typedErrEl.textContent = '';
      typedErrEl.style.display = 'none';
    }
  }

  function openDialog() {
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    document.body.classList.add('fm-dialog-open');
  }

  function closeDialog(result) {
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('fm-dialog-open');
    setOkEnabled(true);
    resetTypedSection();
    const r = resolveFn;
    resolveFn = null;
    mode = 'alert';
    if (typeof r === 'function') r(result);
  }

  function showAlert(opts) {
    const o = normalizeOpts(opts, 'Thông báo');
    mode = 'alert';
    titleEl.textContent = o.title;
    messageEl.textContent = o.message;
    setVariant(o.variant);
    btnOk.textContent = o.okText;
    btnCancel.hidden = true;
    resetTypedSection();
    openDialog();
    setTimeout(() => btnOk.focus(), 30);
    return new Promise((resolve) => {
      resolveFn = () => resolve(undefined);
    });
  }

  function showConfirm(opts) {
    const o = normalizeOpts(opts, 'Xác nhận');
    mode = 'confirm';
    titleEl.textContent = o.title;
    messageEl.textContent = o.message;
    setVariant(o.variant || 'warn');
    btnOk.textContent = o.okText || 'Xác nhận';
    btnCancel.textContent = o.cancelText;
    btnCancel.hidden = false;
    setOkEnabled(true);
    resetTypedSection();
    openDialog();
    setTimeout(() => btnOk.focus(), 30);
    return new Promise((resolve) => {
      resolveFn = (val) => resolve(!!val);
    });
  }

  function showConfirmTyped(opts) {
    const o = normalizeOpts(opts, 'Xác nhận');
    mode = 'confirmTyped';
    requiredPhrase = o.requiredPhrase || DEFAULT_TYPED_PHRASE;
    titleEl.textContent = o.title;
    messageEl.textContent = o.message;
    setVariant(o.variant || 'warn');
    btnOk.textContent = o.okText || 'Tôi xác nhận';
    btnCancel.textContent = o.cancelText;
    btnCancel.hidden = false;
    if (typedWrap) typedWrap.hidden = false;
    const sub = o.sub ? o.sub + ' ' : '';
    if (typedHintEl) {
      typedHintEl.innerHTML =
        sub +
        'Nhập chính xác <strong>' +
        requiredPhrase +
        '</strong> để bật nút <strong>Tôi xác nhận</strong>.';
    }
    if (typedInput) {
      typedInput.value = '';
      typedInput.placeholder = requiredPhrase;
    }
    if (typedErrEl) {
      typedErrEl.textContent = '';
      typedErrEl.style.display = 'none';
    }
    setOkEnabled(false);
    openDialog();
    syncTypedOkButton();
    setTimeout(() => typedInput?.focus(), 30);
    return new Promise((resolve) => {
      resolveFn = (val) => resolve(!!val);
    });
  }

  function onOk() {
    if (mode === 'confirmTyped') {
      if (btnOk.disabled || !phraseMatchesInput(typedInput?.value, requiredPhrase)) {
        if (typedErrEl) {
          typedErrEl.textContent = 'Bạn phải nhập đúng: ' + requiredPhrase;
          typedErrEl.style.display = 'block';
        }
        typedInput?.focus();
        setOkEnabled(false);
        return;
      }
    }
    closeDialog(mode === 'confirm' || mode === 'confirmTyped');
  }

  function onCancel() {
    closeDialog(false);
  }

  btnOk.addEventListener('click', onOk);
  btnCancel.addEventListener('click', onCancel);
  btnClose.addEventListener('click', onCancel);
  backdrop.addEventListener('click', onCancel);
  typedInput?.addEventListener('input', syncTypedOkButton);
  typedInput?.addEventListener('keyup', syncTypedOkButton);
  typedInput?.addEventListener('paste', () => setTimeout(syncTypedOkButton, 0));
  typedInput?.addEventListener('compositionend', syncTypedOkButton);

  document.addEventListener('keydown', (e) => {
    if (!root.classList.contains('is-open')) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    } else if (e.key === 'Enter') {
      if (mode === 'alert') {
        e.preventDefault();
        onOk();
      } else if (mode === 'confirmTyped' && !btnOk.disabled) {
        e.preventDefault();
        onOk();
      }
    }
  });

  global.FmDialog = {
    alert: showAlert,
    confirm: showConfirm,
    confirmTyped: showConfirmTyped,
  };
})(window);
