(function () {
  // The server injects a single payload the page can read without extra requests.
  const appData = window.dashboardData || {};
  const shops = Array.isArray(appData.shops) ? appData.shops : [];
  const chartData = appData.chartData || null;
  const outputRows = Array.isArray(appData.output) ? appData.output : [];
  const marketSnapshot = appData.marketSnapshot || null;
  const lowestRangePrice = appData.lowestRangePrice || null;
  const productTitle = appData.productTitle || null;

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

  function initAiPreview() {
    const trigger = document.getElementById('generate-ai-feedback-btn');
    const thread = document.getElementById('ai-thread');

    if (!trigger || !thread) {
      return;
    }

    function renderThreadMessage(text, isError = false) {
      const message = document.createElement('article');
      const avatar = document.createElement('div');
      const bubble = document.createElement('div');

      message.className = isError ? 'ai-message ai-message-system' : 'ai-message ai-message-assistant';
      avatar.className = 'ai-avatar';
      avatar.textContent = 'AI';
      bubble.className = 'ai-bubble';
      bubble.textContent = text;

      message.appendChild(avatar);
      message.appendChild(bubble);

      thread.replaceChildren(message);
    }

    trigger.addEventListener('click', async () => {
      if (outputRows.length === 0) {
        renderThreadMessage('Run a comparison first, then generate AI feedback.', true);
        return;
      }

      trigger.disabled = true;
      const originalLabel = trigger.textContent;
      trigger.textContent = 'Generating...';
      renderThreadMessage('Generating insights...', false);

      try {
        const response = await fetch('/api/ai-feedback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            output: outputRows,
            chartData,
            marketSnapshot,
            lowestRangePrice,
            productTitle,
          }),
        });

        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(body.error || 'Failed to generate AI feedback.');
        }

        const feedback = body.feedback || 'No AI feedback returned.';
        renderThreadMessage(feedback, false);
      } catch (error) {
        renderThreadMessage(error.message || 'Failed to generate AI feedback.', true);
      } finally {
        trigger.disabled = false;
        trigger.textContent = originalLabel;
      }
    });
  }

  initPriceChart();
  initRetailerControls();
  initAiPreview();
})();
