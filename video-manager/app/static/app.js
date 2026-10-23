(function () {
  "use strict";

  var META = null, EPS = [], QUEUE = [], STATUS = {};
  var view = { ch: "all", st: "all", mode: "list", month: null, open: null, tab: "details", sortAsc: false };
  try { var saved = JSON.parse(localStorage.getItem("vm-view") || "{}");
    ["ch", "st", "mode"].forEach(function (k) { if (saved[k]) view[k] = saved[k]; });
    if (saved.v2 !== 1) view.mode = "list"; } catch (e) {} // 처음 한 번은 새 목록 보기로

  var BADGES = ["검토대기", "다시만들기", "고치는중", "제작중", "막힘", "완료", "예약됨", "공개됨", "준비"];
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
    try { localStorage.setItem("vm-view", JSON.stringify({ ch: view.ch, st: view.st, mode: view.mode, v2: 1 })); } catch (e) {}
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


  // ------------------------------------------------------------ 목록 (유튜브 스튜디오 ‘채널 콘텐츠’처럼)
  var PRIV = { public: ["공개", "🌐"], private: ["비공개", "🔒"], unlisted: ["일부 공개", "🔗"] };
  function privOf(e) {
    if (e.privacy && PRIV[e.privacy]) return PRIV[e.privacy];
    if (e.badge === "예약됨") return ["예약", "🕒"];
    if (e.badge === "공개됨") return ["공개", "🌐"];
    return ["초안", "📝"];
  }
  function dateLabel(e) {
    if (e.badge === "공개됨" || e.privacy === "public") return "게시일";
    if (e.badge === "예약됨") return "예약";
    return "공개 예정";
  }
  function dotDate(d) {
    if (!d) return "날짜 미정";
    var p = d.split("-"); return p[0] + ". " + Number(p[1]) + ". " + Number(p[2]) + ".";
  }
  function oneLine(s) { return String(s || "").replace(/\s+/g, " ").trim(); }
  function drawList() {
    var body = $("listBody"); body.textContent = "";
    var list = filtered().slice().sort(function (x, y) {
      var c = String(x.date || "").localeCompare(String(y.date || ""));
      return view.sortAsc ? c : -c;
    });
    $("sortArrow").textContent = view.sortAsc ? "↑" : "↓";
    if (!list.length) { body.appendChild(h("div", { class: "empty-box", text: "보여 드릴 편이 없습니다." })); return; }
    list.forEach(function (e) {
      var src = thumbSrc(e);
      var pv = privOf(e);
      var pct = Math.round(e.done_steps / META.steps.length * 100);
      var yt = e.video_id ? "https://youtu.be/" + e.video_id : null;
      var row = h("div", { class: "yt-row", role: "button", tabindex: "0",
        onclick: function (ev) { if (ev.target.closest("a,button")) return; openDetail(e.id); },
        onkeydown: function (ev) { if (ev.key === "Enter") openDetail(e.id); } }, [
        h("div", { class: "c-video" }, [
          h("div", { class: "yt-thumb" }, [
            src ? h("img", { src: src, alt: "", loading: "lazy", onerror: function () { this.remove(); } })
                : h("div", { class: "yt-nothumb", text: (e.thumb_lines || []).filter(Boolean)[0] || "썸네일 없음" }),
            e.minutes ? h("span", { class: "yt-dur", text: e.minutes + ":00" }) : null
          ]),
          h("div", { class: "yt-text" }, [
            h("div", { class: "yt-title" + (e.title ? "" : " empty") }, [chTag(e.channel), " ", e.title || (e.ep + "편 · 제목 아직 없음")]),
            h("div", { class: "yt-desc", text: oneLine(e.description) || "설명 없음" }),
            h("div", { class: "yt-actions" }, [
              h("button", { type: "button", class: "yt-ic", title: "세부정보", onclick: function () { openDetail(e.id); } }, ["✏️"]),
              yt ? h("a", { class: "yt-ic", href: yt, target: "_blank", rel: "noopener", title: "유튜브에서 보기" }, ["📊"]) : null,
              h("button", { type: "button", class: "yt-ic", title: e.badge === "예약됨" || e.badge === "공개됨" ? "다시 손보기 시키기" : "이 편 진행 시키기",
                onclick: function () { api("POST", "/api/episodes/" + e.id + "/run").then(function () { toast("PC에게 시켰습니다"); refresh(); }); } }, ["▶️"])
            ])
          ])
        ]),
        h("div", { class: "c-prog" }, [
          e.block ? h("span", { class: "yt-block", text: "막힘" })
                  : h("span", { class: "badge " + e.badge, text: e.badge }),
          h("div", { class: "bar" + (pct === 100 ? " full" : "") }, [h("i", { style: "width:" + pct + "%" })]),
          h("small", { class: "muted", text: e.done_steps + "/" + META.steps.length + "단계" })
        ]),
        h("div", { class: "c-priv" }, [h("span", { class: "yt-priv" }, [pv[1] + " ", pv[0]])]),
        h("div", { class: "c-date" }, [h("div", { text: dotDate(e.date) }), h("small", { class: "muted", text: dateLabel(e) })]),
        h("div", { class: "c-num", text: e.views != null ? e.views.toLocaleString("ko-KR") : "—" }),
        h("div", { class: "c-num", text: e.likes != null ? e.likes.toLocaleString("ko-KR") : "—" })
      ]);
      body.appendChild(row);
    });
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
    view.open = id; view.tab = "details";
    drawDetail();
    var dlg = $("detail");
    if (!dlg.open) dlg.showModal();
  }

  function drawDetail() {
    var e = EPS.filter(function (x) { return x.id === view.open; })[0];
    var body = $("detailBody"); body.textContent = "";
    view.dirty = false;
    if (!e) { $("detail").close(); return; }
    if (["details", "steps", "info"].indexOf(view.tab) < 0) view.tab = "details";
    var src = thumbSrc(e);
    var close = function () { $("detail").close(); };
    var nav = h("aside", { class: "st-nav" }, [
      h("button", { type: "button", class: "st-back", onclick: close }, ["← 채널 콘텐츠"]),
      h("div", { class: "st-mini" }, [
        h("div", { class: "yt-thumb" }, [src ? h("img", { src: src, alt: "" }) : h("div", { class: "yt-nothumb", text: "썸네일 없음" }),
          e.minutes ? h("span", { class: "yt-dur", text: e.minutes + ":00" }) : null]),
        h("div", { class: "muted small", text: "내 동영상 · " + chInfo(e.channel).name + " " + e.ep + "편" }),
        h("div", { class: "st-mini-title", text: e.title || "제목 아직 없음" })
      ]),
      h("nav", {}, [["details", "✏️  세부정보"], ["steps", "📋  진행 단계"], ["info", "⚙️  기타 정보"]].map(function (t) {
        return h("button", { type: "button", class: "st-menu" + (view.tab === t[0] ? " on" : ""), onclick: function () {
          if (view.dirty && !confirm("저장하지 않은 내용이 있어요. 다른 메뉴로 갈까요?")) return;
          view.tab = t[0]; drawDetail();
        } }, [t[1]]);
      }))
    ]);
    var main = h("section", { class: "st-main" });
    if (view.tab === "details") detailsPane(e, main);
    else {
      main.appendChild(h("div", { class: "st-top" }, [h("h2", { text: view.tab === "steps" ? "진행 단계" : "기타 정보" }), h("span", { class: "spacer" }),
        h("button", { type: "button", class: "btn ghost small", onclick: close }, ["닫기 ✕"])]));
      main.appendChild(view.tab === "steps" ? stepsPane(e) : infoPane(e));
    }
    body.appendChild(h("div", { class: "st-wrap" }, [nav, main]));
  }

  function box(label, help, child) {
    return h("div", { class: "st-box" }, [h("div", { class: "st-box-label" }, [].concat(label, help ? [h("span", { class: "st-help", title: help, text: "?" })] : [])), child]);
  }
  function detailsPane(e, main) {
    var pv = privOf(e);
    var lines = (e.thumb_lines || []).slice(0, 4); while (lines.length < 4) lines.push("");
    var title = h("textarea", { class: "st-input", rows: 2, maxlength: 100 }); title.value = e.title || "";
    var desc = h("textarea", { class: "st-input", rows: 14 }); desc.value = e.description || "";
    var tc = h("span", { class: "st-count" }), dc = h("span", { class: "st-count" });
    var upd = function () { tc.textContent = title.value.length + "/100"; tc.className = "st-count" + (title.value.length > 100 ? " over" : ""); dc.textContent = desc.value.length + "/5000"; };
    title.addEventListener("input", upd); desc.addEventListener("input", upd); upd();
    var lineIns = lines.map(function (v, i) { var x = h("input", { type: "text", value: v, placeholder: (i + 1) + "줄" + (i === 3 ? " ([ ] 안이 강조색)" : "") }); return x; });
    var file = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp", hidden: true });
    var src = thumbSrc(e);
    var thumbImg = h("div", { class: "st-thumb-now" }, [src ? h("img", { src: src, alt: "" }) : h("div", { class: "yt-nothumb", text: "썸네일 없음" })]);
    file.addEventListener("change", function () {
      if (!file.files[0]) return;
      var u = URL.createObjectURL(file.files[0]);
      thumbImg.textContent = ""; thumbImg.appendChild(h("img", { src: u, alt: "" }));
      view.dirty = true; saveBtn.disabled = false; undoBtn.disabled = false;
    });
    var undoBtn = h("button", { type: "button", class: "btn st-pill", disabled: true, onclick: function () { view.dirty = false; drawDetail(); } }, ["변경사항 실행취소"]);
    var saveBtn = h("button", { type: "button", class: "btn st-pill primary", disabled: true, onclick: function () {
      var btn = this; btn.disabled = true;
      var bodyData = { title: title.value, description: desc.value, thumb_lines: lineIns.map(function (x) { return x.value; }) };
      var up = file.files[0] ? (function () { var fd = new FormData(); fd.append("file", file.files[0]);
        return api("POST", "/api/episodes/" + e.id + "/thumbnail", fd); })() : Promise.resolve();
      up.then(function () { return api("POST", "/api/episodes/" + e.id + "/edit", bodyData); })
        .then(function (r) { view.dirty = false; toast(r.changed.length ? r.changed.join(" · ") + " 고치기를 PC에게 시켰습니다" : "바뀐 내용이 없습니다"); refresh(); })
        .catch(function (err) { toast(err.message); btn.disabled = false; });
    } }, ["저장"]);
    main.addEventListener("input", function () { saveBtn.disabled = false; undoBtn.disabled = false; });

    main.appendChild(h("div", { class: "st-top" }, [h("h2", { text: "동영상 세부정보" }), h("span", { class: "spacer" }), undoBtn, saveBtn,
      h("button", { type: "button", class: "btn ghost small", title: "닫기", onclick: function () {
        if (view.dirty && !confirm("저장하지 않은 내용이 있어요. 닫을까요?")) return; $("detail").close(); } }, ["✕"])]));

    var left = h("div", { class: "st-left" }, [
      box([h("span", {}, ["제목(필수 항목)"])], "유튜브에 보이는 제목이에요. 저장하면 PC가 유튜브에 반영해요", h("div", {}, [title, tc])),
      box([h("span", {}, ["설명"])], "유튜브 설명란이에요", h("div", {}, [desc, dc])),
      h("div", { class: "st-sec" }, [
        h("h3", { text: "썸네일" }),
        h("p", { class: "muted small", text: "썸네일 그림과 그 위에 얹을 글씨(4줄)예요. 저장하면 PC가 새 썸네일을 만들어 유튜브에 반영해요." }),
        h("div", { class: "st-thumb-row" }, [
          thumbImg,
          h("div", { class: "st-thumb-lines" }, lineIns.concat([
            h("button", { type: "button", class: "btn small", onclick: function () { file.click(); } }, ["🖼 그림 바꾸기"]), file
          ]))
        ])
      ]),
      (e.tags && e.tags.length) ? h("div", { class: "st-sec" }, [h("h3", { text: "태그" }), h("div", { class: "st-tags" }, e.tags.map(function (t) { return h("span", { text: t }); }))]) : null
    ]);

    var yt = e.video_id ? "https://youtu.be/" + e.video_id : null;
    // 미리보기: 공개 영상은 여기서 바로 재생. 예약·비공개 영상은 유튜브가 다른 사이트 안에서 안 틀어 줘서,
    // 누르면 유튜브 스튜디오(채널 주인으로 로그인된 브라우저)에서 바로 볼 수 있게 엶
    var studio = e.video_id ? "https://studio.youtube.com/video/" + e.video_id + "/edit" : null;
    var player = e.video_id && (e.privacy === "public" || e.privacy === "unlisted")
      ? h("iframe", { class: "st-player", src: "https://www.youtube.com/embed/" + e.video_id, title: "동영상 미리보기", allow: "encrypted-media; picture-in-picture", allowfullscreen: true })
      : h(studio ? "a" : "div", { class: "st-player st-player-img", href: studio, target: studio ? "_blank" : null, rel: studio ? "noopener" : null,
          title: studio ? "유튜브 스튜디오에서 미리보기 (채널 주인으로 로그인된 브라우저에서 열려요)" : null },
          [src ? h("img", { src: src, alt: "" }) : h("div", { class: "yt-nothumb", text: "미리보기 없음" }),
           studio ? h("span", { class: "st-play", text: "▶" }) : null,
           studio ? h("span", { class: "st-play-note", text: "눌러서 스튜디오에서 미리보기" }) : null]);
    var review = null;
    if (e.review === "검토대기") {
      review = h("div", { class: "st-review" }, [
        h("b", { text: "🕵 검토 대기 중" }),
        h("p", { class: "small", text: "PC가 일부 공개로 올려 두었어요. 왼쪽 미리보기에서 틀어 보고 하나씩 체크해 주세요." }),
        reviewChecker(e)
      ]);
    } else if (e.review === "다시만들기") {
      review = h("div", { class: "st-review redo" }, [h("b", { text: "🔁 다시 만드는 중" }), h("p", { class: "small", text: "PC가 예전 영상을 삭제하고 다시 만들어요. 다 되면 다시 검토 대기로 와요." })]);
    } else if (e.review === "고치는중") {
      review = h("div", { class: "st-review redo" }, [h("b", { text: "✏️ 고치는 중" }), h("p", { class: "small", text: "영상은 그대로 두고, 체크한 것(썸네일·제목·설명)만 PC가 바꿔요. 다 되면 다시 검토 대기로 와요." })]);
    } else if (e.review === "승인") {
      review = h("div", { class: "st-review ok" }, [h("b", { text: "✅ 승인함" }), h("p", { class: "small", text: "PC가 예약 공개로 바꿔요 (시켜 둔 일에서 진행 상황을 볼 수 있어요)." })]);
    }
    var right = h("div", { class: "st-right" }, [
      review,
      h("div", { class: "st-card" }, [
        player,
        h("div", { class: "st-card-body" }, [
          h("div", { class: "muted small", text: "동영상 링크" }),
          yt ? h("div", { class: "row gap" }, [h("a", { href: yt, target: "_blank", rel: "noopener", class: "st-link", text: yt }),
            h("button", { type: "button", class: "yt-ic", title: "링크 복사", onclick: function () {
              (navigator.clipboard ? navigator.clipboard.writeText(yt) : Promise.reject()).then(function () { toast("링크를 복사했습니다"); }, function () { toast(yt); }); } }, ["📋"])])
             : h("div", { class: "muted", text: "아직 유튜브에 안 올라감" }),
          h("div", { class: "st-kv" }, [
            h("div", {}, [h("span", { class: "muted small", text: "공개 상태" }), h("b", { text: pv[1] + " " + pv[0] })]),
            h("div", {}, [h("span", { class: "muted small", text: dateLabel(e) }), h("b", { text: dotDate(e.date) })]),
            h("div", {}, [h("span", { class: "muted small", text: "조회수" }), h("b", { text: e.views != null ? e.views.toLocaleString("ko-KR") : "—" })]),
            h("div", {}, [h("span", { class: "muted small", text: "좋아요" }), h("b", { text: e.likes != null ? e.likes.toLocaleString("ko-KR") : "—" })]),
            h("div", {}, [h("span", { class: "muted small", text: "길이 · 곡" }), h("b", { text: (e.minutes ? e.minutes + "분" : "—") + (e.songs_total ? " · " + (e.songs_done || 0) + "/" + e.songs_total + "곡" : "") })]),
            h("div", {}, [h("span", { class: "muted small", text: "진행" }), h("b", { text: (e.block ? "막힘 · " : "") + e.done_steps + "/" + META.steps.length + "단계 (" + e.badge + ")" })])
          ]),
          studio ? h("div", { class: "row gap" }, [
            h("a", { class: "btn small primary", href: studio, target: "_blank", rel: "noopener" }, ["▶ 스튜디오에서 미리보기"]),
            h("a", { class: "btn small", href: yt, target: "_blank", rel: "noopener" }, ["유튜브에서 보기"])
          ]) : null,
          studio ? h("p", { class: "muted small", text: "예약·비공개 영상도 채널 주인 구글 계정으로 로그인된 브라우저에서는 볼 수 있어요. 다른 계정이면 ‘볼 수 없는 동영상’으로 나와요." }) : null,
          h("div", { class: "row gap" }, [
            h("button", { type: "button", class: "btn small", onclick: function () {
              api("POST", "/api/episodes/" + e.id + "/run").then(function () { toast("PC에게 시켰습니다"); refresh(); }); } },
              [e.badge === "예약됨" || e.badge === "공개됨" ? "다시 손보기 시키기" : "이 편 진행 시키기"])
          ])
        ])
      ])
    ]);
    main.appendChild(h("div", { class: "st-cols" }, [left, right]));
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
  $("sortDate").addEventListener("click", function () { view.sortAsc = !view.sortAsc; drawList(); });
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
  // 검토 체크: 썸네일 · 제목 · 설명 · 영상을 하나씩 OK / 고치기 → ‘검토 완료’ (세부정보 화면 · 검토할 영상 목록에서 같이 씀)
  function reviewChecker(e) {
    var PARTS = [["썸네일", "🖼"], ["제목", "🔤"], ["설명", "📝"], ["영상", "🎬"]];
    var chk = {}, memo = {}, rows = {};
    var doneBtn = h("button", { type: "button", class: "btn primary", disabled: true }, ["검토 완료"]);
    var sum = h("p", { class: "small rv-sum", text: "네 가지를 모두 체크해 주세요" });
    var redraw = function () {
      var bad = PARTS.filter(function (p) { return chk[p[0]] === false; }).map(function (p) { return p[0]; });
      var all = PARTS.every(function (p) { return chk[p[0]] !== undefined; });
      PARTS.forEach(function (p) {
        var r = rows[p[0]];
        r.ok.classList.toggle("on", chk[p[0]] === true);
        r.no.classList.toggle("on", chk[p[0]] === false);
        r.memo.style.display = chk[p[0]] === false ? "" : "none";
      });
      doneBtn.disabled = !all;
      sum.textContent = !all ? "네 가지를 모두 체크해 주세요"
        : !bad.length ? "모두 OK → 승인하면 " + dotDate(e.date) + "에 맞춰 예약 공개로 바뀌어요"
        : bad.indexOf("영상") >= 0 ? "영상이 별로 → 지금 영상은 유튜브에서 삭제하고 다시 만들어요 (되돌릴 수 없어요)"
        : bad.join(" · ") + "만 고쳐요 → 영상은 그대로 두고 그것만 바꿔요";
      doneBtn.textContent = !all ? "검토 완료" : !bad.length ? "✅ 검토 완료 · 승인" : bad.indexOf("영상") >= 0 ? "🔁 검토 완료 · 다시 만들기" : "✏️ 검토 완료 · 고치기";
    };
    var list = PARTS.map(function (p) {
      var k = p[0];
      var ok = h("button", { type: "button", class: "rv-btn ok", onclick: function () { chk[k] = true; redraw(); } }, ["👍 OK"]);
      var no = h("button", { type: "button", class: "rv-btn no", onclick: function () { chk[k] = false; redraw(); memoBox.focus(); } }, ["👎 고치기"]);
      var memoBox = h("input", { class: "rv-memo", placeholder: k + "의 무엇이 별로인가요? (예: " + ({ 썸네일: "글자가 얼굴을 가려", 제목: "너무 길어", 설명: "첫 줄이 밋밋해", 영상: "목소리가 너무 빨라" })[k] + ")",
        oninput: function () { memo[k] = memoBox.value; } });
      rows[k] = { ok: ok, no: no, memo: memoBox };
      return h("div", { class: "rv-row" }, [h("div", { class: "rv-line" }, [h("b", { text: p[1] + " " + k }), h("div", { class: "rv-pick" }, [ok, no])]), memoBox]);
    });
    doneBtn.onclick = function () {
      var bad = PARTS.filter(function (p) { return chk[p[0]] === false; }).map(function (p) { return p[0]; });
      var name = chInfo(e.channel).name + " " + e.ep + "편";
      var q = !bad.length ? name + "을 승인할까요? PC가 예약 공개로 바꿔요."
        : bad.indexOf("영상") >= 0 ? name + " 영상을 다시 만들까요?\n※ 지금 올라간 영상은 유튜브에서 삭제돼요 (되돌릴 수 없어요)"
        : name + "의 " + bad.join(" · ") + "만 고칠까요? 영상은 그대로예요.";
      if (!confirm(q)) return;
      api("POST", "/api/episodes/" + e.id + "/review", { checks: chk, notes: memo }).then(function () {
        toast(!bad.length ? "승인했어요. PC가 예약 공개로 바꿔요" : bad.indexOf("영상") >= 0 ? "다시 만들기를 시켰어요" : bad.join(" · ") + " 고치기를 시켰어요");
        refresh();
      }).catch(function (err) { toast(err.message); });
    };
    var wrap = h("div", { class: "rv-check" }, [h("div", { class: "rv-list" }, list), sum, h("div", { class: "row gap" }, [doneBtn])]);
    redraw();
    return wrap;
  }

  // 검토할 영상 목록 (검토 완료하면 여기서 빠짐)
  function drawReview() {
    var box = $("reviewBox");
    var list = EPS.filter(function (e) { return e.review === "검토대기" && (view.ch === "all" || e.channel === view.ch); })
      .sort(function (x, y) { return String(x.date).localeCompare(String(y.date)); });
    box.hidden = !list.length;
    box.innerHTML = "";
    if (!list.length) return;
    box.appendChild(h("div", { class: "rvq-head" }, [h("b", { text: "🕵 검토할 영상 " + list.length + "편" }),
      h("span", { class: "muted small", text: "썸네일 · 제목 · 설명 · 영상을 체크하고 검토 완료를 누르면 여기서 빠져요" })]));
    list.forEach(function (e) {
      var src = thumbSrc(e);
      var yt = e.video_id ? "https://youtu.be/" + e.video_id : null;
      box.appendChild(h("div", { class: "rvq-row" }, [
        h("button", { type: "button", class: "rvq-thumb", title: "세부정보 열기 (영상 미리보기)", onclick: function () { openDetail(e.id); } }, [
          src ? h("img", { src: src, alt: "", loading: "lazy", onerror: function () { this.remove(); } }) : h("span", { text: "썸네일 없음" }),
          h("span", { class: "rvq-play", text: "▶" })
        ]),
        h("div", { class: "rvq-info" }, [
          h("div", { class: "yt-title" }, [chTag(e.channel), " ", e.ep + "편 · " + (e.title || "제목 없음")]),
          h("div", { class: "muted small", text: dotDate(e.date) + " 공개 예정" + (yt ? " · " : "") }, [yt ? h("a", { href: yt, target: "_blank", rel: "noopener", text: "유튜브에서 보기" }) : null]),
          h("div", { class: "yt-desc", text: oneLine(e.description) || "설명 없음" })
        ]),
        reviewChecker(e)
      ]));
    });
  }

  function drawAll() {
    drawTabs(); drawSummary(); drawStatus(); drawQueue(); drawReview();
    $("list").hidden = view.mode !== "list"; $("cards").hidden = view.mode !== "cards"; $("cal").hidden = view.mode !== "cal";
    if (view.mode === "list") drawList(); else if (view.mode === "cards") drawCards(); else drawCal();
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
