(function () {
  const retailerContainer = document.getElementById('retailer-container');
  const addBtn = document.getElementById('add-retailer-btn');
  const appData = window.dashboardData || {};
  const shops = Array.isArray(appData.shops) ? appData.shops : [];

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
})();
