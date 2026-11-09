/* Os dados também estão em tabelas HTML: gráficos são uma melhoria opcional. */
(() => {
  const source = document.getElementById('management-chart-data');
  if (!source || typeof window.Chart !== 'function') return;
  const data = JSON.parse(source.textContent);
  const palette = () => {
    const styles = getComputedStyle(document.body);
    const color = (token, fallback) => styles.getPropertyValue(token).trim() || fallback;
    const ink = color('--tenant-surface-ink', '#222222');
    return {ink, colors: [color('--tenant-primary', '#6E4AA3'), color('--tenant-secondary', '#315A76'),
      color('--tenant-accent', '#5C9F63'), ink]};
  };
  const charts = [];
  ['projects', 'members'].forEach((name) => {
    const canvas = document.getElementById(`management-chart-${name}`);
    const series = data[name];
    if (!canvas || !series.values.some(value => value > 0)) return;
    const frame = canvas.closest('.tenant-chart-frame');
    frame.hidden = false;
    try {
      const {ink, colors} = palette();
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
      charts.push(chart);
      requestAnimationFrame(() => chart.resize());
    } catch (error) {
      frame.hidden = true;
    }
  });
  window.addEventListener('pm-display-mode-change', () => {
    const {ink, colors} = palette();
    charts.forEach(chart => {
      chart.data.datasets[0].backgroundColor = colors;
      chart.data.datasets[0].borderColor = ink;
      chart.options.scales.x.ticks.color = ink;
      chart.options.scales.y.ticks.color = ink;
      chart.update('none');
    });
  });
})();
