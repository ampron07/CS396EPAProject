(() => {
  const node = document.getElementById('prediction-data');
  if (!node) return;
  const data = JSON.parse(node.textContent);
  if (typeof Chart === 'undefined') {
    document.querySelectorAll('.prediction-chart-wrap').forEach(el => {
      el.textContent = 'Charts require Chart.js to load. Check your internet connection.';
    });
    return;
  }
  const observed = data.historical;
  const future = data.forecast;
  const holdout = data.holdout;
  const format = n => Number(n).toLocaleString(undefined, {maximumFractionDigits: 2});
  const options = (title) => ({
    responsive: true, maintainAspectRatio: false,
    interaction: {mode: 'index', intersect: false},
    plugins: {legend: {position: 'bottom'}, title: {display: false, text: title}},
    scales: {y: {beginAtZero: true, title: {display: true, text: 'CO₂ short tons/day'}},
             x: {ticks: {maxTicksLimit: 9, maxRotation: 0}}}
  });
  new Chart(document.getElementById('forecast-chart'), {
    type: 'line', data: {
      labels: [...observed.map(x => x.date), ...future.map(x => x.date)],
      datasets: [
        {label: 'Observed', data: [...observed.map(x => x.co2), ...future.map(() => null)],
         borderColor: '#2877a6', backgroundColor: '#2877a6', pointRadius: 0, tension: 0.15},
        {label: 'Projected', data: [...observed.slice(0, -1).map(() => null), observed.at(-1).co2, ...future.map(x => x.co2)],
         borderColor: '#d97706', borderDash: [6, 4], pointRadius: 0, tension: 0.15}
      ]
    }, options: options('Forecast')
  });
  new Chart(document.getElementById('validation-chart'), {
    type: 'line', data: {labels: holdout.map(x => x.date), datasets: [
      {label: 'Actual', data: holdout.map(x => x.actual), borderColor: '#2877a6', pointRadius: 1},
      {label: 'Predicted', data: holdout.map(x => x.predicted), borderColor: '#d97706', borderDash: [6, 4], pointRadius: 1}
    ]}, options: options('Validation')
  });
  const scenario = new Chart(document.getElementById('scenario-chart'), {
    type: 'line', data: {labels: future.map(x => x.date), datasets: [
      {label: 'Baseline', data: future.map(x => x.co2), borderColor: '#2877a6', pointRadius: 0},
      {label: 'Adjusted scenario', data: [], borderColor: '#d97706', pointRadius: 0, borderDash: [6, 4]}
    ]}, options: options('Sensitivity')
  });
  const baseline = future.reduce((sum, x) => sum + x.co2, 0) / future.length;
  const input = document.getElementById('generation-change');
  const refresh = () => {
    const pct = Number(input.value);
    document.getElementById('change-label').textContent = `${pct > 0 ? '+' : ''}${pct}%`;
    document.getElementById('baseline-output').textContent = format(baseline);
    document.getElementById('adjusted-output').textContent = format(baseline * (1 + pct / 100));
    document.getElementById('difference-output').textContent = `${pct > 0 ? '+' : ''}${format(baseline * pct / 100)}`;
    scenario.data.datasets[1].data = future.map(x => x.co2 * (1 + pct / 100));
    scenario.update('none');
  };
  input.addEventListener('input', refresh);
  refresh();
})();
