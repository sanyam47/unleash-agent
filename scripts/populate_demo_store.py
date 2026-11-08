import os
from pathlib import Path

p = Path(r"c:\coding\ai-trainer\backend\data\projects\amazon_store_demo")
p.mkdir(parents=True, exist_ok=True)

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberStore | Next-Gen E-Commerce</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <!-- Top Navigation Bar -->
    <header class="nav-header">
        <div class="nav-container">
            <div class="nav-brand">
                <span class="brand-logo">⚡ Cyber<span class="accent">Store</span></span>
                <span class="brand-badge">PRIME</span>
            </div>
            
            <div class="nav-search">
                <select class="search-cat" id="catSelect">
                    <option value="all">All Departments</option>
                    <option value="hardware">Cyber Hardware</option>
                    <option value="wearables">Neural Gear</option>
                    <option value="accessories">Accessories</option>
                </select>
                <input type="text" id="searchInput" placeholder="Search millions of high-tech gear, components...">
                <button class="search-btn" id="searchBtn">🔍</button>
            </div>

            <div class="nav-actions">
                <div class="nav-item">
                    <span class="subtext">Hello, Engineer</span>
                    <span class="maintext">Account & Lists ▾</span>
                </div>
                <div class="nav-item">
                    <span class="subtext">Returns</span>
                    <span class="maintext">& Orders</span>
                </div>
                <div class="cart-button" id="openCartBtn">
                    <span class="cart-icon">🛒</span>
                    <span class="cart-count" id="cartCounter">0</span>
                    <span class="cart-label">Cart</span>
                </div>
            </div>
        </div>
    </header>

    <!-- Subnav Links -->
    <nav class="subnav">
        <div class="subnav-container">
            <a href="#" class="active">☰ All</a>
            <a href="#">Today's Lightning Deals</a>
            <a href="#">Neural Processors</a>
            <a href="#">Quantum Storage</a>
            <a href="#">Cyber Security Rigs</a>
            <a href="#">Customer Service</a>
        </div>
    </nav>

    <!-- Hero Banner Promo -->
    <section class="hero-banner">
        <div class="hero-content">
            <span class="promo-tag">⚡ PRIME EXCLUSIVE DEAL OF THE DAY</span>
            <h1>Neural H100 GPU Workstations & Cyber Decks</h1>
            <p>Up to 45% off on air-gapped security hardware, AI edge accelerators, and encrypted telemetry gear.</p>
            <button class="btn-cta" onclick="document.getElementById('productsSection').scrollIntoView({behavior:'smooth'})">Shop Limited Deals Now</button>
        </div>
    </section>

    <!-- Product Grid Section -->
    <main class="main-container" id="productsSection">
        <div class="section-header">
            <h2>Featured Products & Best Sellers</h2>
            <span class="results-count" id="resultsCount">Showing 8 products</span>
        </div>

        <div class="product-grid" id="productGrid">
            <!-- Injected via JS -->
        </div>
    </main>

    <!-- Slide-Out Shopping Cart Drawer -->
    <div class="cart-drawer-overlay" id="cartOverlay">
        <div class="cart-drawer">
            <div class="cart-header">
                <h3>Shopping Cart (<span id="drawerItemCount">0</span> items)</h3>
                <button class="close-cart-btn" id="closeCartBtn">&times;</button>
            </div>
            <div class="cart-body" id="cartItemsList">
                <div class="empty-cart-msg">Your CyberStore cart is empty.</div>
            </div>
            <div class="cart-footer">
                <div class="subtotal-row">
                    <span>Subtotal:</span>
                    <strong class="subtotal-price" id="cartSubtotal">$0.00</strong>
                </div>
                <button class="btn-checkout" id="checkoutBtn">Proceed to Air-Gapped Checkout 🔒</button>
            </div>
        </div>
    </div>

    <!-- Notification Toast -->
    <div class="toast-msg" id="toastMsg">Item added to cart!</div>

    <!-- Footer -->
    <footer class="store-footer">
        <div class="back-to-top" onclick="window.scrollTo({top:0, behavior:'smooth'})">Back to top ↑</div>
        <div class="footer-cols">
            <div class="col">
                <h4>Get to Know Us</h4>
                <a href="#">Careers</a>
                <a href="#">About CyberStore</a>
                <a href="#">Investor Relations</a>
                <a href="#">Neural Devices</a>
            </div>
            <div class="col">
                <h4>Shop with Us</h4>
                <a href="#">Your Account</a>
                <a href="#">Your Orders</a>
                <a href="#">Delivery Rates & Policies</a>
                <a href="#">Prime Membership</a>
            </div>
            <div class="col">
                <h4>Security & Privacy</h4>
                <a href="#">Air-Gapped Isolation</a>
                <a href="#">Zero-Knowledge RAG</a>
                <a href="#">Encrypted Ledger</a>
                <a href="#">SOC-2 Certified</a>
            </div>
        </div>
        <div class="footer-bottom">
            <p>© 2026 CyberStore, Inc. Local Antigravity Agent Workspace Demo.</p>
        </div>
    </footer>

    <script src="app.js"></script>
</body>
</html>"""

p.joinpath("index.html").write_text(html, encoding="utf-8")

css = """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

:root {
    --nav-bg: #131921;
    --subnav-bg: #232f3e;
    --accent: #f0c14b;
    --accent-hover: #ddb347;
    --prime-blue: #00a8e1;
    --bg-page: #eaeded;
    --card-bg: #ffffff;
    --text-primary: #0f1111;
    --text-secondary: #565959;
    --price-color: #b12704;
}

body {
    background-color: var(--bg-page);
    color: var(--text-primary);
    overflow-x: hidden;
}

/* Nav Header */
.nav-header {
    background: var(--nav-bg);
    color: white;
    padding: 10px 18px;
    position: sticky;
    top: 0;
    z-index: 1000;
}

.nav-container {
    display: flex;
    align-items: center;
    gap: 16px;
    max-width: 1440px;
    margin: 0 auto;
}

.nav-brand {
    display: flex;
    align-items: baseline;
    gap: 6px;
    cursor: pointer;
}

.brand-logo {
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.5px;
}

.brand-logo .accent {
    color: var(--accent);
}

.brand-badge {
    background: var(--prime-blue);
    font-size: 0.65rem;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 3px;
    letter-spacing: 0.5px;
}

.nav-search {
    flex: 1;
    display: flex;
    height: 40px;
    border-radius: 6px;
    overflow: hidden;
    background: white;
}

.search-cat {
    background: #f3f3f3;
    border: none;
    border-right: 1px solid #ddd;
    padding: 0 10px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    outline: none;
    cursor: pointer;
}

.nav-search input {
    flex: 1;
    border: none;
    padding: 0 12px;
    font-size: 0.95rem;
    outline: none;
}

.search-btn {
    width: 46px;
    background: var(--accent);
    border: none;
    cursor: pointer;
    font-size: 1rem;
    transition: 0.2s;
}

.search-btn:hover {
    background: var(--accent-hover);
}

.nav-actions {
    display: flex;
    align-items: center;
    gap: 18px;
}

.nav-item {
    display: flex;
    flex-direction: column;
    cursor: pointer;
}

.nav-item .subtext {
    font-size: 0.72rem;
    color: #ccc;
}

.nav-item .maintext {
    font-size: 0.86rem;
    font-weight: 700;
}

.cart-button {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    position: relative;
    padding: 4px 8px;
    border: 1px solid transparent;
    border-radius: 4px;
}

.cart-button:hover {
    border-color: white;
}

.cart-icon {
    font-size: 1.5rem;
}

.cart-count {
    position: absolute;
    top: 2px;
    left: 20px;
    background: #e47911;
    color: white;
    font-weight: 800;
    font-size: 0.75rem;
    padding: 0 5px;
    border-radius: 10px;
}

.cart-label {
    font-weight: 700;
    font-size: 0.9rem;
}

/* Subnav */
.subnav {
    background: var(--subnav-bg);
    padding: 7px 18px;
}

.subnav-container {
    display: flex;
    gap: 16px;
    font-size: 0.84rem;
    max-width: 1440px;
    margin: 0 auto;
}

.subnav a {
    color: #e2e8f0;
    text-decoration: none;
    font-weight: 500;
    padding: 3px 6px;
    border-radius: 3px;
}

.subnav a:hover {
    outline: 1px solid white;
}

/* Hero Promo */
.hero-banner {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    color: white;
    padding: 45px 24px;
    border-bottom: 2px solid #334155;
}

.hero-content {
    max-width: 1200px;
    margin: 0 auto;
}

.promo-tag {
    color: var(--accent);
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 1px;
}

.hero-banner h1 {
    font-size: 2.2rem;
    margin: 8px 0;
    font-weight: 800;
}

.hero-banner p {
    font-size: 1rem;
    color: #94a3b8;
    max-width: 650px;
    line-height: 1.5;
    margin-bottom: 18px;
}

.btn-cta {
    background: var(--accent);
    color: #111;
    border: none;
    padding: 10px 22px;
    font-weight: 700;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.95rem;
    transition: 0.2s;
}

.btn-cta:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
}

/* Main Container & Products */
.main-container {
    max-width: 1400px;
    margin: 24px auto;
    padding: 0 16px;
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}

.section-header h2 {
    font-size: 1.35rem;
    font-weight: 700;
}

.results-count {
    font-size: 0.82rem;
    color: var(--text-secondary);
}

.product-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 16px;
}

.product-card {
    background: var(--card-bg);
    border: 1px solid #d5d9d9;
    border-radius: 8px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.2s, box-shadow 0.2s;
}

.product-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.08);
}

.card-img-wrap {
    height: 180px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f8fafc;
    border-radius: 6px;
    font-size: 3.8rem;
    margin-bottom: 12px;
}

.product-title {
    font-size: 0.95rem;
    font-weight: 600;
    line-height: 1.4;
    margin-bottom: 6px;
    color: #007185;
    cursor: pointer;
}

.product-title:hover {
    color: #c45500;
    text-decoration: underline;
}

.rating-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    margin-bottom: 8px;
}

.stars {
    color: #ffa41c;
}

.review-count {
    color: #007185;
}

.price-row {
    display: flex;
    align-items: baseline;
    gap: 4px;
    margin-bottom: 4px;
}

.dollar-sign {
    font-size: 0.8rem;
    color: var(--text-primary);
}

.price-val {
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--price-color);
}

.prime-badge {
    color: var(--prime-blue);
    font-size: 0.75rem;
    font-weight: 800;
    font-style: italic;
    margin-bottom: 6px;
}

.delivery-text {
    font-size: 0.78rem;
    color: var(--text-secondary);
    margin-bottom: 14px;
}

.btn-add-cart {
    background: #ffd814;
    border: 1px solid #fcd200;
    border-radius: 20px;
    padding: 8px 14px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: 0.15s;
    outline: none;
}

.btn-add-cart:hover {
    background: #f7ca00;
    border-color: #f2c200;
}

/* Cart Drawer */
.cart-drawer-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 2000;
    display: none;
    justify-content: flex-end;
}

.cart-drawer {
    background: white;
    width: 380px;
    max-width: 90%;
    height: 100%;
    display: flex;
    flex-direction: column;
    box-shadow: -4px 0 20px rgba(0,0,0,0.2);
    animation: slideIn 0.25s ease-out;
}

@keyframes slideIn {
    from { transform: translateX(100%); }
    to { transform: translateX(0); }
}

.cart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid #e2e8f0;
}

.close-cart-btn {
    background: transparent;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #64748b;
}

.cart-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.cart-item {
    display: flex;
    gap: 12px;
    border-bottom: 1px solid #f1f5f9;
    padding-bottom: 12px;
}

.cart-item-icon {
    font-size: 1.8rem;
    background: #f8fafc;
    padding: 8px;
    border-radius: 6px;
}

.cart-item-info {
    flex: 1;
}

.cart-item-title {
    font-size: 0.84rem;
    font-weight: 600;
    margin-bottom: 4px;
}

.cart-item-price {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--price-color);
}

.cart-item-qty {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
}

.qty-btn {
    background: #e2e8f0;
    border: none;
    padding: 2px 7px;
    border-radius: 3px;
    cursor: pointer;
    font-weight: 700;
}

.cart-footer {
    padding: 16px;
    border-top: 1px solid #e2e8f0;
    background: #f8fafc;
}

.subtotal-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 1.1rem;
    margin-bottom: 14px;
}

.subtotal-price {
    color: var(--price-color);
}

.btn-checkout {
    width: 100%;
    background: #ffd814;
    border: 1px solid #fcd200;
    border-radius: 8px;
    padding: 10px;
    font-weight: 700;
    font-size: 0.95rem;
    cursor: pointer;
}

.btn-checkout:hover {
    background: #f7ca00;
}

/* Toast */
.toast-msg {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #1e293b;
    color: #38bdf8;
    padding: 10px 18px;
    border-radius: 8px;
    font-size: 0.85rem;
    box-shadow: 0 4px 14px rgba(0,0,0,0.3);
    border: 1px solid #334155;
    display: none;
    z-index: 3000;
}

/* Footer */
.store-footer {
    background: #232f3e;
    color: white;
    margin-top: 50px;
}

.back-to-top {
    background: #37475a;
    text-align: center;
    padding: 12px;
    font-size: 0.85rem;
    cursor: pointer;
}

.back-to-top:hover {
    background: #485769;
}

.footer-cols {
    max-width: 1100px;
    margin: 40px auto;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 30px;
    padding: 0 20px;
}

.footer-cols .col h4 {
    font-size: 0.95rem;
    margin-bottom: 12px;
}

.footer-cols .col a {
    display: block;
    color: #ddd;
    text-decoration: none;
    font-size: 0.82rem;
    line-height: 2;
}

.footer-cols .col a:hover {
    text-decoration: underline;
}

.footer-bottom {
    background: #131a22;
    text-align: center;
    padding: 24px;
    font-size: 0.75rem;
    color: #999;
}
"""

p.joinpath("styles.css").write_text(css, encoding="utf-8")

js = """const products = [
    {
        id: 1,
        title: "NeuralDeck NX-9 AI Edge Accelerator (16GB VRAM, TensorCore)",
        category: "hardware",
        price: 749.99,
        rating: 4.8,
        reviews: 1420,
        icon: "💻",
        prime: true,
        delivery: "FREE Delivery Tomorrow, 2 PM"
    },
    {
        id: 2,
        title: "Air-Gapped Hardware Security Key with Biometric Enclave",
        category: "accessories",
        price: 89.50,
        rating: 4.9,
        reviews: 3892,
        icon: "🔑",
        prime: true,
        delivery: "FREE One-Day Delivery"
    },
    {
        id: 3,
        title: "Quantum Zero-Latency Cybernetic Headset & Bone Transducer",
        category: "wearables",
        price: 299.00,
        rating: 4.6,
        reviews: 940,
        icon: "🎧",
        prime: true,
        delivery: "FREE Delivery by Sunday"
    },
    {
        id: 4,
        title: "NVMe M.2 4TB Hardware-Encrypted Ultra-Speed Solid State Drive",
        category: "hardware",
        price: 389.99,
        rating: 4.7,
        reviews: 2150,
        icon: "💾",
        prime: true,
        delivery: "FREE Delivery Tomorrow"
    },
    {
        id: 5,
        title: "Tactical Faraday Shield Backpack (100% EMP & RF Blocking)",
        category: "accessories",
        price: 149.95,
        rating: 4.8,
        reviews: 620,
        icon: "🎒",
        prime: true,
        delivery: "FREE Delivery Tomorrow"
    },
    {
        id: 6,
        title: "Smart Neural Feedback Smart Ring (Sleep, Strain, HRV & SPO2)",
        category: "wearables",
        price: 249.00,
        rating: 4.5,
        reviews: 1110,
        icon: "💍",
        prime: true,
        delivery: "FREE Two-Day Delivery"
    },
    {
        id: 7,
        title: "4K HDR 144Hz Portable Cyberpunk Monitor with Type-C Hub",
        category: "hardware",
        price: 229.99,
        rating: 4.7,
        reviews: 870,
        icon: "🖥️",
        prime: true,
        delivery: "FREE Delivery by Friday"
    },
    {
        id: 8,
        title: "Mechanical Hot-Swap 65% Keyboard with Custom PBT Keycaps",
        category: "accessories",
        price: 119.00,
        rating: 4.9,
        reviews: 4500,
        icon: "⌨️",
        prime: true,
        delivery: "FREE One-Day Delivery"
    }
];

let cart = [];

function renderProducts(items) {
    const grid = document.getElementById('productGrid');
    if (!grid) return;
    
    grid.innerHTML = items.map(p => `
        <div class="product-card">
            <div>
                <div class="card-img-wrap">${p.icon}</div>
                <div class="product-title" onclick="showToast('${p.title}')">${p.title}</div>
                <div class="rating-row">
                    <span class="stars">★★★★★</span>
                    <span class="review-count">${p.rating} (${p.reviews.toLocaleString()})</span>
                </div>
                <div class="price-row">
                    <span class="dollar-sign">$</span>
                    <span class="price-val">${p.price.toFixed(2)}</span>
                </div>
                ${p.prime ? '<div class="prime-badge">⚡prime</div>' : ''}
                <div class="delivery-text">${p.delivery}</div>
            </div>
            <button class="btn-add-cart" onclick="addToCart(${p.id})">Add to Cart</button>
        </div>
    `).join('');

    const countEl = document.getElementById('resultsCount');
    if (countEl) countEl.textContent = `Showing ${items.length} products`;
}

function addToCart(productId) {
    const item = products.find(p => p.id === productId);
    if (!item) return;

    const existing = cart.find(c => c.id === productId);
    if (existing) {
        existing.qty += 1;
    } else {
        cart.push({ ...item, qty: 1 });
    }

    updateCartUI();
    showToast(`Added: ${item.title.substring(0, 36)}...`);
}

function updateCartUI() {
    const totalQty = cart.reduce((sum, item) => sum + item.qty, 0);
    const totalPrice = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);

    const counter = document.getElementById('cartCounter');
    if (counter) counter.textContent = totalQty;

    const drawerCount = document.getElementById('drawerItemCount');
    if (drawerCount) drawerCount.textContent = totalQty;

    const subtotalEl = document.getElementById('cartSubtotal');
    if (subtotalEl) subtotalEl.textContent = `$${totalPrice.toFixed(2)}`;

    const list = document.getElementById('cartItemsList');
    if (!list) return;

    if (cart.length === 0) {
        list.innerHTML = '<div class="empty-cart-msg">Your CyberStore cart is empty.</div>';
    } else {
        list.innerHTML = cart.map(item => `
            <div class="cart-item">
                <div class="cart-item-icon">${item.icon}</div>
                <div class="cart-item-info">
                    <div class="cart-item-title">${item.title}</div>
                    <div class="cart-item-price">$${(item.price * item.qty).toFixed(2)}</div>
                    <div class="cart-item-qty">
                        <span>Qty:</span>
                        <button class="qty-btn" onclick="changeQty(${item.id}, -1)">-</button>
                        <strong>${item.qty}</strong>
                        <button class="qty-btn" onclick="changeQty(${item.id}, 1)">+</button>
                    </div>
                </div>
            </div>
        `).join('');
    }
}

function changeQty(productId, delta) {
    const item = cart.find(c => c.id === productId);
    if (!item) return;

    item.qty += delta;
    if (item.qty <= 0) {
        cart = cart.filter(c => c.id !== productId);
    }
    updateCartUI();
}

function showToast(msg) {
    const toast = document.getElementById('toastMsg');
    if (!toast) return;
    toast.textContent = msg;
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 2800);
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    renderProducts(products);

    const openBtn = document.getElementById('openCartBtn');
    const closeBtn = document.getElementById('closeCartBtn');
    const overlay = document.getElementById('cartOverlay');

    if (openBtn && overlay) {
        openBtn.addEventListener('click', () => {
            overlay.style.display = 'flex';
        });
    }

    if (closeBtn && overlay) {
        closeBtn.addEventListener('click', () => {
            overlay.style.display = 'none';
        });
    }

    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.style.display = 'none';
        });
    }

    const searchInput = document.getElementById('searchInput');
    const catSelect = document.getElementById('catSelect');

    const handleFilter = () => {
        const query = (searchInput.value || '').toLowerCase().trim();
        const cat = catSelect.value;

        const filtered = products.filter(p => {
            const matchesCat = (cat === 'all' || p.category === cat);
            const matchesQuery = p.title.toLowerCase().includes(query);
            return matchesCat && matchesQuery;
        });

        renderProducts(filtered);
    };

    if (searchInput) searchInput.addEventListener('input', handleFilter);
    if (catSelect) catSelect.addEventListener('change', handleFilter);

    const checkoutBtn = document.getElementById('checkoutBtn');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', () => {
            if (cart.length === 0) {
                alert('Your cart is empty! Add products first.');
            } else {
                alert(`Order confirmed! Total: $${cart.reduce((s, i) => s + (i.price * i.qty), 0).toFixed(2)}\\nSecured with Air-Gapped Zero-Knowledge Token.`);
                cart = [];
                updateCartUI();
                overlay.style.display = 'none';
            }
        });
    }
});
"""

p.joinpath("app.js").write_text(js, encoding="utf-8")
print("SUCCESS: amazon_store_demo fully generated!")
