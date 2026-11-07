/* Os dados também estão em tabelas HTML: gráficos são uma melhoria opcional. */
(() => {
  const source = document.getElementById('management-chart-data');
  if (!source || typeof window.Chart !== 'function') return;
  const data = JSON.parse(source.textContent);
  const styles = getComputedStyle(document.body);
  const color = (token, fallback) => styles.getPropertyValue(token).trim() || fallback;
  const ink = color('--tenant-surface-ink', '#222222');
  const colors = [color('--tenant-primary', '#6E4AA3'), color('--tenant-secondary', '#315A76'),
    color('--tenant-accent', '#5C9F63'), ink];
  ['projects', 'members'].forEach((name) => {
    const canvas = document.getElementById(`management-chart-${name}`);
    const series = data[name];
    if (!canvas || !series.values.some(value => value > 0)) return;
    const frame = canvas.closest('.tenant-chart-frame');
    frame.hidden = false;
    try {
      const chart = new window.Chart(canvas, {
        type: 'bar',
        data: {labels: series.labels, datasets: [{label: series.label, data: series.values,
          backgroundColor: colors, borderColor: ink, borderWidth: 1}]},
        options: {
          responsive: true, maintainAspectRatio: false, animation: false,
          plugins: {legend: {display: false}},
          scales: {
            x: {ticks: {color: ink}, grid: {display: false}},
            y: {beginAtZero: true, ticks: {color: ink, precision: 0}}
          }
        }
      });
      requestAnimationFrame(() => chart.resize());
    } catch (error) {
      frame.hidden = true;
    }
  });
})();
