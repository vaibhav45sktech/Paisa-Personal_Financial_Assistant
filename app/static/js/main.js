// ------- Profile Setup: pill-select + live totals -------
(function () {
  const pillContainer = document.querySelector(".pill-select");
  if (pillContainer) {
    const targetId = pillContainer.getAttribute("data-target");
    const hidden = document.getElementById(targetId);
    pillContainer.addEventListener("click", (e) => {
      const btn = e.target.closest(".pill-option");
      if (!btn) return;
      pillContainer.querySelectorAll(".pill-option").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      if (hidden) hidden.value = btn.getAttribute("data-value");
    });
  }

  function formatINR(n) {
    n = Math.round(Number(n) || 0);
    const s = n.toString();
    const isNeg = s.startsWith("-");
    const abs = isNeg ? s.slice(1) : s;
    if (abs.length <= 3) return (isNeg ? "-₹" : "₹") + abs;
    const last3 = abs.slice(-3);
    const other = abs.slice(0, -3);
    const grouped = other.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    return (isNeg ? "-₹" : "₹") + grouped + "," + last3;
  }

  const budgetInputs = document.querySelectorAll(".budget-input");
  const totalEl = document.getElementById("budgetTotal");
  const savingsEl = document.getElementById("estimatedSavings");
  const incomeEl = document.getElementById("income_amount");
  function recalc() {
    if (!totalEl) return;
    let total = 0;
    budgetInputs.forEach((i) => (total += Number(i.value) || 0));
    totalEl.textContent = formatINR(total);
    if (savingsEl && incomeEl) {
      const savings = (Number(incomeEl.value) || 0) - total;
      savingsEl.textContent = formatINR(savings);
      savingsEl.classList.toggle("text-danger", savings < 0);
    }
  }
  budgetInputs.forEach((i) => i.addEventListener("input", recalc));
  if (incomeEl) incomeEl.addEventListener("input", recalc);
  recalc();
})();

// ------- Goals Setup: add/remove goal cards -------
(function () {
  const addBtn = document.getElementById("addGoalBtn");
  const container = document.getElementById("goalsContainer");
  const tpl = document.getElementById("goalTemplate");
  if (!addBtn || !container || !tpl) return;
  function nextIndex() { return container.querySelectorAll(".goal-card").length; }
  addBtn.addEventListener("click", () => {
    const idx = nextIndex();
    let html = tpl.innerHTML.replace(/__INDEX_1__/g, idx + 1).replace(/__INDEX__/g, idx);
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html.trim();
    container.appendChild(wrapper.firstChild);
    wireCard(container.lastElementChild);
  });
  function wireCard(card) {
    if (!card) return;
    const removeBtn = card.querySelector(".remove-goal");
    if (removeBtn) removeBtn.addEventListener("click", () => { card.remove(); renumber(); });
    const nameInput = card.querySelector(".goal-name");
    const preview = card.querySelector(".goal-preview");
    if (nameInput && preview) {
      nameInput.addEventListener("input", () => {
        preview.textContent = nameInput.value.trim() || "Untitled goal";
      });
    }
  }
  function renumber() {
    container.querySelectorAll(".goal-card").forEach((card, i) => {
      const label = card.querySelector(".text-uppercase.small");
      if (label) label.textContent = "Goal #" + (i + 1);
      card.querySelectorAll("[name^='goals-']").forEach((el) => {
        el.setAttribute("name", el.getAttribute("name").replace(/^goals-\d+-/, "goals-" + i + "-"));
      });
      card.querySelectorAll("[id^='prio-']").forEach((el) => {
        el.setAttribute("id", el.getAttribute("id").replace(/^prio-\d+-/, "prio-" + i + "-"));
      });
      card.querySelectorAll("[for^='prio-']").forEach((el) => {
        el.setAttribute("for", el.getAttribute("for").replace(/^prio-\d+-/, "prio-" + i + "-"));
      });
    });
  }
  container.querySelectorAll(".goal-card").forEach(wireCard);
})();

// ------- Confetti on excellent health score -------
(function () {
  const scoreEl = document.getElementById("healthScoreNum");
  if (!scoreEl) return;
  const score = parseFloat(scoreEl.textContent);
  if (score < 85) return;
  const colors = ["#f97316","#14b8a6","#f59e0b","#22c55e","#ec4899","#8b5cf6"];
  for (let i = 0; i < 60; i++) {
    const p = document.createElement("div");
    p.className = "confetti-piece";
    p.style.left = Math.random() * 100 + "vw";
    p.style.background = colors[Math.floor(Math.random() * colors.length)];
    p.style.animationDelay = (Math.random() * 1.5) + "s";
    p.style.transform = "rotate(" + Math.random() * 360 + "deg)";
    document.body.appendChild(p);
    setTimeout(() => p.remove(), 5000);
  }
})();

// ------- Coin-drop sparkle on primary buttons -------
document.addEventListener("click", (e) => {
  const b = e.target.closest(".btn-primary");
  if (!b) return;
  const s = document.createElement("span");
  s.textContent = "💸";
  s.style.cssText = "position:fixed;pointer-events:none;font-size:20px;z-index:9999;transition:transform 700ms ease-out, opacity 700ms;left:" + e.clientX + "px;top:" + e.clientY + "px;";
  document.body.appendChild(s);
  requestAnimationFrame(() => {
    s.style.transform = "translate(-50%,-80px) rotate(30deg)";
    s.style.opacity = "0";
  });
  setTimeout(() => s.remove(), 800);
});
