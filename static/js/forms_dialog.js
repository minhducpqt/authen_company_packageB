/**
 * Custom alert / confirm for Biểu mẫu module (replaces native browser dialogs).
 */
(function (global) {
  const root = document.getElementById('fmDialogRoot');
  if (!root) {
    global.FmDialog = {
      alert: (opts) => Promise.resolve(window.alert(typeof opts === 'string' ? opts : opts?.message)),
      confirm: (opts) => Promise.resolve(window.confirm(typeof opts === 'string' ? opts : opts?.message)),
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

  let resolveFn = null;
  let mode = 'alert';

  const ICONS = {
    info: 'ri-information-line',
    warn: 'ri-error-warning-line',
    danger: 'ri-close-circle-line',
    success: 'ri-checkbox-circle-line',
  };

  function normalizeOpts(opts, fallbackTitle) {
    if (typeof opts === 'string') {
      return { title: fallbackTitle, message: opts };
    }
    return {
      title: opts?.title || fallbackTitle,
      message: opts?.message || '',
      variant: opts?.variant || 'info',
      okText: opts?.okText || 'OK',
      cancelText: opts?.cancelText || 'Huỷ',
    };
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

  function openDialog() {
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    document.body.classList.add('fm-dialog-open');
  }

  function closeDialog(result) {
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('fm-dialog-open');
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
    openDialog();
    setTimeout(() => btnOk.focus(), 30);
    return new Promise((resolve) => {
      resolveFn = (val) => resolve(!!val);
    });
  }

  function onOk() {
    closeDialog(mode === 'confirm');
  }

  function onCancel() {
    closeDialog(false);
  }

  btnOk.addEventListener('click', onOk);
  btnCancel.addEventListener('click', onCancel);
  btnClose.addEventListener('click', onCancel);
  backdrop.addEventListener('click', onCancel);

  document.addEventListener('keydown', (e) => {
    if (!root.classList.contains('is-open')) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    } else if (e.key === 'Enter' && mode === 'alert') {
      e.preventDefault();
      onOk();
    }
  });

  global.FmDialog = { alert: showAlert, confirm: showConfirm };
})(window);
