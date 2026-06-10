const state = {
  business: null,
  media: [],
  trends: [],
  runs: [],
  activeView: "accountView",
  activeTag: "all",
  sortBy: "relevance",
};

const CANONICAL_TREND_TAGS = ["sports", "politics", "crypto", "tech", "economy", "culture", "general"];

const elements = {
  sidebarBusinessName: document.querySelector("#sidebarBusinessName"),
  sidebarIndustry: document.querySelector("#sidebarIndustry"),
  navButtons: document.querySelectorAll("[data-view-target]"),
  views: document.querySelectorAll(".view"),
  accountStatus: document.querySelector("#accountStatus"),
  businessForm: document.querySelector("#businessForm"),
  businessNameInput: document.querySelector("#businessNameInput"),
  industryInput: document.querySelector("#industryInput"),
  startedDateInput: document.querySelector("#startedDateInput"),
  audienceInput: document.querySelector("#audienceInput"),
  whatTheyDoInput: document.querySelector("#whatTheyDoInput"),
  keywordsInput: document.querySelector("#keywordsInput"),
  preferredTagsList: document.querySelector("#preferredTagsList"),
  factsEditorList: document.querySelector("#factsEditorList"),
  addFactButton: document.querySelector("#addFactButton"),
  mediaInput: document.querySelector("#mediaInput"),
  mediaList: document.querySelector("#mediaList"),
  findTrendsButton: document.querySelector("#findTrendsButton"),
  trendStatus: document.querySelector("#trendStatus"),
  trendCount: document.querySelector("#trendCount"),
  visibleTrendCount: document.querySelector("#visibleTrendCount"),
  lastRun: document.querySelector("#lastRun"),
  sortSelect: document.querySelector("#sortSelect"),
  tagFilters: document.querySelector("#tagFilters"),
  trendTable: document.querySelector("#trendTable"),
};

init();

async function init() {
  bindEvents();
  await refreshAccount();
}

function bindEvents() {
  elements.navButtons.forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.viewTarget));
  });
  elements.businessForm.addEventListener("submit", saveBusiness);
  elements.addFactButton.addEventListener("click", () => {
    state.business.facts.push({ id: crypto.randomUUID(), label: "", value: "" });
    renderFactsEditor();
  });
  elements.mediaInput.addEventListener("change", uploadMedia);
  elements.findTrendsButton.addEventListener("click", findTrends);
  elements.sortSelect.addEventListener("change", () => {
    state.sortBy = elements.sortSelect.value;
    renderTrends();
  });
}

async function refreshAccount() {
  const payload = await api("/api/account");
  state.business = payload.business;
  state.media = payload.media || [];
  state.trends = payload.latestTrends || [];
  state.runs = payload.trendRuns || [];
  render();
}

function switchView(viewId) {
  state.activeView = viewId;
  elements.navButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewTarget === viewId);
  });
  elements.views.forEach((view) => {
    view.classList.toggle("is-active", view.id === viewId);
  });
}

async function saveBusiness(event) {
  event.preventDefault();
  setAccountStatus("Saving");
  const updates = {
    businessName: elements.businessNameInput.value.trim(),
    industry: elements.industryInput.value.trim(),
    startedDate: elements.startedDateInput.value,
    audience: elements.audienceInput.value.trim(),
    whatTheyDo: elements.whatTheyDoInput.value.trim(),
    keywords: elements.keywordsInput.value,
    preferredTrendTags: readPreferredTags(),
    facts: readFactsEditor(),
  };
  const payload = await api("/api/business", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  state.business = payload.business;
  setAccountStatus("Saved");
  renderAccount();
}

async function uploadMedia(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  setAccountStatus("Uploading");
  const formData = new FormData();
  formData.append("media", file);
  const payload = await api("/api/media", { method: "POST", body: formData });
  state.media = payload.media;
  elements.mediaInput.value = "";
  setAccountStatus("Ready");
  renderMedia();
}

async function deleteMedia(id) {
  setAccountStatus("Deleting");
  const payload = await api(`/api/media/${encodeURIComponent(id)}`, { method: "DELETE" });
  state.media = payload.media;
  setAccountStatus("Ready");
  renderMedia();
}

async function findTrends() {
  setTrendStatus("Finding");
  elements.findTrendsButton.disabled = true;
  try {
    const payload = await api("/api/trends/find", { method: "POST" });
    state.trends = payload.trends;
    state.runs = [payload.run, ...state.runs].slice(0, 10);
    state.activeTag = "all";
    setTrendStatus("Saved");
    renderTrends();
    renderMetrics();
  } catch (error) {
    console.error(error);
    setTrendStatus("Error");
  } finally {
    elements.findTrendsButton.disabled = false;
  }
}

function render() {
  renderAccount();
  renderMedia();
  renderMetrics();
  renderTrends();
}

function renderAccount() {
  elements.sidebarBusinessName.textContent = state.business.businessName;
  elements.sidebarIndustry.textContent = state.business.industry;
  elements.businessNameInput.value = state.business.businessName || "";
  elements.industryInput.value = state.business.industry || "";
  elements.startedDateInput.value = state.business.startedDate || "";
  elements.audienceInput.value = state.business.audience || "";
  elements.whatTheyDoInput.value = state.business.whatTheyDo || "";
  elements.keywordsInput.value = (state.business.keywords || []).join(", ");
  renderPreferredTags();
  renderFactsEditor();
}

function renderPreferredTags() {
  const selectedTags = new Set(state.business.preferredTrendTags || []);
  elements.preferredTagsList.innerHTML = CANONICAL_TREND_TAGS.map(
    (tag) => `
      <label class="preference-option">
        <input type="checkbox" value="${escapeHtml(tag)}" ${selectedTags.has(tag) ? "checked" : ""} />
        <span>${escapeHtml(tag)}</span>
      </label>
    `
  ).join("");
}

function readPreferredTags() {
  return Array.from(elements.preferredTagsList.querySelectorAll("input:checked")).map((input) => input.value);
}

function renderFactsEditor() {
  elements.factsEditorList.innerHTML = (state.business.facts || [])
    .map(
      (fact) => `
        <div class="fact-row" data-fact-id="${fact.id}">
          <input data-fact-label value="${escapeHtml(fact.label)}" placeholder="Label" />
          <input data-fact-value value="${escapeHtml(fact.value)}" placeholder="Value" />
          <button class="delete-button" type="button" data-delete-fact="${fact.id}" title="Delete fact">×</button>
        </div>
      `
    )
    .join("");

  document.querySelectorAll("[data-delete-fact]").forEach((button) => {
    button.addEventListener("click", () => {
      state.business.facts = state.business.facts.filter((fact) => fact.id !== button.dataset.deleteFact);
      renderFactsEditor();
    });
  });
}

function readFactsEditor() {
  return Array.from(document.querySelectorAll(".fact-row"))
    .map((row) => ({
      id: row.dataset.factId,
      label: row.querySelector("[data-fact-label]").value.trim(),
      value: row.querySelector("[data-fact-value]").value.trim(),
    }))
    .filter((fact) => fact.label || fact.value);
}

function renderMedia() {
  if (state.media.length === 0) {
    elements.mediaList.innerHTML = `<div class="empty-state">No media yet</div>`;
    return;
  }

  elements.mediaList.innerHTML = state.media
    .map(
      (item) => `
        <article class="media-item">
          ${renderMediaPreview(item)}
          <div class="media-name">
            <strong>${escapeHtml(item.name)}</strong>
            <span>${escapeHtml(item.type)} · ${formatBytes(item.size)}</span>
          </div>
          <button class="delete-button" type="button" data-delete-media="${item.id}" title="Delete media">×</button>
        </article>
      `
    )
    .join("");

  document.querySelectorAll("[data-delete-media]").forEach((button) => {
    button.addEventListener("click", () => deleteMedia(button.dataset.deleteMedia));
  });
}

function renderMediaPreview(item) {
  if (item.type === "video") {
    return `<video src="/${item.path}" muted playsinline></video>`;
  }
  return `<img src="/${item.path}" alt="${escapeHtml(item.name)}" />`;
}

function renderMetrics() {
  const visible = getVisibleTrends();
  elements.trendCount.textContent = state.trends.length;
  elements.visibleTrendCount.textContent = visible.length;
  elements.lastRun.textContent = state.runs[0]
    ? new Date(state.runs[0].fetchedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : "Never";
}

function renderTrends() {
  renderTagFilters();
  const trends = getVisibleTrends();
  elements.visibleTrendCount.textContent = trends.length;

  if (trends.length === 0) {
    elements.trendTable.innerHTML = `
      <tr>
        <td class="empty-state" colspan="5">No trends yet</td>
      </tr>
    `;
    return;
  }

  elements.trendTable.innerHTML = trends
    .map(
      (trend) => `
        <tr>
          <td><span class="score-badge">${Math.round(trend.relevanceScore)}</span></td>
          <td><div class="tag-cell">${trend.tags.slice(0, 3).map(renderTag).join("")}</div></td>
          <td>
            <a class="trend-title" href="${escapeHtml(trend.url)}" target="_blank" rel="noreferrer">${escapeHtml(trend.title)}</a>
            <span class="trend-meta">${escapeHtml(formatCloseTime(trend.closeTime))}</span>
          </td>
          <td>${formatNumber(trend.volume24h)}</td>
          <td>${renderBusinessFit(trend)}</td>
        </tr>
      `
    )
    .join("");
}

function renderTagFilters() {
  const tags = [...new Set(state.trends.flatMap((trend) => trend.tags || []))].sort();
  const validTags = new Set(["all", ...tags]);
  if (!validTags.has(state.activeTag)) state.activeTag = "all";
  elements.tagFilters.innerHTML = ["all", ...tags]
    .map(
      (tag) => `
        <button class="tag-filter ${state.activeTag === tag ? "is-active" : ""}" type="button" data-tag="${escapeHtml(tag)}">
          ${escapeHtml(tag)}
        </button>
      `
    )
    .join("");
  document.querySelectorAll("[data-tag]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTag = button.dataset.tag;
      renderTrends();
      renderMetrics();
    });
  });
}

function getVisibleTrends() {
  const filtered =
    state.activeTag === "all"
      ? [...state.trends]
      : state.trends.filter((trend) => (trend.tags || []).includes(state.activeTag));
  return filtered.sort((a, b) => {
    if (state.sortBy === "volume") return b.volume24h - a.volume24h;
    if (state.sortBy === "probability") return b.probability - a.probability;
    if (state.sortBy === "closing") return closeTimeValue(a.closeTime) - closeTimeValue(b.closeTime);
    return b.relevanceScore - a.relevanceScore || b.volume24h - a.volume24h;
  });
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function setAccountStatus(label) {
  elements.accountStatus.textContent = label;
}

function setTrendStatus(label) {
  elements.trendStatus.textContent = label;
}

function renderTag(tag) {
  return `<span class="tag">${escapeHtml(tag)}</span>`;
}

function renderBusinessFit(trend) {
  const matches = trend.preferredTagMatches || [];
  if (matches.length > 0) {
    return `<div class="fit-cell"><strong>Preferred</strong><span>${escapeHtml(matches.join(", "))}</span></div>`;
  }
  if ((trend.matchingTerms || []).length > 0) {
    return `<div class="fit-cell"><strong>Keyword</strong><span>${escapeHtml(trend.matchingTerms.join(", "))}</span></div>`;
  }
  return `<div class="fit-cell"><strong>General</strong><span>${escapeHtml(state.business.businessName)}</span></div>`;
}

function formatCloseTime(value) {
  if (!value) return "No close date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No close date";
  return `Closes ${date.toLocaleDateString([], { month: "short", day: "numeric" })}`;
}

function closeTimeValue(value) {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? Number.MAX_SAFE_INTEGER : time;
}

function formatNumber(value) {
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value || 0);
}

function formatBytes(value) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
