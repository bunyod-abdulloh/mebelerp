document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  const $ = django.jQuery;

  const TEXT_FIELDS = ["name", "unit"];
  const SELECTOR = 'select[id^="id_items-"][id$="-product"]';

  function getOrderCurrency() {
    const el = document.getElementById("id_currency") || document.getElementById("order-currency");
    return el ? (el.value || el.dataset.code) : null;
  }

  function setValue(prefix, field, value) {
    const input = document.getElementById(`${prefix}-${field}`);
    if (input) input.value = value ?? "";
  }

  function parseNum(value) {
    const n = parseFloat(String(value ?? "").replace(/\s/g, "").replace(",", "."));
    return Number.isFinite(n) ? n : 0;
  }

  function fmt(n) {
    return n.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  }

  function getFooter(group) {
    let el = document.getElementById("order-items-total");
    if (!el) {
      el = document.createElement("div");
      el.id = "order-items-total";
      el.style.cssText = "text-align:right;font-weight:600;padding:12px 16px;";
      group.appendChild(el);
    }
    return el;
  }

  function recalcTotal() {
    const group = document.getElementById("items-group");
    if (!group) return;

    let subtotal = 0;
    group.querySelectorAll('input[id^="id_items-"][id$="-quantity"]').forEach((q) => {
      if (q.id.includes("__prefix__")) return;  // "Add another" shabloni
      const prefix = q.id.replace(/-quantity$/, "");
      const del = document.getElementById(`${prefix}-DELETE`);
      if (del && del.checked) return;
      const price = document.getElementById(`${prefix}-unit_price`);
      subtotal += parseNum(q.value) * parseNum(price ? price.value : "");
    });

    const discountEl = document.getElementById("id_discount");
    const discount = discountEl ? parseNum(discountEl.value) : 0;
    const currency = getOrderCurrency() || "";

    let text = `Jami: ${fmt(subtotal)} ${currency}`;
    if (discount > 0) {
      text += ` · Chegirma: ${fmt(discount)} · To'lanadi: ${fmt(subtotal - discount)} ${currency}`;
    }
    getFooter(group).textContent = text;
  }

  function showPriceWarning(prefix, message) {
    const input = document.getElementById(`${prefix}-unit_price`);
    if (!input) return;
    let note = input.parentElement.querySelector(".autofill-warning");
    if (!message) {
      if (note) note.remove();
      return;
    }
    if (!note) {
      note = document.createElement("p");
      note.className = "help autofill-warning";
      note.style.color = "var(--error-fg, #ba2121)";
      input.after(note);
    }
    note.textContent = message;
  }

  async function fillRow(select) {
    if (select.id.includes("__prefix__")) return;
    const prefix = select.id.replace(/-product$/, "");
    const productId = select.value;

    if (!productId) {
      showPriceWarning(prefix, null);
      return;
    }

    let data;
    try {
      const resp = await fetch(
        `${select.dataset.productUrl}?product=${encodeURIComponent(productId)}`,
        { headers: { Accept: "application/json" }, credentials: "same-origin" }
      );
      if (!resp.ok) {
        console.error("Endpoint xato qaytardi:", resp.status);
        return;
      }
      data = await resp.json();
    } catch (err) {
      console.error("Product ma'lumotini olib bo'lmadi:", err);
      return;
    }

    if (select.value !== productId) return;  // eski javob yangisini bosmasin

    TEXT_FIELDS.forEach((f) => setValue(prefix, f, data[f]));

    const orderCurrency = getOrderCurrency();
    if (orderCurrency && orderCurrency !== data.currency) {
      showPriceWarning(
        prefix,
        `Mahsulot narxi ${data.currency} da, buyurtma ${orderCurrency} da. Narxni qo'lda kiriting.`
      );
    } else {
      showPriceWarning(prefix, null);
      setValue(prefix, "unit_price", data.unit_price);
    }
    recalcTotal();
  }

  $(document).on("change", SELECTOR, function () {
    fillRow(this);
  });

  // Miqdor, narx, chegirma, valyuta, o'chirish belgisi o'zgarsa yoki qator qo'shilsa/olib tashlansa
  $(document).on("input change", 'input[id^="id_items-"], #id_discount, #id_currency', recalcTotal);
  $(document).on("formset:added formset:removed", recalcTotal);

  recalcTotal();
});