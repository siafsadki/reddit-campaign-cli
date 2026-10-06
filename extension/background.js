// Reddit Browser Extension - Background Service Worker
let ws = null;
let connectedTabId = null;
let isDebugging = false;
let debugTabId = null;
let consoleBuffer = [];
let consoleMaxEntries = 500;

// Recording state
let isRecording = false;
let recordingActions = [];
let recordingStartTime = 0;
let recordingTabId = null;
let recordingStartUrl = "";

function pushConsoleEntry(entry) {
  consoleBuffer.push(entry);
  const over = consoleBuffer.length - consoleMaxEntries;
  if (over > 0) {
    consoleBuffer.splice(0, over);
  }
}

function sendDebuggerCommand(tabId, method, params = {}) {
  return new Promise((resolve, reject) => {
    chrome.debugger.sendCommand({ tabId }, method, params, (result) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message));
      resolve(result);
    });
  });
}

// Capture console logs / exceptions while debugger is attached.
chrome.debugger.onEvent.addListener((source, method, params) => {
  if (!isDebugging || !debugTabId) return;
  if (!source || source.tabId !== debugTabId) return;

  try {
    if (method === "Runtime.consoleAPICalled") {
      const level = params?.type || "log";
      const args = Array.isArray(params?.args) ? params.args : [];
      const text = args
        .map((a) => {
          if (a && typeof a.value !== "undefined") return String(a.value);
          if (a && typeof a.description === "string") return a.description;
          if (a && typeof a.type === "string") return `[${a.type}]`;
          return "";
        })
        .filter(Boolean)
        .join(" ");
      pushConsoleEntry({ ts: Date.now(), level, text });
    } else if (method === "Runtime.exceptionThrown") {
      const details = params?.exceptionDetails || {};
      const text =
        details?.exception?.description ||
        details?.text ||
        "Uncaught exception";
      pushConsoleEntry({ ts: Date.now(), level: "exception", text: String(text) });
    } else if (method === "Log.entryAdded") {
      const entry = params?.entry || {};
      const level = entry?.level || "log";
      const text = entry?.text || entry?.url || "";
      if (text) pushConsoleEntry({ ts: Date.now(), level, text: String(text) });
    }
  } catch (e) {
    // Ignore console capture errors.
  }
});

chrome.debugger.onDetach.addListener((source, reason) => {
  if (!debugTabId) return;
  if (!source || source.tabId !== debugTabId) return;
  console.log("[reddit] Debugger detached:", reason);
  isDebugging = false;
  debugTabId = null;
});

// service walker active maintenance for alarm
chrome.alarms.create("keepAlive", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "keepAlive") {
    console.log("[reddit] Keep alive ping");
    // WebSocket connection check
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      connect();
    }
  }
});

// WebSocket to the server connection
function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  console.log("[reddit] Attempting WebSocket connection...");
  // Pin to IPv4 to avoid localhost IPv6 resolution issues.
  ws = new WebSocket("ws://127.0.0.1:9877");

  ws.onopen = () => {
    console.log("[reddit] WebSocket connected");
    chrome.action.setBadgeText({ text: "ON" });
    chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
  };

  ws.onclose = () => {
    console.log("[reddit] WebSocket connection disconnected");
    chrome.action.setBadgeText({ text: "" });
    ws = null;
    // 5candle after reconnect trial
    setTimeout(connect, 5000);
  };

  ws.onerror = (error) => {
    console.log("[reddit] WebSocket error:", error);
  };

  ws.onmessage = async (event) => {
    let msgId = null;
    try {
      const message = JSON.parse(event.data);
      msgId = message.id;
      console.log("[reddit] command reception:", message.command, message.params);
      const result = await handleCommand(message);
      console.log("[reddit] command complete:", message.command);
      ws.send(JSON.stringify({ id: msgId, result }));
    } catch (error) {
      console.error("[reddit] command treatment error:", error.message);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ id: msgId, error: error.message }));
      }
    }
  };
}

// command treatment
async function handleCommand(message) {
  const { command, params } = message;

  switch (command) {
    case "consoleStart":
      return await consoleStart(params?.maxEntries);

    case "consoleGet":
      return await consoleGet(params?.limit);

    case "consoleClear":
      return await consoleClear();

    case "consoleStop":
      return await consoleStop();

    case "getTabs":
      return await getTabs();

    case "selectTab":
      return await selectTab(params.tabId);

    case "navigate":
      return await navigate(params.url);

    case "screenshot":
      return await takeScreenshot();

    case "snapshot":
      return await getSnapshot();

    case "click":
      return await clickElement(params.selector);

    case "fill":
      return await fillElement(params.selector, params.value);

    case "press":
      return await pressKey(params.key);

    case "scroll":
      return await scroll(params.direction, params.amount);

    case "getText":
      return await getPageText();

    case "getHtml":
      return await getPageHtml(params?.maxChars);

    case "evaluate":
      return await evaluateScript(params.script);

    case "getLinks":
      return await getLinks(params?.pattern, params?.limit);

    case "getPageInfo":
      return await getPageInfo();

    case "redditComment":
      return await redditComment(params?.body);

    case "redditGetPosts":
      return await redditGetPosts(params?.limit);

    case "redditGetComments":
      return await redditGetComments(params?.limit);

    case "redditGetPostDetail":
      return await redditGetPostDetail();

    case "redditCheckLogin":
      return await redditCheckLogin();

    case "redditUpvote":
      return await redditUpvote(params?.selector);

    case "redditSearch":
      return await redditSearch(params?.query, params?.subreddit, params?.sort, params?.limit);

    case "redditReplyToComment":
      return await redditReplyToComment(params?.thingId, params?.body);

    case "redditGetUserInfo":
      return await redditGetUserInfo();

    case "redditNavigateSub":
      return await redditNavigateSub(params?.subreddit, params?.sort);

    case "getDomTree":
      return await getDomTree(params?.maxDepth, params?.maxNodes);

    case "clickByIndex":
      return await clickByIndex(params?.index);

    case "fillByIndex":
      return await fillByIndex(params?.index, params?.value);

    case "recordingStart":
      return await recordingStart();

    case "recordingStop":
      return await recordingStop();

    case "recordingStatus":
      return {
        isRecording,
        actionCount: recordingActions.length,
        duration: isRecording ? Date.now() - recordingStartTime : 0,
        tabId: recordingTabId,
      };

    case "clickCoords":
      return await clickCoords(params?.x, params?.y);

    case "typeText":
      return await typeText(params?.text);

    case "redditSubmitPost":
      return await redditSubmitPost(params?.subreddit, params?.title, params?.body, params?.autoSubmit);

    default:
      throw new Error(`Unknown command: ${command}`);
  }
}

// tab inventory import
async function getTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs.map((tab) => ({
    id: tab.id,
    title: tab.title,
    url: tab.url,
    active: tab.active,
  }));
}

// tab select
async function selectTab(tabId) {
  connectedTabId = tabId;
  await chrome.tabs.update(tabId, { active: true });
  return { success: true, tabId };
}

// page movement
async function navigate(url) {
  if (!connectedTabId) {
    // bird tab generation
    const tab = await chrome.tabs.create({ url });
    connectedTabId = tab.id;
  } else {
    await chrome.tabs.update(connectedTabId, { url });
  }

  // page load status
  await waitForPageLoad();

  const tab = await chrome.tabs.get(connectedTabId);
  return { success: true, url: tab.url, title: tab.title };
}

// page load status
function waitForPageLoad() {
  return new Promise((resolve) => {
    const listener = (tabId, info) => {
      if (tabId === connectedTabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 500); // addition atmosphere
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    // time out
    setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 30000);
  });
}

// screenshot
async function takeScreenshot() {
  await getActiveTabId();

  const dataUrl = await chrome.tabs.captureVisibleTab(null, {
    format: "png",
  });

  return { image: dataUrl };
}

// today active tab ID import (Reddit tab first of all)
async function getActiveTabId() {
  if (connectedTabId) {
    try {
      const tab = await chrome.tabs.get(connectedTabId);
      if (tab && tab.url && !tab.url.startsWith("chrome://") && !tab.url.startsWith("chrome-extension://")) {
        return connectedTabId;
      }
    } catch {}
  }

  // Reddit tab first of all search
  const allTabs = await chrome.tabs.query({});
  const redditTab = allTabs.find(t => t.url && t.url.includes("reddit.com") && t.active);
  if (redditTab) {
    connectedTabId = redditTab.id;
    return redditTab.id;
  }

  // active tab
  const activeTabs = await chrome.tabs.query({ active: true, currentWindow: true });
  for (const tab of activeTabs) {
    if (tab.url && !tab.url.startsWith("chrome://") && !tab.url.startsWith("chrome-extension://")) {
      connectedTabId = tab.id;
      return tab.id;
    }
  }

  // Reddit tab (Even if it's inactive)
  const anyReddit = allTabs.find(t => t.url && t.url.includes("reddit.com"));
  if (anyReddit) {
    connectedTabId = anyReddit.id;
    return anyReddit.id;
  }

  // any access possible tab
  for (const tab of allTabs) {
    if (tab.url && !tab.url.startsWith("chrome://") && !tab.url.startsWith("chrome-extension://")) {
      connectedTabId = tab.id;
      return tab.id;
    }
  }

  throw new Error("No accessible tab found");
}

// page snapshot (element information)
async function getSnapshot() {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const elements = [];
      const interactiveSelectors = [
        "a",
        "button",
        "input",
        "select",
        "textarea",
        '[role="button"]',
        '[role="link"]',
        '[role="textbox"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[onclick]',
        '[tabindex]',
      ];

      // Shadow DOM penetration collection
      function collectAll(selectors, root = document) {
        const results = [...root.querySelectorAll(selectors)];
        function traverse(node) {
          if (node.shadowRoot) {
            results.push(...node.shadowRoot.querySelectorAll(selectors));
            for (const c of node.shadowRoot.children) traverse(c);
          }
          if (node.children) for (const c of node.children) traverse(c);
        }
        // main web componentonly circuit (performance)
        root.querySelectorAll("shreddit-post, shreddit-comment, shreddit-composer, faceplate-form, faceplate-textarea-input, shreddit-comment-tree").forEach(traverse);
        return results;
      }

      collectAll(interactiveSelectors.join(",")).forEach((el, index) => {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        if (rect.top > window.innerHeight || rect.bottom < 0) return;

        const text =
          el.innerText?.trim().slice(0, 100) ||
          el.value ||
          el.placeholder ||
          el.getAttribute("aria-label") ||
          el.title ||
          "";

        elements.push({
          ref: `ref_${index}`,
          tag: el.tagName.toLowerCase(),
          type: el.type || null,
          text: text,
          role: el.getAttribute("role"),
          selector: generateSelector(el),
          rect: {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          },
        });
      });

      function generateSelector(el) {
        if (el.id) return `#${el.id}`;
        if (el.name) return `[name="${el.name}"]`;

        let path = el.tagName.toLowerCase();
        if (el.className && typeof el.className === "string") {
          const classes = el.className.trim().split(/\s+/).slice(0, 2).join(".");
          if (classes) path += `.${classes}`;
        }
        return path;
      }

      return elements;
    },
  });

  return { elements: results[0]?.result || [] };
}

// element click (page-agent method — Shadow DOM penetration + complete event sequence)
async function clickElement(selector) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (sel) => {
      // Shadow DOM penetration querySelector
      function findDeep(s) {
        let r = document.querySelector(s);
        if (r) return r;
        function traverse(node) {
          if (r) return;
          if (node.shadowRoot) {
            r = node.shadowRoot.querySelector(s);
            if (r) return;
            for (const c of node.shadowRoot.children) traverse(c);
          }
          if (node.children) for (const c of node.children) traverse(c);
        }
        traverse(document.documentElement);
        return r;
      }

      const el = findDeep(sel);
      if (!el) throw new Error(`Element not found: ${sel}`);

      // in the viewport Make it visible scroll
      el.scrollIntoView({ behavior: "instant", block: "center" });

      const rect = el.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const evtInit = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y };

      // page-agent event sequence (mouseenter→mouseover→mousedown→focus→mouseup→click)
      el.dispatchEvent(new MouseEvent("mouseenter", evtInit));
      el.dispatchEvent(new MouseEvent("mouseover", evtInit));
      el.dispatchEvent(new MouseEvent("mousedown", { ...evtInit, button: 0 }));
      el.focus();
      el.dispatchEvent(new MouseEvent("mouseup", { ...evtInit, button: 0 }));
      el.dispatchEvent(new MouseEvent("click", { ...evtInit, button: 0 }));

      return { success: true, tag: el.tagName, shadow: !!el.getRootNode()?.host };
    },
    args: [selector],
  });

  return results[0]?.result;
}

// to the element input (page-agent method — React/contenteditable/native input compatible)
async function fillElement(selector, value) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (sel, val) => {
      // Shadow DOM penetration search
      function findDeep(s) {
        let r = document.querySelector(s);
        if (r) return r;
        function traverse(node) {
          if (r) return;
          if (node.shadowRoot) {
            r = node.shadowRoot.querySelector(s);
            if (r) return;
            for (const c of node.shadowRoot.children) traverse(c);
          }
          if (node.children) for (const c of node.children) traverse(c);
        }
        traverse(document.documentElement);
        return r;
      }

      let el = findDeep(sel);
      if (!el) el = findDeep('[contenteditable="true"]');
      if (!el) el = findDeep('[role="textbox"]');
      if (!el) throw new Error(`Element not found: ${sel}`);

      el.focus();

      const tag = el.tagName.toLowerCase();
      const isContentEditable = el.getAttribute("contenteditable") === "true" || el.isContentEditable;

      if (isContentEditable) {
        // page-agent contentEditable input: beforeinput(delete)→clear→input→beforeinput(insert)→set→input→change
        if (el.dispatchEvent(new InputEvent("beforeinput", {
          bubbles: true, cancelable: true, inputType: "deleteContent"
        }))) {
          el.innerText = "";
          el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContent" }));
        }
        if (el.dispatchEvent(new InputEvent("beforeinput", {
          bubbles: true, cancelable: true, inputType: "insertText", data: val
        }))) {
          el.innerText = val;
          el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: val }));
        }
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } else if (tag === "input" || tag === "textarea") {
        // React native value setter
        const proto = tag === "textarea" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const nativeSetter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
        if (nativeSetter) nativeSetter.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        document.execCommand("selectAll", false, null);
        document.execCommand("delete", false, null);
        document.execCommand("insertText", false, val);
      }

      return { success: true, tag };
    },
    args: [selector, value],
  });

  return results[0]?.result;
}

// key input
async function pressKey(key) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (k) => {
      const keyMap = {
        Enter: { key: "Enter", code: "Enter", keyCode: 13 },
        Tab: { key: "Tab", code: "Tab", keyCode: 9 },
        Escape: { key: "Escape", code: "Escape", keyCode: 27 },
        ArrowUp: { key: "ArrowUp", code: "ArrowUp", keyCode: 38 },
        ArrowDown: { key: "ArrowDown", code: "ArrowDown", keyCode: 40 },
        Backspace: { key: "Backspace", code: "Backspace", keyCode: 8 },
      };

      const keyInfo = keyMap[k] || { key: k, code: k, keyCode: k.charCodeAt(0) };
      const event = new KeyboardEvent("keydown", {
        key: keyInfo.key,
        code: keyInfo.code,
        keyCode: keyInfo.keyCode,
        bubbles: true,
      });

      document.activeElement?.dispatchEvent(event);
      return { success: true };
    },
    args: [key],
  });

  return results[0]?.result;
}

// scroll
async function scroll(direction, amount = 500) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (dir, amt) => {
      const scrollMap = {
        up: [0, -amt],
        down: [0, amt],
        left: [-amt, 0],
        right: [amt, 0],
      };
      const [x, y] = scrollMap[dir] || [0, amt];
      window.scrollBy(x, y);
      return { success: true, scrollY: window.scrollY };
    },
    args: [direction, amount],
  });

  return results[0]?.result;
}

// page text import
async function getPageText() {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      return document.body.innerText;
    },
  });

  return { text: results[0]?.result || "" };
}

// page HTML import
async function getPageHtml(maxChars = 200000) {
  const tabId = await getActiveTabId();
  const limit = Math.max(1000, Math.min(Number(maxChars) || 200000, 2000000));

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (maxLen) => {
      const html = document.documentElement?.outerHTML || "";
      return html.length > maxLen ? html.slice(0, maxLen) : html;
    },
    args: [limit],
  });

  return { html: results[0]?.result || "" };
}

// page link collection (eval otiosity)
async function getLinks(pattern, limit = 20) {
  const tabId = await getActiveTabId();
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (pat, lim) => {
      const links = [];
      const seen = new Set();
      document.querySelectorAll("a[href]").forEach((a) => {
        const href = a.href;
        if (!href || seen.has(href)) return;
        if (pat && !href.includes(pat)) return;
        seen.add(href);
        links.push({
          url: href,
          text: (a.textContent || "").trim().substring(0, 120),
        });
      });
      return links.slice(0, lim);
    },
    args: [pattern || null, limit || 20],
  });
  return { links: results[0]?.result || [] };
}

// page basic information (eval otiosity)
async function getPageInfo() {
  const tabId = await getActiveTabId();
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      return {
        title: document.title,
        url: window.location.href,
        domain: window.location.hostname,
      };
    },
  });
  return results[0]?.result || {};
}

// ═══ Reddit exclusive command (page-agent method — Shadow DOM penetration) ═══

// Reddit Write a comment — page-agent method Shadow DOM perfection penetration
async function redditComment(body) {
  const tabId = await getActiveTabId();
  const log = [];

  try {
    await ensureDebugger(tabId);
  } catch (e) {
    log.push('debugger attach failed: ' + e.message);
  }

  // Step 1: trigger coordinate Find (executeScript)
  const step1 = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const ct = document.querySelector('shreddit-comment-tree') || document.querySelector('#comment-tree');
      if (ct) ct.scrollIntoView({ behavior: 'instant', block: 'center' });
      else window.scrollBy(0, 500);

      const trigger = document.querySelector('faceplate-textarea-input');
      if (trigger) {
        trigger.scrollIntoView({ behavior: 'instant', block: 'center' });
        let rect = trigger.getBoundingClientRect();
        // display:contentsperson case shadow root in git coordinate import
        if (rect.width === 0 && trigger.shadowRoot) {
          const inner = trigger.shadowRoot.querySelector('div, span, textarea, input');
          if (inner) rect = inner.getBoundingClientRect();
        }
        // still 0This side Rangeas trial
        if (rect.width === 0) {
          const range = document.createRange();
          range.selectNodeContents(trigger);
          rect = range.getBoundingClientRect();
        }
        return { found: true, x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), w: Math.round(rect.width), h: Math.round(rect.height) };
      }
      return { found: false };
    },
  });

  const triggerInfo = step1[0]?.result || {};
  log.push('trigger: ' + JSON.stringify(triggerInfo));

  if (!triggerInfo.found) {
    return { success: false, error: 'trigger undiscovered', log };
  }

  // Step 2: CDP with a click editor opening
  try {
    await sendDebuggerCommand(tabId, 'Input.dispatchMouseEvent', {
      type: 'mousePressed', x: triggerInfo.x, y: triggerInfo.y, button: 'left', clickCount: 1,
    });
    await sendDebuggerCommand(tabId, 'Input.dispatchMouseEvent', {
      type: 'mouseReleased', x: triggerInfo.x, y: triggerInfo.y, button: 'left', clickCount: 1,
    });
    log.push('CDP click trigger OK');
  } catch (e) {
    log.push('CDP click failed: ' + e.message);
    await chrome.scripting.executeScript({
      target: { tabId },
      func: () => { const t = document.querySelector('faceplate-textarea-input'); if (t) { t.click(); t.focus(); } },
    });
  }

  await new Promise(r => setTimeout(r, 2500));

  // Step 3: In the editor text input (executeScript + execCommand)
  const step3 = await chrome.scripting.executeScript({
    target: { tabId },
    func: (commentBody) => {
      const log = [];
      let editor = null;
      const composers = document.querySelectorAll('shreddit-composer');
      for (const comp of composers) {
        editor = comp.querySelector('div[data-lexical-editor="true"]')
          || comp.querySelector('div[contenteditable="true"][role="textbox"]')
          || comp.querySelector('div[contenteditable="true"]');
        if (editor) { log.push('editor in composer'); break; }
      }
      if (!editor) {
        const forms = document.querySelectorAll('faceplate-form');
        for (const form of forms) {
          if ((form.getAttribute('action') || '').includes('comment')) {
            editor = form.querySelector('div[data-lexical-editor="true"]') || form.querySelector('div[contenteditable="true"]');
            if (editor) { log.push('editor in faceplate-form'); break; }
          }
        }
      }
      if (!editor) {
        const allCE = document.querySelectorAll('[contenteditable="true"]');
        for (const ce of allCE) {
          const r = ce.getBoundingClientRect();
          if (r.width > 50 && r.height > 10) { editor = ce; log.push('editor via scan ' + r.width + 'x' + r.height); break; }
        }
      }
      if (!editor) { log.push('NO EDITOR'); return { ok: false, log }; }

      let rect = editor.getBoundingClientRect();
      // display:contents correction — parents composerat actual rendered coordinate
      if (rect.width === 0) {
        const comp = editor.closest('shreddit-composer');
        if (comp && comp.shadowRoot) {
          const slot = comp.shadowRoot.querySelector('slot[name="rte"]');
          if (slot) {
            const assigned = slot.assignedElements();
            if (assigned.length > 0) rect = assigned[0].getBoundingClientRect();
          }
          if (rect.width === 0) {
            const inner = comp.shadowRoot.querySelector('div, reddit-rte');
            if (inner) rect = inner.getBoundingClientRect();
          }
        }
      }
      log.push('editor: ' + Math.round(rect.width) + 'x' + Math.round(rect.height));

      // The editor I can't see it If not CDP click necessary — coordinate return
      if (rect.width === 0) {
        log.push('editor still 0x0 — returning for CDP click');
        return { ok: false, needCdpClick: true, log };
      }

      // focus + execCommand (Lexical compatible)
      editor.focus();
      const sel = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(editor);
      sel.removeAllRanges();
      sel.addRange(range);
      document.execCommand('delete', false, null);
      const ok = document.execCommand('insertText', false, commentBody);
      log.push('insertText: ' + ok);
      const editorText = (editor.innerText || '').trim();
      log.push('text: ' + editorText.slice(0, 50));

      // Submit button coordinate Find
      let btnRect = null;
      let btnText = '';
      const form = editor.closest('faceplate-form') || editor.closest('shreddit-composer');
      if (form) {
        const btn = form.querySelector('button[type="submit"]');
        if (btn && !btn.disabled) {
          const r = btn.getBoundingClientRect();
          btnRect = { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
          btnText = btn.textContent.trim();
        }
      }
      if (!btnRect) {
        const allBtns = document.querySelectorAll('button');
        for (const b of allBtns) {
          const t = (b.textContent || '').trim().toLowerCase();
          if (t === 'comment' && !b.disabled) {
            const r = b.getBoundingClientRect();
            if (r.width > 20) {
              btnRect = { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
              btnText = b.textContent.trim();
              break;
            }
          }
        }
      }
      log.push('btn: ' + btnText + ' ' + JSON.stringify(btnRect));
      return { ok: true, editorText: editorText.slice(0, 60), btnRect, btnText, log };
    },
    args: [body],
  });

  let inputInfo = step3[0]?.result || {};
  log.push(...(inputInfo.log || []));

  // The editor 0x0 — actual click possible area looking for CDP typing
  if (!inputInfo.ok && inputInfo.needCdpClick) {
    log.push('fallback: find clickable editor area');

    // Step 3.5: editor of the realm actual coordinate Find (parents/sibling/slotat)
    const step3a = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // method1: shreddit-composer in visible element Find
        const composers = document.querySelectorAll('shreddit-composer');
        for (const comp of composers) {
          // Shadow DOM in editor container
          if (comp.shadowRoot) {
            const rte = comp.shadowRoot.querySelector('reddit-rte, .editor-container, [slot], div');
            if (rte) {
              const r = rte.getBoundingClientRect();
              if (r.width > 50 && r.height > 20) return { x: Math.round(r.x + 20), y: Math.round(r.y + 20), src: 'shadow-rte' };
            }
          }
          // directly child middle visible thing
          const children = comp.querySelectorAll('*');
          for (const child of children) {
            const r = child.getBoundingClientRect();
            if (r.width > 50 && r.height > 20 && r.y > 0) {
              return { x: Math.round(r.x + 20), y: Math.round(r.y + 20), src: 'composer-child:' + child.tagName };
            }
          }
          // composer self
          const cr = comp.getBoundingClientRect();
          if (cr.width > 50) return { x: Math.round(cr.x + 20), y: Math.round(cr.y + 50), src: 'composer-self' };
        }
        // method2: p[data-lexical-text] around
        const lp = document.querySelector('p[data-lexical-text]');
        if (lp) {
          const r = lp.getBoundingClientRect();
          if (r.width > 0) return { x: Math.round(r.x + 10), y: Math.round(r.y + 5), src: 'lexical-p' };
        }
        // method3: submit button topside (The editor commonly button as soon as stomach)
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
          if ((b.textContent || '').trim().toLowerCase() === 'comment') {
            const r = b.getBoundingClientRect();
            if (r.y > 100) return { x: Math.round(r.x), y: Math.round(r.y - 80), src: 'above-btn' };
          }
        }
        return null;
      },
    });
    const editorCoords = step3a[0]?.result;
    log.push('editor coords: ' + JSON.stringify(editorCoords));

    try {
      // editor area CDP with a click focus
      if (editorCoords) {
        await sendDebuggerCommand(tabId, 'Input.dispatchMouseEvent', {
          type: 'mousePressed', x: editorCoords.x, y: editorCoords.y, button: 'left', clickCount: 1,
        });
        await sendDebuggerCommand(tabId, 'Input.dispatchMouseEvent', {
          type: 'mouseReleased', x: editorCoords.x, y: editorCoords.y, button: 'left', clickCount: 1,
        });
        await new Promise(r => setTimeout(r, 500));
        log.push('CDP click editor at ' + editorCoords.src);
      }

      // Ctrl+Aas existing detail select after delete
      await sendDebuggerCommand(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: 'a', code: 'KeyA', modifiers: 2 });
      await sendDebuggerCommand(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: 'a', code: 'KeyA' });
      await sendDebuggerCommand(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: 'Backspace', code: 'Backspace' });
      await sendDebuggerCommand(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: 'Backspace', code: 'Backspace' });
      await new Promise(r => setTimeout(r, 300));

      // text input (random With delay like a person)
      for (const char of body) {
        await sendDebuggerCommand(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', text: char, key: char, code: '' });
        await sendDebuggerCommand(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: char, code: '' });
        await new Promise(r => setTimeout(r, 20 + Math.random() * 50));
      }
      log.push('CDP typeText done (' + body.length + ' chars)');
    } catch (e) {
      log.push('CDP typeText failed: ' + e.message);
      // fill fallback — input Events too causes
      await chrome.scripting.executeScript({
        target: { tabId },
        func: (text) => {
          const editors = document.querySelectorAll('shreddit-composer');
          for (const comp of editors) {
            const ed = comp.querySelector('div[contenteditable="true"]');
            if (ed) {
              ed.focus();
              ed.innerText = text;
              ed.dispatchEvent(new Event('input', {bubbles: true}));
              ed.dispatchEvent(new Event('change', {bubbles: true}));
              return;
            }
          }
        },
        args: [body],
      });
      log.push('fill fallback done');
    }

    await new Promise(r => setTimeout(r, 1000));

    // button coordinate again Find
    const step3b = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // editor text check
        const composers = document.querySelectorAll('shreddit-composer');
        let editorText = '';
        for (const comp of composers) {
          const ed = comp.querySelector('div[contenteditable="true"]');
          if (ed) { editorText = (ed.innerText || '').trim(); break; }
        }
        // button Find
        let btnRect = null, btnText = '';
        const allBtns = document.querySelectorAll('button');
        for (const b of allBtns) {
          const t = (b.textContent || '').trim().toLowerCase();
          if (t === 'comment' && !b.disabled) {
            const r = b.getBoundingClientRect();
            if (r.width > 20) {
              btnRect = { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), w: r.width };
              btnText = b.textContent.trim();
              break;
            }
          }
        }
        // Button too 0x0This side JS click trial
        if (!btnRect) {
          for (const b of allBtns) {
            const t = (b.textContent || '').trim().toLowerCase();
            if (t === 'comment' && !b.disabled) { b.click(); btnText = 'JS-clicked'; break; }
          }
        }
        return { editorText: editorText.slice(0, 60), btnRect, btnText };
      },
    });
    inputInfo = step3b[0]?.result || {};
    inputInfo.ok = true;
    log.push('editorText: ' + (inputInfo.editorText || ''));
    log.push('btn: ' + inputInfo.btnText + ' ' + JSON.stringify(inputInfo.btnRect));

    if (inputInfo.btnText === 'JS-clicked') {
      // already JSas Clicked
      log.push('submit via JS click');
      await new Promise(r => setTimeout(r, 3000));
      const step5 = await chrome.scripting.executeScript({
        target: { tabId },
        func: (snippet) => (document.body.innerText || '').includes(snippet),
        args: [body.slice(0, 40)],
      });
      const verified = step5[0]?.result || false;
      log.push('verified=' + verified);
      return { success: true, verified, log, message: verified ? 'comment confirmed' : 'unconfirmed' };
    }
  }

  if (!inputInfo.ok) return { success: false, error: "editor doesn't exist", log };
  if (!inputInfo.editorText || inputInfo.editorText.length < 5) log.push('WARNING: editor text empty');
  if (!inputInfo.btnRect) return { success: false, error: "submit button doesn't exist", bodyEntered: true, log };

  // Step 4: CDP with a click submit
  await new Promise(r => setTimeout(r, 500));
  try {
    await sendDebuggerCommand(tabId, 'Input.dispatchMouseEvent', {
      type: 'mousePressed', x: inputInfo.btnRect.x, y: inputInfo.btnRect.y, button: 'left', clickCount: 1,
    });
    await sendDebuggerCommand(tabId, 'Input.dispatchMouseEvent', {
      type: 'mouseReleased', x: inputInfo.btnRect.x, y: inputInfo.btnRect.y, button: 'left', clickCount: 1,
    });
    log.push('CDP click submit OK: ' + inputInfo.btnText);
  } catch (e) {
    log.push('CDP submit failed: ' + e.message);
    await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const allBtns = document.querySelectorAll('button');
        for (const b of allBtns) {
          if ((b.textContent || '').trim().toLowerCase() === 'comment' && !b.disabled) { b.click(); break; }
        }
      },
    });
  }

  // Step 5: verification
  await new Promise(r => setTimeout(r, 3000));
  const step5 = await chrome.scripting.executeScript({
    target: { tabId },
    func: (snippet) => (document.body.innerText || '').includes(snippet),
    args: [body.slice(0, 40)],
  });

  const verified = step5[0]?.result || false;
  log.push('verified=' + verified);
  return { success: true, verified, log, message: verified ? 'comment confirmed' : 'unconfirmed' };
}


// Reddit post inventory collection (subreddit on the page)
async function redditGetPosts(limit = 10) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (lim) => {
      const posts = [];
      // shreddit-post element
      const postEls = document.querySelectorAll("shreddit-post");
      for (const el of postEls) {
        const title = el.getAttribute("post-title") || "";
        const permalink = el.getAttribute("permalink") || "";
        const author = el.getAttribute("author") || "";
        const score = parseInt(el.getAttribute("score")) || 0;
        const commentCount = parseInt(el.getAttribute("comment-count")) || 0;
        const createdAt = el.getAttribute("created-timestamp") || "";

        if (title) {
          posts.push({
            title,
            permalink,
            url: permalink ? "https://www.reddit.com" + permalink : "",
            author,
            score,
            commentCount,
            createdAt,
          });
        }
        if (posts.length >= lim) break;
      }

      // shreddit-postgo If there is no link based fallback
      if (posts.length === 0) {
        const links = document.querySelectorAll('a[href*="/comments/"]');
        const seen = new Set();
        for (const a of links) {
          const href = a.href;
          if (href && href.includes("/comments/") && !seen.has(href)) {
            seen.add(href);
            posts.push({
              title: (a.textContent || "").trim().substring(0, 120),
              url: href,
              permalink: new URL(href).pathname,
              author: "",
              score: 0,
              commentCount: 0,
            });
            if (posts.length >= lim) break;
          }
        }
      }
      return posts;
    },
    args: [limit || 10],
  });

  return { posts: results[0]?.result || [] };
}

// Reddit post particular information (post on the page)
async function redditGetPostDetail() {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const post = document.querySelector("shreddit-post");
      const title = post?.getAttribute("post-title") || document.title;
      const author = post?.getAttribute("author") || "";
      const score = parseInt(post?.getAttribute("score")) || 0;
      const commentCount = parseInt(post?.getAttribute("comment-count")) || 0;
      const subreddit = post?.getAttribute("subreddit-prefixed-name") || "";
      const createdAt = post?.getAttribute("created-timestamp") || "";

      // text extraction
      const bodyEl = document.querySelector('[slot="text-body"]')
        || document.querySelector(".text-neutral-content");
      const body = bodyEl ? bodyEl.textContent.trim() : "";

      return {
        title, author, score, commentCount, subreddit, createdAt, body,
        url: window.location.href,
      };
    },
  });

  return results[0]?.result || {};
}

// Reddit comment inventory collection (post on the page)
async function redditGetComments(limit = 30) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (lim) => {
      const comments = [];
      const commentEls = document.querySelectorAll("shreddit-comment");
      for (const el of commentEls) {
        const author = el.getAttribute("author") || "unknown";
        const score = parseInt(el.getAttribute("score")) || 0;
        const depth = parseInt(el.getAttribute("depth")) || 0;
        const thingId = el.getAttribute("thingid") || "";

        // comment text
        const bodyEl = el.querySelector('[slot="comment"]')
          || el.querySelector(".md");
        const body = bodyEl ? bodyEl.textContent.trim().substring(0, 500) : "";

        if (body) {
          comments.push({ author, body, score, depth, thingId });
        }
        if (comments.length >= lim) break;
      }
      return comments;
    },
    args: [limit || 30],
  });

  return { comments: results[0]?.result || [] };
}

// Reddit login status check
async function redditCheckLogin() {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      // several with selector log in detect (Reddit UI change react)
      const expandBtn = document.querySelector("#expand-user-drawer-button");
      const userMenu = document.querySelector('[id*="user-drawer"]')
        || document.querySelector('button[aria-label*="profile"]')
        || document.querySelector('button[aria-label*="User"]')
        || document.querySelector('faceplate-dropdown-menu-button')
        || document.querySelector('[data-testid="user-menu-toggle"]');
      const loginBtn = document.querySelector('a[href*="login"]');
      const loginBtnAlt = document.querySelector('button[data-testid="login-button"]')
        || document.querySelector('a[data-testid="login-button"]');

      // log in the button There is no, posthumous work the menu If there is logged in thing
      const hasUserElement = !!(expandBtn || userMenu);
      const hasLoginBtn = !!(loginBtn || loginBtnAlt);
      const loggedIn = hasUserElement || !hasLoginBtn;

      // attempt to extract username
      let username = expandBtn?.textContent?.trim() || "";
      if (!username && userMenu) {
        username = userMenu.textContent?.trim() || "";
      }

      return {
        loggedIn,
        username: username || null,
      };
    },
  });

  return results[0]?.result || { loggedIn: false };
}

// ═══ page-agent style DOM tree extraction ═══
async function getDomTree(maxDepth = 5, maxNodes = 200) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (mDepth, mNodes) => {
      let nodeCount = 0;
      const interactiveTags = new Set([
        "A", "BUTTON", "INPUT", "SELECT", "TEXTAREA",
        "SHREDDIT-POST", "SHREDDIT-COMMENT", "FACEPLATE-TEXTAREA-INPUT",
      ]);
      const interactiveRoles = new Set([
        "button", "link", "textbox", "checkbox", "radio", "menuitem", "tab",
      ]);

      // Global index mapping save (clickByIndex/fillByIndexat use)
      window.__redditDomMap = [];

      function traverse(el, depth) {
        if (nodeCount >= mNodes || depth > mDepth) return null;
        if (!el || el.nodeType !== 1) return null;

        const tag = el.tagName;
        const style = getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return null;

        const isInteractive = interactiveTags.has(tag)
          || interactiveRoles.has(el.getAttribute("role"))
          || el.getAttribute("contenteditable") === "true"
          || el.hasAttribute("onclick")
          || el.hasAttribute("tabindex");

        const rect = el.getBoundingClientRect();
        const visible = rect.width > 0 && rect.height > 0;

        let node = null;

        if (isInteractive && visible) {
          const idx = window.__redditDomMap.length;
          window.__redditDomMap.push(el);
          nodeCount++;

          const text = (el.innerText || el.value || el.placeholder ||
            el.getAttribute("aria-label") || el.getAttribute("post-title") || "").trim().slice(0, 80);

          node = {
            idx, tag: tag.toLowerCase(),
            role: el.getAttribute("role"),
            type: el.type || null,
            text,
            href: el.href || null,
            rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
          };

          // shreddit-post addition attribute
          if (tag === "SHREDDIT-POST") {
            node.postTitle = el.getAttribute("post-title");
            node.author = el.getAttribute("author");
            node.score = el.getAttribute("score");
            node.permalink = el.getAttribute("permalink");
          }
          // shreddit-comment addition attribute
          if (tag === "SHREDDIT-COMMENT") {
            node.author = el.getAttribute("author");
            node.score = el.getAttribute("score");
            node.depth = el.getAttribute("depth");
            node.thingId = el.getAttribute("thingid");
          }
        }

        // child circuit
        const children = [];
        for (const child of el.children) {
          const c = traverse(child, depth + 1);
          if (c) children.push(c);
        }

        if (node) {
          if (children.length) node.children = children;
          return node;
        }
        if (children.length === 1) return children[0];
        if (children.length > 1) return { tag: tag.toLowerCase(), children };
        return null;
      }

      const tree = traverse(document.body, 0);
      return { tree, totalNodes: nodeCount, url: location.href };
    },
    args: [maxDepth || 5, maxNodes || 200],
  });

  return results[0]?.result || {};
}

// page-agent style index based click
async function clickByIndex(index) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (idx) => {
      if (!window.__redditDomMap || !window.__redditDomMap[idx]) {
        throw new Error(`Index ${idx} not found — call getDomTree first`);
      }
      const el = window.__redditDomMap[idx];
      el.scrollIntoView({ behavior: "instant", block: "center" });
      const rect = el.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const evtInit = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y };
      el.dispatchEvent(new PointerEvent("pointerenter", evtInit));
      el.dispatchEvent(new MouseEvent("mouseenter", evtInit));
      el.dispatchEvent(new PointerEvent("pointerover", evtInit));
      el.dispatchEvent(new MouseEvent("mouseover", evtInit));
      el.dispatchEvent(new PointerEvent("pointerdown", { ...evtInit, button: 0 }));
      el.dispatchEvent(new MouseEvent("mousedown", { ...evtInit, button: 0 }));
      el.focus();
      el.dispatchEvent(new PointerEvent("pointerup", { ...evtInit, button: 0 }));
      el.dispatchEvent(new MouseEvent("mouseup", { ...evtInit, button: 0 }));
      el.dispatchEvent(new MouseEvent("click", { ...evtInit, button: 0 }));
      return { success: true, tag: el.tagName.toLowerCase(), text: (el.innerText || "").slice(0, 50) };
    },
    args: [index],
  });

  return results[0]?.result;
}

// page-agent style index based input
async function fillByIndex(index, value) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (idx, val) => {
      if (!window.__redditDomMap || !window.__redditDomMap[idx]) {
        throw new Error(`Index ${idx} not found — call getDomTree first`);
      }
      const el = window.__redditDomMap[idx];
      el.focus();
      const tag = el.tagName.toLowerCase();
      const isContentEditable = el.getAttribute("contenteditable") === "true" || el.isContentEditable;

      if (isContentEditable) {
        el.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, cancelable: true, inputType: "insertText", data: val }));
        el.innerText = val;
        el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: val }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } else if (tag === "input" || tag === "textarea") {
        const proto = tag === "textarea" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const nativeSetter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
        if (nativeSetter) nativeSetter.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        document.execCommand("selectAll", false, null);
        document.execCommand("delete", false, null);
        document.execCommand("insertText", false, val);
      }
      return { success: true, tag, text: val.slice(0, 50) };
    },
    args: [index, value],
  });

  return results[0]?.result;
}

// ═══ Reddit addition exclusive command ═══

// Reddit Upvote (post or comment)
async function redditUpvote(selector) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (sel) => {
      // selector designation city corresponding element within, or not page first post
      const container = sel ? document.querySelector(sel) : document.querySelector("shreddit-post");
      if (!container) return { success: false, error: "Target doesn't exist" };

      const upBtn = container.querySelector('button[upvote]')
        || container.querySelector('button[aria-label*="upvote"]')
        || container.querySelector('button[aria-label*="Upvote"]');

      if (!upBtn) return { success: false, error: "Upvote button doesn't exist" };

      // already Is it pressed? check
      const pressed = upBtn.getAttribute("aria-pressed") === "true";
      if (pressed) return { success: true, alreadyUpvoted: true };

      const rect = upBtn.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const evtInit = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y };
      upBtn.dispatchEvent(new PointerEvent("pointerdown", { ...evtInit, button: 0 }));
      upBtn.dispatchEvent(new MouseEvent("mousedown", { ...evtInit, button: 0 }));
      upBtn.dispatchEvent(new PointerEvent("pointerup", { ...evtInit, button: 0 }));
      upBtn.dispatchEvent(new MouseEvent("mouseup", { ...evtInit, button: 0 }));
      upBtn.dispatchEvent(new MouseEvent("click", { ...evtInit, button: 0 }));

      return { success: true };
    },
    args: [selector || null],
  });

  return results[0]?.result || { success: false };
}

// Reddit search (subreddit my or entire)
async function redditSearch(query, subreddit, sort = "relevance", limit = 10) {
  const tabId = await getActiveTabId();

  const searchUrl = subreddit
    ? `https://www.reddit.com/r/${subreddit}/search/?q=${encodeURIComponent(query)}&restrict_sr=1&sort=${sort}`
    : `https://www.reddit.com/search/?q=${encodeURIComponent(query)}&sort=${sort}`;

  await chrome.tabs.update(tabId, { url: searchUrl });
  await waitForPageLoad();
  await new Promise(r => setTimeout(r, 2000));

  return await redditGetPosts(limit);
}

// Reddit post write (CDP + JS hybrid)
async function redditSubmitPost(subreddit, title, body, autoSubmit = false) {
  const tabId = await getActiveTabId();
  const log = [];

  // Step 1: post write to page movement
  const submitUrl = `https://www.reddit.com/r/${subreddit}/submit?type=TEXT`;
  log.push(`Navigating to ${submitUrl}`);
  await chrome.tabs.update(tabId, { url: submitUrl });
  await waitForPageLoad();
  await new Promise(r => setTimeout(r, 3000));

  // Step 2: title input (CDP typeText use)
  log.push("Entering title...");
  try {
    await ensureDebugger(tabId);

    // title field Find + click
    const titleResult = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const titleInput = document.querySelector('textarea[name="title"]')
          || document.querySelector('div[data-testid="post-title"] textarea')
          || document.querySelector('input[name="title"]');
        if (titleInput) {
          titleInput.focus();
          titleInput.click();
          const rect = titleInput.getBoundingClientRect();
          return { found: true, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }
        return { found: false };
      },
    });

    const titleInfo = titleResult[0]?.result;
    if (titleInfo?.found) {
      await sendDebuggerCommand(tabId, "Input.dispatchMouseEvent", {
        type: "mousePressed", x: titleInfo.x, y: titleInfo.y, button: "left", clickCount: 1,
      });
      await sendDebuggerCommand(tabId, "Input.dispatchMouseEvent", {
        type: "mouseReleased", x: titleInfo.x, y: titleInfo.y, button: "left",
      });
      await new Promise(r => setTimeout(r, 300));

      // CDPas text input
      for (const ch of title) {
        await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
          type: "keyDown", text: ch, key: ch,
        });
        await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
          type: "keyUp", key: ch,
        });
        await new Promise(r => setTimeout(r, 20 + Math.random() * 30));
      }
      log.push("Title entered via CDP");
    } else {
      // Fallback: JS inject
      await chrome.scripting.executeScript({
        target: { tabId },
        func: (t) => {
          const input = document.querySelector('textarea[name="title"]')
            || document.querySelector('input[name="title"]');
          if (input) {
            const nativeSetter = Object.getOwnPropertyDescriptor(
              window.HTMLTextAreaElement?.prototype || window.HTMLInputElement?.prototype,
              "value"
            )?.set;
            if (nativeSetter) nativeSetter.call(input, t);
            else input.value = t;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
          }
        },
        args: [title],
      });
      log.push("Title entered via JS fallback");
    }
  } catch (e) {
    log.push(`Title error: ${e.message}`);
  }

  await new Promise(r => setTimeout(r, 1000));

  // Step 3: text input
  log.push("Entering body...");
  try {
    const bodyResult = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const editor = document.querySelector('div[contenteditable="true"]')
          || document.querySelector('.public-DraftEditor-content')
          || document.querySelector('div[role="textbox"]');
        if (editor) {
          editor.focus();
          editor.click();
          const rect = editor.getBoundingClientRect();
          return { found: true, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }
        return { found: false };
      },
    });

    const bodyInfo = bodyResult[0]?.result;
    if (bodyInfo?.found) {
      await sendDebuggerCommand(tabId, "Input.dispatchMouseEvent", {
        type: "mousePressed", x: bodyInfo.x, y: bodyInfo.y, button: "left", clickCount: 1,
      });
      await sendDebuggerCommand(tabId, "Input.dispatchMouseEvent", {
        type: "mouseReleased", x: bodyInfo.x, y: bodyInfo.y, button: "left",
      });
      await new Promise(r => setTimeout(r, 300));

      for (const ch of body) {
        if (ch === "\n") {
          await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
            type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13,
          });
          await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
            type: "keyUp", key: "Enter", code: "Enter",
          });
        } else {
          await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
            type: "keyDown", text: ch, key: ch,
          });
          await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
            type: "keyUp", key: ch,
          });
        }
        await new Promise(r => setTimeout(r, 15 + Math.random() * 25));
      }
      log.push("Body entered via CDP");
    } else {
      log.push("Body editor not found");
    }
  } catch (e) {
    log.push(`Body error: ${e.message}`);
  }

  await new Promise(r => setTimeout(r, 1000));

  // Step 4: automatic submit (autoSubmit == trueDay only)
  if (autoSubmit) {
    log.push("Auto-submitting...");
    const submitResult = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const postBtn = Array.from(document.querySelectorAll("button")).find(
          (b) => b.textContent?.trim().toLowerCase() === "post"
        );
        if (postBtn && !postBtn.disabled) {
          postBtn.click();
          return { clicked: true };
        }
        return { clicked: false, error: "Post button not found or disabled" };
      },
    });
    const sr = submitResult[0]?.result;
    log.push(sr?.clicked ? "Submit clicked" : `Submit failed: ${sr?.error}`);

    if (sr?.clicked) {
      await new Promise(r => setTimeout(r, 5000));
      const tab = await chrome.tabs.get(tabId);
      const url = tab?.url || "";
      if (url.includes("/comments/")) {
        log.push(`Post successful! URL: ${url}`);
        return { success: true, url, log };
      }
      log.push(`Post URL check: ${url}`);
    }
  } else {
    log.push("Ready for manual submit (autoSubmit=false)");
  }

  return { success: autoSubmit, ready: !autoSubmit, log };
}

// Reddit In the comments Reply Put it on (thingId based)
async function redditReplyToComment(thingId, body) {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (tid, replyBody) => {
      // thingIdas comment Find
      const comment = document.querySelector(`shreddit-comment[thingid="${tid}"]`);
      if (!comment) return { success: false, error: `comment ${tid} doesn't exist` };

      // Reply button Find
      const replyBtn = comment.querySelector('button[aria-label*="Reply"]')
        || comment.querySelector('button[aria-label*="reply"]');

      if (!replyBtn) return { success: false, error: "Reply button doesn't exist" };

      replyBtn.click();

      return new Promise((resolve) => {
        setTimeout(() => {
          // Reply input area Find (comment interior)
          const editor = comment.querySelector('div[contenteditable="true"]')
            || comment.querySelector('faceplate-form div[contenteditable="true"]');

          if (!editor) {
            resolve({ success: false, error: "Reply input area doesn't exist" });
            return;
          }

          editor.focus();
          document.execCommand("selectAll", false, null);
          document.execCommand("delete", false, null);
          document.execCommand("insertText", false, replyBody);
          editor.dispatchEvent(new Event("input", { bubbles: true }));

          setTimeout(() => {
            const submitBtn = comment.querySelector('button[type="submit"]')
              || comment.querySelector('button[slot="submit-button"]');

            let btn = submitBtn;
            if (!btn) {
              const btns = comment.querySelectorAll("button");
              for (const b of btns) {
                const txt = b.textContent.trim().toLowerCase();
                if (txt === "reply" || txt === "comment") { btn = b; break; }
              }
            }

            if (btn && !btn.disabled) {
              btn.click();
              resolve({ success: true, message: "Reply Submitted" });
            } else {
              resolve({ success: false, error: "submit button doesn't exist", bodyEntered: true });
            }
          }, 1000);
        }, 1500);
      });
    },
    args: [thingId, body],
  });

  return results[0]?.result || { success: false };
}

// Reddit today log in user information
async function redditGetUserInfo() {
  const tabId = await getActiveTabId();

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const userBtn = document.querySelector("#expand-user-drawer-button");
      const username = userBtn?.textContent?.trim() || "";

      // karma information (profile from drawer)
      const karmaEls = document.querySelectorAll('[id*="karma"], [data-testid*="karma"]');
      let karma = null;
      for (const el of karmaEls) {
        const text = el.textContent.trim();
        if (text && /^\d/.test(text)) { karma = text; break; }
      }

      return {
        loggedIn: !!userBtn,
        username: username || null,
        karma,
        url: window.location.href,
      };
    },
  });

  return results[0]?.result || { loggedIn: false };
}

// Reddit To subreddit movement
async function redditNavigateSub(subreddit, sort = "hot") {
  const tabId = await getActiveTabId();
  const url = `https://www.reddit.com/r/${subreddit}/${sort}/`;
  await chrome.tabs.update(tabId, { url });
  await waitForPageLoad();
  await new Promise(r => setTimeout(r, 2000));

  // subreddit information collection
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const header = document.querySelector('shreddit-subreddit-header');
      const members = header?.getAttribute("subscribers") || "";
      const name = header?.getAttribute("display-name") || "";
      const desc = header?.getAttribute("public-description") || "";
      return {
        success: true,
        name, members, description: desc.slice(0, 200),
        url: location.href,
      };
    },
  });

  return results[0]?.result || { success: true, url: `https://www.reddit.com/r/${subreddit}/` };
}

// CDP based coordinate click — Shadow DOM to the inside arrival
async function clickCoords(x, y) {
  const tabId = await getActiveTabId();
  await ensureDebugger(tabId);

  // mousePressed + mouseReleased (actual browser click)
  await sendDebuggerCommand(tabId, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: Math.round(x),
    y: Math.round(y),
    button: "left",
    clickCount: 1,
  });
  await sendDebuggerCommand(tabId, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: Math.round(x),
    y: Math.round(y),
    button: "left",
    clickCount: 1,
  });

  return { success: true, x: Math.round(x), y: Math.round(y) };
}

// CDP based text input — keyboard to event actual typing
async function typeText(text) {
  const tabId = await getActiveTabId();
  await ensureDebugger(tabId);

  for (const char of text) {
    await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
      type: "keyDown",
      text: char,
      key: char,
      code: `Key${char.toUpperCase()}`,
      unmodifiedText: char,
    });
    await sendDebuggerCommand(tabId, "Input.dispatchKeyEvent", {
      type: "keyUp",
      key: char,
      code: `Key${char.toUpperCase()}`,
    });
    // bot detect evasion: 50-200ms random typing delay (human being typing speed simulation)
    await new Promise(r => setTimeout(r, 50 + Math.random() * 150));
  }

  return { success: true, length: text.length };
}

// debugger attach helper
async function ensureDebugger(tabId) {
  if (isDebugging && debugTabId === tabId) return;

  // existing debugger detach (which tab or)
  if (isDebugging && debugTabId) {
    try {
      await new Promise((r) => chrome.debugger.detach({ tabId: debugTabId }, () => r()));
    } catch {}
    isDebugging = false;
    debugTabId = null;
  }

  // Target of tab existing Debugger too detach trial
  try {
    await new Promise((r) => chrome.debugger.detach({ tabId }, () => r()));
  } catch {}

  try {
    await new Promise((resolve, reject) => {
      chrome.debugger.attach({ tabId }, "1.3", () => {
        const err = chrome.runtime.lastError;
        if (err) return reject(new Error(err.message));
        resolve();
      });
    });
  } catch (e) {
    if (!e.message?.includes("Already attached")) throw e;
  }

  isDebugging = true;
  debugTabId = tabId;
  try { await sendDebuggerCommand(tabId, "Runtime.enable", {}); } catch {}
  try { await sendDebuggerCommand(tabId, "Input.enable", {}); } catch {}
}

// script execution (Debugger Runtime.evaluate — CSP perfection detour)
async function evaluateScript(script) {
  const tabId = await getActiveTabId();

  // debugger yet not If it sticks Paste
  if (!isDebugging || debugTabId !== tabId) {
    if (isDebugging && debugTabId && debugTabId !== tabId) {
      try {
        await new Promise((r) => chrome.debugger.detach({ tabId: debugTabId }, r));
      } catch {}
    }
    await new Promise((resolve, reject) => {
      chrome.debugger.attach({ tabId }, "1.3", () => {
        const err = chrome.runtime.lastError;
        if (err) return reject(new Error(err.message));
        resolve();
      });
    });
    isDebugging = true;
    debugTabId = tabId;
    try { await sendDebuggerCommand(tabId, "Runtime.enable", {}); } catch {}
  }

  // Runtime.evaluateas execution (CSP ignore)
  const evalResult = await sendDebuggerCommand(tabId, "Runtime.evaluate", {
    expression: script,
    returnByValue: true,
    awaitPromise: false,
  });

  if (evalResult?.exceptionDetails) {
    return { result: { __error: evalResult.exceptionDetails.text || "eval error" } };
  }

  return { result: evalResult?.result?.value };
}

async function consoleStart(maxEntries = 500) {
  const tabId = await getActiveTabId();
  const nextMax = Math.max(50, Math.min(Number(maxEntries) || 500, 5000));
  consoleMaxEntries = nextMax;
  consoleBuffer = [];

  if (isDebugging && debugTabId === tabId) {
    return { success: true, tabId, alreadyAttached: true };
  }

  if (isDebugging && debugTabId && debugTabId !== tabId) {
    try {
      await new Promise((resolve) => chrome.debugger.detach({ tabId: debugTabId }, () => resolve()));
    } catch {}
    isDebugging = false;
    debugTabId = null;
  }

  await new Promise((resolve, reject) => {
    chrome.debugger.attach({ tabId }, "1.3", () => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message));
      resolve();
    });
  });

  isDebugging = true;
  debugTabId = tabId;

  // Enable domains needed for console + errors.
  try {
    await sendDebuggerCommand(tabId, "Runtime.enable", {});
  } catch {}
  try {
    await sendDebuggerCommand(tabId, "Log.enable", {});
  } catch {}

  return { success: true, tabId, maxEntries: consoleMaxEntries };
}

async function consoleStop() {
  if (!isDebugging || !debugTabId) {
    return { success: true, detached: false };
  }
  const tabId = debugTabId;
  await new Promise((resolve) => chrome.debugger.detach({ tabId }, () => resolve()));
  isDebugging = false;
  debugTabId = null;
  return { success: true, detached: true };
}

async function consoleClear() {
  consoleBuffer = [];
  return { success: true };
}

async function consoleGet(limit = 200) {
  const lim = Math.max(1, Math.min(Number(limit) || 200, 2000));
  const logs = consoleBuffer.slice(-lim);
  return {
    attached: isDebugging,
    tabId: debugTabId,
    total: consoleBuffer.length,
    logs,
  };
}

// message handler (popupat situation For confirmation + telerecording action reception)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "getStatus") {
    sendResponse({ connected: ws && ws.readyState === WebSocket.OPEN });
  } else if (message.type === "recordedAction" && isRecording) {
    const action = message.action;
    action.id = `act-${recordingActions.length}`;

    // Take screenshot and attach to action
    chrome.tabs.captureVisibleTab(null, { format: "jpeg", quality: 60 }, (dataUrl) => {
      if (dataUrl) {
        action.screenshotBefore = dataUrl;
      }
      recordingActions.push(action);
    });
  }
  return true;
});

// Recording: inject content script and start
async function recordingStart() {
  const tabId = await getActiveTabId();

  if (isRecording) {
    return { success: false, message: "already telerecording In progress." };
  }

  isRecording = true;
  recordingActions = [];
  recordingStartTime = Date.now();
  recordingTabId = tabId;

  const tab = await chrome.tabs.get(tabId);
  recordingStartUrl = tab.url || "";

  // Inject content script
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["record-content.js"],
  });

  return { success: true, tabId, url: recordingStartUrl };
}

// Recording: stop and return collected actions
async function recordingStop() {
  if (!isRecording) {
    return { success: false, message: "telerecording drum no." };
  }

  // Cleanup content script
  if (recordingTabId) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: recordingTabId },
        func: () => {
          if (window.__redditRecorderCleanup) window.__redditRecorderCleanup();
        },
      });
    } catch (e) {
      // Tab may have been closed
    }
  }

  const result = {
    success: true,
    actions: recordingActions,
    url: recordingStartUrl,
    duration: Date.now() - recordingStartTime,
    actionCount: recordingActions.length,
  };

  isRecording = false;
  recordingActions = [];
  recordingStartTime = 0;
  recordingTabId = null;
  recordingStartUrl = "";

  return result;
}

// Re-inject content script on page navigation during recording
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!isRecording || tabId !== recordingTabId) return;

  if (changeInfo.status === "complete") {
    // Record navigate action
    recordingActions.push({
      id: `act-${recordingActions.length}`,
      type: "navigate",
      timestamp: Date.now() - recordingStartTime,
      url: tab.url || "",
    });

    // Re-inject content script
    chrome.scripting
      .executeScript({
        target: { tabId },
        files: ["record-content.js"],
      })
      .catch(() => {
        // Ignore injection errors (e.g., chrome:// pages)
      });
  }
});

// Extension installation/update city connection
chrome.runtime.onInstalled.addListener(() => {
  console.log("[reddit] Extension installation/updated");
  connect();
});

// browser start city connection
chrome.runtime.onStartup.addListener(() => {
  console.log("[reddit] browser Started");
  connect();
});

// start city connection trial
connect();
