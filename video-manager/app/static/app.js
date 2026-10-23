(function () {
  "use strict";

  var META = null, EPS = [], QUEUE = [], STATUS = {};
  var view = { ch: "all", st: "all", mode: "cards", month: null, open: null, tab: "steps" };
  try { var saved = JSON.parse(localStorage.getItem("vm-view") || "{}");
    ["ch", "st", "mode"].forEach(function (k) { if (saved[k]) view[k] = saved[k]; }); } catch (e) {}

  var BADGES = ["제작중", "막힘", "완료", "예약됨", "공개됨", "준비"];
  var DOW = ["일", "월", "화", "수", "목", "금", "토"];

  // ------------------------------------------------------------ 도우미
  function $(id) { return document.getElementById(id); }
  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    });
    (kids || []).forEach(function (c) {
      if (c == null || c === false) return;
      el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function api(method, url, body) {
    var opt = { method: method, headers: {} };
    if (body instanceof FormData) opt.body = body;
    else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
    return fetch(url, opt).then(function (r) {
      if (r.status === 401) { location.href = "/login"; throw new Error("login"); }
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(d.detail || "오류가 났습니다");
        return d;
      });
    });
  }
  var toastT;
  function toast(msg) {
    var t = $("toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(function () { t.hidden = true; }, 3000);
  }
  function saveView() {
    try { localStorage.setItem("vm-view", JSON.stringify({ ch: view.ch, st: view.st, mode: view.mode })); } catch (e) {}
  }
  function chInfo(key) {
    return (META.channels.filter(function (c) { return c.key === key; })[0]) || { name: key, color: "#888" };
  }
  function chTag(key) {
    var c = chInfo(key);
    return h("span", { class: "ch", style: "background:" + c.color, text: c.name });
  }
  function dateText(d) {
    if (!d) return "날짜 미정";
    var x = new Date(d + "T00:00:00");
    if (isNaN(x)) return d;
    return (x.getMonth() + 1) + "월 " + x.getDate() + "일(" + DOW[x.getDay()] + ")";
  }
  function ago(iso) {
    var m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (isNaN(m)) return "";
    if (m < 1) return "방금";
    if (m < 60) return m + "분 전";
    if (m < 1440) return Math.floor(m / 60) + "시간 전";
    return Math.floor(m / 1440) + "일 전";
  }
  function numText(n) {
    if (n == null) return "";
    if (n >= 10000) return (n / 10000).toFixed(n >= 100000 ? 0 : 1) + "만";
    return n.toLocaleString("ko-KR");
  }
  function thumbSrc(e) {
    if (e.thumb) return "/thumbs/" + encodeURIComponent(e.thumb);
    if (e.video_id) return "https://i.ytimg.com/vi/" + e.video_id + "/hqdefault.jpg";
    return null;
  }
  function thumbBox(e, withBadge) {
    var src = thumbSrc(e);
    var box = h("div", { class: "thumb" });
    var lines = h("div", { class: "lines" },
      (e.thumb_lines && e.thumb_lines.filter(Boolean).length ? e.thumb_lines.filter(Boolean) : ["썸네일 아직 없음"])
        .map(function (s) { return h("span", { text: s }); }));
    box.appendChild(lines);
    if (src) {
      var img = h("img", { src: src, alt: "", loading: "lazy" });
      img.addEventListener("error", function () { img.remove(); });
      box.appendChild(img);
    }
    if (withBadge) box.appendChild(h("span", { class: "badge " + e.badge, text: e.badge }));
    if (e.minutes) box.appendChild(h("span", { class: "dur", text: e.minutes + "분" }));
    return box;
  }
  function filtered() {
    return EPS.filter(function (e) {
      return (view.ch === "all" || e.channel === view.ch) && (view.st === "all" || e.badge === view.st);
    });
  }

  // ------------------------------------------------------------ 고르기 줄
  function drawTabs() {
    var ct = $("chTabs"); ct.textContent = "";
    [{ key: "all", name: "두 채널" }].concat(META.channels).forEach(function (c) {
      ct.appendChild(h("button", { class: view.ch === c.key ? "on" : "", text: c.name,
        onclick: function () { view.ch = c.key; saveView(); drawAll(); } }));
    });
    var st = $("stTabs"); st.textContent = "";
    var counts = {};
    EPS.forEach(function (e) { if (view.ch === "all" || e.channel === view.ch) counts[e.badge] = (counts[e.badge] || 0) + 1; });
    ["all"].concat(BADGES).forEach(function (b) {
      if (b !== "all" && !counts[b] && view.st !== b) return;
      st.appendChild(h("button", { class: view.st === b ? "on" : "",
        text: b === "all" ? "모두" : b + " " + counts[b],
        onclick: function () { view.st = b; saveView(); drawAll(); } }));
    });
    Array.prototype.forEach.call($("viewTabs").children, function (b) {
      b.className = b.dataset.v === view.mode ? "on" : "";
    });
  }

  function drawSummary() {
    var list = EPS.filter(function (e) { return view.ch === "all" || e.channel === view.ch; });
    var views = list.reduce(function (s, e) { return s + (e.views || 0); }, 0);
    var next = list.filter(function (e) { return e.date >= META.today && e.badge !== "예약됨" && e.badge !== "공개됨"; })
      .sort(function (a, b) { return a.date.localeCompare(b.date); })[0];
    var parts = ["모두 " + list.length + "편"];
    if (views) parts.push("총 조회수 " + numText(views));
    if (next) parts.push("가장 급한 편: " + chInfo(next.channel).name + " " + next.ep + "편 (" + dateText(next.date) + " 공개)");
    $("summary").textContent = parts.join(" · ");
  }

  // ------------------------------------------------------------ 카드
  function drawCards() {
    var box = $("cards"); box.textContent = "";
    var list = filtered();
    if (!list.length) { box.appendChild(h("div", { class: "empty-box", text: "보여 드릴 편이 없습니다." })); return; }
    list.forEach(function (e) {
      var pct = Math.round(e.done_steps / META.steps.length * 100);
      box.appendChild(h("button", { class: "card", type: "button", onclick: function () { openDetail(e.id); } }, [
        thumbBox(e, true),
        h("div", { class: "card-body" }, [
          h("div", { class: "card-meta" }, [chTag(e.channel), e.ep + "편", "·", dateText(e.date) + " 공개"]),
          h("div", { class: "card-title" + (e.title ? "" : " empty"), text: e.title || "제목 아직 없음" }),
          h("div", { class: "bar" + (pct === 100 ? " full" : "") }, [h("i", { style: "width:" + pct + "%" })]),
          h("div", { class: "card-foot" }, [
            e.block ? h("span", { style: "color:var(--bad)", text: "막힘: " + e.block.slice(0, 30) })
                    : h("span", { text: e.done_steps + "/" + META.steps.length + "단계" }),
            e.views != null ? h("span", { class: "views", text: "조회 " + numText(e.views) }) : null
          ])
        ])
      ]));
    });
  }

  // ------------------------------------------------------------ 달력
  function drawCal() {
    if (!view.month) { var t = new Date(META.today + "T00:00:00"); view.month = new Date(t.getFullYear(), t.getMonth(), 1); }
    var m = view.month;
    $("monthName").textContent = m.getFullYear() + "년 " + (m.getMonth() + 1) + "월";
    var g = $("calGrid"); g.textContent = "";
    DOW.forEach(function (d) { g.appendChild(h("div", { class: "cal-dow", text: d })); });
    var first = m.getDay(), last = new Date(m.getFullYear(), m.getMonth() + 1, 0).getDate();
    var cells = Math.ceil((first + last) / 7) * 7;
    var list = filtered();
    for (var i = 0; i < cells; i++) {
      var n = i - first + 1;
      if (n < 1 || n > last) { g.appendChild(h("div", { class: "cal-day out" })); continue; }
      var key = m.getFullYear() + "-" + String(m.getMonth() + 1).padStart(2, "0") + "-" + String(n).padStart(2, "0");
      var day = h("div", { class: "cal-day" + (key === META.today ? " today" : "") }, [h("div", { class: "cal-num", text: n })]);
      list.filter(function (e) { return e.date === key; }).forEach(function (e) {
        var src = thumbSrc(e);
        day.appendChild(h("button", { class: "cal-ep", type: "button", onclick: function () { openDetail(e.id); } }, [
          src ? h("img", { src: src, alt: "", loading: "lazy", onerror: function () { this.remove(); } }) : null,
          h("div", { class: "t" }, [h("span", { class: "ch", style: "background:" + chInfo(e.channel).color,
            title: chInfo(e.channel).name, text: chInfo(e.channel).name.slice(0, 2) }), e.ep + "편", h("span", { class: "badge " + e.badge, text: e.badge })])
        ]));
      });
      g.appendChild(day);
    }
  }

  // ------------------------------------------------------------ PC 상태 · 시킨 일 · 기록
  function drawStatus() {
    var s = STATUS || {}, el = $("now");
    var mins = s.at ? (Date.now() - new Date(s.at).getTime()) / 60000 : 1e9;
    var working = s.state === "일함" && mins < 15, stale = s.state === "일함" && mins >= 15;
    el.className = "now" + (working ? " working" : stale ? " stale" : s.state === "막힘" ? " blocked" : "");
    $("nowState").textContent = !s.at ? "PC 소식이 아직 없습니다" : working ? "PC가 지금 일하는 중" :
      stale ? "일하다가 소식이 끊겼습니다" : s.state === "막힘" ? "막혔습니다" : "PC 쉬는 중";
    $("nowAt").textContent = s.at ? ago(s.at) + " 소식" : "";
    var d = $("nowDoing");
    if (working && s.doing) { d.hidden = false; d.textContent = s.doing; } else d.hidden = true;
    $("nowLast").textContent = s.last || "—";
    $("nowNext").textContent = s.next || "—";
  }

  function drawQueue() {
    var box = $("queue"); box.textContent = "";
    var items = QUEUE.filter(function (q) { return q.state !== "완료" || Date.now() - new Date(q.updated_at) < 864e5; });
    if (!items.length) { box.hidden = true; return; }
    box.hidden = false;
    var left = items.filter(function (q) { return q.state !== "완료"; }).length;
    box.appendChild(h("b", { text: left ? "시켜 두신 일 " + left + "건 — PC가 차례로 합니다" : "시켜 두신 일 — 다 했습니다" }));
    items.forEach(function (q) {
      box.appendChild(h("div", { class: "q-item" }, [
        h("div", { class: "what" }, [
          h("div", { text: q.label || q.kind }),
          q.note ? h("div", { class: "muted small", text: q.note }) : null,
          h("div", { class: "muted small", text: ago(q.created_at) + " 누르심" })
        ]),
        h("span", { class: "pill " + q.state, text: q.state === "요청" ? "기다리는 중" : q.state }),
        q.state === "요청" ? h("button", { class: "btn ghost small", text: "취소",
          onclick: function () { api("DELETE", "/api/queue/" + q.id).then(refresh); } }) : null
      ]));
    });
  }

  function drawLog(items) {
    var ol = $("logList"); ol.textContent = "";
    if (!items.length) ol.appendChild(h("li", {}, [h("span", { text: "" }), h("span", { class: "muted", text: "아직 기록이 없습니다" })]));
    items.forEach(function (r) {
      var d = new Date(r.at);
      ol.appendChild(h("li", {}, [
        h("span", { text: (d.getMonth() + 1) + "/" + d.getDate() + " " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0") }),
        h("span", { text: r.text })
      ]));
    });
  }

  // ------------------------------------------------------------ 자세히
  function openDetail(id) {
    view.open = id; view.tab = view.tab || "steps";
    drawDetail();
    var dlg = $("detail");
    if (!dlg.open) dlg.showModal();
  }

  function drawDetail() {
    var e = EPS.filter(function (x) { return x.id === view.open; })[0];
    var body = $("detailBody"); body.textContent = "";
    view.dirty = false;
    if (!e) { $("detail").close(); return; }

    var ytUrl = e.video_id ? "https://youtu.be/" + e.video_id : null;
    body.appendChild(h("div", { class: "d-head" }, [
      thumbBox(e, false),
      h("div", { class: "info" }, [
        h("div", { class: "card-meta" }, [chTag(e.channel), e.ep + "편", h("span", { class: "badge " + e.badge, text: e.badge })]),
        h("h3", { text: e.title || "제목 아직 없음" }),
        h("div", { class: "muted", text: dateText(e.date) + " 공개" + (e.minutes ? " · " + e.minutes + "분" : "") +
          (e.songs_total ? " · 곡 " + (e.songs_done || 0) + "/" + e.songs_total : "") }),
        e.views != null ? h("div", { text: "조회 " + numText(e.views) + (e.likes != null ? " · 좋아요 " + numText(e.likes) : "") +
          (e.privacy ? " · " + ({ public: "공개", private: "비공개", unlisted: "일부공개" }[e.privacy] || e.privacy) : "") }) : null,
        h("div", { class: "row gap" }, [
          ytUrl ? h("a", { class: "btn small", href: ytUrl, target: "_blank", rel: "noopener", text: "유튜브에서 보기" }) : null,
          h("button", { class: "btn primary small", text: e.badge === "예약됨" || e.badge === "공개됨" ? "다시 손보기 시키기" : "이 편 진행 시키기",
            onclick: function () { api("POST", "/api/episodes/" + e.id + "/run").then(function () { toast("PC에게 시켰습니다"); refresh(); }); } })
        ])
      ])
    ]));

    var tabs = h("div", { class: "tabs d-tabs" });
    [["steps", "아홉 단계"], ["text", "썸네일·제목·설명"], ["info", "정보 고치기"]].forEach(function (t) {
      tabs.appendChild(h("button", { class: view.tab === t[0] ? "on" : "", text: t[1],
        onclick: function () { view.tab = t[0]; drawDetail(); } }));
    });
    body.appendChild(tabs);

    if (view.tab === "steps") body.appendChild(stepsPane(e));
    else if (view.tab === "text") body.appendChild(textPane(e));
    else body.appendChild(infoPane(e));
  }

  function stepsPane(e) {
    var box = h("div", { class: "stack" });
    if (e.block) box.appendChild(h("div", { class: "alert", text: "막혀 있습니다 — " + e.block }));
    if (e.note) box.appendChild(h("div", { class: "note", text: e.note }));
    var list = h("div", { class: "steps" });
    META.steps.forEach(function (s) {
      var v = e.steps[s] || "작업대기";
      var sel = h("select", { "aria-label": s + " 상태", onchange: function () {
        var p = {}; p[s] = this.value;
        api("PATCH", "/api/episodes/" + e.id, { steps: p }).then(refresh);
      } }, META.states.map(function (st) { return h("option", { value: st, selected: st === v, text: st }); }));
      list.appendChild(h("div", { class: "step " + v }, [h("span", { class: "name", text: s }), sel]));
      var memo = (e.step_notes || {})[s];
      if (memo) list.appendChild(h("div", { class: "alert small", text: s + " — " + memo }));
    });
    box.appendChild(list);
    box.appendChild(h("p", { class: "muted small", text: "보통은 PC의 Claude가 알아서 바꿉니다. 직접 고치셔도 됩니다." }));
    return box;
  }

  function field(labelText, value, opts) {
    opts = opts || {};
    var input = opts.rows ? h("textarea", { rows: opts.rows }) : h("input", { type: "text" });
    input.value = value || "";
    var count = h("span", { class: "count" });
    function upd() {
      var n = input.value.length;
      count.textContent = n + (opts.max ? " / " + opts.max : "") + "자";
      count.className = "count" + (opts.max && n > opts.max ? " over" : "");
    }
    input.addEventListener("input", upd); upd();
    var lab = h("label", {}, [h("span", { class: "row" }, [labelText, h("span", { class: "spacer" }), count]), input]);
    lab.input = input;
    return lab;
  }

  function textPane(e) {
    var lines = (e.thumb_lines || []).slice(0, 4); while (lines.length < 4) lines.push("");
    var f = [
      field("썸네일 1줄", lines[0], { max: 10 }), field("썸네일 2줄", lines[1], { max: 8 }),
      field("썸네일 3줄", lines[2], { max: 8 }), field("썸네일 4줄 ([ ] 안이 강조색)", lines[3], { max: 16 })
    ];
    var title = field("유튜브 제목", e.title, { max: 100, rows: 2 });
    var desc = field("유튜브 설명", e.description, { rows: 10 });
    var file = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp" });
    var box = h("div", { class: "stack" }, [
      h("div", { class: "edit-grid" }, f),
      title, desc,
      h("label", {}, ["썸네일 그림 바꾸기 (선택)", file]),
      h("div", { class: "row gap" }, [
        h("button", { class: "btn primary", text: "이 내용으로 반영 시키기", onclick: function () {
          var btn = this; btn.disabled = true;
          var body = { title: title.input.value, description: desc.input.value,
            thumb_lines: f.map(function (x) { return x.input.value; }) };
          var up = file.files[0] ? (function () { var fd = new FormData(); fd.append("file", file.files[0]);
            return api("POST", "/api/episodes/" + e.id + "/thumbnail", fd); })() : Promise.resolve();
          up.then(function () { return api("POST", "/api/episodes/" + e.id + "/edit", body); })
            .then(function (r) {
              view.dirty = false;
              toast(r.changed.length ? r.changed.join(" · ") + " 고치기를 PC에게 시켰습니다" : "바뀐 내용이 없습니다");
              refresh();
            })
            .catch(function (err) { toast(err.message); })
            .finally(function () { btn.disabled = false; });
        } }),
        h("span", { class: "muted small", text: "사이트에 먼저 저장되고, PC가 유튜브와 썸네일에 실제로 반영합니다." })
      ])
    ]);
    return box;
  }

  function infoPane(e) {
    var date = h("input", { type: "date", value: e.date || "" });
    var minutes = h("input", { type: "number", min: 0, value: e.minutes != null ? e.minutes : "" });
    var vid = h("input", { type: "text", value: e.video_id || "", placeholder: "예: https://youtu.be/xxxxxxxxxxx" });
    var block = h("input", { type: "text", value: e.block || "", placeholder: "막힌 이유 (비우면 막힘 풀림)" });
    var note = h("textarea", { rows: 3 }); note.value = e.note || "";
    return h("div", { class: "stack" }, [
      h("div", { class: "edit-grid" }, [
        h("label", {}, ["공개 날짜", date]), h("label", {}, ["길이(분)", minutes]),
        h("label", {}, ["유튜브 영상 주소", vid]), h("label", {}, ["막힘", block])
      ]),
      h("label", {}, ["메모", note]),
      h("div", { class: "row gap" }, [
        h("button", { class: "btn primary", text: "저장", onclick: function () {
          var m = /(?:youtu\.be\/|v=|shorts\/)([A-Za-z0-9_-]{11})/.exec(vid.value);
          api("PATCH", "/api/episodes/" + e.id, {
            date: date.value, minutes: minutes.value === "" ? null : Number(minutes.value),
            video_id: m ? m[1] : vid.value.trim(), block: block.value.trim(), note: note.value
          }).then(function () { view.dirty = false; toast("저장했습니다"); refresh(); }).catch(function (err) { toast(err.message); });
        } }),
        h("span", { class: "spacer" }),
        h("button", { class: "btn danger small", text: "이 편 지우기", onclick: function () {
          if (!confirm(chInfo(e.channel).name + " " + e.ep + "편을 사이트에서 지울까요? (유튜브 영상은 그대로입니다)")) return;
          api("DELETE", "/api/episodes/" + e.id).then(function () { $("detail").close(); refresh(); });
        } })
      ])
    ]);
  }

  // ------------------------------------------------------------ 버튼들
  function sendQueue(kind, label, btn) {
    btn.disabled = true;
    api("POST", "/api/queue", { kind: kind, label: label })
      .then(function () { $("nowMsg").textContent = label + "을(를) 보냈습니다"; refresh(); })
      .catch(function (err) { $("nowMsg").textContent = err.message; })
      .finally(function () { setTimeout(function () { btn.disabled = false; }, 1500); });
  }
  $("btnGo").addEventListener("click", function () { sendQueue("이어서", "이어서 진행", this); });
  $("btnStop").addEventListener("click", function () { sendQueue("멈춤", "잠깐 멈춤", this); });
  $("viewTabs").addEventListener("click", function (ev) {
    var v = ev.target.dataset && ev.target.dataset.v; if (!v) return;
    view.mode = v; saveView(); drawAll();
  });
  $("prevM").addEventListener("click", function () { view.month = new Date(view.month.getFullYear(), view.month.getMonth() - 1, 1); drawCal(); });
  $("nextM").addEventListener("click", function () { view.month = new Date(view.month.getFullYear(), view.month.getMonth() + 1, 1); drawCal(); });
  $("btnAdd").addEventListener("click", function () {
    var sel = $("addCh"); sel.textContent = "";
    META.channels.forEach(function (c) { sel.appendChild(h("option", { value: c.key, selected: view.ch === c.key, text: c.name })); });
    $("addDlg").showModal();
  });
  $("addCancel").addEventListener("click", function () { $("addDlg").close(); });
  $("addForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var fd = new FormData(this);
    api("POST", "/api/episodes", { channel: fd.get("channel"), date: fd.get("date"), start: !!fd.get("start") })
      .then(function (e) { $("addDlg").close(); toast(chInfo(e.channel).name + " " + e.ep + "편을 넣었습니다"); refresh(); })
      .catch(function (err) { toast(err.message); });
  });
  $("btnStats").addEventListener("click", function () {
    var b = this; b.disabled = true;
    api("POST", "/api/youtube/refresh").then(function (r) { toast("조회수를 " + r.updated + "편 새로 받았습니다"); refresh(); })
      .catch(function (err) { toast(err.message); }).finally(function () { b.disabled = false; });
  });
  $("detail").addEventListener("close", function () { view.open = null; view.dirty = false; });
  // 고쳐 쓰는 중인 글은 30초 새로고침에 날아가지 않게 합니다
  $("detail").addEventListener("input", function () { view.dirty = true; });

  // ------------------------------------------------------------ 그리기 · 새로고침
  function drawAll() {
    drawTabs(); drawSummary(); drawStatus(); drawQueue();
    $("cards").hidden = view.mode !== "cards"; $("cal").hidden = view.mode !== "cal";
    if (view.mode === "cards") drawCards(); else drawCal();
    if (view.open && $("detail").open) {
      if (!view.dirty) drawDetail();
    }
  }

  function refresh() {
    return Promise.all([api("GET", "/api/episodes"), api("GET", "/api/queue"), api("GET", "/api/status"), api("GET", "/api/log")])
      .then(function (r) { EPS = r[0]; QUEUE = r[1]; STATUS = r[2]; drawAll(); drawLog(r[3]); })
      .catch(function (err) { if (err.message !== "login") toast("불러오지 못했습니다: " + err.message); });
  }

  api("GET", "/api/meta").then(function (m) {
    META = m;
    $("btnStats").hidden = !m.youtube_stats;
    refresh();
    setInterval(function () { if (!document.hidden) refresh(); }, 30000);
  });
})();
