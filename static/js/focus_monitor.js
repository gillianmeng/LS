/**
 * 切屏/失焦监测：依赖 Page Visibility + 最短后台时长，向服务端上报并展示提示。
 * 由课程详情页或考试中间页调用 window.lsInitFocusMonitor(config)
 */
(function () {
  "use strict";

  function showToast(message, level) {
    if (!message) return;
    var host = document.getElementById("ls-focus-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "ls-focus-toast-host";
      host.setAttribute("aria-live", "polite");
      host.style.cssText =
        "position:fixed;left:50%;top:1.25rem;transform:translateX(-50%);z-index:99999;max-width:min(92vw,24rem);pointer-events:none;";
      document.body.appendChild(host);
    }
    var el = document.createElement("div");
    var bg =
      level === "error"
        ? "rgba(185,28,28,.95)"
        : level === "success"
          ? "rgba(5,150,105,.95)"
          : "rgba(217,119,6,.95)";
    el.style.cssText =
      "pointer-events:auto;margin-bottom:8px;padding:12px 16px;border-radius:12px;font-size:13px;line-height:1.45;color:#fff;box-shadow:0 8px 32px rgba(15,23,42,.2);" +
      "background:" +
      bg +
      ";animation:lsFadeIn .2s ease;";
    el.textContent = message;
    host.appendChild(el);
    if (!document.getElementById("ls-focus-toast-style")) {
      var st = document.createElement("style");
      st.id = "ls-focus-toast-style";
      st.textContent =
        "@keyframes lsFadeIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}";
      document.head.appendChild(st);
    }
    setTimeout(function () {
      el.style.opacity = "0";
      el.style.transition = "opacity .35s ease";
      setTimeout(function () {
        el.remove();
      }, 400);
    }, 5200);
  }

  window.lsInitFocusMonitor = function (config) {
    if (!config || !config.reportUrl || !config.csrfToken) return;

    var graceMs = (config.graceSeconds || 12) * 1000;
    var minHiddenMs = config.minHiddenMs || 800;
    var started = Date.now();
    var hiddenSince = null;
    var posting = false;
    var queue = false;

    function payload() {
      var o = { scope: config.scope };
      if (config.courseId != null) o.course_id = config.courseId;
      if (config.sessionId) o.session_id = config.sessionId;
      return o;
    }

    function send() {
      if (posting) {
        queue = true;
        return;
      }
      posting = true;
      fetch(config.reportUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": config.csrfToken,
        },
        body: JSON.stringify(payload()),
      })
        .then(function (r) {
          return r.json().then(function (data) {
            return { ok: r.ok, data: data, status: r.status };
          });
        })
        .then(function (res) {
          posting = false;
          if (queue) {
            queue = false;
            send();
            return;
          }
          var d = res.data || {};
          if (d.toast) showToast(d.toast, d.toast_level || "warning");
          if (d.force_redirect) {
            window.location.href = d.force_redirect;
          }
        })
        .catch(function () {
          posting = false;
          if (queue) {
            queue = false;
            send();
          }
        });
    }

    document.addEventListener("visibilitychange", function () {
      if (Date.now() - started < graceMs) return;
      if (document.visibilityState === "hidden") {
        hiddenSince = Date.now();
      } else if (document.visibilityState === "visible" && hiddenSince) {
        var dt = Date.now() - hiddenSince;
        hiddenSince = null;
        if (dt >= minHiddenMs) {
          send();
        }
      }
    });
  };
})();
