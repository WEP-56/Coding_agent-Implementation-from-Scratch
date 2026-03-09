(() => {
  const storageKey = "codinggirl-docs-theme";

  function resolveInitialTheme() {
    const stored = window.localStorage.getItem(storageKey);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;

    const nextLabel =
      theme === "dark"
        ? "切换到浅色 / Switch to light"
        : "切换到深色 / Switch to dark";

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(theme === "dark"));
      const label = button.querySelector("[data-theme-label]");
      if (label) {
        label.textContent = nextLabel;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(resolveInitialTheme());

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const current = document.documentElement.dataset.theme === "dark"
          ? "dark"
          : "light";
        const next = current === "dark" ? "light" : "dark";
        window.localStorage.setItem(storageKey, next);
        applyTheme(next);
      });
    });
  });
})();
