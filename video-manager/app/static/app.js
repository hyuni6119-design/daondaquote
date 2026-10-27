(function () {
  "use strict";

  var META = null, EPS = [], QUEUE = [], STATUS = {};
  var SIDE_NAV = document.getElementById("sideNav");
  var TOOL_PAGES = { refs: 1, saved: 1, log: 1, settings: 1 }; // 채널과 따로 있는 메뉴
  var TOOL_SUB = { refs: "레퍼런스 채널을 분석해서 프롬프트를 만들어요 (채널과 따로)", lyrics: "참고 가사로 수노에 넣을 새 가사를 만들어요 (채널과 따로)",
    saved: "저장해 둔 레퍼런스 채널 — 채널마다 골라 써요", log: "사이트·서버·PC가 한 일", settings: "서버 일꾼 · 저장 공간 · 채널 연결" };
  var OLD_PAGE = { upload: "make", titles: "make", rules: "chset", prompts: "chset", thumbs: "list", shop: "list", lyrics: "chset" }; // 예전 메뉴 → 새 메뉴
  var UP_PRESET = null; // 🎬 새 영상 만들기에서 올리기 창을 열 때 채널·날짜 미리 채움
  var view = { ch: "all", st: "all", mode: "list", month: null, open: null, tab: "details", sortAsc: false };
  try { var saved = JSON.parse(localStorage.getItem("vm-view") || "{}");
    ["ch", "st", "mode", "page"].forEach(function (k) { if (saved[k]) view[k] = saved[k]; });
    if (saved.v2 !== 1) view.mode = "list"; } catch (e) {} // 처음 한 번은 새 목록 보기로

  var BADGES = ["검토대기", "다시만들기", "고치는중", "제작중", "막힘", "완료", "예약됨", "공개됨", "비공개", "일부공개", "준비"];
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
    try { localStorage.setItem("vm-view", JSON.stringify({ ch: view.ch, st: view.st, mode: view.mode, page: view.page, v2: 1 })); } catch (e) {}
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
    // 왼쪽 채널 목록 (라이브 관리자처럼) — 채널은 ＋ 로 늘릴 수 있음
    if (view.ch !== "all" && !META.channels.some(function (c) { return c.key === view.ch; })) view.ch = "all";
    var nav = $("channelNav"); nav.textContent = "";
    var activeBtn = null;
    [{ key: "all", name: "전체 채널" }].concat(META.channels).forEach(function (c) {
      var n = EPS.filter(function (e) { return c.key === "all" || e.channel === c.key; }).length;
      var wait = EPS.filter(function (e) { return (c.key === "all" || e.channel === c.key) && e.review === "검토대기"; }).length;
      var btn = nav.appendChild(h("button", { type: "button", class: "channel-item" + (view.ch === c.key ? " active" : ""),
        onclick: function (ev) { if (ev.target.closest("[data-edit]")) return; view.ch = c.key; saveView(); if (TOOL_PAGES[view.page]) setPage("list"); else drawAll(); } }, [
        h("span", { class: "ci-name" }, [c.key === "all" ? null : h("i", { class: "ci-dot", style: "background:" + c.color }), c.display || c.name]),
        h("span", { class: "cnt" }, [wait ? h("b", { class: "ci-wait", title: "검토 대기", text: "🕵" + wait }) : null, String(n),
          c.key === "all" ? null : h("span", { class: "edit", "data-edit": c.key, title: "채널 이름·색 바꾸기", onclick: function () { openChannelDialog(c); } }, ["✎"])])
      ]));
      if (view.ch === c.key && !TOOL_PAGES[view.page]) activeBtn = btn;
      if (TOOL_PAGES[view.page]) btn.classList.remove("active");
    });
    // 고른 채널 바로 아래에 메뉴 (채널 → 메뉴 순서)
    if (activeBtn) activeBtn.after(SIDE_NAV); else SIDE_NAV.remove();
    var cur = META.channels.filter(function (c) { return c.key === view.ch; })[0];
    $("pageTitle").textContent = cur ? (cur.display || cur.name) : "전체 채널";
    $("pageSub").textContent = cur ? "이 채널의 편마다 썸네일, 제목, 진행상황을 봅니다" : META.channels.map(function (c) { return c.display || c.name; }).join(" · ") + " — 편마다 썸네일, 제목, 진행상황을 한눈에 봅니다";
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
    if (e.badge === "비공개") return "예약 없음 (원래 공개일)";
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

  // 📌 내가 할 일 — 고른 채널에서 사장님이 직접 해야 할 것만 (전체 채널이면 채널마다)
  function todosOf(key) {
    var out = [], rl = RULES[key] || {}, nm = chInfo(key).name;
    var mine = EPS.filter(function (e) { return e.channel === key; });
    var go = function (page, epId) { return function () { if (epId) view.makeEp = epId; view.ch = key; saveView(); setPage(page); drawAll(); }; };
    var rv = mine.filter(function (e) { return e.review === "검토대기"; });
    if (rv.length) out.push({ ic: "🕵", t: rv.map(function (e) { return e.ep + "편"; }).join(", ") + " 검토하고 승인하기", sub: "아래 「검토할 영상」에서 보고 승인하면 공개 날짜에 예약돼요", btn: "검토하기", fn: function () { $("reviewBox").scrollIntoView({ behavior: "smooth" }); } });
    var stuck = QUEUE.filter(function (q) { return q.state === "막힘" && mine.some(function (e) { return e.id === q.episode_id; }); });
    if (stuck.length) out.push({ ic: "⚠", t: "막힌 일 " + stuck.length + "건 확인하기", sub: stuck[0].note || stuck[0].label, btn: "보기", fn: function () { $("queue").scrollIntoView({ behavior: "smooth" }); } });
    if (!rl.ref_id && !rl.ref_note) out.push({ ic: "📚", t: "레퍼런스 채널 정하기", sub: "정해 두면 제목·썸네일·가사가 그 채널 스타일로 나와요", btn: "채널 설정", fn: go("chset") });
    var making = mine.filter(function (e) { return !e.video_id; }).sort(function (a, b) { return String(a.date).localeCompare(String(b.date)); });
    making.forEach(function (e) {
      var mk = e.make || {}, jobs = mk.jobs || {}, all = jobs.all || {}, done = mk.done || {}, songs = mk.songs || [];
      var tag = e.ep + "편 (" + dotDate(e.date) + ")";
      if (all.state === "요청" || all.state === "만드는중") { out.push({ ic: "⏳", t: tag + " AI가 만드는 중이에요", sub: "기다리면 돼요 — 다 되면 여기에 다음 할 일이 떠요", info: true }); return; }
      if (!e.title && !songs.length) { out.push({ ic: "✨", t: tag + " 「한 번에 다 만들기」 누르기", sub: "주제부터 가사까지 AI가 만들어요", btn: "만들러 가기", fn: go("make", e.id) }); return; }
      if (mk.thumb_prompt && !thumbSrc(e)) out.push({ ic: "🖼", t: tag + " 썸네일 그림 뽑아서 넣기", sub: "프롬프트 복사 → ChatGPT에 붙여 넣기 → 나온 그림 넣기", btn: "하러 가기", fn: go("make", e.id) });
      if (songs.length && !done.songs) {
        var sd = mk.song_done || {}, n = songs.filter(function (x, i) { return sd[i]; }).length;
        out.push({ ic: "🎵", t: tag + " 수노로 노래 만들기 (" + n + "/" + songs.length + "곡)", sub: "곡마다 가사 복사 → 수노에 붙여 넣기 → mp3 받기", btn: "하러 가기", fn: go("make", e.id) });
      } else if (done.songs && !done.video) out.push({ ic: "💬", t: tag + " 영상 만들어 달라고 Claude에게 말하기", sub: "채팅에 「" + nm + " " + e.ep + "편 영상 만들어 줘」 + mp3 폴더", btn: "자세히", fn: go("make", e.id) });
    });
    if (!making.length) {
      var last = mine.map(function (e) { return e.date; }).filter(Boolean).sort().pop();
      out.push({ ic: "＋", t: "다음 편 시작하기" + (last ? " (마지막 편 " + dotDate(last) + ")" : ""), sub: "「＋ 새 편 시작」을 누르면 AI가 한 번에 다 만들어요", btn: "만들러 가기", fn: go("make") });
    }
    return out;
  }
  function drawTodo() {
    var box = $("todoBox"); box.innerHTML = "";
    var keys = view.ch === "all" ? META.channels.map(function (c) { return c.key; }) : [view.ch];
    var rows = [];
    keys.forEach(function (k) { todosOf(k).forEach(function (t) { t.key = k; rows.push(t); }); });
    var real = rows.filter(function (t) { return !t.info; }).length;
    box.appendChild(h("div", { class: "row gap" }, [h("b", { class: "todo-h", text: "📌 내가 할 일" }), h("span", { class: "muted small", text: real ? real + "개" : "지금은 없어요 ✅" })]));
    rows.forEach(function (t) {
      box.appendChild(h("div", { class: "todo-row" + (t.info ? " info" : "") }, [
        h("span", { class: "todo-ic", text: t.ic }),
        h("div", { class: "ti-main" }, [h("div", {}, [view.ch === "all" ? chTag2(t.key) : null, view.ch === "all" ? " " : null, h("b", { text: t.t })]), t.sub ? h("span", { class: "muted small", text: t.sub }) : null]),
        t.btn ? h("button", { type: "button", class: "btn small", onclick: t.fn }, [t.btn]) : null
      ]));
    });
  }

  function drawQueue() {
    var box = $("queue"); box.textContent = "";
    var epCh = {}; EPS.forEach(function (e) { epCh[e.id] = e.channel; });
    var items = QUEUE.filter(function (q) { return (q.state !== "완료" || Date.now() - new Date(q.updated_at) < 864e5) && (view.ch === "all" || epCh[q.episode_id] === view.ch); });
    if (!items.length) { box.hidden = true; return; }
    box.hidden = false;
    var left = items.filter(function (q) { return q.state !== "완료"; }).length;
    box.appendChild(h("b", { text: left ? "시켜 두신 일 " + left + "건 — 차례로 해요" : "시켜 두신 일 — 다 했어요" }));
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
    $("logCount").textContent = items.length ? "최근 " + items.length + "개 · 눌러서 열기" : "";
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
    // 황금주파수는 웨일의 두 번째 구글 계정(authuser=1) — 안 붙이면 ‘권한이 없습니다’가 뜸
    var studio = e.video_id ? "https://studio.youtube.com/video/" + e.video_id + "/edit" + (e.channel === "A" ? "?authuser=1" : "") : null;
    var player = e.video_id && (e.privacy === "public" || e.privacy === "unlisted")
      ? h("iframe", { class: "st-player", src: "https://www.youtube.com/embed/" + e.video_id, title: "동영상 미리보기", referrerpolicy: "strict-origin-when-cross-origin", allow: "encrypted-media; picture-in-picture", allowfullscreen: true })
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
      review = h("div", { class: "st-review ok" }, [h("b", { text: "✅ 승인함" }), h("p", { class: "small", text: "서버가 1분 안에 공개 날짜로 예약해요." })]);
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
    drawTabs(); drawSummary(); drawStatus(); drawTodo(); drawQueue(); drawReview();
    $("list").hidden = view.mode !== "list"; $("cards").hidden = view.mode !== "cards"; $("cal").hidden = view.mode !== "cal";
    if (view.mode === "list") drawList(); else if (view.mode === "cards") drawCards(); else drawCal();
    if (view.open && $("detail").open) {
      if (!view.dirty) drawDetail();
    }
    drawPage();
  }

  // ------------------------------------------------------------ 영상 올리기 (사이트에서 직접)
  // 영상 파일은 8MB 조각으로 서버에 받아 두고(끊기면 이어서), 「유튜브로 올리기」를 누르면
  // 라이브 관리자 서버의 일꾼이 1분 안에 일부 공개로 올리고 그 편을 검토대기로 만듭니다.
  var UPS = [];
  var UP_CHUNK = 8 * 1024 * 1024;
  var upFiles = {};      // 올리기 번호 → 고른 영상 파일 (이어 올리기용)
  var upSending = {};    // 올리기 번호 → 지금 조각 보내는 중
  var UP_STATE = { "받는중": "서버로 받는 중", "준비": "올릴 준비 됨", "대기": "유튜브 차례 기다림", "올리는중": "유튜브로 올리는 중", "올림": "올림 · 검토대기", "실패": "실패" };

  function gb(n) { return (n / 1073741824).toFixed(2) + "GB"; }

  function sendVideo(u, file) {
    if (upSending[u.id]) return;
    upSending[u.id] = true;
    upFiles[u.id] = file;
    var pos = u.received || 0;
    function step() {
      if (pos >= file.size) { upSending[u.id] = false; refreshUploads(); return; }
      var end = Math.min(pos + UP_CHUNK, file.size);
      fetch("/api/uploads/" + u.id + "/video?offset=" + pos, { method: "PUT", body: file.slice(pos, end) })
        .then(function (r) {
          if (r.status === 409) return r.json().then(function (d) { var x = {}; try { x = JSON.parse(d.detail); } catch (e) { /* 다른 오류 */ } if (x.received == null) throw new Error(d.detail); pos = x.received; });
          if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || "받기 실패"); });
          return r.json().then(function (nu) { pos = nu.received; u.received = nu.received; upProgress(u.id, nu.received / nu.size); });
        })
        .then(step)
        .catch(function (err) {
          upSending[u.id] = false;
          toast("영상 받기가 끊겼어요: " + err.message + " — 「이어 올리기」를 눌러 주세요");
          refreshUploads();
        });
    }
    step();
  }
  function upProgress(id, frac) {
    document.querySelectorAll('[data-upbar="' + id + '"]').forEach(function (b) { b.style.width = Math.round(frac * 100) + "%"; });
    document.querySelectorAll('[data-uptxt="' + id + '"]').forEach(function (t) { t.textContent = Math.round(frac * 100) + "%"; });
  }

  function refreshUploads() {
    return api("GET", "/api/uploads").then(function (list) {
      UPS = list;
      drawUploads();
      if (view.page === "upload") drawPage();
      // 일꾼을 기다리는 게 있으면 5초마다 다시 봄
      clearTimeout(refreshUploads.t);
      if (UPS.some(function (u) { return u.state === "대기" || u.state === "올리는중" || u.draft === "요청"; })) refreshUploads.t = setTimeout(refreshUploads, 5000);
      if (upOpen && $("upDlg").open) drawUpDialog();
    }).catch(function () { /* 다음에 */ });
  }

  function drawUploads() {
    var box = $("upBox");
    var recent = UPS.filter(function (u) { return u.state !== "올림" || Date.now() - new Date(u.updated_at).getTime() < 864e5; });
    box.hidden = !recent.length;
    box.innerHTML = "";
    if (!recent.length) return;
    box.appendChild(h("div", { class: "rvq-head" }, [h("b", { text: "⬆ 올리는 영상 " + recent.length + "개" }), h("span", { class: "muted small", text: "다 올라가면 그 편이 🕵 검토할 영상에 떠요" })]));
    recent.forEach(function (u) {
      var frac = u.state === "올리는중" || u.state === "올림" ? (u.progress || 0) / 100 : (u.size ? u.received / u.size : 0);
      var stuck = u.state === "받는중" && !upSending[u.id];
      box.appendChild(h("div", { class: "up-row" + (u.state === "실패" ? " bad" : "") }, [
        h("span", { class: "ch", style: "background:" + chInfo(u.channel).color, text: chInfo(u.channel).name }),
        h("div", { class: "up-main" }, [
          h("b", { text: u.title || u.filename || "제목 없음" }),
          h("div", { class: "muted small", text: (UP_STATE[u.state] || u.state) + " · " + dotDate(u.date) + (u.error ? " · " + u.error : "") + (u.youtube_id ? " · youtu.be/" + u.youtube_id : "") }),
          h("div", { class: "bar up-bar" }, [h("i", { "data-upbar": u.id, style: "width:" + Math.round(frac * 100) + "%" })])
        ]),
        h("span", { class: "small", "data-uptxt": u.id, text: Math.round(frac * 100) + "%" }),
        h("button", { type: "button", class: "btn small", onclick: function () { openUpload(u.id); } }, [stuck ? "이어 올리기" : u.state === "실패" ? "다시 보기" : "열기"])
      ]));
    });
  }

  var upOpen = null; // 열어 둔 올리기 번호 (새로 만들 때는 "new")
  function openUpload(id) { upOpen = id || "new"; drawUpDialog(); if (!$("upDlg").open) $("upDlg").showModal(); }

  function drawUpDialog() {
    var body = $("upBody");
    var u = upOpen === "new" ? null : UPS.filter(function (x) { return x.id === upOpen; })[0];
    if (body.contains(document.activeElement) && document.activeElement.tagName !== "BUTTON") return; // 쓰는 중에는 다시 그리지 않음
    body.innerHTML = "";
    var close = function () { $("upDlg").close(); upOpen = null; };
    var head = h("div", { class: "up-head" }, [h("h3", { text: u ? "영상 올리기 · " + chInfo(u.channel).name : "⬆ 영상 올리기" }), h("button", { type: "button", class: "yt-ic", onclick: close }, ["✕"])]);
    body.appendChild(head);

    // 1) 채널 · 날짜 · 영상 파일
    var chSel = h("select", {}, META.channels.map(function (c) { return h("option", { value: c.key, text: c.name }); }));
    var dateIn = h("input", { type: "date", value: (u && u.date) || "" });
    if (u) { chSel.value = u.channel; chSel.disabled = true; }
    else if (UP_PRESET) { chSel.value = UP_PRESET.channel; dateIn.value = UP_PRESET.date || ""; }
    var fileIn = h("input", { type: "file", accept: "video/mp4,video/*" });
    var drop = h("label", { class: "up-drop" }, [fileIn, h("b", { text: u ? (u.received >= u.size ? "✅ " + u.filename + " (" + gb(u.size) + ") 서버에 다 받음" : "🎬 " + u.filename + " — 같은 파일을 다시 골라 이어 올리기") : "🎬 영상 파일을 끌어다 놓거나 눌러서 고르기" }),
      h("span", { class: "muted small", text: "mp4 · 8GB까지 · 올리는 동안 이 창은 닫아도 되지만 사이트 탭은 열어 두세요" })]);
    var bar = u ? h("div", { class: "bar up-bar" }, [h("i", { "data-upbar": u.id, style: "width:" + Math.round((u.size ? u.received / u.size : 0) * 100) + "%" })]) : null;
    fileIn.addEventListener("change", function () {
      var f = fileIn.files[0];
      if (!f) return;
      if (u) {
        if (f.size !== u.size) return toast("처음 고른 파일과 크기가 달라요. 같은 파일을 골라 주세요");
        sendVideo(u, f); return;
      }
      if (!dateIn.value) { fileIn.value = ""; return toast("먼저 공개 날짜를 골라 주세요"); }
      api("POST", "/api/uploads", { channel: chSel.value, date: dateIn.value, filename: f.name, size: f.size }).then(function (nu) {
        UPS.unshift(nu); upOpen = nu.id; sendVideo(nu, f); drawUpDialog(); drawUploads();
      }).catch(function (err) { toast(err.message); });
    });
    body.appendChild(h("div", { class: "up-sec" }, [
      h("div", { class: "row gap" }, [h("label", { class: "inline" }, ["채널 ", chSel]), h("label", { class: "inline" }, ["공개 날짜 ", dateIn])]),
      drop, bar
    ]));
    if (!u) { body.appendChild(h("p", { class: "muted small", text: "채널과 공개 날짜를 고르고 영상 파일을 넣으면 서버로 받기 시작해요. 그다음 썸네일·제목을 넣어요." })); return; }

    dateIn.addEventListener("change", function () { api("PATCH", "/api/uploads/" + u.id, { date: dateIn.value }).then(function (x) { u.date = x.date; }); });

    // 2) 썸네일 · 수록곡.json
    var thIn = h("input", { type: "file", accept: "image/jpeg,image/png" });
    var chIn = h("input", { type: "file", accept: ".json,application/json" });
    thIn.addEventListener("change", function () {
      var fd = new FormData(); fd.append("file", thIn.files[0]);
      api("POST", "/api/uploads/" + u.id + "/thumb", fd).then(function () { toast("썸네일을 넣었어요"); refreshUploads(); }).catch(function (err) { toast(err.message); });
    });
    chIn.addEventListener("change", function () {
      var fd = new FormData(); fd.append("file", chIn.files[0]);
      api("POST", "/api/uploads/" + u.id + "/chapters", fd).then(function (x) { toast("수록곡 " + x.chapters.length + "줄을 넣었어요 — AI 초안을 누르면 설명에 챕터가 들어가요"); refreshUploads(); }).catch(function (err) { toast(err.message); });
    });
    body.appendChild(h("div", { class: "up-sec up-two" }, [
      h("label", { class: "up-drop small" }, [thIn, u.thumb ? h("img", { class: "up-thumb", src: "/api/uploads/" + u.id + "/thumb?v=" + encodeURIComponent(u.updated_at) }) : null, h("b", { text: u.thumb ? "🖼 썸네일 바꾸기" : "🖼 썸네일 넣기 (jpg·png)" })]),
      h("label", { class: "up-drop small" }, [chIn, h("b", { text: u.chapters && u.chapters.length ? "🕐 수록곡 " + u.chapters.length + "줄 들어감" : "🕐 수록곡.json 넣기 (챕터)" }), h("span", { class: "muted small", text: "두번붙이기.py 가 남긴 파일" })])
    ]));

    // 3) 제목 · 설명 · 태그 (AI 초안)
    var tIn = h("input", { type: "text", maxlength: "100", value: u.title || "", placeholder: "제목 (100자까지)" });
    var dIn = h("textarea", { rows: "10", placeholder: "설명" }); dIn.value = u.description || "";
    var gIn = h("input", { type: "text", value: (u.tags || []).join(", "), placeholder: "태그 (쉼표로 나눔)" });
    var save = function () { return api("PATCH", "/api/uploads/" + u.id, { title: tIn.value.trim(), description: dIn.value, tags: gIn.value.split(",").map(function (x) { return x.trim(); }).filter(Boolean) }); };
    [tIn, dIn, gIn].forEach(function (x) { x.addEventListener("change", function () { save().catch(function (err) { toast(err.message); }); }); });
    var drafting = u.draft === "요청";
    var aiBtn = h("button", { type: "button", class: "btn", disabled: drafting, onclick: function () {
      save().then(function () { return api("POST", "/api/uploads/" + u.id + "/draft"); }).then(function () { toast("AI가 초안을 쓰는 중이에요 (1분쯤)"); refreshUploads(); }).catch(function (err) { toast(err.message); });
    } }, [drafting ? "✨ AI가 쓰는 중…" : "✨ AI 초안"]);
    var alts = String(u.draft_note || "").split("\n").filter(Boolean);
    body.appendChild(h("div", { class: "up-sec stack" }, [
      h("div", { class: "row gap" }, [h("b", { text: "제목 · 설명 · 태그" }), aiBtn, u.draft === "실패" ? h("span", { class: "small bad", text: "AI 초안 실패: " + u.draft_note }) : null]),
      tIn,
      u.draft === "완료" && alts.length ? h("div", { class: "up-alts" }, [h("span", { class: "muted small", text: "다른 제목 후보 (누르면 바뀜)" })].concat(alts.map(function (t) {
        return h("button", { type: "button", class: "chip", onclick: function () { tIn.value = t; save(); } }, [t]);
      }))) : null,
      dIn, gIn,
      h("p", { class: "muted small", text: "올릴 때 함께 넣는 것: 카테고리 음악 · 아동용 아님 · AI 변경 콘텐츠 「예」 · 일부 공개. 제품 태그·수익 창출은 올린 뒤 PC 웨일이 붙여요." })
    ]));

    // 4) 유튜브로 올리기
    var ready = u.received >= u.size;
    var canGo = ready && (u.state === "준비" || u.state === "실패");
    var foot = h("div", { class: "row gap up-foot" }, [
      h("button", { type: "button", class: "btn primary", disabled: !canGo, onclick: function () {
        if (!tIn.value.trim()) return toast("제목을 써 주세요");
        if (!confirm(chInfo(u.channel).name + " 채널에 일부 공개로 올릴까요?\n(링크를 아는 사람만 볼 수 있고, 사이트에서 승인해야 " + dotDate(u.date) + " 21:00 예약 공개로 바뀌어요)")) return;
        save().then(function () { return api("POST", "/api/uploads/" + u.id + "/go"); }).then(function () { toast("유튜브로 보내요 — 1분 안에 시작해요"); close(); refreshUploads(); refresh(); }).catch(function (err) { toast(err.message); });
      } }, [u.state === "대기" || u.state === "올리는중" ? "유튜브로 보내는 중…" : u.state === "올림" ? "✅ 올림" : u.state === "실패" ? "다시 올리기" : "⬆ 유튜브로 올리기 (일부 공개)"]),
      !ready ? h("span", { class: "muted small", text: "영상 파일을 서버로 받는 중이에요 — 다 받으면 누를 수 있어요" }) : null,
      h("span", { class: "spacer" }),
      u.state !== "올리는중" ? h("button", { type: "button", class: "btn small", onclick: function () {
        if (!confirm("이 올리기를 지울까요? (서버에 받아 둔 파일도 지워요 · 이미 유튜브에 올라간 영상은 그대로)")) return;
        api("DELETE", "/api/uploads/" + u.id).then(function () { close(); refreshUploads(); });
      } }, ["지우기"]) : null
    ]);
    body.appendChild(foot);
  }

  $("btnUp").addEventListener("click", function () { openUpload(null); });

  // ------------------------------------------------------------ 채널 넣기 · 고치기
  var chEditing = null;
  function openChannelDialog(c) {
    chEditing = c || null;
    var f = $("chForm");
    $("chDlgTitle").textContent = c ? "채널 고치기 · " + c.name : "채널 넣기";
    f.name.value = c ? c.name : ""; f.display.value = c ? (c.display || "") : ""; f.color.value = c ? c.color : "#7c5cff";
    $("chDlg").showModal();
  }
  $("addChannel").addEventListener("click", function () { openChannelDialog(null); });
  $("chCancel").addEventListener("click", function () { $("chDlg").close(); });
  $("chForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var f = ev.target, body = { name: f.name.value.trim(), display: f.display.value.trim(), color: f.color.value };
    (chEditing ? api("PATCH", "/api/channels/" + chEditing.key, body) : api("POST", "/api/channels", body)).then(function () {
      $("chDlg").close(); toast(chEditing ? "채널을 고쳤어요" : "채널 ‘" + body.name + "’을 넣었어요");
      return api("GET", "/api/meta").then(function (m) { META = m; refresh(); });
    }).catch(function (err) { toast(err.message); });
  });
  $("menuToggle").addEventListener("click", function () { $("sidebar").classList.toggle("open"); });
  $("btnStats").addEventListener("click", function (ev) { ev.preventDefault(); });
  $("upDlg").addEventListener("close", function () { upOpen = null; UP_PRESET = null; });
  $("shopWrap").addEventListener("toggle", function () { if ($("shopWrap").open) drawShopPage($("shopBox")); });
  // 창 전체 어디에 끌어다 놓아도 브라우저가 파일을 열지 않게
  ["dragover", "drop"].forEach(function (ev) { $("upDlg").addEventListener(ev, function (e) { if (e.target.type !== "file") e.preventDefault(); }); });

  // ------------------------------------------------------------ 왼쪽 메뉴 화면들 (라이브 관리자처럼)
  var RULES = {}, SYS = {}, LOGS = [];
  var PAGE_NAME = { list: "영상 목록", upload: "영상 올리기", rules: "만들기 규칙", titles: "제목·설명", prompts: "프롬프트", refs: "채널 분석", lyrics: "수노 가사", make: "새 영상 만들기", chset: "채널 설정", saved: "레퍼런스 채널", thumbs: "썸네일", shop: "쇼핑 태그", log: "실행 기록", settings: "설정·상태" };
  view.page = view.page || "list";
  function setPage(p) {
    view.page = p; saveView();
    Array.prototype.forEach.call(SIDE_NAV.querySelectorAll(".nav-item"), function (b) { b.classList.toggle("active", b.dataset.page === p); });
    Array.prototype.forEach.call(document.querySelectorAll("#toolNav .nav-item, #bottomNav .nav-item"), function (b) { b.classList.toggle("active", b.dataset.page === p); });
    if (META) drawTabs();
    Array.prototype.forEach.call(document.querySelectorAll(".page"), function (el) { el.hidden = el.id !== "page-" + p; });
    $("sidebar").classList.remove("open");
    drawPage();
    window.scrollTo(0, 0);
  }
  SIDE_NAV.addEventListener("click", function (ev) { var b = ev.target.closest(".nav-item"); if (b) setPage(b.dataset.page); });
  ["toolNav", "bottomNav"].forEach(function (id) { $(id).addEventListener("click", function (ev) { var b = ev.target.closest(".nav-item"); if (b) setPage(b.dataset.page); }); });
  function chList() { return META.channels.filter(function (c) { return view.ch === "all" || c.key === view.ch; }); }
  function chEps() { return EPS.filter(function (e) { return view.ch === "all" || e.channel === view.ch; }); }
  function head(title, sub, right) {
    return h("div", { class: "page-head" }, [h("div", {}, [view.page === "titles" && title !== "제목·설명" ? h("h2", { text: title }) : null, sub ? h("p", { class: "muted small", text: sub }) : null]), right || null]);
  }
  function chTag2(key) { var c = chInfo(key); return h("span", { class: "ch", style: "background:" + c.color, text: c.display || c.name }); }

  function drawPage() {
    if (!META) return;
    var cur = META.channels.filter(function (c) { return c.key === view.ch; })[0];
    var chName = cur ? (cur.display || cur.name) : "전체 채널";
    $("pageTitle").textContent = view.page === "list" ? chName : PAGE_NAME[view.page];
    if (view.page !== "list") $("pageSub").textContent = TOOL_PAGES[view.page] ? TOOL_SUB[view.page] : chName + (view.ch === "all" ? "" : " 채널");
    var pbox = $("page-" + view.page), opened = {};
    var dkey = function (dt) { if (dt.dataset.k) return dt.dataset.k; var c = dt.closest("[data-k]"); var s = dt.querySelector("summary"); return (c ? c.dataset.k : "") + "|" + (s ? s.textContent : ""); };
    if (pbox) Array.prototype.forEach.call(pbox.querySelectorAll("details"), function (dt) { opened[dkey(dt)] = dt.open; });
    var fn = { upload: drawUploadPage, rules: drawRulesPage, titles: drawTitlesPage, prompts: drawPromptsPage, refs: drawRefsPage, lyrics: drawLyricsPage, make: drawMakePage, chset: drawChsetPage, saved: drawSavedPage, thumbs: drawThumbsPage, shop: drawShopPage, log: drawLogPage, settings: drawSettingsPage }[view.page];
    if (fn) fn(pbox);
    if (view.page === "list") { // 목록 화면 아래 🛍 쇼핑 태그 확인
      var vods = chEps().filter(function (x) { return x.video_id; });
      $("shopCount").textContent = vods.filter(function (x) { return (x.shop_tags || 0) >= 4; }).length + " / " + vods.length + "편 확인됨";
      if ($("shopWrap").open) drawShopPage($("shopBox"));
    }
    if (pbox) Array.prototype.forEach.call(pbox.querySelectorAll("details"), function (dt) { var k = dkey(dt); if (k in opened) dt.open = opened[k]; });
  }

  // ⬆ 영상 올리기 — 올린 것 · 올리는 중인 것 전부
  function drawUploadPage(box) {
    box.innerHTML = "";
    box.appendChild(head("영상 올리기", "영상 파일을 넣으면 서버가 유튜브에 일부 공개로 올리고, 그 편이 🕵 검토할 영상에 떠요. 승인하면 공개 날짜에 예약돼요.",
      h("button", { type: "button", class: "btn primary", onclick: function () { openUpload(null); } }, ["⬆ 새 영상 올리기"])));
    var list = UPS.filter(function (u) { return view.ch === "all" || u.channel === view.ch; });
    if (!list.length) { box.appendChild(h("div", { class: "card-box empty", text: "아직 올린 영상이 없어요" })); return; }
    var wrapBox = h("div", { class: "card-box" });
    list.forEach(function (u) {
      var frac = u.state === "올리는중" || u.state === "올림" ? (u.progress || 0) / 100 : (u.size ? u.received / u.size : 0);
      wrapBox.appendChild(h("div", { class: "up-row" + (u.state === "실패" ? " bad" : "") }, [
        chTag2(u.channel),
        h("div", { class: "up-main" }, [
          h("b", { text: u.title || u.filename || "제목 없음" }),
          h("div", { class: "muted small", text: (UP_STATE[u.state] || u.state) + " · " + dotDate(u.date) + " · " + gb(u.size) + (u.error ? " · " + u.error : "") }),
          h("div", { class: "bar up-bar" }, [h("i", { "data-upbar": u.id, style: "width:" + Math.round(frac * 100) + "%" })])
        ]),
        u.youtube_id ? h("a", { class: "small", href: "https://youtu.be/" + u.youtube_id, target: "_blank", rel: "noopener", text: "유튜브" }) : h("span", { class: "small", "data-uptxt": u.id, text: Math.round(frac * 100) + "%" }),
        h("button", { type: "button", class: "btn small", onclick: function () { openUpload(u.id); } }, ["열기"])
      ]));
    });
    box.appendChild(wrapBox);
  }

  // ⚙ 만들기 규칙 — 곡 개수 · 반복 · 길이 · 공개 시각
  function drawRulesPage(box) {
    box.innerHTML = "";
    box.appendChild(head("만들기 규칙", "채널마다 영상을 어떻게 만들지 정해요. 영상을 만들 때 이 값대로 만들어요 (바꾸면 다음 편부터)."));
    chList().forEach(function (c) {
      var r = RULES[c.key] || {};
      var f = {};
      var num = function (k, label, unit, min, max) {
        f[k] = h("input", { type: "number", min: String(min), max: String(max), value: r[k] != null ? r[k] : "" });
        return h("label", { class: "rule" }, [h("span", { text: label }), h("div", { class: "rule-in" }, [f[k], h("em", { text: unit })])]);
      };
      var est = h("div", { class: "rule-est" });
      var sel = function (opts, v) { var el = h("select", { class: "ref-url" }, opts.map(function (o) { return h("option", { value: o[0], text: o[1] }); })); el.value = v; return el; };
      var calc = function () {
        var mins = Math.round((+f.songs.value || 0) * (+f.song_seconds.value || 0) * (+f.loops.value || 0) / 60);
        var lo = +f.min_minutes.value || 0, hi = +f.max_minutes.value || 0;
        var ok = mins >= lo && (!hi || mins <= hi);
        est.className = "rule-est " + (ok ? "ok" : "warn");
        est.textContent = "예상 길이 약 " + Math.floor(mins / 60) + "시간 " + (mins % 60) + "분 (" + mins + "분) — " + (ok ? "목표 안에 들어가요" : "목표(" + lo + "~" + hi + "분)를 벗어나요");
      };
      f.publish_time = h("input", { type: "time", value: r.publish_time || "21:00" });
      var card = h("div", { class: "card-box rules-card" }, [
        h("div", { class: "row gap" }, [chTag2(c.key), h("b", { text: (c.display || c.name) + " 만들기 규칙" })]),
        h("div", { class: "rules-grid" }, [
          num("songs", "서로 다른 곡 개수", "곡", 1, 60),
          num("loops", "반복 횟수 (바퀴)", "바퀴", 1, 10),
          num("song_seconds", "곡 하나 평균 길이", "초", 60, 900),
          num("min_minutes", "목표 길이 최소", "분", 1, 600),
          num("max_minutes", "목표 길이 최대", "분", 1, 600),
          num("every_days", "며칠마다 한 편", "일", 1, 30),
          h("label", { class: "rule" }, [h("span", { text: "공개 시각 (한국)" }), h("div", { class: "rule-in" }, [f.publish_time])]),
          h("label", { class: "rule" }, [h("span", { text: "처음 올릴 때" }), h("div", { class: "rule-in" }, [h("b", { text: "일부 공개 → 검토 → 승인하면 예약" })])])
        ]),
        h("b", { class: "auto-h", text: "🤖 자동화" }),
        h("div", { class: "rules-grid" }, [
          h("label", { class: "rule" }, [h("span", { text: "다음 편 알아서 시작" }), h("div", { class: "rule-in" }, [f.auto_make = sel([["1", "켜기 — 서버가 알아서 시작"], ["0", "끄기 — 내가 눌러서 시작"]], String(r.auto_make != null ? r.auto_make : 1))])]),
          num("lead_days", "공개 며칠 전에 시작", "일 전", 1, 30),
          h("label", { class: "rule" }, [h("span", { text: "썸네일 그림 AI (유료)" }), h("div", { class: "rule-in" }, [f.thumb_ai = sel([["", "끄기 — 프롬프트만 (무료)"], ["gpt-image-1-mini", "가장 저렴 (mini) · 한 장 약 20원"], ["gpt-image-1", "좋은 것 · 한 장 약 90원"]], r.thumb_ai || "")])]),
          h("label", { class: "rule" }, [h("span", { text: "그림 품질" }), h("div", { class: "rule-in" }, [f.thumb_quality = sel([["low", "낮음 (가장 쌈)"], ["medium", "보통"], ["high", "높음 (비쌈)"]], r.thumb_quality || "medium")])])
        ]),
        est,
        h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", onclick: function () {
          var body = {}; Object.keys(f).forEach(function (k) { body[k] = f[k].value; });
          api("PUT", "/api/rules/" + c.key, body).then(function (nr) { RULES[c.key] = nr; toast((c.display || c.name) + " 규칙을 저장했어요"); calc(); }).catch(function (err) { toast(err.message); });
        } }, ["저장"])])
      ]);
      Object.keys(f).forEach(function (k) { f[k].addEventListener("input", calc); });
      box.appendChild(card);
      calc();
    });
  }

  // ✍ 제목·설명 — 채널 규칙 + 편마다 AI로 만들기
  function drawTitlesPage(box) {
    if (box.contains(document.activeElement) && /TEXTAREA|INPUT/.test(document.activeElement.tagName)) return; // 쓰는 중에는 다시 그리지 않음
    box.innerHTML = "";
    box.appendChild(head("제목·설명", "채널마다 제목 규칙과 예시를 적어 두면, AI가 그 규칙대로 제목 후보 3개와 설명 첫머리를 만들어요. 고르면 유튜브에도 바로 반영돼요."));
    box.appendChild(h("div", { class: "card-box" }, [h("span", { class: "small", text: "제목·설명 규칙과 예시는 🧠 프롬프트 메뉴에서 정해요." }),
      h("button", { type: "button", class: "btn small", onclick: function () { setPage("prompts"); } }, ["🧠 프롬프트 열기"])]));
    var list = chEps().slice().sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });
    var tbl = h("div", { class: "card-box" });
    list.forEach(function (e) {
      var src = thumbSrc(e);
      var cands = (e.ai_titles || []).map(function (t) {
        return h("button", { type: "button", class: "chip", title: "이 제목으로 바꾸기", onclick: function () {
          if (!confirm("제목을 이걸로 바꿀까요?" + (e.video_id ? "\n(유튜브에도 1분 안에 반영돼요)" : "") + "\n\n" + t)) return;
          api("POST", "/api/episodes/" + e.id + "/edit", { title: t }).then(function () { toast("제목을 바꿨어요"); refresh(); }).catch(function (err) { toast(err.message); });
        } }, [t]);
      });
      tbl.appendChild(h("div", { class: "ti-row" }, [
        h("div", { class: "yt-thumb" }, [src ? h("img", { src: src, alt: "" }) : null]),
        h("div", { class: "ti-main" }, [
          h("div", {}, [chTag2(e.channel), " ", h("b", { text: e.ep + "편 · " + dotDate(e.date) })]),
          h("div", { class: "ti-title", text: e.title || "제목 없음" }),
          cands.length ? h("div", { class: "up-alts" }, [h("span", { class: "muted small", text: "AI 제목 후보 (누르면 바뀜)" })].concat(cands)) : null,
          e.ai_desc ? h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "AI 설명 첫머리 보기" }), h("pre", { text: String(e.ai_desc).split("━")[0].trim() }),
            h("button", { type: "button", class: "btn small", onclick: function () {
              if (!confirm("설명을 AI 것으로 바꿀까요? (수록곡·끝맺음은 그대로)")) return;
              api("POST", "/api/episodes/" + e.id + "/edit", { description: e.ai_desc }).then(function () { toast("설명을 바꿨어요"); refresh(); }).catch(function (err) { toast(err.message); });
            } }, ["이 설명으로 바꾸기"])]) : null,
          e.ai_state === "실패" ? h("span", { class: "small bad", text: "AI 실패: " + e.ai_note }) : null
        ]),
        h("button", { type: "button", class: "btn small", disabled: e.ai_state === "요청", onclick: function () {
          api("POST", "/api/episodes/" + e.id + "/ai").then(function () { toast("AI가 쓰는 중이에요 (1분쯤)"); refresh(); }).catch(function (err) { toast(err.message); });
        } }, [e.ai_state === "요청" ? "✨ 쓰는 중…" : "✨ AI로 만들기"])
      ]));
    });
    box.appendChild(head("편마다 제목", list.length + "편"));
    box.appendChild(tbl);
  }

  // 🧠 프롬프트 — 채널마다 제목·설명·썸네일·영상 그림·가사 프롬프트
  var PROMPT_FIELDS = [
    ["title_rules", "제목 프롬프트", 5, "예) 이모지로 시작 · 후킹 문구 + 약속 · 끝은 “| 부처님 노래 | 키워드·키워드” 꼴"],
    ["desc_rules", "설명 프롬프트", 5, "예) 첫 두 줄은 위로하는 말 · 수록곡 타임라인 · 해시태그 3개"],
    ["examples", "잘된 제목 예시 (한 줄에 하나)", 4, ""],
    ["thumb_prompt", "썸네일 그림 프롬프트", 5, "그림 AI에 넣을 프롬프트 + 썸네일 글자 넣는 법"],
    ["image_prompt", "영상 배경 그림 프롬프트", 4, "긴 노래 영상 화면에 깔 그림 (16:9)"],
    ["lyrics_prompt", "노래 가사 프롬프트", 7, "주제 · 말투 · 절/후렴 구조 · 줄 수 · 피할 표현 · 수노 스타일 태그"]
  ];
  function drawPromptsPage(box) {
    if (box.contains(document.activeElement) && /TEXTAREA|INPUT/.test(document.activeElement.tagName)) return; // 쓰는 중에는 다시 그리지 않음
    box.innerHTML = "";
    box.appendChild(head("프롬프트", "채널마다 AI에게 줄 프롬프트예요. 영상을 만들 때(가사·썸네일·영상 그림·제목·설명) 이 내용을 그대로 따라요. 🔍 채널 분석에서 레퍼런스 채널 결과를 한 번에 넣을 수도 있어요. 가사 프롬프트는 맨 아래 「🎵 참고 가사로…」로도 만들 수 있어요."));
    chList().forEach(function (c) {
      var r = RULES[c.key] || {};
      var f = {};
      var kids = [h("summary", {}, [chTag2(c.key), h("b", { text: " 프롬프트" }), r.ref_note ? h("span", { class: "muted small", text: "  · " + r.ref_note }) : null])];
      PROMPT_FIELDS.forEach(function (p) {
        f[p[0]] = h("textarea", { rows: String(p[2]), placeholder: p[3] });
        f[p[0]].value = r[p[0]] || "";
        kids.push(h("label", { class: "stack" }, [h("span", { class: "small", text: p[1] }), f[p[0]]]));
      });
      kids.push(h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", onclick: function () {
        var body = {}; Object.keys(f).forEach(function (k) { body[k] = f[k].value; });
        api("PUT", "/api/rules/" + c.key, body).then(function (nr) { RULES[c.key] = nr; toast((c.display || c.name) + " 프롬프트를 저장했어요"); }).catch(function (err) { toast(err.message); });
      } }, ["저장"])]));
      box.appendChild(h("details", { class: "card-box rules-card", open: view.ch !== "all" || chList().length === 1 }, kids));
    });
  }

  // 🔍 채널 분석 — 레퍼런스 채널을 분석해서 프롬프트를 만들어 줌
  var REFS = [], REF_DRAFT = {};
  var REF_KEYS = [["summary", "이 채널이 잘 되는 이유"], ["songs_hint", "곡 수·길이"], ["title_rules", "제목 프롬프트"], ["desc_rules", "설명 프롬프트"], ["examples", "예시 제목"],
    ["thumb_prompt", "썸네일 그림 프롬프트"], ["image_prompt", "영상 배경 그림 프롬프트"], ["lyrics_prompt", "노래 가사 프롬프트"]];
  function drawRefsPage(box) {
    if (box.contains(document.activeElement) && /TEXTAREA|INPUT/.test(document.activeElement.tagName)) return;
    box.innerHTML = "";
    box.appendChild(head("채널 분석", "따라 하고 싶은 채널 주소를 넣으면, 서버가 그 채널 인기 영상의 제목·설명·태그·썸네일을 읽고 AI가 똑같은 공식으로 만들 수 있는 프롬프트(제목·설명·썸네일·영상 그림·가사)를 1~2분 안에 써 줘요. 문장을 베끼지 않고 공식만 가져와요."));
    var url = h("input", { type: "text", placeholder: "예) https://www.youtube.com/@채널이름  또는 그 채널 영상 주소", class: "ref-url", oninput: function () { REF_DRAFT.url = url.value; } });
    var note = h("input", { type: "text", placeholder: "메모 (선택) — 예) 썸네일 색감 위주로 봐 줘", class: "ref-url", oninput: function () { REF_DRAFT.note = note.value; } });
    url.value = REF_DRAFT.url || ""; note.value = REF_DRAFT.note || "";
    box.appendChild(h("div", { class: "card-box" }, [
      h("b", { text: "레퍼런스 채널 넣기" }), url, note,
      h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", onclick: function () {
        if (!url.value.trim()) { toast("채널 주소를 넣어 주세요"); return; }
        api("POST", "/api/refs", { url: url.value.trim(), note: note.value.trim() }).then(function () { REF_DRAFT = {}; toast("분석을 맡겼어요 (1~2분)"); refreshExtra(); }).catch(function (err) { toast(err.message); });
      } }, ["🔍 분석 맡기기"]), h("span", { class: "muted small", text: "유튜브 사용량은 한 번에 4 정도예요 (채널 이름만 넣으면 검색이라 100)" })])
    ]));
    if (!REFS.length) { box.appendChild(h("div", { class: "card-box empty", text: "아직 분석한 채널이 없어요" })); return; }
    var delRef = function (rf, ev) {
      ev.preventDefault(); ev.stopPropagation();
      if (confirm("‘" + ((rf.channel || {}).title || rf.url) + "’ 분석을 지울까요?\n(채널에 넣어 둔 프롬프트는 그대로 남아요)")) api("DELETE", "/api/refs/" + rf.id).then(function () { toast("지웠어요"); refreshExtra(); });
    };
    REFS.forEach(function (rf, i) {
      var ci = rf.channel || {}, res = rf.result || {};
      var st = { "요청": "⏳ 차례 기다림", "분석중": "🔍 분석 중…", "완료": "✅ 완료", "실패": "⚠ 실패" }[rf.state] || rf.state;
      var kids = [h("summary", { class: "row gap ref-sum" }, [
        ci.thumb ? h("img", { class: "ref-avatar", src: ci.thumb, alt: "" }) : null,
        h("div", { class: "ti-main" }, [h("b", { text: ci.title || rf.url }),
          h("span", { class: "muted small", text: (ci.handle ? ci.handle + " · " : "") + (ci.subs ? "구독자 " + ci.subs.toLocaleString() + " · " : "") + (ci.videos ? "영상 " + ci.videos + "개 · " : "") + String(rf.updated_at || "").slice(5, 16).replace("T", " ") })]),
        h("span", { class: "spacer" }),
        h("span", { class: "shop-st " + (rf.state === "완료" ? "ok" : "wait"), text: st }),
        h("button", { type: "button", class: "btn small ref-del", title: "이 분석 지우기", onclick: function (ev) { delRef(rf, ev); } }, ["🗑 삭제"])
      ])];
      if (rf.note) kids.push(h("span", { class: "muted small", text: "메모: " + rf.note }));
      if (rf.error) kids.push(h("span", { class: "small set-bad", text: rf.error }));
      var vidCard = function (v) {
        return h("a", { class: "ref-vid", href: "https://youtu.be/" + v.id, target: "_blank", rel: "noopener" }, [
          h("div", { class: "yt-thumb" }, [h("img", { src: "https://i.ytimg.com/vi/" + v.id + "/mqdefault.jpg", alt: "" })]),
          h("span", { class: "small", text: v.title }),
          h("span", { class: "muted small", text: "📅 " + dotDate(v.date) + " 올림 · 조회수 " + v.views.toLocaleString() + " · " + (v.live ? "라이브" : v.min + "분") })]);
      };
      if (ci.every || ci.last) kids.push(h("div", { class: "ref-cad" }, [
        ci.last ? h("span", { text: "마지막 업로드 " + dotDate(ci.last) }) : null,
        ci.every ? h("span", { text: "평균 " + ci.every + "일마다 올림" }) : null]));
      if (ci.top && ci.top.length) kids.push(h("details", { class: "ti-desc", open: true }, [h("summary", { class: "small", text: "인기 영상 (조회수 순)" }), h("div", { class: "ref-top" }, ci.top.map(vidCard))]));
      if (ci.recent && ci.recent.length) kids.push(h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "최근 올린 영상 (올린 날 순)" }), h("div", { class: "ref-top" }, ci.recent.map(vidCard))]));
      if (rf.state === "완료") {
        REF_KEYS.forEach(function (k) {
          if (!res[k[0]]) return;
          kids.push(h("details", { class: "ti-desc", open: k[0] === "summary" }, [h("summary", { class: "small", text: k[1] }), copyBtn(res[k[0]]), h("pre", { text: res[k[0]] })]));
        });
        kids.push(h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", onclick: function () {
          var nm = prompt("📚 레퍼런스 채널로 저장할 이름", ci.title || rf.url);
          if (nm == null) return;
          api("POST", "/api/refs/" + rf.id + "/save", { name: nm }).then(function () { toast("📚 레퍼런스 채널에 저장했어요"); refreshExtra(); }).catch(function (err) { toast(err.message); });
        } }, ["💾 레퍼런스로 저장"]), h("span", { class: "muted small", text: "저장하면 왼쪽 📚 레퍼런스 채널에서 다시 불러와 채널에 쓸 수 있어요" })]));
        kids.push(sampleBox(rf));
        kids.push(h("div", { class: "row gap" }, [h("span", { class: "small", text: "이 프롬프트를 채널에 넣기:" })].concat(META.channels.map(function (c) {
          return h("button", { type: "button", class: "btn small", onclick: function () {
            if (!confirm((c.display || c.name) + " 채널의 프롬프트(제목·설명·예시·썸네일·영상 그림·가사)를 이 분석 결과로 바꿀까요?\n(만들기 규칙의 곡 수·길이는 그대로예요)")) return;
            api("POST", "/api/refs/" + rf.id + "/apply/" + c.key).then(function (nr) { RULES[c.key] = nr; toast((c.display || c.name) + " 프롬프트에 넣었어요 — 🧠 프롬프트에서 고칠 수 있어요"); }).catch(function (err) { toast(err.message); });
          } }, ["→ " + (c.display || c.name)]);
        }))));
      }
      kids.push(h("div", { class: "row gap" }, [
        rf.state === "완료" || rf.state === "실패" ? h("button", { type: "button", class: "btn small", onclick: function () { api("POST", "/api/refs/" + rf.id + "/retry").then(refreshExtra); } }, ["다시 분석"]) : null,
        h("button", { type: "button", class: "btn small ghost", onclick: function (ev) { delRef(rf, ev); } }, ["🗑 삭제"])
      ]));
      // 채널마다 접기 · 처음엔 맨 위(가장 최근) 분석만 펼침
      box.appendChild(h("details", { class: "card-box ref-card", "data-k": "ref" + rf.id, open: i === 0 }, kids));
    });
  }

  function copyBtn(text, label) {
    return h("button", { type: "button", class: "btn small copy-btn", onclick: function () {
      var done = function () { toast("복사했어요 — 붙여 넣기(Ctrl+V) 하세요"); };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
      else { fallbackCopy(text); done(); }
    } }, [label || "📋 복사"]);
  }
  function fallbackCopy(text) {
    var t = h("textarea", {}); t.value = text; document.body.appendChild(t); t.select();
    try { document.execCommand("copy"); } catch (e) {}
    t.remove();
  }

  // 분석한 프롬프트로 예시 한 편(제목·설명·곡 목록·첫 곡 가사·썸네일 글자·그림 프롬프트)을 시험으로 만들어 봄
  var SAMPLE_TOPIC = {};
  function sampleBox(rf) {
    var sm = rf.sample || {}, busy = rf.sample_state === "요청" || rf.sample_state === "만드는중";
    var topic = h("input", { type: "text", class: "ref-url", placeholder: "이번 편 주제 (선택) — 예) 가을밤 마음 비우기", oninput: function () { SAMPLE_TOPIC[rf.id] = topic.value; } });
    topic.value = SAMPLE_TOPIC[rf.id] != null ? SAMPLE_TOPIC[rf.id] : (rf.sample_topic || "");
    var kids = [h("b", { text: "✨ 예시로 만들어보기" }),
      h("span", { class: "muted small", text: "이 프롬프트대로 영상 한 편을 만들면 어떻게 나오는지 글로 먼저 시험해 봐요 (유튜브에는 아무것도 안 올라가요)." }),
      h("div", { class: "row gap sample-go" }, [topic, h("button", { type: "button", class: "btn primary", disabled: busy, onclick: function () {
        api("POST", "/api/refs/" + rf.id + "/sample", { topic: topic.value }).then(function () { toast("예시를 만드는 중이에요 (1분쯤)"); refreshExtra(); }).catch(function (err) { toast(err.message); });
      } }, [busy ? "만드는 중…" : rf.sample_state === "완료" ? "다시 만들어보기" : "✨ 만들어보기"])])];
    if (rf.sample_error) kids.push(h("span", { class: "small set-bad", text: rf.sample_error }));
    if (rf.sample_state === "완료" && sm.titles) {
      kids.push(h("div", { class: "sample-sec" }, [h("span", { class: "small", text: "제목 후보" })].concat(sm.titles.map(function (t) { return h("div", { class: "sample-title", text: t }); }))));
      if (sm.thumb_text) kids.push(h("div", { class: "sample-sec" }, [h("span", { class: "small", text: "썸네일 글자" }), h("div", { class: "sample-thumb", text: sm.thumb_text })]));
      if (sm.songs && sm.songs.length) kids.push(h("div", { class: "sample-sec" }, [h("span", { class: "small", text: "곡 목록 (" + sm.songs.length + "곡)" }), h("ol", { class: "sample-songs" }, sm.songs.map(function (t) { return h("li", { text: t }); }))]));
      var ly = sm.lyrics || {};
      if (ly.text) kids.push(h("details", { class: "ti-desc", open: true }, [h("summary", { class: "small", text: "첫 곡 가사 — " + (ly.title || "") }), ly.style ? h("div", { class: "muted small", text: "수노 스타일: " + ly.style }) : null, copyBtn(ly.text), h("pre", { text: ly.text })]));
      if (sm.description) kids.push(h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "설명 전체" }), h("pre", { text: sm.description })]));
      if (sm.thumb_prompt) kids.push(h("details", { class: "ti-desc", open: true }, [h("summary", { class: "small", text: "🖼 이번 편 썸네일 프롬프트 — 그림 AI(ChatGPT·Gemini)에 그대로 붙여 넣으면 그림+글자까지 나와요" }), copyBtn(sm.thumb_prompt), h("pre", { text: sm.thumb_prompt })]));
      if (sm.image_prompt) kids.push(h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "이번 편 영상 배경 그림 프롬프트" }), copyBtn(sm.image_prompt), h("pre", { text: sm.image_prompt })]));
    }
    return h("div", { class: "sample-box" }, kids);
  }

  // 🎵 수노 가사 — 참고 가사를 넣으면 같은 공식의 새 가사 + 수노 스타일 + 재사용 가사 프롬프트
  var LYRICS = [], LY_DRAFT = {}, LY_TOPIC = {};
  function drawLyricsPage(box) {
    if (box.contains(document.activeElement) && /TEXTAREA|INPUT|SELECT/.test(document.activeElement.tagName)) return;
    box.innerHTML = "";
    box.appendChild(head("수노 가사", "따라 하고 싶은 노래 가사를 붙여 넣으면, AI가 줄 수·후렴 반복·말투 같은 공식만 뽑아서 수노에 그대로 붙여 넣을 새 가사와 스타일을 1분 안에 만들어 줘요. 문장은 베끼지 않아요."));
    var title = h("input", { type: "text", class: "ref-url", placeholder: "참고 노래 제목 (선택)", oninput: function () { LY_DRAFT.title = title.value; } });
    var lyr = h("textarea", { rows: "10", placeholder: "참고할 가사를 여기에 붙여 넣으세요 (한 소절만 넣어도 돼요)", oninput: function () { LY_DRAFT.ref = lyr.value; } });
    var topic = h("input", { type: "text", class: "ref-url", placeholder: "새 노래 주제 (선택) — 예) 돌아가신 어머니께 드리는 기도", oninput: function () { LY_DRAFT.topic = topic.value; } });
    if (LY_DRAFT.ch == null && view.ch !== "all") LY_DRAFT.ch = view.ch;
    var ch = h("select", { class: "ref-url", onchange: function () { LY_DRAFT.ch = ch.value; } }, [h("option", { value: "", text: "채널 말투 참고 안 함" })].concat(META.channels.map(function (c) {
      return h("option", { value: c.key, text: (c.display || c.name) + " 가사 프롬프트도 참고" });
    })));
    title.value = LY_DRAFT.title || ""; lyr.value = LY_DRAFT.ref || ""; topic.value = LY_DRAFT.topic || ""; ch.value = LY_DRAFT.ch || "";
    box.appendChild(h("div", { class: "card-box" }, [h("b", { text: "참고 가사 넣기" }), title, lyr, topic, ch,
      h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", onclick: function () {
        if (!lyr.value.trim()) { toast("참고 가사를 넣어 주세요"); return; }
        api("POST", "/api/lyrics", { title: title.value, ref_lyrics: lyr.value, topic: topic.value, channel: ch.value }).then(function () {
          LY_DRAFT = {}; toast("가사를 만드는 중이에요 (1분쯤)"); refreshExtra();
        }).catch(function (err) { toast(err.message); });
      } }, ["🎵 수노 가사 만들기"])])]));
    var lys = LYRICS.filter(function (j) { return view.ch === "all" || !j.channel || j.channel === view.ch; });
    if (!lys.length) { box.appendChild(h("div", { class: "card-box empty", text: "아직 만든 가사가 없어요" })); return; }
    lys.forEach(function (j, i) {
      var res = j.result || {}, busy = j.state === "요청" || j.state === "만드는중";
      var st = { "요청": "⏳ 차례 기다림", "만드는중": "🎵 만드는 중…", "완료": "✅ 완료", "실패": "⚠ 실패" }[j.state] || j.state;
      var del = function (ev) { ev.preventDefault(); ev.stopPropagation(); if (confirm("이 가사를 지울까요?")) api("DELETE", "/api/lyrics/" + j.id).then(function () { toast("지웠어요"); refreshExtra(); }); };
      var kids = [h("summary", { class: "row gap ref-sum" }, [
        h("div", { class: "ti-main" }, [h("b", { text: res.suno_title || j.title || "가사 " + j.id }),
          h("span", { class: "muted small", text: "참고: " + (j.title || String(j.ref_lyrics || "").split("\n")[0].slice(0, 30)) + (j.topic ? " · 주제: " + j.topic : "") + " · " + String(j.updated_at || "").slice(5, 16).replace("T", " ") })]),
        h("span", { class: "spacer" }),
        h("span", { class: "shop-st " + (j.state === "완료" ? "ok" : "wait"), text: st }),
        h("button", { type: "button", class: "btn small ref-del", onclick: del }, ["🗑 삭제"])
      ])];
      if (j.error) kids.push(h("span", { class: "small set-bad", text: j.error }));
      if (j.state === "완료") {
        kids.push(h("div", { class: "sample-box" }, [h("b", { text: "수노에 이대로 붙여 넣기" }),
          sunoField("Song Title (제목)", res.suno_title, false),
          sunoField("Style of Music (스타일)", res.suno_style, false),
          sunoField("Lyrics (가사)", res.suno_lyrics, true),
          res.check ? h("span", { class: "muted small", text: "겹침 점검: " + res.check }) : null]));
        if (res.analysis) kids.push(h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "참고 가사 공식 분석" }), h("pre", { text: res.analysis })]));
        if (res.lyrics_prompt) kids.push(h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "재사용 가사 프롬프트 (다음에 주제만 바꿔 쓰기)" }), copyBtn(res.lyrics_prompt), h("pre", { text: res.lyrics_prompt }),
          h("div", { class: "row gap" }, [h("span", { class: "small", text: "채널 가사 프롬프트로 넣기:" })].concat(META.channels.map(function (c) {
            return h("button", { type: "button", class: "btn small", onclick: function () {
              if (!confirm((c.display || c.name) + " 채널의 가사 프롬프트를 이걸로 바꿀까요?")) return;
              api("POST", "/api/lyrics/" + j.id + "/apply/" + c.key).then(function (nr) { RULES[c.key] = nr; toast("넣었어요 — 채널 프롬프트에서 고칠 수 있어요"); }).catch(function (err) { toast(err.message); });
            } }, ["→ " + (c.display || c.name)]);
          })))]));
      }
      var t2 = h("input", { type: "text", class: "ref-url", placeholder: "다른 주제로 다시 (선택)", oninput: function () { LY_TOPIC[j.id] = t2.value; } });
      t2.value = LY_TOPIC[j.id] != null ? LY_TOPIC[j.id] : "";
      kids.push(h("div", { class: "row gap sample-go" }, [t2, h("button", { type: "button", class: "btn small", disabled: busy, onclick: function () {
        api("POST", "/api/lyrics/" + j.id + "/retry", t2.value ? { topic: t2.value } : {}).then(function () { delete LY_TOPIC[j.id]; toast("다시 만드는 중이에요"); refreshExtra(); });
      } }, ["🔁 다시 만들기"])]));
      kids.push(h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "넣었던 참고 가사 보기" }), h("pre", { text: j.ref_lyrics || "" })]));
      box.appendChild(h("details", { class: "card-box ref-card", "data-k": "ly" + j.id, open: i === 0 }, kids));
    });
  }
  function sunoField(label, text, big) {
    return h("div", { class: "sample-sec" }, [h("div", { class: "row gap" }, [h("span", { class: "small", text: label }), copyBtn(text || "")]),
      h(big ? "pre" : "div", { class: big ? "suno-lyrics" : "sample-title", text: text || "" })]);
  }

  // ⚙ 채널 설정 — 만들기 규칙 + 프롬프트를 한 화면에
  function drawChsetPage(box) {
    if (box.contains(document.activeElement) && /TEXTAREA|INPUT|SELECT/.test(document.activeElement.tagName)) return;
    box.innerHTML = "";
    chList().forEach(function (c) { box.appendChild(h("div", { class: "card-box" }, [h("div", { class: "row gap" }, [chTag2(c.key)]), refLine(c.key)])); });
    var a = box.appendChild(h("div", {})), b = box.appendChild(h("div", {}));
    drawRulesPage(a);
    b.appendChild(h("h3", { class: "set-h", text: "🧠 프롬프트" }));
    var pb = b.appendChild(h("div", {}));
    drawPromptsPage(pb);
    var lw = box.appendChild(h("details", { class: "card-box", "data-k": "chset-lyrics" }, [h("summary", {}, [h("b", { text: "🎵 참고 가사로 가사 프롬프트 만들기" }),
      h("span", { class: "muted small", text: "  마음에 드는 노래 가사를 넣으면 그 형식대로 가사 프롬프트를 만들어 줘요" })])]));
    drawLyricsPage(lw.appendChild(h("div", {})));
  }

  // 🎬 새 영상 만들기 — 한 편을 1~6단계 순서대로
  var MK_TOPIC = {};
  function addDays(d, n) { var x = new Date(d + "T00:00:00"); x.setDate(x.getDate() + n); return x.getFullYear() + "-" + String(x.getMonth() + 1).padStart(2, "0") + "-" + String(x.getDate()).padStart(2, "0"); }
  function drawMakePage(box) {
    if (box.contains(document.activeElement) && /TEXTAREA|INPUT|SELECT/.test(document.activeElement.tagName)) return;
    box.innerHTML = "";
    if (view.ch === "all") {
      box.appendChild(head("새 영상 만들기", "어느 채널 영상을 만들까요?"));
      box.appendChild(h("div", { class: "mk-pick" }, META.channels.map(function (c) {
        return h("button", { type: "button", class: "card-box mk-ch", onclick: function () { view.ch = c.key; saveView(); drawAll(); } }, [chTag2(c.key), h("b", { text: (c.display || c.name) + " 영상 만들기 →" })]);
      })));
      return;
    }
    var key = view.ch, rl = RULES[key] || {};
    var mine = EPS.filter(function (e) { return e.channel === key; });
    var todo = mine.filter(function (e) { return !e.video_id; }).sort(function (a, b) { return String(a.date).localeCompare(String(b.date)); });
    var e = todo.filter(function (x) { return x.id === view.makeEp; })[0] || todo[0];
    var newEp = function () {
      var last = mine.map(function (x) { return x.date; }).filter(Boolean).sort().pop();
      var date = last ? addDays(last, +rl.every_days || 2) : META.today;
      if (date < META.today) date = META.today;
      api("POST", "/api/episodes", { channel: key, date: date }).then(function (ne) {
        view.makeEp = ne.id;
        return api("POST", "/api/episodes/" + ne.id + "/make", { job: "all" }).then(function () { toast(ne.ep + "편 시작 — AI가 주제부터 가사까지 한 번에 만들고 있어요"); refresh(); });
      }).catch(function (err) { toast(err.message); });
    };
    var pick = h("select", { class: "ref-url mk-sel", onchange: function () { view.makeEp = +pick.value; drawPage(); } }, todo.map(function (x) {
      return h("option", { value: String(x.id), text: x.ep + "편 · " + dotDate(x.date) + " 공개 예정" + (x.make && x.make.topic ? " · " + (x.make.topic.length > 18 ? x.make.topic.slice(0, 18) + "…" : x.make.topic) : "") });
    }));
    if (e) pick.value = String(e.id);
    box.appendChild(refLine(key));
    box.appendChild(head("새 영상 만들기", "「✨ 한 번에 다 만들기」를 누르면 AI가 주제·썸네일 문구와 프롬프트·곡 목록·제목·설명·가사를 다 만들어요. 썸네일 그림만 프롬프트를 복사해서 뽑아 넣으면 돼요.",
      h("div", { class: "row gap" }, [todo.length ? pick : null, h("button", { type: "button", class: "btn primary", onclick: newEp }, ["＋ 새 편 시작"])])));
    if (!e) { box.appendChild(h("div", { class: "card-box empty", text: "만들고 있는 편이 없어요. 「＋ 새 편 시작」을 눌러 주세요." })); return; }
    view.makeEp = e.id;
    var mk = e.make || {}, done = mk.done || {}, jobs = mk.jobs || {};
    var save = function (body, msg) { return api("POST", "/api/episodes/" + e.id + "/make", body).then(function () { if (msg) toast(msg); refresh(); }).catch(function (err) { toast(err.message); }); };
    var busy = function (k) { return jobs[k] && (jobs[k].state === "요청" || jobs[k].state === "만드는중"); };
    var jobErr = function (k) { return jobs[k] && jobs[k].state === "실패" ? h("span", { class: "small set-bad", text: "AI 실패: " + jobs[k].error }) : null; };
    var songs = mk.songs || [], sd = mk.song_done || {};
    var steps = [
      { k: "topic", t: "주제 정하기", ok: !!mk.topic },
      { k: "thumb", t: "썸네일", ok: !!thumbSrc(e) },
      { k: "title", t: "제목·설명", ok: !!e.title && !!e.description },
      { k: "songs", t: "가사·노래 (수노)", ok: !!done.songs },
      { k: "video", t: "영상 만들기", ok: !!done.video || !!e.video_id },
      { k: "upload", t: "올리기 · 검토 · 승인", ok: !!e.video_id && (e.review === "승인" || e.badge === "예약됨" || e.badge === "공개됨") }
    ];
    var cur = steps.filter(function (s) { return !s.ok; })[0];
    var all = jobs.all || {}, allBusy = all.state === "요청" || all.state === "만드는중";
    var STAGE = { topic: "주제 정하는 중", thumb: "썸네일 문구·프롬프트 만드는 중", plan: "곡 목록 정하는 중", title: "제목·설명 쓰는 중", lyrics: "가사 쓰는 중" };
    var lyDone = songs.filter(function (x) { return x.lyrics; }).length;
    box.appendChild(h("div", { class: "card-box mk-all" + (allBusy ? " busy" : "") }, [
      h("div", { class: "row gap" }, [
        h("button", { type: "button", class: "btn primary mk-all-btn", disabled: allBusy, onclick: function () {
          if ((mk.topic || e.title || songs.length) && !confirm("이 편을 처음부터 다시 다 만들까요?\n(주제를 적어 두었으면 그 주제는 그대로 써요)")) return;
          save({ job: "all" }, "AI가 한 번에 만들고 있어요 — 몇 분 걸려요");
        } }, [allBusy ? "⏳ 만드는 중…" : all.state === "완료" ? "🔁 한 번에 다시 만들기" : "✨ 한 번에 다 만들기"]),
        h("div", { class: "ti-main" }, [
          h("b", { text: allBusy ? (STAGE[all.stage] || "차례 기다리는 중") + (all.stage === "lyrics" ? " (" + lyDone + "/" + songs.length + ")" : "") : all.state === "완료" ? "✅ 다 만들었어요 — 썸네일 그림만 뽑아 넣으면 돼요" : all.state === "실패" ? "⚠ 중간에 멈췄어요: " + all.error : "주제부터 가사까지 AI가 다 정해요" }),
          h("span", { class: "muted small", text: "주제 → 썸네일 문구·프롬프트 → 곡 목록 → 제목·설명 → 가사 순서로, 1분마다 조금씩 이어서 만들어요 (8곡이면 10분쯤)" })
        ])
      ])
    ]));
    box.appendChild(h("div", { class: "mk-bar" }, steps.map(function (s, i) {
      return h("span", { class: "mk-dot" + (s.ok ? " ok" : s === cur ? " now" : "") }, [(s.ok ? "✓" : String(i + 1)) + " " + s.t]);
    })));
    box.appendChild(h("div", { class: "muted small mk-ep", text: chInfo(key).name + " " + e.ep + "편 · " + dotDate(e.date) + " 공개 예정" }));
    var body = {
      topic: function () {
        var inp = h("input", { type: "text", class: "ref-url", placeholder: "예) 멀리 사는 자식을 위한 어머니의 기도", oninput: function () { MK_TOPIC[e.id] = inp.value; } });
        inp.value = MK_TOPIC[e.id] != null ? MK_TOPIC[e.id] : (mk.topic || "");
        return [h("span", { class: "muted small", text: "「한 번에 다 만들기」를 누르면 AI가 정해요. 원하는 주제가 있으면 적고 저장한 뒤 누르면 그 주제로 만들어요." }),
          h("div", { class: "row gap sample-go" }, [inp, h("button", { type: "button", class: "btn primary", onclick: function () { delete MK_TOPIC[e.id]; save({ topic: inp.value }, "주제를 저장했어요"); } }, ["저장"])])];
      },
      thumb: function () {
        var file = h("input", { type: "file", accept: "image/*", onchange: function () {
          if (!file.files[0]) return;
          var fd = new FormData(); fd.append("file", file.files[0]);
          api("POST", "/api/episodes/" + e.id + "/thumbnail", fd).then(function () { toast("썸네일을 넣었어요"); refresh(); }).catch(function (err) { toast(err.message); });
        } });
        return [
          h("span", { class: "muted small", text: "① 「프롬프트 만들기」 → ② 📋 복사해서 ChatGPT·Gemini에 붙여 넣기 → ③ 나온 그림을 여기에 넣기" }),
          h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", disabled: busy("thumb"), onclick: function () { save({ job: "thumb" }, "썸네일 프롬프트를 만드는 중이에요 (1분쯤)"); } },
            [busy("thumb") ? "만드는 중…" : mk.thumb_prompt ? "🔁 다시 만들기" : "✨ 썸네일 프롬프트 만들기"]), rl.thumb_prompt ? null : h("span", { class: "muted small", text: "채널 설정에 썸네일 프롬프트가 없어서 기본 분위기로 만들어요" })]),
          jobErr("thumb"),
          mk.thumb_text ? h("div", { class: "sample-thumb", text: mk.thumb_text }) : null,
          mk.thumb_prompt ? h("details", { class: "ti-desc", open: true }, [h("summary", { class: "small", text: "썸네일 프롬프트 (그림 AI에 그대로 붙여 넣기)" }), copyBtn(mk.thumb_prompt), h("pre", { text: mk.thumb_prompt })]) : null,
          h("div", { class: "mk-thumb" }, [h("div", { class: "yt-thumb" }, [thumbSrc(e) ? h("img", { src: thumbSrc(e), alt: "" }) : h("span", { class: "muted small", text: "아직 썸네일 없음" })]),
            h("label", { class: "btn" }, ["🖼 썸네일 그림 넣기", file])])
        ];
      },
      title: function () {
        var apply = function (field, val, label) {
          if (!confirm(label + "을 이걸로 할까요?\n\n" + String(val).slice(0, 300))) return;
          var b = {}; b[field] = val;
          (e.video_id ? api("POST", "/api/episodes/" + e.id + "/edit", b) : api("PATCH", "/api/episodes/" + e.id, b)).then(function () { toast(label + "을 넣었어요"); refresh(); }).catch(function (err) { toast(err.message); });
        };
        return [
          h("span", { class: "muted small", text: "주제·썸네일 문구·곡 제목에 맞춰 AI가 제목 후보 3개와 설명을 써요. 누르면 바로 들어가요." }),
          h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", disabled: e.ai_state === "요청", onclick: function () {
            api("POST", "/api/episodes/" + e.id + "/ai").then(function () { toast("AI가 쓰는 중이에요 (1분쯤)"); refresh(); }).catch(function (err) { toast(err.message); });
          } }, [e.ai_state === "요청" ? "쓰는 중…" : "✨ 제목·설명 만들기"])]),
          e.ai_state === "실패" ? h("span", { class: "small set-bad", text: "AI 실패: " + e.ai_note }) : null,
          (e.ai_titles || []).length ? h("div", { class: "up-alts" }, [h("span", { class: "muted small", text: "제목 후보 (누르면 넣기)" })].concat(e.ai_titles.map(function (t) {
            return h("button", { type: "button", class: "chip", onclick: function () { apply("title", t, "제목"); } }, [t]);
          }))) : null,
          e.ai_desc ? h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "AI 설명 보기" }), h("pre", { text: e.ai_desc }),
            h("button", { type: "button", class: "btn small", onclick: function () { apply("description", e.ai_desc, "설명"); } }, ["이 설명 넣기"])]) : null,
          (function () {
            var ti = h("input", { type: "text", class: "ref-url", value: e.title || "", placeholder: "아직 없음" });
            return h("div", { class: "mk-now" }, [h("span", { class: "small", text: "지금 제목 (직접 고쳐도 돼요)" }), h("div", { class: "row gap sample-go" }, [ti,
              h("button", { type: "button", class: "btn small", onclick: function () {
                (e.video_id ? api("POST", "/api/episodes/" + e.id + "/edit", { title: ti.value }) : api("PATCH", "/api/episodes/" + e.id, { title: ti.value })).then(function () { toast("제목을 고쳤어요"); refresh(); }).catch(function (err) { toast(err.message); });
              } }, ["저장"])])]);
          })(),
          e.description ? h("details", { class: "ti-desc" }, [h("summary", { class: "small", text: "지금 설명 보기" }), h("pre", { text: e.description })]) : null
        ];
      },
      songs: function () {
        var kids = [
          h("span", { class: "muted small", text: "AI가 곡 " + (+rl.songs || 8) + "개의 제목과 가사를 써요 (몇 분 걸려요). 곡마다 📋 복사해서 수노에 붙여 넣고, 만든 곡은 체크하세요." }),
          h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", disabled: busy("songs"), onclick: function () {
            if (songs.length && !confirm("곡 목록과 가사를 새로 만들까요? (지금 것은 바뀌어요)")) return;
            save({ job: "songs" }, "곡 목록과 가사를 만드는 중이에요 (몇 분)");
          } }, [busy("songs") ? "만드는 중… (" + songs.filter(function (x) { return x.lyrics; }).length + "/" + (songs.length || "?") + ")" : songs.length ? "🔁 다시 만들기" : "✨ 곡 목록·가사 만들기"])]),
          jobErr("songs")
        ];
        if (songs.length && songs[0].style) kids.push(sunoField("Style of Music (모든 곡 공통)", songs[0].style, false));
        songs.forEach(function (sg, i) {
          var chk = h("input", { type: "checkbox", onchange: function () { var x = {}; x[i] = chk.checked; save({ song_done: x }); } }); chk.checked = !!sd[i];
          kids.push(h("details", { class: "ti-desc mk-song", "data-k": "song" + e.id + "-" + i }, [
            h("summary", { class: "small" }, [(sd[i] ? "✅ " : "") + (i + 1) + ". " + (sg.title || "") + (sg.lyrics ? "" : "  (가사 쓰는 중…)")]),
            sg.idea ? h("div", { class: "muted small", text: sg.idea }) : null,
            h("div", { class: "row gap" }, [copyBtn(sg.title || "", "📋 제목 복사"), sg.lyrics ? copyBtn(sg.lyrics, "📋 가사 복사") : null]),
            sg.lyrics ? h("pre", { class: "suno-lyrics", text: sg.lyrics }) : null,
            h("label", { class: "mk-check" }, [chk, "수노로 만들었어요"])
          ]));
        });
        kids.push(h("label", { class: "mk-check" }, [h("input", { type: "checkbox", checked: !!done.songs, onchange: function (ev) { save({ done: { songs: ev.target.checked } }); } }), "노래를 다 만들고 파일(mp3)도 받았어요"]));
        kids.push(h("span", { class: "muted small", text: "참고할 노래 가사가 있으면 ⚙ 채널 설정 맨 아래 「🎵 참고 가사로 가사 프롬프트 만들기」에서 그 형식을 채널 가사 프롬프트로 만들 수 있어요." }));
        return kids;
      },
      video: function () {
        return [
          h("div", { class: "mk-now" }, [h("span", { class: "small", text: "영상은 Claude가 만들어요. 채팅에 이렇게 말해 주세요:" }), h("b", { text: "「" + chInfo(key).name + " " + e.ep + "편 영상 만들어 줘」" })]),
          h("span", { class: "muted small", text: "노래 파일(mp3)이 있는 폴더도 같이 알려 주세요. 만든 영상은 이 편 날짜로 올리기까지 해 둘게요." }),
          h("label", { class: "mk-check" }, [h("input", { type: "checkbox", checked: !!done.video, onchange: function (ev) { save({ done: { video: ev.target.checked } }); } }), "영상이 다 만들어졌어요"])
        ];
      },
      upload: function () {
        var st = !e.video_id ? "아직 유튜브에 안 올라갔어요" : e.review === "검토대기" ? "유튜브에 일부 공개로 올라갔어요 — 📋 영상 목록 맨 위 🕵 검토할 영상에서 보고 승인하세요" : e.badge === "예약됨" ? "승인됨 · " + dotDate(e.date) + " " + (rl.publish_time || "21:00") + " 공개 예약" : e.badge;
        return [
          h("div", { class: "mk-now" }, [h("span", { class: "small", text: "지금 상태" }), h("b", { text: st })]),
          !e.video_id ? h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", onclick: function () { UP_PRESET = { channel: key, date: e.date }; openUpload(null); } }, ["⬆ 영상 파일 올리기"]),
            h("span", { class: "muted small", text: "Claude가 올리면 이 단계는 저절로 넘어가요" })]) : null,
          e.video_id && e.review === "검토대기" ? h("button", { type: "button", class: "btn primary", onclick: function () { setPage("list"); } }, ["🕵 검토하러 가기"]) : null
        ];
      }
    };
    steps.forEach(function (s, i) {
      box.appendChild(h("details", { class: "card-box mk-step" + (s.ok ? " ok" : s === cur ? " now" : ""), "data-k": "mk" + e.id + "-" + s.k, open: s === cur }, [
        h("summary", { class: "row gap ref-sum" }, [h("span", { class: "mk-num", text: s.ok ? "✓" : String(i + 1) }), h("b", { text: s.t }), h("span", { class: "spacer" }),
          h("span", { class: "shop-st " + (s.ok ? "ok" : "wait"), text: s.ok ? "✅ 됨" : s === cur ? "👉 지금 할 차례" : "기다림" })])
      ].concat(body[s.k]())));
    });
  }

  // 📚 레퍼런스 채널 — 채널 분석 결과를 저장해 두고 채널마다 골라 씀
  var SAVED = [];
  var SAVED_KEYS = [["summary", "이 채널이 잘 되는 이유"], ["songs_hint", "곡 수·길이"], ["title_rules", "제목 프롬프트"], ["desc_rules", "설명 프롬프트"], ["examples", "예시 제목"],
    ["thumb_prompt", "썸네일 그림 프롬프트"], ["image_prompt", "영상 배경 그림 프롬프트"], ["lyrics_prompt", "노래 가사 프롬프트"]];
  function usersOf(sid) { return META.channels.filter(function (c) { return (RULES[c.key] || {}).ref_id === sid; }); }
  function applySaved(sid, key, after) {
    var sr = SAVED.filter(function (x) { return x.id === sid; })[0], c = chInfo(key);
    if (!sr || !confirm((c.display || c.name) + " 채널의 레퍼런스를 ‘" + sr.name + "’로 바꿀까요?\n제목·설명·예시·썸네일·영상 그림·가사 프롬프트가 이 레퍼런스 것으로 바뀌어요.")) return;
    api("POST", "/api/saved-refs/" + sid + "/apply/" + key).then(function (nr) { RULES[key] = nr; toast("레퍼런스를 ‘" + sr.name + "’로 바꿨어요"); if (after) after(); drawPage(); }).catch(function (err) { toast(err.message); });
  }
  // 채널마다 “지금 레퍼런스: OO [바꾸기]” 줄
  function refLine(key) {
    var rl = RULES[key] || {};
    var sel = h("select", { class: "ref-url ref-pick", onchange: function () { var v = +sel.value; sel.value = String(rl.ref_id || 0); if (v) applySaved(v, key); } },
      [h("option", { value: "0", text: SAVED.length ? "레퍼런스 바꾸기…" : "저장한 레퍼런스가 없어요" })].concat(SAVED.map(function (x) { return h("option", { value: String(x.id), text: x.name }); })));
    sel.value = "0";
    return h("div", { class: "ref-line" }, [h("span", { class: "small", text: "📚 레퍼런스 채널" }),
      h("b", { text: rl.ref_note || "아직 없음" }), h("span", { class: "spacer" }), sel,
      h("button", { type: "button", class: "btn small", onclick: function () { setPage("saved"); } }, ["보관함"])]);
  }
  function drawSavedPage(box) {
    if (box.contains(document.activeElement) && /TEXTAREA|INPUT|SELECT/.test(document.activeElement.tagName)) return;
    box.innerHTML = "";
    box.appendChild(head("레퍼런스 채널", "🔍 채널 분석에서 「💾 레퍼런스로 저장」한 것들이에요. 내용을 고쳐 저장하거나, 채널에 골라 넣을 수 있어요. 채널은 한 번에 레퍼런스 하나를 써요."));
    if (!SAVED.length) { box.appendChild(h("div", { class: "card-box empty", text: "저장한 레퍼런스가 없어요. 🔍 채널 분석 결과에서 「💾 레퍼런스로 저장」을 눌러 주세요." })); return; }
    SAVED.forEach(function (sr) {
      var ci = sr.channel || {}, res = sr.result || {}, users = usersOf(sr.id);
      var name = h("input", { type: "text", class: "ref-url", value: sr.name });
      var f = {};
      var kids = [h("summary", { class: "row gap ref-sum" }, [
        ci.thumb ? h("img", { class: "ref-avatar", src: ci.thumb, alt: "" }) : null,
        h("div", { class: "ti-main" }, [h("b", { text: sr.name }), h("span", { class: "muted small", text: (ci.title ? ci.title + " · " : "") + (ci.subs ? "구독자 " + ci.subs.toLocaleString() + " · " : "") + "저장 " + String(sr.saved_at || "").slice(0, 10) })]),
        h("span", { class: "spacer" }),
        users.length ? h("span", { class: "shop-st ok", text: "사용 중: " + users.map(function (c) { return c.display || c.name; }).join(", ") }) : h("span", { class: "shop-st wait", text: "안 쓰는 중" }),
        h("button", { type: "button", class: "btn small ref-del", onclick: function (ev) {
          ev.preventDefault(); ev.stopPropagation();
          if (confirm("‘" + sr.name + "’을 보관함에서 지울까요?\n(채널에 들어가 있는 프롬프트는 그대로 남아요)")) api("DELETE", "/api/saved-refs/" + sr.id).then(function () { toast("지웠어요"); refreshExtra(); });
        } }, ["🗑 삭제"])
      ])];
      kids.push(h("label", { class: "stack" }, [h("span", { class: "small", text: "이름" }), name]));
      SAVED_KEYS.forEach(function (k) {
        f[k[0]] = h("textarea", { rows: k[0] === "summary" ? "5" : "4" }); f[k[0]].value = res[k[0]] || "";
        kids.push(h("label", { class: "stack" }, [h("span", { class: "small", text: k[1] }), f[k[0]]]));
      });
      kids.push(h("div", { class: "row gap" }, [h("button", { type: "button", class: "btn primary", onclick: function () {
        var r = {}; Object.keys(f).forEach(function (k) { r[k] = f[k].value; });
        api("PATCH", "/api/saved-refs/" + sr.id, { name: name.value, result: r }).then(function () { toast("저장했어요" + (users.length ? " — 쓰는 채널에도 다시 넣으려면 아래 버튼을 눌러 주세요" : "")); refreshExtra(); }).catch(function (err) { toast(err.message); });
      } }, ["💾 저장"])]));
      kids.push(h("div", { class: "row gap" }, [h("span", { class: "small", text: "이 레퍼런스를 채널에 쓰기:" })].concat(META.channels.map(function (c) {
        return h("button", { type: "button", class: "btn small", onclick: function () { applySaved(sr.id, c.key); } }, ["→ " + (c.display || c.name)]);
      }))));
      box.appendChild(h("details", { class: "card-box ref-card", "data-k": "saved" + sr.id }, kids));
    });
  }

  // 🖼 썸네일 — 16:9 그대로 모아 보기
  function drawThumbsPage(box) {
    box.innerHTML = "";
    box.appendChild(head("썸네일", "편마다 썸네일을 16:9 그대로 봐요. 누르면 세부정보에서 문구·그림을 바꿀 수 있어요."));
    var grid = h("div", { class: "th-grid" });
    chEps().slice().sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); }).forEach(function (e) {
      var src = thumbSrc(e);
      grid.appendChild(h("button", { type: "button", class: "th-card", onclick: function () { openDetail(e.id); } }, [
        h("div", { class: "yt-thumb th-img" }, [src ? h("img", { src: src, alt: "" }) : h("span", { class: "muted small", text: "썸네일 없음" })]),
        h("div", { class: "th-cap" }, [chTag2(e.channel), h("b", { text: " " + e.ep + "편 · " + dotDate(e.date) }), h("span", { class: "badge " + e.badge, text: e.badge })])
      ]));
    });
    box.appendChild(grid);
  }

  // 🛍 쇼핑 태그 — 편마다 붙었는지
  function drawShopPage(box) {
    box.innerHTML = "";
    var list = chEps().filter(function (e) { return e.video_id; }).sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });
    var done = list.filter(function (e) { return (e.shop_tags || 0) >= 4; }).length;
    box.appendChild(head("쇼핑 태그", "유튜브 API로는 못 붙여서, PC 웨일 예약 작업이 매일 21:20 · 00:20에 붙이고 다시 열어 확인한 뒤 여기에 적어요 (PC가 켜져 있어야 해요). 라이브 쇼핑 태그도 같은 작업이 붙여요.",
      h("div", { class: "shop-sum" }, [h("b", { text: done + " / " + list.length }), h("span", { class: "muted small", text: "편 확인됨" })])));
    var tbl = h("div", { class: "card-box" });
    list.forEach(function (e) {
      var ok = (e.shop_tags || 0) >= 4;
      tbl.appendChild(h("div", { class: "shop-row" }, [
        h("div", { class: "yt-thumb" }, [thumbSrc(e) ? h("img", { src: thumbSrc(e), alt: "" }) : null]),
        h("div", { class: "ti-main" }, [h("div", {}, [chTag2(e.channel), " ", h("b", { text: e.ep + "편 · " + dotDate(e.date) })]), h("div", { class: "ti-title", text: e.title || "" })]),
        h("span", { class: "shop-st " + (ok ? "ok" : "wait"), text: ok ? "✅ 4개 붙음" : "⏳ 아직" }),
        h("span", { class: "muted small", text: e.shop_checked_at ? "확인 " + String(e.shop_checked_at).slice(5, 16).replace("T", " ") : "확인 전" }),
        h("a", { class: "btn small", href: "https://studio.youtube.com/video/" + e.video_id + "/edit" + (chInfo(e.channel).name === "황금주파수" ? "?authuser=1" : ""), target: "_blank", rel: "noopener", text: "스튜디오" })
      ]));
    });
    if (!list.length) tbl.appendChild(h("p", { class: "muted", text: "유튜브에 올라간 편이 없어요" }));
    box.appendChild(tbl);
  }

  // 🕘 실행 기록
  function drawLogPage(box) {
    box.innerHTML = "";
    box.appendChild(head("실행 기록", "사이트·서버·PC가 한 일 (최근 " + LOGS.length + "개)"));
    var ol = h("ol", { class: "card-box log-list" });
    LOGS.forEach(function (r) {
      var d = new Date(r.at);
      ol.appendChild(h("li", {}, [h("span", { class: "muted small", text: (d.getMonth() + 1) + "/" + d.getDate() + " " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0") }), h("span", { text: r.text })]));
    });
    box.appendChild(ol);
  }

  // 🔧 설정·상태
  function drawSettingsPage(box) {
    box.innerHTML = "";
    var at = SYS.at ? new Date(SYS.at) : null;
    var fresh = at && Date.now() - at.getTime() < 5 * 60e3;
    box.appendChild(head("설정·상태", "서버 일꾼(1분마다)이 적는 상태예요."));
    box.appendChild(h("div", { class: "set-grid" }, [
      h("div", { class: "card-box" }, [h("b", { text: "서버 일꾼" }), h("div", { class: "set-big " + (fresh ? "ok" : "warn"), text: fresh ? "● 돌고 있어요" : "● 응답 없음" }),
        h("span", { class: "muted small", text: at ? "마지막 " + at.toLocaleString("ko-KR") : "아직 기록 없음" }),
        h("span", { class: "muted small", text: "유튜브로 보낼 차례인 영상 " + (SYS.waiting || 0) + "개" })]),
      h("div", { class: "card-box" }, [h("b", { text: "서버 저장 공간" }), h("div", { class: "set-big", text: (SYS.freeGB != null ? SYS.freeGB : "—") + "GB 남음" }),
        h("div", { class: "bar" }, [h("i", { style: "width:" + (SYS.totalGB ? Math.round((1 - SYS.freeGB / SYS.totalGB) * 100) : 0) + "%" })]),
        h("span", { class: "muted small", text: "영상 파일은 유튜브에 올린 뒤 지워요" })])
    ]));
    var chBox = h("div", { class: "card-box" }, [h("div", { class: "row gap" }, [h("b", { text: "채널 연결 · 오늘 유튜브 사용량" }), h("span", { class: "spacer" }),
      h("button", { type: "button", class: "btn small", onclick: function () { openChannelDialog(null); } }, ["＋ 채널 넣기"])])]);
    META.channels.forEach(function (c) {
      var s = (SYS.channels || []).filter(function (x) { return x.key === c.key; })[0] || {};
      var q = s.quota || 0;
      chBox.appendChild(h("div", { class: "set-ch" }, [
        chTag2(c.key),
        h("span", { class: "small " + (s.linked && !s.error ? "set-ok" : "set-bad"), text: s.linked ? (s.error ? "⚠ " + s.error : "✅ 구글 연결됨 (라이브 관리자)") : "⚠ 라이브 관리자에 같은 이름 채널이 없거나 연결 안 됨" }),
        h("div", { class: "bar set-q" }, [h("i", { style: "width:" + Math.min(100, Math.round(q / 100)) + "%" })]),
        h("span", { class: "small", text: q.toLocaleString() + " / 10,000" }),
        h("button", { type: "button", class: "btn small", onclick: function () { openChannelDialog(c); } }, ["✎"])
      ]));
    });
    chBox.appendChild(h("p", { class: "muted small", text: "새 채널은 라이브 관리자에 먼저 넣고 구글 연결을 한 뒤, 여기 ‘채널 넣기’에 똑같은 이름으로 넣으면 조회수·올리기가 그 채널로 돼요. 사용량이 8,500을 넘으면 라이브 채팅만 쉬어요." }));
    box.appendChild(chBox);
  }

  function refreshExtra() {
    return Promise.all([api("GET", "/api/rules"), api("GET", "/api/system"), api("GET", "/api/refs"), api("GET", "/api/lyrics"), api("GET", "/api/saved-refs")]).then(function (r) {
      RULES = r[0]; SYS = r[1]; REFS = r[2]; LYRICS = r[3]; SAVED = r[4];
      if (view.page !== "list") drawPage(); else drawTodo();
      // AI 를 기다리는 편이 있으면 5초 뒤 다시
      clearTimeout(refreshExtra.t);
      var mkBusy = EPS.some(function (e) { return e.make && e.make.jobs && Object.keys(e.make.jobs).some(function (k) { var j = e.make.jobs[k]; return j.state === "요청" || j.state === "만드는중"; }); });
      if (EPS.some(function (e) { return e.ai_state === "요청"; }) || mkBusy) refreshExtra.t = setTimeout(function () { refresh(); }, 6000);
      else if (REFS.some(function (x) { return x.state === "요청" || x.state === "분석중" || x.sample_state === "요청" || x.sample_state === "만드는중"; }) || LYRICS.some(function (x) { return x.state === "요청" || x.state === "만드는중"; })) refreshExtra.t = setTimeout(refreshExtra, 5000);
    }).catch(function () { /* 다음에 */ });
  }

  function refresh() {
    return Promise.all([api("GET", "/api/episodes"), api("GET", "/api/queue"), api("GET", "/api/status"), api("GET", "/api/log")])
      .then(function (r) { EPS = r[0]; QUEUE = r[1]; STATUS = r[2]; LOGS = r[3]; drawAll(); drawLog(r[3]); refreshUploads(); refreshExtra(); })
      .catch(function (err) { if (err.message !== "login") toast("불러오지 못했습니다: " + err.message); });
  }

  api("GET", "/api/meta").then(function (m) {
    META = m;
    $("btnStats").hidden = !m.youtube_stats;
    if (OLD_PAGE[view.page]) view.page = OLD_PAGE[view.page];
    if (!PAGE_NAME[view.page]) view.page = "list";
    setPage(view.page);
    refresh();
    setInterval(function () { if (!document.hidden) refresh(); }, 30000);
  });
})();
