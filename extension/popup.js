// automatic update check - manifest version and comparison
async function checkAndReload() {
  try {
    const manifest = chrome.runtime.getManifest();
    // Fetch the latest manifest from disk (for unpacked extensions)
    const resp = await fetch(chrome.runtime.getURL("manifest.json") + "?t=" + Date.now());
    const diskManifest = await resp.json();
    if (diskManifest.version !== manifest.version) {
      console.log("[reddit] New version detected:", manifest.version, "→", diskManifest.version);
      chrome.runtime.reload();
      return;
    }
  } catch (e) {
    console.log("[reddit] version check failure:", e);
  }
}

// Connection status check
async function checkStatus() {
  const statusEl = document.getElementById("status");

  try {
    // Check status in background
    const response = await chrome.runtime.sendMessage({ type: "getStatus" });
    if (response?.connected) {
      statusEl.className = "status connected";
      statusEl.textContent = "✓ connected";
    } else {
      statusEl.className = "status disconnected";
      statusEl.textContent = "connection status middle...";
    }
  } catch (e) {
    statusEl.className = "status disconnected";
    statusEl.textContent = "connection status middle...";
  }
}

// Check for updates first, then check the connection status
checkAndReload().then(() => {
  checkStatus();
  setInterval(checkStatus, 2000);
});
