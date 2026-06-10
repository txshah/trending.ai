const http = require("http");
const fs = require("fs/promises");
const path = require("path");
const crypto = require("crypto");
const { spawn } = require("child_process");

const PORT = Number(process.env.PORT || 3000);
const ROOT = __dirname;
const PUBLIC_DIR = path.join(ROOT, "public");
const DATA_DIR = path.join(ROOT, "data");
const UPLOAD_DIR = path.join(DATA_DIR, "uploads");
const DB_PATH = path.join(DATA_DIR, "dashboard-db.json");
const BUSINESS_CSV_PATH = path.join(DATA_DIR, "business.csv");
const TRENDS_CSV_PATH = path.join(DATA_DIR, "trends.csv");
let dbWriteQueue = Promise.resolve();
const CANONICAL_TREND_TAGS = ["sports", "politics", "crypto", "tech", "economy", "culture", "general"];

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".mp4": "video/mp4",
  ".mov": "video/quicktime",
  ".webm": "video/webm",
};

const DEFAULT_BUSINESS = {
  id: "biz_olive_and_oak",
  accountId: "acct_mock_olive_and_oak",
  ownerName: "Maya Patel",
  businessName: "Olive & Oak",
  industry: "Neighborhood restaurant",
  startedDate: "2021-05-14",
  whatTheyDo: "Olive & Oak is a seasonal Mediterranean-American restaurant focused on wood-fired mains, share plates, natural wine, and warm neighborhood hospitality.",
  audience: "local diners, date-night guests, young professionals, families, and private event hosts in the neighborhood",
  keywords: [
    "restaurant",
    "dining",
    "food",
    "hospitality",
    "mediterranean",
    "wine",
    "seasonal",
    "local",
    "events",
    "brunch",
    "dinner",
  ],
  facts: [
    { id: "fact_started", label: "Started", value: "May 2021" },
    { id: "fact_cuisine", label: "Cuisine", value: "Seasonal Mediterranean-American" },
    { id: "fact_signature", label: "Signature", value: "Wood-fired lamb, mezze boards, and natural wine flights" },
    { id: "fact_services", label: "Services", value: "Dinner, weekend brunch, private dining, and catering" },
    { id: "fact_voice", label: "Voice", value: "Warm, local, generous, and ingredient-led" },
  ],
  preferredTrendTags: ["culture", "economy", "sports"],
};

async function main() {
  await ensureDataStore();
  const server = http.createServer((req, res) => {
    handleRequest(req, res).catch((error) => {
      console.error(error);
      sendJson(res, 500, { error: "Internal server error" });
    });
  });
  server.listen(PORT, () => {
    console.log(`Dashboard running at http://localhost:${PORT}`);
  });
}

async function ensureDataStore() {
  await fs.mkdir(UPLOAD_DIR, { recursive: true });
  let db;
  try {
    db = JSON.parse(await fs.readFile(DB_PATH, "utf-8"));
  } catch {
    db = {};
  }
  await writeDb(normalizeDb(db));
}

async function handleRequest(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === "GET" && url.pathname === "/api/account") {
    const db = await readDb();
    sendJson(res, 200, db);
    return;
  }

  if (req.method === "PATCH" && url.pathname === "/api/business") {
    const updates = await readJsonBody(req);
    await withDbWriteLock(async () => {
      const db = await readDb();
      db.business = normalizeBusiness({ ...db.business, ...updates });
      await writeDb(db);
      await writeBusinessCsv(db.business, db.media);
      sendJson(res, 200, { business: db.business });
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/media") {
    const upload = await parseMultipartMedia(req);
    await withDbWriteLock(async () => {
      const db = await readDb();
      db.media.unshift(upload);
      await writeDb(db);
      await writeBusinessCsv(db.business, db.media);
      sendJson(res, 201, { media: db.media, item: upload });
    });
    return;
  }

  if (req.method === "DELETE" && url.pathname.startsWith("/api/media/")) {
    const id = decodeURIComponent(url.pathname.replace("/api/media/", ""));
    await withDbWriteLock(async () => {
      const db = await readDb();
      const item = db.media.find((media) => media.id === id);
      db.media = db.media.filter((media) => media.id !== id);
      if (item) {
        await fs.unlink(path.join(ROOT, item.path)).catch(() => {});
      }
      await writeDb(db);
      await writeBusinessCsv(db.business, db.media);
      sendJson(res, 200, { media: db.media });
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/trends/find") {
    const db = await readDb();
    const trends = await findTrends(db.business);
    const run = {
      id: crypto.randomUUID(),
      fetchedAt: new Date().toISOString(),
      source: "polymarket",
      count: trends.length,
    };
    await withDbWriteLock(async () => {
      const latestDb = await readDb();
      latestDb.lastTrendRun = run;
      await writeDb(latestDb);
      await writeTrendsCsv(run, trends);
      spawnSnapshotScript();
      sendJson(res, 200, { run, trends });
    });
    return;
  }

  if (req.method === "GET") {
    await serveStatic(url.pathname, res);
    return;
  }

  sendJson(res, 404, { error: "Not found" });
}

async function readDb() {
  const db = JSON.parse(await fs.readFile(DB_PATH, "utf-8"));
  return normalizeDb(db);
}

async function writeDb(db) {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.writeFile(DB_PATH, JSON.stringify(normalizeDb(db), null, 2));
}

function withDbWriteLock(operation) {
  const run = dbWriteQueue.then(operation, operation);
  dbWriteQueue = run.catch(() => {});
  return run;
}

function normalizeDb(db) {
  const business = normalizeBusiness(db.business || db.account || DEFAULT_BUSINESS);
  const media = Array.isArray(db.media) ? db.media : Array.isArray(db.sources) ? db.sources : [];
  return {
    business,
    media: media.map(normalizeMediaItem),
    lastTrendRun: db.lastTrendRun || null,
  };
}

function normalizeBusiness(input) {
  const businessId = input.id && !String(input.id).startsWith("acct_") ? input.id : DEFAULT_BUSINESS.id;
  return {
    ...DEFAULT_BUSINESS,
    ...input,
    id: businessId,
    accountId: input.accountId || input.id || DEFAULT_BUSINESS.accountId,
    ownerName: input.ownerName || input.name || DEFAULT_BUSINESS.ownerName,
    name: undefined,
    products: undefined,
    keywords: normalizeKeywords(input.keywords || DEFAULT_BUSINESS.keywords),
    facts: normalizeFacts(input.facts || DEFAULT_BUSINESS.facts),
    preferredTrendTags: normalizePreferredTrendTags(input.preferredTrendTags || DEFAULT_BUSINESS.preferredTrendTags),
  };
}

function normalizeFacts(facts) {
  if (!Array.isArray(facts)) return DEFAULT_BUSINESS.facts;
  return facts
    .filter((fact) => fact && (fact.label || fact.value))
    .map((fact) => ({
      id: fact.id || crypto.randomUUID(),
      label: String(fact.label || "").trim(),
      value: String(fact.value || "").trim(),
    }));
}

function normalizeKeywords(keywords) {
  if (Array.isArray(keywords)) {
    return keywords.map((keyword) => String(keyword).trim().toLowerCase()).filter(Boolean);
  }
  return String(keywords || "")
    .split(",")
    .map((keyword) => keyword.trim().toLowerCase())
    .filter(Boolean);
}

function normalizePreferredTrendTags(tags) {
  const normalized = normalizeTags(Array.isArray(tags) ? tags : String(tags || "").split(","));
  return normalized.filter((tag) => CANONICAL_TREND_TAGS.includes(tag));
}

function normalizeMediaItem(item) {
  return {
    id: item.id || crypto.randomUUID(),
    name: item.name || "business-media",
    mimeType: item.mimeType || "application/octet-stream",
    type: item.type || (String(item.mimeType || "").startsWith("video/") ? "video" : "image"),
    size: Number(item.size || 0),
    uploadedAt: item.uploadedAt || new Date().toISOString(),
    path: item.path || "",
  };
}


async function serveStatic(rawPathname, res) {
  const pathname = rawPathname === "/" ? "/index.html" : rawPathname;
  const decodedPath = decodeURIComponent(pathname);
  const filePath = path.normalize(path.join(PUBLIC_DIR, decodedPath));
  const uploadPath = path.normalize(path.join(ROOT, decodedPath));
  const selectedPath = decodedPath.startsWith("/data/uploads/") ? uploadPath : filePath;
  const allowedRoot = decodedPath.startsWith("/data/uploads/") ? UPLOAD_DIR : PUBLIC_DIR;

  if (!selectedPath.startsWith(allowedRoot)) {
    sendJson(res, 403, { error: "Forbidden" });
    return;
  }

  try {
    const body = await fs.readFile(selectedPath);
    res.writeHead(200, { "Content-Type": MIME_TYPES[path.extname(selectedPath)] || "application/octet-stream" });
    res.end(body);
  } catch {
    sendJson(res, 404, { error: "Not found" });
  }
}

async function parseMultipartMedia(req) {
  const contentType = req.headers["content-type"] || "";
  const boundary = contentType.match(/boundary=(.+)$/)?.[1];
  if (!boundary) {
    throw new Error("Missing multipart boundary");
  }

  const body = await readRequestBuffer(req, 80 * 1024 * 1024);
  const binary = body.toString("binary");
  const boundaryText = `--${boundary}`;
  const part = binary
    .split(boundaryText)
    .find((chunk) => chunk.includes('name="media"') || chunk.includes('name="image"'));
  if (!part) {
    throw new Error("Missing media field");
  }

  const [headerText, ...rest] = part.split("\r\n\r\n");
  const disposition = headerText.match(/filename="([^"]+)"/);
  const type = headerText.match(/Content-Type:\s*([^\r\n]+)/i);
  const originalName = sanitizeFilename(disposition?.[1] || "business-media");
  const mimeType = type?.[1] || "application/octet-stream";
  if (!mimeType.startsWith("image/") && !mimeType.startsWith("video/")) {
    throw new Error("Only image and video uploads are supported");
  }

  const dataBinary = rest.join("\r\n\r\n").replace(/\r\n--$/, "").replace(/\r\n$/, "");
  const buffer = Buffer.from(dataBinary, "binary");
  const ext = extensionForMime(mimeType) || path.extname(originalName) || ".bin";
  const id = crypto.randomUUID();
  const filename = `${id}${ext}`;
  await fs.writeFile(path.join(UPLOAD_DIR, filename), buffer);
  return {
    id,
    name: originalName,
    mimeType,
    type: mimeType.startsWith("video/") ? "video" : "image",
    size: buffer.length,
    uploadedAt: new Date().toISOString(),
    path: `data/uploads/${filename}`,
  };
}

function readRequestBuffer(req, maxBytes) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let total = 0;
    req.on("data", (chunk) => {
      total += chunk.length;
      if (total > maxBytes) {
        reject(new Error("Request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

async function readJsonBody(req) {
  const body = await readRequestBuffer(req, 1024 * 1024);
  return JSON.parse(body.toString("utf-8") || "{}");
}

async function findTrends(business) {
  const polymarket = await fetchPolymarketEvents(80);
  return enrichTrends(polymarket, business).slice(0, 60);
}

async function fetchPolymarketEvents(limit) {
  const params = new URLSearchParams({
    active: "true",
    closed: "false",
    order: "volume_24hr",
    ascending: "false",
    limit: String(limit),
  });
  const response = await fetch(`https://gamma-api.polymarket.com/events?${params}`);
  if (!response.ok) {
    throw new Error(`Polymarket returned ${response.status}`);
  }
  const events = await response.json();
  return events.map(normalizePolymarketEvent);
}

function normalizePolymarketEvent(event) {
  const slug = String(event.slug || event.id || "");
  const rawTagText = [
    extractPolymarketCategory(event),
    ...extractPolymarketTags(event),
    event.title || "",
    event.question || "",
  ].join(" ");
  const inferredTags = inferTags(rawTagText);
  const tags = normalizeTags(inferredTags.length ? inferredTags : [canonicalFallbackTag(rawTagText)]);
  const topMarket = Array.isArray(event.markets) ? event.markets[0] || {} : {};
  return {
    source: "polymarket",
    trendId: String(event.id || slug),
    title: String(event.title || event.question || slug),
    category: tags[0] || "general",
    tags,
    url: slug ? `https://polymarket.com/event/${slug}` : "",
    volume24h: firstNumber(event.volume24hr, event.volume_24hr),
    volumeTotal: firstNumber(event.volume),
    liquidity: firstNumber(event.liquidity),
    probability: firstNumber(topMarket.lastTradePrice, topMarket.bestAsk, topMarket.bestBid),
    closeTime: String(event.endDate || event.end_date || ""),
    status: event.active ? "open" : "inactive",
  };
}

function enrichTrends(trends, business) {
  return trends
    .map((trend) => {
      const text = `${trend.title} ${trend.category} ${trend.tags.join(" ")}`.toLowerCase();
      const tokens = new Set(text.match(/[a-z0-9]+/g) || []);
      const matchingTerms = business.keywords.filter((keyword) => tokens.has(keyword));
      const preferredTagMatches = trend.tags.filter((tag) => business.preferredTrendTags.includes(tag));
      const preferredTagMatch = preferredTagMatches.length > 0;
      const relevanceScore = Math.min(
        100,
        Math.min(matchingTerms.length * 8, 32) +
          volumeBonus(trend.volume24h) +
          probabilityBonus(trend.probability)
      );
      return {
        ...trend,
        relevanceScore,
        preferredTagMatch,
        preferredTagMatches,
        matchingTerms,
        contentAngles: [
          `What this market implies for ${business.businessName}`,
          `A customer-facing take on ${matchingTerms.join(", ") || trend.category || "market activity"}`,
        ],
      };
    })
    .sort((a, b) => b.volume24h - a.volume24h || b.volumeTotal - a.volumeTotal);
}

async function writeTrendsCsv(run, trends) {
  const columns = [
    "fetched_at",
    "source",
    "trend_id",
    "title",
    "category",
    "tags",
    "url",
    "volume_24h",
    "volume_total",
    "probability",
    "close_time",
    "status",
  ];
  const rows = trends.map((trend) =>
    [
      run.fetchedAt,
      trend.source,
      trend.trendId,
      trend.title,
      trend.category,
      trend.tags.join("; "),
      trend.url,
      trend.volume24h,
      trend.volumeTotal,
      trend.probability || "",
      trend.closeTime,
      trend.status,
    ]
      .map(csvCell)
      .join(",")
  );
  await fs.writeFile(TRENDS_CSV_PATH, `${columns.join(",")}\n${rows.join("\n")}\n`);
}

async function writeBusinessCsv(business, media) {
  const columns = [
    "saved_at",
    "business_name",
    "industry",
    "started_date",
    "audience",
    "what_they_do",
    "keywords",
    "preferred_trend_tags",
    "facts",
    "media_files",
  ];
  const row = [
    new Date().toISOString(),
    business.businessName,
    business.industry,
    business.startedDate,
    business.audience,
    business.whatTheyDo,
    business.keywords.join("; "),
    business.preferredTrendTags.join("; "),
    business.facts.map((f) => `${f.label}: ${f.value}`).join("; "),
    media.map((m) => m.path).join("; "),
  ]
    .map(csvCell)
    .join(",");
  await fs.writeFile(BUSINESS_CSV_PATH, `${columns.join(",")}\n${row}\n`);
}

function spawnSnapshotScript() {
  const proc = spawn("python3", [path.join(ROOT, "scripts", "generate_snapshot.py")], { cwd: ROOT });
  proc.stdout.on("data", (d) => console.log("[snapshot]", d.toString().trim()));
  proc.stderr.on("data", (d) => console.error("[snapshot]", d.toString().trim()));
  proc.on("error", (err) => console.error("[snapshot] failed to start:", err.message));
}

function extractPolymarketCategory(event) {
  if (Array.isArray(event.tags) && event.tags.length > 0) {
    const tag = event.tags[0];
    return typeof tag === "string" ? tag : String(tag.label || tag.name || "");
  }
  return String(event.category || "");
}

function extractPolymarketTags(event) {
  if (!Array.isArray(event.tags)) return [];
  return event.tags.map((tag) => (typeof tag === "string" ? tag : String(tag.label || tag.name || "")));
}

function inferTags(text) {
  const lower = text.toLowerCase();
  const rules = {
    sports: ["nba", "nfl", "nhl", "mlb", "soccer", "world cup", "champion", "ufc", "tennis"],
    politics: ["election", "trump", "biden", "senate", "congress", "president", "mayor", "governor", "politics"],
    crypto: ["bitcoin", "ethereum", "crypto", "solana", "xrp", "token"],
    tech: ["ai", "openai", "apple", "google", "tesla", "meta", "nvidia", "software", "technology", "big tech"],
    economy: ["fed", "inflation", "rates", "recession", "gdp", "market"],
    culture: ["movie", "album", "grammy", "oscar", "celebrity", "streaming"],
  };
  return Object.entries(rules)
    .filter(([, needles]) => needles.some((needle) => includesSignal(lower, needle)))
    .map(([tag]) => tag);
}

function canonicalFallbackTag(text) {
  const lower = text.toLowerCase();
  if (lower.includes("sports")) return "sports";
  if (lower.includes("politics")) return "politics";
  if (lower.includes("crypto")) return "crypto";
  if (lower.includes("tech")) return "tech";
  if (lower.includes("economy") || lower.includes("finance")) return "economy";
  if (lower.includes("culture") || lower.includes("entertainment")) return "culture";
  return "general";
}

function includesSignal(text, needle) {
  if (/^[a-z0-9]+$/.test(needle) && needle.length <= 3) {
    return new RegExp(`\\b${needle}\\b`).test(text);
  }
  return text.includes(needle);
}

function normalizeTags(tags) {
  const seen = new Set();
  return tags
    .flatMap((tag) => String(tag || "").split(","))
    .map((tag) => tag.trim().toLowerCase())
    .filter((tag) => tag && tag !== "all")
    .filter((tag) => {
      if (seen.has(tag)) return false;
      seen.add(tag);
      return true;
    });
}

function volumeBonus(volume24h) {
  if (volume24h >= 1000000) return 24;
  if (volume24h >= 500000) return 18;
  if (volume24h >= 100000) return 12;
  if (volume24h > 0) return 6;
  return 2;
}

function probabilityBonus(probability) {
  if (!probability) return 0;
  if (probability >= 0.35 && probability <= 0.65) return 8;
  if (probability >= 0.2 && probability <= 0.8) return 5;
  return 2;
}

function firstNumber(...values) {
  for (const value of values) {
    const number = Number(value);
    if (Number.isFinite(number)) return number;
  }
  return 0;
}

function sanitizeFilename(filename) {
  return path.basename(filename).replace(/[^a-zA-Z0-9._-]/g, "_");
}

function extensionForMime(mimeType) {
  return {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
  }[mimeType];
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function sendJson(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
