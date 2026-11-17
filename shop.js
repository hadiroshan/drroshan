/* ============================================================
   Shared shop engine — cart state, coupons, orders, checkout,
   simulated payment gateway, theme, toasts.
   Used by cart.html, checkout.html, payment.html
   ============================================================ */

// ---------- utilities ----------
const faNum = n => Number(n).toLocaleString('fa-IR');
const money = n => faNum(n) + ' تومان';
const toEnDigits = s => String(s)
    .replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const onlyDigits = s => toEnDigits(s).replace(/[^0-9]/g, '');

function toastX(msg, type = '') {
    let t = document.getElementById('toastX');
    if (!t) { t = document.createElement('div'); t.id = 'toastX'; t.className = 'toast-x'; document.body.appendChild(t); }
    t.textContent = msg;
    t.className = 'toast-x show ' + type;
    clearTimeout(t._h);
    t._h = setTimeout(() => t.classList.remove('show'), 3000);
}

// ---------- theme ----------
(function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme:dark)').matches)) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
})();
function toggleThemeX() {
    const el = document.documentElement;
    const dark = el.getAttribute('data-theme') === 'dark';
    if (dark) { el.removeAttribute('data-theme'); localStorage.setItem('theme', 'light'); }
    else { el.setAttribute('data-theme', 'dark'); localStorage.setItem('theme', 'dark'); }
    document.querySelectorAll('[data-theme-icon]').forEach(b => b.textContent = dark ? '🌙' : '☀️');
}

// ---------- catalog (single source of truth, shared with index.html) ----------
const CATALOG = {
    'دوره جامع پایتون':        { price: 12000000, emoji: '🐍', gradient: '#1e3a5f,#2563eb' },
    'هوش مصنوعی کاربردی':      { price: 15000000, emoji: '🤖', gradient: '#065f46,#06b6d4' },
    'تحلیل داده با پایتون':    { price: 12500000, emoji: '📊', gradient: '#7c3aed,#a78bfa' },
    'Deep Learning پیشرفته':   { price: 18000000, emoji: '🧠', gradient: '#be185d,#f472b6' },
    'وب‌اپلیکیشن با Django':   { price: 13500000, emoji: '🌐', gradient: '#92400e,#f59e0b' },
    'پکیج کامل هوش مصنوعی':    { price: 25000000, emoji: '📦', gradient: '#1e293b,#475569' }
};

// ---------- cart state (persisted) ----------
const CART_KEY = 'hr_cart_v1';
let cart = [];
try { cart = JSON.parse(localStorage.getItem(CART_KEY) || '[]'); } catch (e) { cart = []; }

function saveCart() { localStorage.setItem(CART_KEY, JSON.stringify(cart)); }
function cartCount() { return cart.reduce((s, i) => s + i.qty, 0); }
function cartSubtotal() { return cart.reduce((s, i) => s + i.price * i.qty, 0); }

function cartAdd(name, qty = 1) {
    const meta = CATALOG[name]; if (!meta) return;
    const ex = cart.find(i => i.name === name);
    if (ex) ex.qty += qty;
    else cart.push({ name, price: meta.price, emoji: meta.emoji, gradient: meta.gradient, qty });
    saveCart(); renderAll();
}
function cartSetQty(idx, qty) {
    if (!cart[idx]) return;
    cart[idx].qty = qty;
    if (cart[idx].qty <= 0) cart.splice(idx, 1);
    saveCart(); renderAll();
}
function cartRemove(idx) { cart.splice(idx, 1); saveCart(); renderAll(); }
function cartClear() { cart = []; saveCart(); renderAll(); }

// ---------- coupons ----------
const COUPONS = { 'ROOSHAN30': 30, 'PYTHON20': 20, 'AI15': 15 };
let appliedCoupon = null; // {code, percent}

function couponDiscount() {
    return appliedCoupon ? Math.round(cartSubtotal() * appliedCoupon.percent / 100) : 0;
}
function shippingCost() {
    if (cart.length === 0) return 0;
    const afterDiscount = cartSubtotal() - couponDiscount();
    return afterDiscount >= 20000000 ? 0 : 500000;
}
function cartTotal() { return Math.max(0, cartSubtotal() - couponDiscount() + shippingCost()); }

function applyCouponCode(code) {
    const c = toEnDigits(code).trim().toUpperCase();
    const msgEl = document.getElementById('couponMsg');
    if (!c) { if (msgEl) { msgEl.textContent = 'کد تخفیف را وارد کنید'; msgEl.className = 'coupon-msg err'; } return false; }
    if (COUPONS[c]) {
        appliedCoupon = { code: c, percent: COUPONS[c] };
        try { sessionStorage.setItem('hr_coupon', c); } catch (e) {}
        if (msgEl) { msgEl.textContent = '✓ کد ' + c + ' اعمال شد — ' + faNum(COUPONS[c]) + '٪ تخفیف'; msgEl.className = 'coupon-msg ok'; }
        toastX('🎉 کد تخفیف ' + faNum(COUPONS[c]) + '٪ اعمال شد', 'ok');
        renderAll(); return true;
    }
    appliedCoupon = null;
    try { sessionStorage.removeItem('hr_coupon'); } catch (e) {}
    if (msgEl) { msgEl.textContent = '✗ کد تخفیف نامعتبر است'; msgEl.className = 'coupon-msg err'; }
    return false;
}
(function restoreCoupon() {
    try {
        const c = sessionStorage.getItem('hr_coupon');
        if (c && COUPONS[c]) appliedCoupon = { code: c, percent: COUPONS[c] };
    } catch (e) {}
})();

// ---------- orders ----------
function generateOrder(orderInfo, paymentResult) {
    const order = {
        code: 'HR-' + Date.now().toString().slice(-6) + Math.floor(10 + Math.random() * 89),
        items: JSON.parse(JSON.stringify(cart)),
        subtotal: cartSubtotal(),
        discount: couponDiscount(),
        coupon: appliedCoupon ? appliedCoupon.code : null,
        shipping: shippingCost(),
        total: cartTotal(),
        customer: orderInfo,
        payment: paymentResult,
        date: new Date().toISOString(),
        status: paymentResult.status
    };
    try {
        const orders = JSON.parse(localStorage.getItem('hr_orders') || '[]');
        orders.push(order);
        localStorage.setItem('hr_orders', JSON.stringify(orders));
    } catch (e) {}
    return order;
}

// ارسال سفارش به سرور جنگو (داشبورد) — مشترک بین همهٔ مسیرهای خرید
function pushOrderToServer(order, onUpdate) {
    try {
        fetch('/api/orders/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...order, payment: { ...order.payment, receipt: order.payment.receipt || '' } }),
        }).then(r => r.json()).then(d => {
            if (d && d.ok && d.code && d.code !== order.code) {
                order.code = d.code;
                try {
                    const lo = JSON.parse(sessionStorage.getItem('hr_last_order') || 'null');
                    if (lo && lo.code) { lo.code = d.code; sessionStorage.setItem('hr_last_order', JSON.stringify(lo)); }
                    const orders = JSON.parse(localStorage.getItem('hr_orders') || '[]');
                    const match = orders[orders.length - 1];
                    if (match && match.payment && match.payment.method === order.payment.method && match.total === order.total) match.code = d.code, localStorage.setItem('hr_orders', JSON.stringify(orders));
                } catch (e) {}
                if (typeof onUpdate === 'function') onUpdate(d.code);
            }
        }).catch(() => {});
    } catch (e) {}
}

// ---------- checkout draft shared across steps/pages ----------
const DRAFT_KEY = 'hr_checkout_draft';
function saveDraft(patch) {
    try {
        const d = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || '{}');
        Object.assign(d, patch);
        sessionStorage.setItem(DRAFT_KEY, JSON.stringify(d));
    } catch (e) {}
}
function readDraft() {
    try { return JSON.parse(sessionStorage.getItem(DRAFT_KEY) || '{}'); } catch (e) { return {}; }
}
function clearDraft() { try { sessionStorage.removeItem(DRAFT_KEY); } catch (e) {} }

// ---------- form validation helpers ----------
function validateIranMobile(v) { return /^09\d{9}$/.test(onlyDigits(v)); }
function validateNationalCode(v) {
    const c = onlyDigits(v);
    if (c.length !== 10 || /^(\d)\1{9}$/.test(c)) return false;
    const check = +c[9];
    let sum = 0;
    for (let i = 0; i < 9; i++) sum += +c[i] * (10 - i);
    const r = sum % 11;
    return r < 2 ? check === r : check === 11 - r;
}
function validateEmail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }
function validatePostalCode(v) { return /^\d{10}$/.test(onlyDigits(v)); }

function setFieldError(inputEl, hasError, msg) {
    const g = inputEl.closest('.f-group');
    if (!g) return;
    g.classList.toggle('invalid', hasError);
    const e = g.querySelector('.f-error');
    if (e && msg) e.textContent = msg;
}

// ---------- card number (Luhn) ----------
function validateCardNumber(num) {
    const digits = onlyDigits(num);
    if (digits.length !== 16) return false;
    let sum = 0;
    for (let i = 0; i < 16; i++) {
        let d = +digits[i];
        if (i % 2 === 0) { d *= 2; if (d > 9) d -= 9; }
        sum += d;
    }
    return sum % 10 === 0;
}
// Iranian bank detection by BIN prefix
function detectBank(num) {
    const bin = onlyDigits(num).slice(0, 4);
    const banks = {
        '6037': 'بانک ملی', '5859': 'بانک ملی', '5892': 'سپه', '6219': 'بانک سامان',
        '6273': 'بانک تجارت', '5858': 'تجارت', '6280': 'بانک مسکن',
        '5022': 'بانک پاسارگاد', '6274': 'بانک اقتصاد نوین', '5028': 'بانک شهر',
        '5042': 'بانک رفاه', '6063': 'بانک ملت', '6104': 'بانک ملت',
        '9919': 'بانک ملت', '5894': 'بانک سپه', '6276': 'بانک صنعت و معدن',
        '6392': 'بانک کشاورزی', '6038': 'بانک کشاورزی', '5054': 'بانک کوثر',
        '6362': 'بانک آینده', '5058': 'بانک توریسم', '6367': 'بانک آینده',
        '5029': 'بانک توسعه تعاون', '6064': 'بانک گردشگری', '2071': 'بانک توسعه صادرات'
    };
    return banks[bin] || null;
}

// ---------- cart badge on any page ----------
function updateNavBadges() {
    document.querySelectorAll('[data-cart-count]').forEach(el => {
        el.textContent = faNum(cartCount());
        el.classList.toggle('hidden', cartCount() === 0);
    });
}

// ---------- render hook (pages override window.renderAll) ----------
function renderAll() {
    updateNavBadges();
    if (typeof window.onShopRender === 'function') window.onShopRender();
}

// initial paint
document.addEventListener('DOMContentLoaded', renderAll);

// ---------- mini confetti ----------
function shopConfetti() {
    const colors = ['#2563eb', '#06b6d4', '#22c55e', '#f59e0b', '#ef4444', '#a78bfa'];
    for (let i = 0; i < 70; i++) {
        const c = document.createElement('div');
        const s = 6 + Math.random() * 8;
        c.style.cssText = 'position:fixed;top:-12px;left:' + (Math.random() * 100) + 'vw;width:' + s + 'px;height:' + (s * .5) + 'px;background:' + colors[i % colors.length] + ';z-index:10001;pointer-events:none;border-radius:2px;';
        document.body.appendChild(c);
        c.animate([
            { transform: 'translateY(0) rotate(0)', opacity: 1 },
            { transform: 'translateY(' + innerHeight + 'px) rotate(' + (Math.random() * 720 - 360) + 'deg)', opacity: 0 }
        ], { duration: 2200 + Math.random() * 1800, easing: 'cubic-bezier(.3,.6,.6,1)' }).onfinish = () => c.remove();
    }
}
