// 내 정보 금고 — 서버
// 서버는 암호화된 덩어리(암호문)만 저장합니다. 마스터 비밀번호와 실제 내용은 서버로 오지 않습니다.
// 외부 패키지 없이 Node.js 기본 기능만 사용합니다.
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const PORT = Number(process.env.PORT) || 3000;
const DATA_DIR = process.env.DATA_DIR || "/data";
const FILE = path.join(DATA_DIR, "vault.json");
const BACKUP_DIR = path.join(DATA_DIR, "backups");
const KEEP_BACKUPS = 50;
const MAX_BODY = 4 * 1024 * 1024;
const PUBLIC_DIR = path.join(__dirname, "public");
const STATIC = {
  "/": ["index.html", "text/html; charset=utf-8"],
  "/index.html": ["index.html", "text/html; charset=utf-8"],
  "/app.js": ["app.js", "text/javascript; charset=utf-8"],
  "/style.css": ["style.css", "text/css; charset=utf-8"],
};

// ---- 저장 ----
function load() {
  try { return JSON.parse(fs.readFileSync(FILE, "utf8")); } catch { return null; }
}
function save(obj) {
  fs.mkdirSync(BACKUP_DIR, { recursive: true });
  if (fs.existsSync(FILE)) {
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    fs.copyFileSync(FILE, path.join(BACKUP_DIR, "vault-" + stamp + ".json"));
    const old = fs.readdirSync(BACKUP_DIR).filter(f => f.startsWith("vault-")).sort();
    old.slice(0, Math.max(0, old.length - KEEP_BACKUPS)).forEach(f => fs.rmSync(path.join(BACKUP_DIR, f)));
  }
  const tmp = FILE + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(obj));
  fs.renameSync(tmp, FILE);
}

// ---- 로그인 시도 제한 ----
const FAIL_WINDOW = 15 * 60 * 1000;
const PER_IP_LIMIT = 10;
const GLOBAL_LIMIT = 50;
const fails = new Map(); // ip -> [timestamps]
let globalFails = [];
function clientIp(req) {
  const xff = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim();
  return xff || req.socket.remoteAddress || "?";
}
function recent(list) { const now = Date.now(); return list.filter(t => now - t < FAIL_WINDOW); }
function blocked(ip) {
  globalFails = recent(globalFails);
  const mine = recent(fails.get(ip) || []);
  fails.set(ip, mine);
  return mine.length >= PER_IP_LIMIT || globalFails.length >= GLOBAL_LIMIT;
}
function recordFail(ip) {
  const now = Date.now();
  fails.set(ip, [...recent(fails.get(ip) || []), now]);
  globalFails.push(now);
}

// ---- 도우미 ----
const sha256 = s => crypto.createHash("sha256").update(s).digest();
function authOk(req, vault) {
  const m = /^Bearer ([0-9a-f]{64})$/.exec(String(req.headers.authorization || ""));
  if (!m || !vault) return false;
  const given = sha256(m[1]);
  const want = Buffer.from(vault.authHash, "hex");
  return want.length === given.length && crypto.timingSafeEqual(given, want);
}
const isB64 = s => typeof s === "string" && s.length > 0 && s.length < MAX_BODY && /^[A-Za-z0-9+/=]+$/.test(s);
const validBlob = b => b && isB64(b.iv) && isB64(b.ct);
const validAuth = a => typeof a === "string" && /^[0-9a-f]{64}$/.test(a);
const validIter = n => Number.isInteger(n) && n >= 100000 && n <= 5000000;

const SECURITY_HEADERS = {
  "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Strict-Transport-Security": "max-age=31536000",
  "Cache-Control": "no-store",
};
function send(res, status, body, type) {
  const isJson = type === undefined;
  res.writeHead(status, { ...SECURITY_HEADERS, "Content-Type": isJson ? "application/json; charset=utf-8" : type });
  res.end(isJson ? JSON.stringify(body) : body);
}
function readJson(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on("data", c => { size += c.length; if (size > MAX_BODY) { reject(new Error("too_large")); req.destroy(); } else chunks.push(c); });
    req.on("end", () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}")); } catch { reject(new Error("bad_json")); } });
    req.on("error", reject);
  });
}

// ---- API ----
async function api(req, res, url) {
  const ip = clientIp(req);
  const vault = load();

  // 금고가 있는지, 비밀번호 계산에 쓸 소금(salt)만 알려줍니다. 비밀은 없습니다.
  if (url === "/api/meta" && req.method === "GET") {
    return send(res, 200, vault ? { exists: true, salt: vault.salt, iter: vault.iter } : { exists: false });
  }

  // 처음 한 번만: 금고 만들기
  if (url === "/api/setup" && req.method === "POST") {
    if (vault) return send(res, 409, { error: "already_exists" });
    const b = await readJson(req);
    if (!isB64(b.salt) || !validIter(b.iter) || !validAuth(b.auth) || !validBlob(b.blob)) return send(res, 400, { error: "bad_request" });
    save({ salt: b.salt, iter: b.iter, authHash: sha256(b.auth).toString("hex"), version: 1, blob: { iv: b.blob.iv, ct: b.blob.ct }, updatedAt: new Date().toISOString() });
    return send(res, 201, { version: 1 });
  }

  if (url === "/api/vault" || url === "/api/password") {
    if (blocked(ip)) return send(res, 429, { error: "too_many_attempts" });
    if (!authOk(req, vault)) { recordFail(ip); return send(res, vault ? 401 : 404, { error: vault ? "wrong_password" : "no_vault" }); }
    fails.delete(ip);

    if (url === "/api/vault" && req.method === "GET") {
      return send(res, 200, { version: vault.version, blob: vault.blob, updatedAt: vault.updatedAt });
    }
    if (url === "/api/vault" && req.method === "PUT") {
      const b = await readJson(req);
      if (!validBlob(b.blob) || !Number.isInteger(b.version)) return send(res, 400, { error: "bad_request" });
      // 다른 기기에서 먼저 바뀌었으면 덮어쓰지 않고 최신본을 돌려줍니다.
      if (b.version !== vault.version) return send(res, 409, { error: "stale", version: vault.version, blob: vault.blob });
      const next = { ...vault, version: vault.version + 1, blob: { iv: b.blob.iv, ct: b.blob.ct }, updatedAt: new Date().toISOString() };
      save(next);
      return send(res, 200, { version: next.version });
    }
    if (url === "/api/password" && req.method === "PUT") {
      const b = await readJson(req);
      if (!isB64(b.salt) || !validIter(b.iter) || !validAuth(b.auth) || !validBlob(b.blob) || !Number.isInteger(b.version)) return send(res, 400, { error: "bad_request" });
      if (b.version !== vault.version) return send(res, 409, { error: "stale", version: vault.version, blob: vault.blob });
      const next = { salt: b.salt, iter: b.iter, authHash: sha256(b.auth).toString("hex"), version: vault.version + 1, blob: { iv: b.blob.iv, ct: b.blob.ct }, updatedAt: new Date().toISOString() };
      save(next);
      return send(res, 200, { version: next.version });
    }
  }
  return send(res, 404, { error: "not_found" });
}

const server = http.createServer(async (req, res) => {
  const url = (req.url || "/").split("?")[0];
  try {
    if (url.startsWith("/api/")) return await api(req, res, url);
    if (url === "/healthz") return send(res, 200, "ok", "text/plain");
    const hit = STATIC[url];
    if (hit && (req.method === "GET" || req.method === "HEAD")) {
      return send(res, 200, fs.readFileSync(path.join(PUBLIC_DIR, hit[0])), hit[1]);
    }
    send(res, 404, "Not found", "text/plain; charset=utf-8");
  } catch (e) {
    const code = e && e.message === "too_large" ? 413 : e && e.message === "bad_json" ? 400 : 500;
    if (code === 500) console.error(e);
    if (!res.headersSent) send(res, code, { error: "server_error" });
  }
});
server.listen(PORT, () => console.log("vault listening on " + PORT + ", data in " + DATA_DIR));
