(() => {
  document.querySelectorAll('[data-password-toggle]').forEach(button => {
    const input = document.getElementById(button.getAttribute('aria-controls'));
    if (!input) return;
    button.hidden = false;
    const name = input.labels[0]?.textContent.trim().toLowerCase() || 'senha';
    button.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.textContent = show ? 'Ocultar' : 'Mostrar';
      button.setAttribute('aria-pressed', String(show));
      button.setAttribute('aria-label', `${show ? 'Ocultar' : 'Mostrar'} ${name}`);
    });
  });
  const summary = document.querySelector('[data-auth-error-summary]');
  if (summary) summary.focus();
})();
