(function(){
  var selected = {};

  window.onCheckbox = function(cb) {
    var tr = cb.closest('tr');
    var pid = tr.dataset.productId;
    if (cb.checked) {
      selected[pid] = {
        name: tr.dataset.name,
        brand: tr.dataset.brandTitle,
        section: tr.dataset.section,
        price: tr.dataset.price,
        brandId: tr.dataset.brand
      };
      tr.classList.add('selected');
    } else {
      delete selected[pid];
      tr.classList.remove('selected');
    }
    updateBasket();
  };

  window.toggleSection = function(head) {
    var section = head.closest('.section');
    section.classList.toggle('collapsed');
  };

  window.toggleBrand = function(head) {
    var card = head.closest('.brand-card');
    card.classList.toggle('collapsed');
  };

  window.clearSelection = function() {
    selected = {};
    document.querySelectorAll('tbody tr.selected').forEach(function(tr){ tr.classList.remove('selected'); });
    document.querySelectorAll('.check-col input[type="checkbox"]').forEach(function(cb){ cb.checked = false; });
    updateBasket();
  };

  window.openOrderModal = function() {
    var count = Object.keys(selected).length;
    if (!count) return;
    document.getElementById('modalCount').textContent = 'Выбрано товаров: ' + count;
    document.getElementById('orderModal').classList.add('open');
  };

  window.closeOrderModal = function() {
    document.getElementById('orderModal').classList.remove('open');
    hideAllErrors();
  };

  window.submitOrder = function(e) {
    e.preventDefault();
    var name = document.getElementById('clientName').value.trim();
    var company = document.getElementById('clientCompany').value.trim();
    var phone = document.getElementById('clientPhone').value.trim();
    var note = document.getElementById('clientNote').value.trim();

    hideAllErrors();
    var valid = true;
    if (!name) { showError('nameError'); valid = false; }
    if (!company) { showError('companyError'); valid = false; }
    if (!phone) { showError('phoneError'); valid = false; }
    if (!valid) return;

    var count = Object.keys(selected).length;
    if (!count) return;

    var products = [];
    for (var pid in selected) {
      if (selected.hasOwnProperty(pid)) {
        products.push(selected[pid]);
      }
    }
    products.sort(function(a,b){ return a.section.localeCompare(b.section) || a.brand.localeCompare(b.brand); });

    var orderData = {
      clientName: name,
      clientCompany: company,
      clientPhone: phone,
      clientNote: note,
      products: products,
      createdAt: new Date().toISOString()
    };

    downloadOrderFile(orderData);
    closeOrderModal();
    showSuccessToast();
  };

  function downloadOrderFile(orderData) {
    var html = document.documentElement.outerHTML;
    var parser = new DOMParser();
    var doc = parser.parseFromString(html, 'text/html');

    var existing = doc.getElementById('order-data');
    if (existing) existing.remove();

    var script = doc.createElement('script');
    script.id = 'order-data';
    script.type = 'application/json';
    script.textContent = JSON.stringify(orderData, null, 2);
    doc.head.appendChild(script);

    var blob = new Blob(['<!DOCTYPE html>\n' + doc.documentElement.outerHTML], {type: 'text/html;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    var safeCompany = orderData.clientCompany.replace(/[^a-z0-9а-я]/gi, '_').substring(0, 30);
    a.download = 'Заказ на дегустацию - ' + safeCompany + '.html';
    a.href = url;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function updateBasket() {
    var count = Object.keys(selected).length;
    var basket = document.getElementById('basket');
    var countEl = document.getElementById('basketCount');
    var labelEl = document.getElementById('basketLabel');
    var btn = document.getElementById('basketBtn');

    countEl.textContent = count;
    if (count > 0) {
      basket.classList.add('visible');
      labelEl.textContent = count + ' ' + plural(count, ['позиция','позиции','позиций']);
      btn.disabled = false;
    } else {
      basket.classList.remove('visible');
      labelEl.textContent = 'Ничего не выбрано';
      btn.disabled = true;
    }
  }

  function plural(n, forms) {
    n = Math.abs(n) % 100;
    var n1 = n % 10;
    if (n > 10 && n < 20) return forms[2];
    if (n1 > 1 && n1 < 5) return forms[1];
    if (n1 === 1) return forms[0];
    return forms[2];
  }

  function showError(id) {
    var el = document.getElementById(id);
    if (el) el.classList.add('show');
  }

  function hideAllErrors() {
    document.querySelectorAll('.error-text').forEach(function(el){ el.classList.remove('show'); });
  }

  function showSuccessToast() {
    var toast = document.getElementById('successToast');
    toast.classList.add('show');
    setTimeout(function(){ toast.classList.remove('show'); }, 4000);
  }

  window.dismissBanner = function() {
    document.getElementById('orderBanner').classList.remove('visible');
  };

  // Manager view: detect incoming order
  var orderScript = document.getElementById('order-data');
  if (orderScript) {
    try {
      var order = JSON.parse(orderScript.textContent);
      var banner = document.getElementById('orderBanner');
      var bannerText = document.getElementById('orderBannerText');
      bannerText.innerHTML =
        '<strong>Заказ на дегустацию</strong> &mdash; ' +
        escapeHtml(order.clientName) + ', ' +
        escapeHtml(order.clientCompany) + ', ' +
        escapeHtml(order.clientPhone) +
        (order.clientNote ? ' &middot; ' + escapeHtml(order.clientNote) : '') +
        ' &nbsp;&middot;&nbsp; <strong>' + order.products.length + ' ' + plural(order.products.length, ['позиция','позиции','позиций']) + '</strong>';
      banner.classList.add('visible');

      var selectedPids = {};
      order.products.forEach(function(p){
        selectedPids[p.name] = true;
      });
      document.querySelectorAll('tbody tr[data-name]').forEach(function(tr){
        if (selectedPids[tr.dataset.name]) {
          tr.classList.add('selected');
          tr.querySelector('input[type="checkbox"]').checked = true;
        }
      });
      updateBasketFromOrder(order);
    } catch(e) {}
  }

  function updateBasketFromOrder(order) {
    order.products.forEach(function(p){
      var found = false;
      document.querySelectorAll('tbody tr[data-name]').forEach(function(tr){
        if (tr.dataset.name === p.name && !found) {
          found = true;
          selected[tr.dataset.productId] = p;
        }
      });
    });
    updateBasket();
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  document.getElementById('orderModal').addEventListener('click', function(e){
    if (e.target === this) closeOrderModal();
  });
})();
