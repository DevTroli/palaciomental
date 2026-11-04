/* Pickr melhora o campo HEX; o formulário continua funcional sem JavaScript. */
(() => {
  const inputs = Array.from(document.querySelectorAll("[data-theme-color]"));
  const preview = document.querySelector("#identity-preview");
  if (!preview) return;
  const hex = /^#[0-9a-f]{6}$/i;
  const textOn = color => {
    const channels = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16) / 255)
      .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
    return channels.reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0) > .179 ? "#000000" : "#ffffff";
  };
  const sync = () => {
    const colors = {};
    inputs.forEach(input => { if (hex.test(input.value)) colors[input.dataset.themeColor] = input.value; });
    if (colors.primary) {
      const header = preview.querySelector(".identity-preview-header");
      header.style.background = colors.primary;
      header.style.color = textOn(colors.primary);
    }
    if (colors.background) preview.style.background = colors.background;
    const body = preview.querySelector(".identity-preview-body");
    if (colors.surface) {
      body.style.background = colors.surface;
      body.querySelectorAll("h3,p").forEach(el => { el.style.color = textOn(colors.surface); });
    }
    if (colors.accent) {
      const button = body.querySelector("button");
      button.style.background = colors.accent;
      button.style.color = textOn(colors.accent);
      button.style.borderColor = colors.secondary || colors.accent;
    }
  };
  inputs.forEach(input => {
    input.addEventListener("input", sync);
    if (!window.Pickr) return;
    const row = document.createElement("div");
    row.className = "identity-color-row";
    input.before(row);
    row.append(input);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "identity-color-trigger";
    button.setAttribute("aria-label", `Selecionar ${input.labels[0]?.textContent || "cor"}`);
    row.prepend(button);
    const picker = Pickr.create({
      el: button, useAsButton: true, theme: "nano", default: hex.test(input.value) ? input.value : "#6E4AA3",
      lockOpacity: true, defaultRepresentation: "HEX",
      components: {preview: true, hue: true, interaction: {hex: true, input: true, save: true, cancel: true}},
      i18n: {"ui:dialog": "Selecionar cor", "btn:toggle": button.getAttribute("aria-label"), "btn:save": "Aplicar", "btn:cancel": "Cancelar",
        "aria:palette": "Saturação e luminosidade", "aria:hue": "Tonalidade",
        "aria:input": "Valor da cor", "aria:btn:save": "Aplicar e fechar", "aria:btn:cancel": "Cancelar e fechar"}
    });
    const updateSwatch = () => { if (hex.test(input.value)) button.style.background = input.value; };
    picker.on("save", color => {
      if (color) input.value = color.toHEXA().toString().slice(0, 7).toUpperCase();
      input.dispatchEvent(new Event("input", {bubbles: true}));
      picker.hide();
    });
    input.addEventListener("input", updateSwatch);
    input.addEventListener("change", () => { if (hex.test(input.value)) picker.setColor(input.value); });
    updateSwatch();
  });
  const name = document.querySelector("#id_nome_exibicao");
  name?.addEventListener("input", () => { preview.querySelector("#name-preview").textContent = name.value || "Sua organização"; });
  const logo = document.querySelector("[data-logo-input]");
  logo?.addEventListener("change", () => {
    const file = logo.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = event => { preview.querySelector("#logo-preview").src = event.target.result; };
    reader.readAsDataURL(file);
  });
  sync();
  const cover = document.querySelector("[data-cover-input]");
  cover?.addEventListener("change", () => {
    const file = cover.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = event => {
      const image = preview.querySelector("#cover-preview");
      image.src = event.target.result;
      image.hidden = false;
    };
    reader.readAsDataURL(file);
  });
})();
