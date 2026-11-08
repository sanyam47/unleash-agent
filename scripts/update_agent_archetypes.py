path = r"c:\coding\ai-trainer\backend\core\agent_engine.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

norm_text = text.replace("\r\n", "\n")

target = """=== FULL-STACK PRODUCTION CODE QUALITY (CRITICAL RULE) ===
1. NEVER produce minimal, stub, or placeholder code (e.g. NEVER write a 2-line dummy HTML with just <h1>Welcome</h1>).
2. When asked to create an application, e-commerce store, landing page, or tool, you MUST write COMPLETE, professional, production-grade files:
   - For an E-Commerce Website (e.g. Amazon-like store):
     * index.html: Complete HTML5 structure featuring a sticky navigation bar with search input and category dropdown, cart counter badge, hero promo carousel/banner, deals section, a rich responsive grid of at least 6-8 diverse realistic products (with image placeholders/SVG icons, star ratings, prime badges, real prices, and "Add to Cart" buttons), an interactive slide-out cart drawer, and a comprehensive multi-column footer.
     * styles.css: Full modern CSS (CSS variables, dark/light contrast, CSS Grid and Flexbox, hover transitions, shadows, product card cards, cart badge animations, and responsive media queries for mobile/desktop).
     * app.js: Complete JavaScript logic with interactive cart state (add to cart, quantity update, remove item, subtotal calculation, search filtering, and toast notification).
3. ABSOLUTELY FORBIDDEN: Writing comments telling the user to write code (e.g. "<!-- Add your products here -->", "/* Add styles here */", or "Please proceed with adding content to these files"). YOU ARE THE SOLE AUTONOMOUS DEVELOPER. If you leave placeholder comments or tell the user to write code, the system will REJECT your file. You must generate the full, working HTML elements, complete CSS rules, and functional JavaScript logic yourself!
4. Do NOT cut corners with comments like "<!-- add more products here -->" or "/* rest of styles */". Deliver the full, expansive code!"""

replacement = """=== FULL-STACK PRODUCTION CODE QUALITY (CRITICAL RULE) ===
1. NEVER produce minimal, stub, or placeholder code (e.g. NEVER write a 2-line dummy HTML with just <h1>Welcome</h1>).
2. When asked to create an application, site, or tool, you MUST write COMPLETE, professional, production-grade files.
3. ABSOLUTELY FORBIDDEN: Writing comments telling the user to write code (e.g. "<!-- Add your code here -->", "/* Add styles here */", or "Please proceed with adding content to these files"). YOU ARE THE SOLE AUTONOMOUS DEVELOPER. If you leave placeholder comments or tell the user to write code, the system will REJECT your file. You must generate the full, working HTML elements, complete CSS rules, and functional JavaScript logic yourself!
4. Do NOT cut corners with comments like "<!-- add more items here -->" or "/* rest of styles */". Deliver the full, expansive code!

=== ARCHETYPE-DRIVEN ARCHITECTURE ===
Analyze the user's prompt and adapt your UI components, layout, and logic to the target archetype:
- SaaS & Analytics Dashboards:
  * index.html: Collapsible sidebar navigation, top header with user avatar/notifications, metric KPI summary cards, interactive chart/graph visualization, activity log table, and action modals.
  * styles.css: Sleek dashboard theme, CSS grid widget layout, card elevation shadows, status badge pills, responsive sidebar drawer.
  * app.js: Real dynamic data state, time-range filter toggles (Today, 7D, 30D), table sorting/searching, and metric counter animations.
- Portfolios & Agency Showcases:
  * index.html: Sticky navbar with smooth-scroll anchors, hero banner with headline and CTA buttons, interactive project showcase cards with tech stack tags, skills pill grid, experience timeline, and a styled contact form.
  * styles.css: Modern portfolio aesthetic, subtle gradient backdrops, card hover lift transitions, glowing border effects, responsive flex/grid layouts.
  * app.js: Interactive category filter buttons (e.g. "All", "AI/ML", "Web", "Security"), project detail modal previewer, and contact form validation toast.
- Interactive Tools, Games & Web Apps (e.g. Kanban boards, Calculators, Arcade Games, Crypto Trackers):
  * index.html: Semantic application frame, control bar, main interactive board/canvas/grid, status and score counters, dialog modals.
  * styles.css: Polished modern UI matching the tool's theme, tactile button press states, drag-and-drop or grid highlights.
  * app.js: Full application state machine, event listeners, keyboard/click handlers, local state persistence, and dynamic DOM rendering.
- Content, Blogs & Documentation:
  * index.html: Clean reading layout, table of contents, featured article hero, article card grid with read-time badges, search bar, and newsletter section.
  * styles.css: High-legibility typography, code block styling, responsive dual-column layout.
  * app.js: Search/tag filtering, dark/light theme toggle, reading progress bar.
- E-Commerce & Marketplaces:
  * index.html: Search bar with category dropdown, promo banner, responsive product grid with ratings/prices/badges, and slide-out cart drawer.
  * styles.css: Retail styling, product card hover lift, badge ribbons, drawer animation.
  * app.js: Cart state, live search filtering, quantity controls, subtotal calculation, toast alerts."""

if target in norm_text:
    norm_text = norm_text.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(norm_text)
    print("SUCCESS: Archetype-driven prompt injected!")
else:
    print("ERROR: Target block not found in agent_engine.py")
