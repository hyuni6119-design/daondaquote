// 내 정보 금고 — 브라우저 쪽
// 마스터 비밀번호로 열쇠를 만들어 여기서 암호화/복호화합니다. 서버에는 암호문만 보냅니다.
(() => {
  "use strict";
  const CATS = ["이메일", "구글·애드센스", "전자책", "강의", "카페·커뮤니티", "쇼핑·결제", "SNS", "금융", "기타"];
  const ITER = 600000;
  const $ = id => document.getElementById(id);
  const views = ["viewLoading", "viewUnavailable", "viewSetup", "viewUnlock", "viewMain"];
  function show(v) { views.forEach(x => $(x).hidden = x !== v); $("topActions").hidden = v !== "viewMain"; }

  let meta = null;           // {exists, salt, iter}
  let key = null, auth = null, salt = null, iter = ITER, version = 0;
  let items = [], filter = "전체", editingId = null, lockTimer = null, saving = false;

  function msg(el, text, kind) { const m = $(el); m.hidden = !text; m.className = "msg " + (kind || "err"); m.textContent = text || ""; }
  let toastT; function toast(t) { const e = $("toast"); e.textContent = t; e.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => e.hidden = true, 2200); }

  // ---- 암호화 ----
  const enc = new TextEncoder(), dec = new TextDecoder();
  const b64 = buf => { let s = ""; new Uint8Array(buf).forEach(b => s += String.fromCharCode(b)); return btoa(s); };
  const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  const hex = buf => Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join("");
  // 비밀번호 하나에서 두 가지를 만듭니다: 앞 32바이트는 암호화 열쇠(서버로 안 감), 뒤 32바이트는 서버 출입증.
  async function derive(pw, saltBytes, iterations) {
    const base = await crypto.subtle.importKey("raw", enc.encode(pw), "PBKDF2", false, ["deriveBits"]);
    const bits = new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", salt: saltBytes, iterations, hash: "SHA-256" }, base, 512));
    const k = await crypto.subtle.importKey("raw", bits.slice(0, 32), "AES-GCM", false, ["encrypt", "decrypt"]);
    return { key: k, auth: hex(bits.slice(32)) };
  }
  async function seal(list, k) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, k, enc.encode(JSON.stringify({ items: list })));
    return { iv: b64(iv), ct: b64(ct) };
  }
  async function unseal(blob, k) {
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, k, unb64(blob.ct));
    const obj = JSON.parse(dec.decode(pt));
    return Array.isArray(obj.items) ? obj.items : [];
  }
  function genPassword() {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%*?";
    const out = [];
    while (out.length < 16) { const n = crypto.getRandomValues(new Uint8Array(1))[0]; if (n < 252) out.push(chars[n % chars.length]); }
    return out.join("");
  }

  // ---- 서버 ----
  async function call(method, url, body, token) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers.Authorization = "Bearer " + token;
    const r = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined, cache: "no-store" });
    let data = null; try { data = await r.json(); } catch { }
    return { status: r.status, data };
  }
  const errText = s => s === 429 ? "잘못 입력한 횟수가 많아 15분 동안 잠겼어요. 잠시 후 다시 시도해 주세요."
    : s === 401 ? "마스터 비밀번호가 맞지 않아요." : "서버에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.";

  // 저장: 다른 기기에서 먼저 바뀌었으면(409) 최신본과 합친 뒤 다시 저장합니다.
  async function persist(change) {
    if (saving) { toast("저장 중이에요. 잠시만요."); return false; }
    saving = true;
    try {
      for (let attempt = 0; attempt < 3; attempt++) {
        const next = change(items);
        const r = await call("PUT", "/api/vault", { version, blob: await seal(next, key) }, auth);
        if (r.status === 200) { version = r.data.version; items = next; return true; }
        if (r.status === 409 && r.data && r.data.blob) {
          items = await unseal(r.data.blob, key); version = r.data.version;
          toast("다른 기기에서 바뀐 내용을 먼저 불러왔어요");
          continue;
        }
        if (r.status === 401) { toast("다시 잠금 해제해 주세요"); lock(); return false; }
        toast(errText(r.status)); return false;
      }
      toast("저장하지 못했어요. 새로고침 후 다시 시도해 주세요."); return false;
    } catch { toast("서버에 연결하지 못했어요. 인터넷 연결을 확인해 주세요."); return false; }
    finally { saving = false; }
  }

  // ---- 자동 잠금 ----
  function bump() { if (!key) return; clearTimeout(lockTimer); lockTimer = setTimeout(lock, 10 * 60 * 1000); }
  ["click", "keydown", "touchstart"].forEach(ev => document.addEventListener(ev, bump, { passive: true }));
  function lock() {
    key = null; auth = null; items = []; editingId = null; clearTimeout(lockTimer);
    $("list").textContent = ""; $("unlockPw").value = ""; $("editor").hidden = true; msg("unlockMsg", "");
    show(meta && meta.exists ? "viewUnlock" : "viewSetup");
  }
  $("lockBtn").onclick = lock;

  // ---- 만들기 / 열기 ----
  $("viewSetup").addEventListener("submit", async e => {
    e.preventDefault();
    const a = $("setupPw").value, b = $("setupPw2").value;
    if (a.length < 10) return msg("setupMsg", "10자 이상으로 정해주세요.");
    if (a !== b) return msg("setupMsg", "두 번 입력한 비밀번호가 달라요.");
    $("setupBtn").disabled = true; msg("setupMsg", "금고를 만드는 중…", "ok");
    try {
      salt = crypto.getRandomValues(new Uint8Array(16)); iter = ITER;
      const d = await derive(a, salt, iter);
      const r = await call("POST", "/api/setup", { salt: b64(salt), iter, auth: d.auth, blob: await seal([], d.key) });
      if (r.status === 409) { msg("setupMsg", "이미 금고가 있어요. 새로고침해서 마스터 비밀번호로 열어주세요."); return; }
      if (r.status !== 201) { msg("setupMsg", errText(r.status)); return; }
      key = d.key; auth = d.auth; version = r.data.version; items = [];
      meta = { exists: true, salt: b64(salt), iter };
      $("setupPw").value = $("setupPw2").value = ""; msg("setupMsg", "");
      enterMain();
    } catch { msg("setupMsg", "서버에 연결하지 못했어요."); }
    finally { $("setupBtn").disabled = false; }
  });

  $("viewUnlock").addEventListener("submit", async e => {
    e.preventDefault();
    $("unlockBtn").disabled = true; msg("unlockMsg", "여는 중…", "ok");
    try {
      salt = unb64(meta.salt); iter = meta.iter;
      const d = await derive($("unlockPw").value, salt, iter);
      const r = await call("GET", "/api/vault", null, d.auth);
      if (r.status !== 200) { msg("unlockMsg", errText(r.status)); return; }
      items = await unseal(r.data.blob, d.key);
      key = d.key; auth = d.auth; version = r.data.version;
      $("unlockPw").value = ""; msg("unlockMsg", ""); enterMain();
    } catch { msg("unlockMsg", "금고를 열지 못했어요."); }
    finally { $("unlockBtn").disabled = false; }
  });
  function enterMain() { show("viewMain"); filter = "전체"; $("search").value = ""; render(); bump(); }

  // ---- 목록 ----
  function catCounts() { const c = { 전체: items.length }; items.forEach(i => c[i.cat] = (c[i.cat] || 0) + 1); return c; }
  function renderChips() {
    const c = catCounts(), box = $("chips"); box.textContent = "";
    ["전체", ...CATS].forEach(name => {
      if (name !== "전체" && !c[name]) return;
      const b = document.createElement("button"); b.type = "button"; b.className = "chip";
      b.setAttribute("aria-pressed", String(filter === name));
      b.append(name); const n = document.createElement("span"); n.className = "n"; n.textContent = c[name] || 0; b.append(n);
      b.onclick = () => { filter = name; render(); };
      box.append(b);
    });
  }
  async function copy(text, label) {
    try { await navigator.clipboard.writeText(text); toast(label + " 복사됨"); }
    catch { toast("복사가 안 돼요. 길게 눌러 직접 복사해 주세요."); }
  }
  function fieldRow(k, v, secret) {
    const row = document.createElement("div"); row.className = "field";
    const kk = document.createElement("span"); kk.className = "k"; kk.textContent = k;
    const vv = document.createElement("span"); vv.className = "v";
    const acts = document.createElement("span"); acts.className = "row";
    let shown = !secret;
    const paint = () => vv.textContent = shown ? v : "••••••••";
    paint();
    if (secret) {
      const s = document.createElement("button"); s.type = "button"; s.className = "ghost"; s.textContent = "보기";
      s.onclick = () => { shown = !shown; s.textContent = shown ? "숨기기" : "보기"; paint(); }; acts.append(s);
    }
    const c = document.createElement("button"); c.type = "button"; c.className = "ghost"; c.textContent = "복사"; c.onclick = () => copy(v, k);
    acts.append(c);
    row.append(kk, vv, acts); return row;
  }
  function render() {
    renderChips();
    const q = $("search").value.trim().toLowerCase();
    const list = $("list"); list.textContent = "";
    const shown = items
      .filter(i => filter === "전체" || i.cat === filter)
      .filter(i => !q || [i.name, i.user, i.url, i.note, i.cat].some(x => (x || "").toLowerCase().includes(q)))
      .sort((a, b) => (a.cat || "").localeCompare(b.cat || "", "ko") || (a.name || "").localeCompare(b.name || "", "ko"));
    if (!shown.length) {
      const e = document.createElement("div"); e.className = "empty";
      e.textContent = items.length ? "찾는 항목이 없어요." : "아직 저장한 정보가 없어요. ‘+ 새 항목’을 눌러 메일 계정부터 하나씩 넣어보세요.";
      list.append(e); return;
    }
    shown.forEach(i => {
      const card = document.createElement("article"); card.className = "card";
      const head = document.createElement("div"); head.className = "card-head";
      const nm = document.createElement("span"); nm.className = "name"; nm.textContent = i.name;
      const tg = document.createElement("span"); tg.className = "tag"; tg.textContent = i.cat;
      head.append(nm, tg); card.append(head);
      if (i.user) card.append(fieldRow("아이디", i.user, false));
      if (i.pw) card.append(fieldRow("비밀번호", i.pw, true));
      if (i.url) {
        const l = document.createElement("div"); l.className = "link";
        if (/^https?:\/\//i.test(i.url)) { const a = document.createElement("a"); a.href = i.url; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = i.url; l.append(a); }
        else l.textContent = i.url;
        card.append(l);
      }
      if (i.note) { const n = document.createElement("div"); n.className = "note"; n.textContent = i.note; card.append(n); }
      const acts = document.createElement("div"); acts.className = "row end";
      const ed = document.createElement("button"); ed.type = "button"; ed.textContent = "수정"; ed.onclick = () => openEditor(i);
      const del = document.createElement("button"); del.type = "button"; del.className = "danger"; del.textContent = "삭제";
      del.onclick = () => {
        const cf = document.createElement("div"); cf.className = "confirm";
        const t = document.createElement("span"); t.className = "grow"; t.textContent = "‘" + i.name + "’을(를) 지울까요? 되돌릴 수 없어요.";
        const no = document.createElement("button"); no.type = "button"; no.textContent = "취소"; no.onclick = () => cf.replaceWith(acts);
        const yes = document.createElement("button"); yes.type = "button"; yes.className = "danger"; yes.textContent = "지우기";
        yes.onclick = async () => { if (await persist(list => list.filter(x => x.id !== i.id))) toast("지웠어요"); render(); };
        cf.append(t, no, yes); acts.replaceWith(cf);
      };
      acts.append(ed, del); card.append(acts);
      list.append(card);
    });
  }
  $("search").addEventListener("input", render);

  // ---- 입력 ----
  CATS.forEach(c => { const o = document.createElement("option"); o.value = o.textContent = c; $("fCat").append(o); });
  function openEditor(item) {
    editingId = item ? item.id : null;
    $("editorTitle").textContent = item ? "항목 수정" : "새 항목";
    $("fName").value = item ? item.name : "";
    $("fCat").value = item ? item.cat : (filter !== "전체" ? filter : "이메일");
    $("fUser").value = item ? (item.user || "") : "";
    $("fPw").value = item ? (item.pw || "") : "";
    $("fUrl").value = item ? (item.url || "") : "";
    $("fNote").value = item ? (item.note || "") : "";
    $("editor").hidden = false; $("fName").focus(); window.scrollTo({ top: 0, behavior: "smooth" });
  }
  $("addBtn").onclick = () => openEditor(null);
  $("cancelBtn").onclick = () => { $("editor").hidden = true; editingId = null; };
  $("genBtn").onclick = () => { $("fPw").value = genPassword(); };
  $("editor").addEventListener("submit", async e => {
    e.preventDefault();
    const id = editingId || crypto.randomUUID();
    const rec = {
      id, name: $("fName").value.trim(), cat: $("fCat").value, user: $("fUser").value.trim(), pw: $("fPw").value,
      url: $("fUrl").value.trim(), note: $("fNote").value.trim(), updatedAt: new Date().toISOString()
    };
    if (!rec.name) return;
    $("saveBtn").disabled = true;
    const ok = await persist(list => list.some(x => x.id === id) ? list.map(x => x.id === id ? rec : x) : [...list, rec]);
    $("saveBtn").disabled = false;
    if (!ok) return;
    $("editor").hidden = true; editingId = null; toast("저장했어요"); render();
  });

  // ---- 백업 ----
  $("backupBtn").onclick = async () => {
    const file = { v: 2, salt: b64(salt), iter, blob: await seal(items, key), createdAt: new Date().toISOString() };
    const url = URL.createObjectURL(new Blob([JSON.stringify(file)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = "내정보금고-백업-" + new Date().toISOString().slice(0, 10) + ".json";
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 5000);
    toast("백업 파일을 저장했어요");
  };
  $("importFile").addEventListener("change", async e => {
    const f = e.target.files && e.target.files[0]; e.target.value = "";
    if (!f || !key) return;
    let got;
    try {
      const file = JSON.parse(await f.text());
      // 같은 금고의 백업이면 지금 열쇠로 열립니다. 비밀번호를 바꾼 뒤라면 옛 비밀번호가 필요해요.
      const same = file.salt === b64(salt) && file.iter === iter;
      const oldPw = $("importPw").value;
      if (!same && !oldPw) { $("importPwRow").hidden = false; toast("예전 비밀번호로 만든 백업이에요. 그 비밀번호를 넣고 다시 골라주세요."); return; }
      const k = same ? key : (await derive(oldPw, unb64(file.salt), file.iter)).key;
      got = await unseal(file.blob, k);
      $("importPw").value = "";
    } catch { toast("백업 파일을 열지 못했어요. 비밀번호를 확인해 주세요."); return; }
    const have = new Set(items.map(i => i.id));
    const add = got.filter(i => i && i.id && !have.has(i.id));
    if (!add.length) { toast("새로 추가할 항목이 없어요"); return; }
    if (await persist(list => { const h = new Set(list.map(i => i.id)); return [...list, ...add.filter(i => !h.has(i.id))]; })) {
      toast(add.length + "개 항목을 불러왔어요"); render();
    }
  });

  // ---- 마스터 비밀번호 바꾸기 ----
  $("pwForm").addEventListener("submit", async e => {
    e.preventDefault();
    const o = $("oldPw").value, n = $("newPw").value, n2 = $("newPw2").value;
    if (n.length < 10) return msg("pwMsg", "새 비밀번호는 10자 이상으로 정해주세요.");
    if (n !== n2) return msg("pwMsg", "새 비밀번호 두 개가 달라요.");
    $("pwBtn").disabled = true; msg("pwMsg", "바꾸는 중…", "ok");
    try {
      const oldD = await derive(o, salt, iter);
      if (oldD.auth !== auth) { msg("pwMsg", "지금 마스터 비밀번호가 맞지 않아요."); return; }
      const newSalt = crypto.getRandomValues(new Uint8Array(16));
      const d = await derive(n, newSalt, ITER);
      const r = await call("PUT", "/api/password", { version, salt: b64(newSalt), iter: ITER, auth: d.auth, blob: await seal(items, d.key) }, auth);
      if (r.status === 409) { msg("pwMsg", "다른 기기에서 내용이 바뀌었어요. 잠갔다가 다시 열고 시도해 주세요."); return; }
      if (r.status !== 200) { msg("pwMsg", errText(r.status)); return; }
      key = d.key; auth = d.auth; salt = newSalt; iter = ITER; version = r.data.version;
      meta = { exists: true, salt: b64(newSalt), iter: ITER };
      $("oldPw").value = $("newPw").value = $("newPw2").value = "";
      msg("pwMsg", "바꿨어요. 이제 새 비밀번호로 여세요. 예전 백업 파일은 옛 비밀번호로만 열려요.", "ok");
    } catch { msg("pwMsg", "서버에 연결하지 못했어요."); }
    finally { $("pwBtn").disabled = false; }
  });

  // ---- 시작 ----
  (async () => {
    if (!window.crypto || !crypto.subtle) {
      $("unavailText").textContent = "이 주소는 https로 열어야 해요. 주소 앞이 https:// 인지 확인해 주세요.";
      return show("viewUnavailable");
    }
    try {
      const r = await call("GET", "/api/meta");
      if (r.status !== 200) throw 0;
      meta = r.data;
      show(meta.exists ? "viewUnlock" : "viewSetup");
    } catch { show("viewUnavailable"); }
  })();
})();
