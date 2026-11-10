(() => {
  const status = document.getElementById('membros-atualizacao');
  let controller;

  async function updateDirectory(url, addHistory) {
    const directory = document.getElementById('diretorio-membros');
    if (!directory) return;
    if (controller) controller.abort();
    controller = new AbortController();
    directory.setAttribute('aria-busy', 'true');
    if (status) status.textContent = 'Atualizando lista de pessoas.';
    try {
      const response = await fetch(url, { credentials: 'same-origin', signal: controller.signal });
      if (!response.ok || response.redirected) throw new Error('Lista indisponível');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const updated = page.getElementById('diretorio-membros');
      if (!updated) throw new Error('Lista indisponível');
      directory.replaceWith(updated);
      if (addHistory) history.pushState({ membersDirectory: true }, '', url);
      if (status) status.textContent = 'Lista de pessoas atualizada.';
      updated.querySelector('#membros-titulo')?.focus({ preventScroll: true });
    } catch (error) {
      if (error.name !== 'AbortError') window.location.assign(url);
    } finally {
      directory.removeAttribute('aria-busy');
    }
  }

  document.addEventListener('click', event => {
    const link = event.target.closest('#diretorio-membros .tenant-member-filters a, #diretorio-membros .tenant-member-pagination a');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    event.preventDefault();
    updateDirectory(url.href, true);
  });
  window.addEventListener('popstate', () => updateDirectory(window.location.href, false));
})();
