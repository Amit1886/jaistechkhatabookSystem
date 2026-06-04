(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  function setResult(html) {
    const el = document.getElementById("voiceResult");
    if (!el) return;
    el.innerHTML = html || "";
  }

  function speechSupported() {
    return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  function startMic(onText) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setResult("<div class='text-danger'>Speech recognition not supported in this browser.</div>");
      return;
    }

    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    rec.onstart = () => setResult("<div class='text-muted'>Listening…</div>");
    rec.onerror = (e) => {
      const code = String(e && (e.error || e.message) ? (e.error || e.message) : "unknown");
      if (code === "not-allowed" || code === "service-not-allowed") {
        setResult(
          "<div class='text-danger'>Microphone access blocked. Allow microphone permission for this site and reload. If you're self-hosting, ensure the response header <code>Permissions-Policy</code> allows <code>microphone</code>.</div>"
        );
        return;
      }
      setResult(`<div class='text-danger'>Mic error: ${code}</div>`);
    };
    rec.onresult = (e) => {
      try {
        const text = e.results[0][0].transcript || "";
        onText(text);
        setResult("<div class='text-success'>Captured voice text.</div>");
      } catch (err) {
        setResult("<div class='text-danger'>Could not read voice text.</div>");
      }
    };
    rec.onend = () => {};
    rec.start();
  }

  async function runCommand(text) {
    const clean = String(text || "").trim();
    if (!clean) {
      setResult("<div class='text-danger'>Please enter a command.</div>");
      return;
    }
    setResult("<div class='text-muted'>Processing…</div>");
    try {
      const resp = await fetch("/api/voice/command/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken") || "",
        },
        body: JSON.stringify({ text: clean }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) {
        const msg = data.error || data.reply || "Failed";
        setResult(`<div class='text-danger'>${msg}</div>`);
        return;
      }
      const reply = data.reply || "Created";
      const link = data.redirect_url ? `<div class='mt-1'><a class='btn unified-btn-outline btn-sm' href='${data.redirect_url}'>Open Entry</a></div>` : "";
      setResult(`<div class='text-success'>${reply}</div>${link}`);
    } catch (err) {
      setResult("<div class='text-danger'>Network/Server error.</div>");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const startBtn = document.getElementById("voiceStartBtn");
    const runBtn = document.getElementById("voiceRunBtn");
    const textEl = document.getElementById("voiceText");

    if (startBtn) {
      startBtn.addEventListener("click", () => {
        if (!textEl) return;
        startMic((t) => {
          textEl.value = t;
        });
      });
      if (!speechSupported()) {
        startBtn.disabled = true;
        startBtn.title = "Speech recognition not supported";
      }
    }

    if (runBtn) {
      runBtn.addEventListener("click", () => runCommand(textEl ? textEl.value : ""));
    }
  });
})();
