/* O seletor visual complementa o campo de código, que funciona sem JavaScript. */
(() => {
  const inputs = Array.from(document.querySelectorAll("[data-theme-color]"));
  const preview = document.querySelector("#identity-preview");
  if (!preview) return;
  const hex = /^#[0-9a-f]{6}$/i;
  const luminance = color => {
    const channels = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16) / 255)
      .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
    return channels.reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
  };
  const textOn = color => luminance(color) > .179 ? "#000000" : "#ffffff";
  const contrast = (a, b) => {
    const values = [luminance(a), luminance(b)].sort((x, y) => x - y);
    return (values[1] + .05) / (values[0] + .05);
  };
  const brandBackground = color => {
    const channels = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16));
    for (let factor = 255; factor >= 0; factor--) {
      const candidate = "#" + channels.map(c => Math.floor(c * factor / 255).toString(16).padStart(2, "0")).join("");
      if (contrast(candidate, "#ffffff") >= 4.7) return candidate;
    }
  };
  const sync = () => {
    const colors = {};
    inputs.forEach(input => { if (hex.test(input.value)) colors[input.dataset.themeColor] = input.value; });
    if (colors.primary) {
      const solid = brandBackground(colors.primary);
      const selection = preview.querySelector(".identity-preview-selection");
      const selected = colors.surface && contrast(solid, colors.surface) < 3 ? textOn(colors.surface) : solid;
      selection.style.background = selected;
      selection.style.color = textOn(selected);
    }
    if (colors.background) preview.style.background = colors.background;
    const body = preview.querySelector(".identity-preview-body");
    if (colors.surface) {
      body.style.background = colors.surface;
      const header = preview.querySelector(".identity-preview-header");
      header.style.background = colors.surface;
      header.style.color = textOn(colors.surface);
      const footer = preview.querySelector(".identity-preview-footer");
      footer.style.background = colors.surface;
      footer.style.color = textOn(colors.surface);
      body.querySelectorAll("h3,p").forEach(el => { el.style.color = textOn(colors.surface); });
      if (colors.primary) {
        body.querySelector(".identity-preview-link").style.color = contrast(colors.primary, colors.surface) >= 4.5 ? colors.primary : textOn(colors.surface);
      }
    }
    if (colors.accent) {
      const button = body.querySelector("button");
      button.style.background = colors.accent;
      button.style.color = textOn(colors.accent);
      button.style.borderColor = colors.secondary || colors.accent;
    }
  };
  let enhancedColors = 0;
  inputs.forEach(input => {
    input.addEventListener("input", sync);
    if (!window.Pickr) return;
    const row = document.createElement("div");
    row.className = "identity-color-row";
    input.before(row);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "identity-color-trigger";
    const fieldName = input.labels[0]?.textContent.trim() || "cor";
    button.setAttribute("aria-label", `Escolher ${fieldName.toLowerCase()}`);
    button.setAttribute("aria-expanded", "false");
    if (input.getAttribute("aria-describedby")) button.setAttribute("aria-describedby", input.getAttribute("aria-describedby"));
    if (input.getAttribute("aria-invalid")) button.setAttribute("aria-invalid", input.getAttribute("aria-invalid"));
    const swatch = document.createElement("span");
    swatch.className = "identity-color-swatch";
    swatch.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = "Escolher cor";
    const indicator = document.createElement("span");
    indicator.className = "identity-color-indicator";
    indicator.setAttribute("aria-hidden", "true");
    indicator.textContent = "⌄";
    button.append(swatch, label, indicator);
    row.append(button);
    const fallbackColor = getComputedStyle(document.documentElement).getPropertyValue(`--tenant-${input.dataset.themeColor}`).trim();
    const initialColor = hex.test(input.value) ? input.value : (hex.test(fallbackColor) ? fallbackColor : "#6E4AA3");
    let picker;
    try {
      picker = Pickr.create({
        el: button, useAsButton: true, theme: "nano", default: initialColor,
        lockOpacity: true, defaultRepresentation: "HEX",
        components: {preview: true, hue: true, interaction: {save: true, cancel: true}},
        i18n: {"ui:dialog": "Selecionar cor", "btn:toggle": button.getAttribute("aria-label"), "btn:save": "Aplicar", "btn:cancel": "Cancelar",
          "aria:palette": "Saturação e luminosidade", "aria:hue": "Tonalidade",
          "aria:input": "Valor da cor", "aria:btn:save": "Aplicar e fechar", "aria:btn:cancel": "Cancelar e fechar"}
      });
    } catch (_) {
      row.remove();
      return;
    }
    const details = document.createElement("details");
    details.className = "identity-color-advanced";
    const summary = document.createElement("summary");
    summary.textContent = "Informar código da cor (opcional)";
    details.append(summary);
    input.before(details);
    details.append(input);
    if (input.closest(".has-error")) details.open = true;
    enhancedColors++;
    const updateSwatch = () => { swatch.style.background = hex.test(input.value) ? input.value : initialColor; };
    picker.on("save", color => {
      if (color) input.value = color.toHEXA().toString().slice(0, 7).toUpperCase();
      input.dispatchEvent(new Event("input", {bubbles: true}));
      picker.hide();
    });
    picker.on("show", () => button.setAttribute("aria-expanded", "true"));
    picker.on("hide", () => button.setAttribute("aria-expanded", "false"));
    input.addEventListener("input", updateSwatch);
    input.addEventListener("change", () => { if (hex.test(input.value)) picker.setColor(input.value); });
    updateSwatch();
  });
  if (enhancedColors === inputs.length && inputs.length) document.querySelector(".identity-color-fallback").hidden = true;
  document.querySelectorAll("[data-branding-clear]").forEach(checkbox => {
    const originalLabel = checkbox.closest("label");
    const kind = checkbox.dataset.brandingClear === "logo" ? "logo" : "capa";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "branding-file-action";
    button.disabled = checkbox.disabled;
    button.setAttribute("aria-describedby", `${checkbox.id}_help ${checkbox.id}_status`);
    const icon = originalLabel.querySelector(".branding-file-trash").cloneNode(true);
    const text = document.createElement("span");
    button.append(icon, text);
    originalLabel.before(button);
    originalLabel.hidden = true;
    const status = document.getElementById(`${checkbox.id}_status`);
    const updateLabel = () => {
      originalLabel.querySelector("[data-clear-label]").textContent = checkbox.checked ? "Remoção marcada — desmarque para manter" : "Remover imagem atual";
      text.textContent = checkbox.checked ? "Desfazer remoção" : "Remover imagem atual";
      button.setAttribute("aria-label", checkbox.checked ? `Desfazer remoção da ${kind}` : `Remover ${kind} atual`);
      status.hidden = !checkbox.checked;
    };
    checkbox.addEventListener("change", () => {
      if (checkbox.checked && !window.confirm(`Remover a ${kind} atual? Ela deixará de aparecer quando você salvar as alterações.`)) checkbox.checked = false;
      updateLabel();
    });
    button.addEventListener("click", () => checkbox.click());
    updateLabel();
  });
  const name = document.querySelector("#id_nome_exibicao");
  const defaultName = preview.dataset.organizationName || "Sua organização";
  const footerDescription = document.querySelector("#id_slogan_rodape");
  const footerEmail = document.querySelector("#id_email_contato");
  const socials = [["instagram_url", "Instagram"], ["facebook_url", "Facebook"]]
    .map(([id, label]) => [document.getElementById(`id_${id}`), label]);
  const syncFooter = () => {
    preview.querySelector("#footer-preview-name").textContent = name?.value.trim() || defaultName;
    preview.querySelector("#footer-preview-description").textContent = footerDescription?.value.trim() || "Seu ambiente de projetos e conexões.";
    const email = preview.querySelector("#footer-preview-email");
    email.textContent = footerEmail?.value.trim() || "";
    email.hidden = !email.textContent;
    const social = preview.querySelector("#footer-preview-social");
    social.textContent = socials.filter(([input]) => input?.value.trim()).map(([, label]) => label).join(" · ");
    social.hidden = !social.textContent;
  };
  name?.addEventListener("input", () => { preview.querySelector("#name-preview").textContent = name.value.trim() || defaultName; syncFooter(); });
  [footerDescription, footerEmail, ...socials.map(([input]) => input)].forEach(input => input?.addEventListener("input", syncFooter));
  syncFooter();
  const tabList = document.querySelector(".identity-tabs");
  const tabs = Array.from(tabList?.querySelectorAll('[role="tab"]') || []);
  const panels = tabs.map(tab => document.getElementById(tab.getAttribute("aria-controls")));
  if (tabs.length && panels.every(Boolean)) {
    const activate = (index, focus = false) => {
      tabs.forEach((tab, i) => {
        const active = i === index;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        panels[i].hidden = !active;
      });
      if (focus) tabs[index].focus();
    };
    panels.forEach((panel, i) => {
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", tabs[i].id);
      if (panel.querySelector(".has-error")) {
        tabs[i].dataset.hasErrors = "true";
        tabs[i].setAttribute("aria-label", `${tabs[i].textContent.trim()} — contém erros`);
      }
      tabs[i].addEventListener("click", () => activate(i));
      tabs[i].addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = (i + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        activate(next, true);
      });
    });
    const firstError = panels.findIndex(panel => panel.querySelector(".has-error"));
    activate(firstError < 0 ? 0 : firstError);
    document.querySelector(".tenant-identity-form").classList.add("has-identity-tabs");
    tabList.hidden = false;
  }
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
