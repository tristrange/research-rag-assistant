(() => {
  const modes = ["auto", "light", "dark"];
  let preference = "auto";
  try {
    const saved = localStorage.getItem("research-rag-theme");
    if (modes.includes(saved)) preference = saved;
  } catch {}

  const system = matchMedia("(prefers-color-scheme: dark)");
  function applyTheme() {
    document.documentElement.dataset.theme = preference === "auto"
      ? (system.matches ? "dark" : "light") : preference;
  }
  applyTheme();
  system.addEventListener("change", applyTheme);

  document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("theme-select");
    if (!selector) return;
    selector.value = preference;
    selector.addEventListener("change", () => {
      if (!modes.includes(selector.value)) return;
      preference = selector.value;
      applyTheme();
      try { localStorage.setItem("research-rag-theme", preference); } catch {}
    });
  });
})();
