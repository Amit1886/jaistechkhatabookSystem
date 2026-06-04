(function () {
  function onReady(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  onReady(function () {
    const modalEl = document.getElementById("kpConfirmModal");
    if (!modalEl || !window.bootstrap) return;

    const modal = new bootstrap.Modal(modalEl);
    const titleEl = modalEl.querySelector("[data-confirm-title]");
    const bodyEl = modalEl.querySelector("[data-confirm-body]");
    const confirmBtn = modalEl.querySelector("[data-confirm-ok]");

    let pendingForm = null;

    function openForForm(form) {
      pendingForm = form;
      const title = form.getAttribute("data-confirm-title") || "Confirm";
      const message = form.getAttribute("data-confirm-message") || "Are you sure you want to continue?";
      const okText = form.getAttribute("data-confirm-ok-text") || "Yes, Continue";

      if (titleEl) titleEl.textContent = title;
      if (bodyEl) bodyEl.textContent = message;
      if (confirmBtn) confirmBtn.textContent = okText;

      modal.show();
    }

    document.addEventListener("submit", function (e) {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (!form.hasAttribute("data-confirm")) return;

      // Allow programmatic bypass
      if (form.__kpConfirmBypass) return;

      e.preventDefault();
      openForForm(form);
    });

    if (confirmBtn) {
      confirmBtn.addEventListener("click", function () {
        if (!pendingForm) return;
        pendingForm.__kpConfirmBypass = true;
        pendingForm.submit();
      });
    }
  });
})();

