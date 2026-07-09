/* ==========================================================================
   SOC-PYME · main.js — interacciones públicas y utilidades compartidas
   ========================================================================== */
(function () {
  "use strict";

  // --- Animaciones "reveal" (IntersectionObserver) ------------------------
  const revealEls = document.querySelectorAll(".reveal");
  if (revealEls.length) {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e, i) => {
          if (e.isIntersecting) {
            setTimeout(() => e.target.classList.add("visible"), i * 100);
            obs.unobserve(e.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    revealEls.forEach((el) => obs.observe(el));
  }

  // --- Menú móvil ---------------------------------------------------------
  const navToggle = document.querySelector("[data-nav-toggle]");
  const navMenu = document.getElementById("nav-menu");
  if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => navMenu.classList.toggle("open"));
  }

  // --- Flash messages: cerrar y auto-descartar ----------------------------
  document.querySelectorAll(".flash").forEach((flash) => {
    const close = flash.querySelector(".flash-close");
    const dismiss = () => {
      flash.style.transition = "opacity .3s, transform .3s";
      flash.style.opacity = "0";
      flash.style.transform = "translateX(30px)";
      setTimeout(() => flash.remove(), 300);
    };
    if (close) close.addEventListener("click", dismiss);
    setTimeout(dismiss, 6000);
  });

  // --- Validación de formularios en cliente -------------------------------
  // Marca campos requeridos vacíos y valida contraseña en el registro.
  document.querySelectorAll("form[data-validate]").forEach((form) => {
    form.addEventListener("submit", (ev) => {
      let ok = true;

      form.querySelectorAll("[required]").forEach((input) => {
        const field = input.closest(".field");
        clearError(field);
        if (!input.value.trim()) {
          showError(field, "Este campo es obligatorio.");
          ok = false;
        }
      });

      // Email
      const email = form.querySelector('input[type="email"]');
      if (email && email.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
        showError(email.closest(".field"), "Email inválido.");
        ok = false;
      }

      // Contraseña (registro)
      const pw = form.querySelector('input[name="password"]');
      if (pw && form.dataset.validate === "register") {
        if (pw.value && !/^(?=.*[A-Za-z])(?=.*\d).{8,}$/.test(pw.value)) {
          showError(pw.closest(".field"), "Mínimo 8 caracteres, con una letra y un número.");
          ok = false;
        }
        const confirm = form.querySelector('input[name="confirm"]');
        if (confirm && confirm.value !== pw.value) {
          showError(confirm.closest(".field"), "Las contraseñas no coinciden.");
          ok = false;
        }
      }

      if (!ok) ev.preventDefault();
    });
  });

  function showError(field, msg) {
    if (!field) return;
    field.classList.add("has-error");
    let err = field.querySelector(".err.js-err");
    if (!err) {
      err = document.createElement("span");
      err.className = "err js-err";
      field.appendChild(err);
    }
    err.textContent = msg;
  }

  function clearError(field) {
    if (!field) return;
    field.classList.remove("has-error");
    const err = field.querySelector(".err.js-err");
    if (err) err.remove();
  }
})();
