(function () {
  // The server injects a single payload the page can read without extra requests.
  const appData = window.dashboardData || {};
  const shops = Array.isArray(appData.shops) ? appData.shops : [];
  const chartData = appData.chartData || null;

  function initPriceChart() {
    // Skip chart boot if the page has no chart data yet.
    const canvas = document.getElementById('price-history-chart');
    if (!canvas || !chartData || !Array.isArray(chartData.labels) || !Array.isArray(chartData.series)) {
      return;
    }
    if (typeof Chart === 'undefined') {
      return;
    }

    const palette = ['#47249c', '#e5007d', '#0f766e', '#1d4ed8', '#ea580c', '#7c3aed'];
    const datasets = chartData.series.map((series, index) => ({
      label: series.name,
      data: Array.isArray(series.points) ? series.points : [],
      borderColor: palette[index % palette.length],
      backgroundColor: palette[index % palette.length],
      tension: 0.2,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 4,
      spanGaps: true,
    }));

    new Chart(canvas, {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false,
        },
        plugins: {
          legend: {
            position: 'bottom',
          },
        },
        scales: {
          x: {
            ticks: {
              autoSkip: true,
              maxTicksLimit: 10,
            },
          },
          y: {
            title: {
              display: true,
              text: 'Price (GBP)',
            },
          },
        },
      },
    });
  }

  function initRetailerControls() {
    // These controls only exist after a product has been loaded.
    const retailerContainer = document.getElementById('retailer-container');
    const addBtn = document.getElementById('add-retailer-btn');

    if (!retailerContainer || !addBtn || shops.length === 0) {
      return;
    }

    // Build the option list once, then clone it for each added row.
    const optionTemplate = document.createDocumentFragment();
    shops.forEach((shop) => {
      const option = document.createElement('option');
      option.value = String(shop.id);
      option.textContent = shop.name;
      optionTemplate.appendChild(option);
    });

    function createRetailerRow() {
      // Each row is just a select plus a remove button.
      const row = document.createElement('div');
      row.className = 'retailer-row fade-item';

      const select = document.createElement('select');
      select.name = 'shop_ids';
      select.appendChild(optionTemplate.cloneNode(true));

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'remove-btn';
      removeBtn.textContent = 'x';
      removeBtn.setAttribute('aria-label', 'Remove retailer');
      removeBtn.addEventListener('click', () => removeRetailer(removeBtn));

      row.appendChild(select);
      row.appendChild(removeBtn);

      row.addEventListener('animationend', () => {
        row.classList.remove('fade-item');
      }, { once: true });

      return row;
    }

    function removeRetailer(button) {
      // Keep at least one retailer selector visible.
      if (retailerContainer.children.length <= 1) {
        return;
      }

      const row = button.closest('.retailer-row');
      if (!row) {
        return;
      }

      row.classList.add('leaving');
      row.addEventListener('animationend', () => row.remove(), { once: true });
    }

    addBtn.addEventListener('click', () => {
      retailerContainer.appendChild(createRetailerRow());
    });

    window.removeRetailer = removeRetailer;
  }

  initPriceChart();
  initRetailerControls();
})();
