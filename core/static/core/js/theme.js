// Theme toggler. The current preference comes from a cookie set by the
// server-side ToggleThemeView, but we also set the data-theme attribute
// optimistically so the UI updates without a full page reload.

(function () {
  "use strict";

  const COOKIE = "controle_interno_theme";

  function readCookie(name) {
    const match = document.cookie.match(
      new RegExp("(?:^|; )" + name.replace(/[.$?*|{}()[\]\\\/+^]/g, "\\$&") + "=([^;]*)")
    );
    return match ? decodeURIComponent(match[1]) : null;
  }

  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }

  function highlight(theme) {
    document.querySelectorAll(".theme-toggle button[data-theme]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.theme === theme);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const initial = readCookie(COOKIE) || "auto";
    applyTheme(initial);
    highlight(initial);

    document.querySelectorAll(".theme-toggle button[data-theme]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const theme = btn.dataset.theme;
        applyTheme(theme);
        highlight(theme);

        // Persist via the server so the choice survives reloads/logouts.
        const form = btn.closest("form");
        if (form) {
          const themeInput = form.querySelector('input[name="theme"]');
          if (themeInput) {
            themeInput.value = theme;
          }
          form.submit();
        }
      });
    });
  });
})();
