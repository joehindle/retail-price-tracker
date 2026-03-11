(function () {
  const appData = window.dashboardData || {};
  const shops = Array.isArray(appData.shops) ? appData.shops : [];
  const chartData = appData.chartData || null;

  function initPriceChart() {
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
    const retailerContainer = document.getElementById('retailer-container');
    const addBtn = document.getElementById('add-retailer-btn');

    if (!retailerContainer || !addBtn || shops.length === 0) {
      return;
    }

    function createRetailerRow() {
      const row = document.createElement('div');
      row.className = 'retailer-row fade-item';

      const select = document.createElement('select');
      select.name = 'shop_ids';

      shops.forEach((shop) => {
        const option = document.createElement('option');
        option.value = String(shop.id);
        option.textContent = shop.name;
        select.appendChild(option);
      });

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
