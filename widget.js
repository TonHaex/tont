(function () {
  const config = window.TonGPTConfig || {};
  const apiUrl = config.apiUrl || "http://localhost:8000/chat";
  const title = config.title || "TonGPT";
  const intro = config.intro || "Stel een vraag over tonhaex.nl.";
  const maxSources = Number(config.maxSources || 3);

  const styles = document.createElement("style");
  styles.textContent = `
    .tongpt-button {
      position: fixed;
      right: 20px;
      bottom: 20px;
      z-index: 99998;
      border: 0;
      border-radius: 999px;
      padding: 12px 16px;
      background: #161616;
      color: #fff;
      font: 600 15px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      box-shadow: 0 10px 30px rgba(0, 0, 0, .22);
      cursor: pointer;
      transition: transform .16s ease, box-shadow .16s ease;
    }
    .tongpt-button:hover {
      transform: translateY(-1px);
      box-shadow: 0 14px 34px rgba(0, 0, 0, .24);
    }
    .tongpt-panel {
      position: fixed;
      right: 20px;
      bottom: 76px;
      z-index: 99999;
      width: min(380px, calc(100vw - 40px));
      height: min(560px, calc(100vh - 110px));
      display: none;
      flex-direction: column;
      overflow: hidden;
      border: 1px solid #dedede;
      border-radius: 8px;
      background: #fff;
      color: #1d1d1d;
      box-shadow: 0 18px 55px rgba(0, 0, 0, .24);
      font: 15px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .tongpt-panel[data-open="true"] { display: flex; }
    .tongpt-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
      border-bottom: 1px solid #ededed;
      font-weight: 700;
    }
    .tongpt-close {
      width: 32px;
      height: 32px;
      border: 0;
      border-radius: 999px;
      background: transparent;
      cursor: pointer;
      font-size: 22px;
      line-height: 1;
      color: #242424;
    }
    .tongpt-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px 14px;
      background: #fafafa;
    }
    .tongpt-message {
      width: fit-content;
      max-width: 88%;
      margin: 0 0 12px;
      padding: 11px 13px;
      border-radius: 8px;
      line-height: 1.45;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }
    .tongpt-message.bot {
      background: #fff;
      border: 1px solid #e8e8e8;
    }
    .tongpt-message.user {
      margin-left: auto;
      background: #161616;
      color: #fff;
    }
    .tongpt-sources {
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid #ececec;
      font-size: 13px;
      white-space: normal;
    }
    .tongpt-sources-title {
      margin-bottom: 6px;
      color: #666;
      font-weight: 700;
    }
    .tongpt-sources a {
      display: block;
      margin-top: 5px;
      color: #454545;
      text-decoration-thickness: 1px;
      text-underline-offset: 2px;
    }
    .tongpt-form {
      display: flex;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid #ededed;
      background: #fff;
    }
    .tongpt-input {
      flex: 1;
      min-width: 0;
      border: 1px solid #d6d6d6;
      border-radius: 8px;
      padding: 10px 11px;
      font: inherit;
    }
    .tongpt-input:focus {
      border-color: #8bb6ff;
      box-shadow: 0 0 0 3px rgba(139, 182, 255, .32);
      outline: 0;
    }
    .tongpt-submit {
      border: 0;
      border-radius: 8px;
      min-width: 92px;
      padding: 0 14px;
      background: #161616;
      color: #fff;
      font-weight: 700;
      cursor: pointer;
    }
    .tongpt-submit:disabled {
      opacity: .55;
      cursor: wait;
    }
    @media (max-width: 520px) {
      .tongpt-button {
        right: 14px;
        bottom: 14px;
      }
      .tongpt-panel {
        right: 10px;
        bottom: 66px;
        width: calc(100vw - 20px);
        height: min(620px, calc(100vh - 82px));
      }
      .tongpt-message {
        max-width: 94%;
      }
      .tongpt-form {
        gap: 7px;
        padding: 10px;
      }
      .tongpt-submit {
        min-width: 82px;
      }
    }
  `;

  const button = document.createElement("button");
  button.className = "tongpt-button";
  button.type = "button";
  button.textContent = title;

  const panel = document.createElement("section");
  panel.className = "tongpt-panel";
  panel.setAttribute("aria-label", title);
  panel.innerHTML = `
    <div class="tongpt-header">
      <span>${escapeHtml(title)}</span>
      <button class="tongpt-close" type="button" aria-label="Sluiten">&times;</button>
    </div>
    <div class="tongpt-messages"></div>
    <form class="tongpt-form">
      <input class="tongpt-input" name="question" type="text" maxlength="800" autocomplete="off" placeholder="Typ je vraag..." />
      <button class="tongpt-submit" type="submit">Stel vraag</button>
    </form>
  `;

  document.head.appendChild(styles);
  document.body.appendChild(button);
  document.body.appendChild(panel);

  const messages = panel.querySelector(".tongpt-messages");
  const form = panel.querySelector(".tongpt-form");
  const input = panel.querySelector(".tongpt-input");
  const submit = panel.querySelector(".tongpt-submit");

  button.addEventListener("click", () => {
    const nextOpen = panel.getAttribute("data-open") !== "true";
    panel.setAttribute("data-open", String(nextOpen));
    if (nextOpen) input.focus();
  });

  panel.querySelector(".tongpt-close").addEventListener("click", () => {
    panel.setAttribute("data-open", "false");
  });

  addMessage("bot", intro);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    input.value = "";
    addMessage("user", question);
    const loading = addMessage("bot", "Ik zoek in tonhaex.nl...");
    submit.disabled = true;
    submit.textContent = "Bezig";

    try {
      const data = await askTonGPT(question, loading);
      loading.remove();
      addMessage("bot", data.answer, data.sources || []);
    } catch (error) {
      console.error("TonGPT request failed", error);
      loading.remove();
      addMessage("bot", "Ik kan TonGPT nu even niet bereiken. Controleer of de server draait en probeer het opnieuw.");
    } finally {
      submit.disabled = false;
      submit.textContent = "Stel vraag";
      input.focus();
    }
  });

  async function askTonGPT(question, loadingMessage) {
    try {
      return await requestAnswer(question);
    } catch (firstError) {
      loadingMessage.textContent = "TonGPT wordt wakker. Ik probeer het nog een keer...";
      messages.scrollTop = messages.scrollHeight;
      await wait(6500);
      return requestAnswer(question);
    }
  }

  async function requestAnswer(question) {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question })
    });
    if (!response.ok) throw new Error(`Request failed with ${response.status}`);
    return response.json();
  }

  function wait(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function addMessage(kind, text, sources) {
    const item = document.createElement("div");
    item.className = `tongpt-message ${kind}`;
    item.textContent = text;

    const cleanSources = uniqueSources(sources || []).slice(0, maxSources);
    if (cleanSources.length) {
      const sourceList = document.createElement("div");
      sourceList.className = "tongpt-sources";
      const sourceTitle = document.createElement("div");
      sourceTitle.className = "tongpt-sources-title";
      sourceTitle.textContent = cleanSources.length === 1 ? "Bron" : "Bronnen";
      sourceList.appendChild(sourceTitle);

      cleanSources.forEach((source) => {
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = cleanTitle(source.title || source.url);
        sourceList.appendChild(link);
      });
      item.appendChild(sourceList);
    }

    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
    return item;
  }

  function uniqueSources(sources) {
    const seen = new Set();
    return sources.filter((source) => {
      if (!source || !source.url || seen.has(source.url)) return false;
      seen.add(source.url);
      return true;
    });
  }

  function cleanTitle(value) {
    return String(value)
      .replace(/^["']|["']$/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
