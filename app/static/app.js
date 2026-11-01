const state = {
  screen: "add",
  kind: "spending",
  month: initialMonth(),
  categories: [],
  transactions: [],
  editing: null,
};

function todayISO() {
  const now = new Date();
  return isoDate(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
}

function initialMonth() {
  const stored = sessionStorage.getItem("budget-month");
  return /^\d{4}-\d{2}$/.test(stored || "") ? stored : currentMonth();
}

function isoDate(year, month, day) {
  return `${year}-${pad(month)}-${pad(day)}`;
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function shiftMonth(ym, delta) {
  const [year, month] = ym.split("-").map(Number);
  const next = new Date(year, month - 1 + delta, 1);
  return `${next.getFullYear()}-${pad(next.getMonth() + 1)}`;
}

function monthTitle(ym) {
  const [year, month] = ym.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-CA", {
    month: "long",
    year: "numeric",
  });
}

function shortDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
  });
}

function toCents(amount) {
  const negative = String(amount).startsWith("-");
  const [whole, fraction = "00"] = String(amount).replace("-", "").split(".");
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0").slice(0, 2));
  return negative ? -cents : cents;
}

function moneyFromCents(cents) {
  const sign = cents < 0 ? "−" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100).toLocaleString("en-CA");
  const rem = String(abs % 100).padStart(2, "0");
  return `${sign}$${dollars}.${rem}`;
}

function money(amount) {
  return moneyFromCents(toCents(amount));
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new Error("Could not reach the budget site.");
  }
  if (response.status === 401 && !path.endsWith("/api/login")) {
    showLogin();
    throw new Error("Sign in required.");
  }
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    const detail = data && data.detail;
    const message = typeof detail === "string" ? detail : "Check the entry and try again.";
    throw new Error(message);
  }
  return data;
}

function showLogin() {
  document.querySelector("#app-view").hidden = true;
  document.querySelector("#login-view").hidden = false;
  document.querySelector("#login-password").focus();
}

async function enterApp() {
  document.querySelector("#login-view").hidden = true;
  document.querySelector("#app-view").hidden = false;
  const date = document.querySelector("#entry-date");
  if (!date.value) date.value = todayISO();
  await loadCategories();
  setKind(state.kind);
  await showScreen("add");
}

function setKind(kind) {
  state.kind = kind;
  document.querySelectorAll("[data-kind]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.kind === kind));
  });
  renderCategorySelect();
  renderCategoryLists();
}

async function loadCategories() {
  state.categories = await api("/api/categories");
  renderCategorySelect();
  renderCategoryLists();
}

function renderCategorySelect(preferredId) {
  const select = document.querySelector("#entry-category");
  const preferred = preferredId ?? (state.editing ? state.editing.category_id : Number(select.value));
  const options = state.categories.filter(
    (category) => category.kind === state.kind && (!category.hidden || category.id === preferred)
  );
  select.replaceChildren();
  for (const category of options) {
    const option = document.createElement("option");
    option.value = String(category.id);
    option.textContent = category.hidden ? `${category.name} (hidden)` : category.name;
    select.append(option);
  }
  if (options.some((category) => category.id === preferred)) {
    select.value = String(preferred);
  }
}

function renderCategoryLists() {
  const active = document.querySelector("#active-categories");
  const hidden = document.querySelector("#hidden-categories");
  const rows = state.categories.filter((category) => category.kind === state.kind);
  fillCategoryList(active, rows.filter((category) => !category.hidden), "Remove", "hide");
  fillCategoryList(hidden, rows.filter((category) => category.hidden), "Put back", "restore");
  if (!active.children.length) active.append(emptyItem("None on the dropdown."));
  if (!hidden.children.length) hidden.append(emptyItem("None hidden."));
}

function fillCategoryList(list, rows, label, action) {
  list.replaceChildren();
  for (const category of rows) {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = category.name;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "text-button";
    button.dataset[action] = String(category.id);
    button.textContent = label;
    item.append(name, button);
    list.append(item);
  }
}

function emptyItem(text) {
  const item = document.createElement("li");
  const name = document.createElement("span");
  name.className = "hint";
  name.textContent = text;
  item.append(name);
  return item;
}

function resetForm() {
  state.editing = null;
  document.querySelector("#entry-date").value = todayISO();
  document.querySelector("#entry-amount").value = "";
  document.querySelector("#entry-notes").value = "";
  document.querySelector("#form-error").textContent = "";
  document.querySelector("#save-entry").textContent = "Save entry";
  document.querySelector("#cancel-edit").hidden = true;
  document.querySelector("#delete-entry").hidden = true;
  setKind("spending");
}

function renderMonthLabels() {
  const label = monthTitle(state.month);
  document.querySelectorAll(".month-label").forEach((node) => {
    node.textContent = label;
  });
}

async function showScreen(name, { fromTab = false } = {}) {
  if (fromTab && name === "add") resetForm();
  state.screen = name;
  for (const screen of ["add", "month", "summary", "export"]) {
    document.querySelector(`#screen-${screen}`).hidden = screen !== name;
  }
  document.querySelectorAll(".tab").forEach((tab) => {
    if (tab.dataset.screen === name) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  });
  const titles = {
    add: state.editing ? "Edit entry" : "Add",
    month: "This month",
    summary: "Summary",
    export: "Export",
  };
  document.querySelector("#screen-title").textContent = titles[name];
  renderMonthLabels();
  window.scrollTo(0, 0);
  if (name === "month") await loadMonth();
  if (name === "summary") await loadSummary();
  if (name === "export") await loadPreview();
}

async function changeMonth(delta) {
  state.month = shiftMonth(state.month, delta);
  sessionStorage.setItem("budget-month", state.month);
  renderMonthLabels();
  if (state.screen === "month") await loadMonth();
  if (state.screen === "summary") await loadSummary();
  if (state.screen === "export") await loadPreview();
}

async function loadMonth() {
  const list = document.querySelector("#month-list");
  const empty = document.querySelector("#month-empty");
  const count = document.querySelector("#month-count");
  try {
    state.transactions = await api(`/api/transactions?month=${state.month}`);
  } catch (error) {
    state.transactions = [];
    list.replaceChildren();
    empty.hidden = false;
    empty.textContent = error.message;
    count.textContent = "";
    document.querySelector("#month-hint").hidden = true;
    return;
  }
  list.replaceChildren();
  empty.hidden = state.transactions.length > 0;
  empty.textContent = "No entries this month.";
  document.querySelector("#month-hint").hidden = state.transactions.length === 0;
  const noun = state.transactions.length === 1 ? "entry" : "entries";
  count.textContent = `${state.transactions.length} ${noun}`;
  for (const tx of state.transactions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "entry";
    button.dataset.edit = String(tx.id);
    const date = document.createElement("span");
    date.className = "entry-date";
    date.textContent = shortDate(tx.date);
    const main = document.createElement("span");
    main.className = "entry-main";
    const category = document.createElement("span");
    category.className = "entry-cat";
    category.textContent = tx.category;
    main.append(category);
    if (tx.notes) {
      const note = document.createElement("span");
      note.className = "entry-note";
      note.textContent = tx.notes;
      main.append(note);
    }
    const amount = document.createElement("span");
    amount.className = `entry-amt ${tx.kind}`;
    amount.textContent = money(tx.amount);
    button.append(date, main, amount);
    list.append(button);
  }
}

function differenceSentence(totals) {
  const income = toCents(totals.income);
  const spending = toCents(totals.spending);
  const net = income - spending;
  if (income === 0 && spending === 0) return "No income or spending this month.";
  if (net === 0) return "Income and spending match.";
  if (net > 0) return `Income is ${moneyFromCents(net)} more than spending.`;
  return `Spending is ${moneyFromCents(-net)} more than income.`;
}

async function loadSummary() {
  let data;
  try {
    data = await api(`/api/summary?month=${state.month}`);
  } catch (error) {
    document.querySelector("#difference-text").textContent = error.message;
    return;
  }
  document.querySelector("#total-income").textContent = money(data.totals.income);
  document.querySelector("#total-spending").textContent = money(data.totals.spending);
  const net = document.querySelector("#total-net");
  const netCents = toCents(data.totals.net);
  net.textContent = money(data.totals.net);
  net.classList.toggle("income", netCents > 0);
  net.classList.toggle("spending", netCents < 0);
  document.querySelector("#difference-text").textContent = differenceSentence(data.totals);
  renderCompare(data.totals);
  renderBars(document.querySelector("#income-bars"), data.income_by_category, "income");
  renderBars(document.querySelector("#spending-bars"), data.spending_by_category, "spending");
}

function renderCompare(totals) {
  const box = document.querySelector("#compare");
  box.replaceChildren();
  const income = toCents(totals.income);
  const spending = toCents(totals.spending);
  if (income === 0 && spending === 0) return;
  const max = Math.max(income, spending);
  box.append(
    compareRow("Income", income, max, "income"),
    compareRow("Spending", spending, max, "spending")
  );
}

function compareRow(label, cents, max, kind) {
  const row = document.createElement("div");
  row.className = "compare-row stack";
  row.append(barLabel(label, moneyFromCents(cents)), barTrack(cents, max, kind));
  return row;
}

function renderBars(container, rows, kind) {
  container.replaceChildren();
  if (!rows.length) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = "None this month.";
    container.append(note);
    return;
  }
  const max = Math.max(...rows.map((row) => toCents(row.total)));
  for (const row of rows) {
    const wrap = document.createElement("div");
    wrap.className = "bar-row stack";
    const noun = row.count === 1 ? "entry" : "entries";
    wrap.append(
      barLabel(row.category, `${money(row.total)} · ${row.count} ${noun}`),
      barTrack(toCents(row.total), max, kind)
    );
    container.append(wrap);
  }
}

function barLabel(name, amount) {
  const top = document.createElement("div");
  top.className = "bar-label";
  const label = document.createElement("span");
  label.textContent = name;
  const value = document.createElement("span");
  value.textContent = amount;
  top.append(label, value);
  return top;
}

function barTrack(cents, max, kind) {
  const track = document.createElement("div");
  track.className = "track";
  const fill = document.createElement("div");
  fill.className = `fill ${kind}`;
  fill.style.width = max === 0 ? "0%" : `${(cents / max) * 100}%`;
  track.append(fill);
  return track;
}

async function fetchExport(format) {
  const response = await fetch(
    `/api/export?month=${encodeURIComponent(state.month)}&format=${format}`
  );
  if (response.status === 401) {
    showLogin();
    throw new Error("Sign in required.");
  }
  const text = await response.text();
  if (!response.ok) {
    let message = "Could not build the report.";
    try {
      const data = JSON.parse(text);
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      /* The body was not JSON. */
    }
    throw new Error(message);
  }
  return text;
}

async function loadPreview() {
  const preview = document.querySelector("#report-preview");
  try {
    preview.textContent = await fetchExport("md");
  } catch (error) {
    preview.textContent = error.message;
  }
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function downloadReport(format) {
  const preview = document.querySelector("#report-preview");
  try {
    const text = await fetchExport(format);
    const type = format === "json" ? "application/json" : "text/markdown";
    downloadFile(`budget-${state.month}.${format}`, text, type);
    if (format === "md") preview.textContent = text;
  } catch (error) {
    preview.textContent = error.message;
  }
}

async function saveEntry(event) {
  event.preventDefault();
  const error = document.querySelector("#form-error");
  error.textContent = "";
  const select = document.querySelector("#entry-category");
  if (!select.value) {
    error.textContent = "Add a category before saving.";
    return;
  }
  const payload = {
    date: document.querySelector("#entry-date").value,
    amount: document.querySelector("#entry-amount").value,
    kind: state.kind,
    category_id: Number(select.value),
    notes: document.querySelector("#entry-notes").value,
  };
  const button = document.querySelector("#save-entry");
  button.disabled = true;
  try {
    if (state.editing) {
      await api(`/api/transactions/${state.editing.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      rememberMonth(payload.date);
      resetForm();
      await showScreen("month");
    } else {
      await api("/api/transactions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      rememberMonth(payload.date);
      document.querySelector("#entry-amount").value = "";
      document.querySelector("#entry-notes").value = "";
      document.querySelector("#entry-amount").focus();
    }
  } catch (err) {
    error.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

function rememberMonth(isoDateValue) {
  state.month = isoDateValue.slice(0, 7);
  sessionStorage.setItem("budget-month", state.month);
  renderMonthLabels();
}

async function deleteEntry() {
  if (!state.editing) return;
  if (!window.confirm(`Delete this ${state.editing.category} entry?`)) return;
  try {
    await api(`/api/transactions/${state.editing.id}`, { method: "DELETE" });
    resetForm();
    await showScreen("month");
  } catch (error) {
    document.querySelector("#form-error").textContent = error.message;
  }
}

function startEdit(tx) {
  state.editing = tx;
  document.querySelector("#entry-date").value = tx.date;
  document.querySelector("#entry-amount").value = tx.amount;
  document.querySelector("#entry-notes").value = tx.notes;
  document.querySelector("#form-error").textContent = "";
  document.querySelector("#save-entry").textContent = "Save changes";
  document.querySelector("#cancel-edit").hidden = false;
  document.querySelector("#delete-entry").hidden = false;
  setKind(tx.kind);
  renderCategorySelect(tx.category_id);
  showScreen("add");
}

async function setHidden(id, hidden) {
  const category = state.categories.find((item) => item.id === id);
  if (!category) return;
  if (hidden) {
    const ok = window.confirm(
      `Remove ${category.name} from the dropdown? Entries that already use it will keep the category.`
    );
    if (!ok) return;
  }
  document.querySelector("#category-error").textContent = "";
  try {
    await api(`/api/categories/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ hidden }),
    });
    await loadCategories();
  } catch (error) {
    document.querySelector("#category-error").textContent = error.message;
  }
}

async function addCategory(event) {
  event.preventDefault();
  const input = document.querySelector("#new-category");
  const error = document.querySelector("#category-error");
  error.textContent = "";
  try {
    const created = await api("/api/categories", {
      method: "POST",
      body: JSON.stringify({ name: input.value, kind: state.kind }),
    });
    input.value = "";
    await loadCategories();
    renderCategorySelect(created.id);
  } catch (err) {
    error.textContent = err.message;
  }
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#login-error");
  error.textContent = "";
  const password = document.querySelector("#login-password").value;
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    document.querySelector("#login-password").value = "";
    await enterApp();
  } catch (err) {
    error.textContent = err.message;
  }
});

document.querySelector("#entry-form").addEventListener("submit", saveEntry);
document.querySelector("#cancel-edit").addEventListener("click", async () => {
  resetForm();
  await showScreen("month");
});
document.querySelector("#delete-entry").addEventListener("click", deleteEntry);
document.querySelector("#category-form").addEventListener("submit", addCategory);
document.querySelector(".segment").addEventListener("click", (event) => {
  const button = event.target.closest("[data-kind]");
  if (button) setKind(button.dataset.kind);
});
document.querySelector("#month-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-edit]");
  if (!button) return;
  const tx = state.transactions.find((row) => row.id === Number(button.dataset.edit));
  if (tx) startEdit(tx);
});
document.querySelector("#download-md").addEventListener("click", () => downloadReport("md"));
document.querySelector("#download-json").addEventListener("click", () => downloadReport("json"));
document.querySelector("#lock-button").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  showLogin();
});

document.addEventListener("click", async (event) => {
  const tab = event.target.closest(".tab");
  if (tab) {
    await showScreen(tab.dataset.screen, { fromTab: true });
    return;
  }
  const step = event.target.closest("[data-month-step]");
  if (step) {
    await changeMonth(Number(step.dataset.monthStep));
    return;
  }
  const hide = event.target.closest("[data-hide]");
  if (hide) {
    await setHidden(Number(hide.dataset.hide), true);
    return;
  }
  const restore = event.target.closest("[data-restore]");
  if (restore) await setHidden(Number(restore.dataset.restore), false);
});

fetch("/api/session")
  .then(async (response) => {
    if (response.ok) await enterApp();
    else showLogin();
  })
  .catch(() => showLogin());
