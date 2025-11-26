(() => {
  const BACKEND = "https://cp317-group-18-project.onrender.com";

  function getInitials(name, email) {
    if (name) {
      const parts = name.trim().split(/\s+/);
      if (parts.length === 1) return parts[0][0].toUpperCase();
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return email ? email[0].toUpperCase() : "?";
  }

  function colorFromString(str) {
    if (!str) return "#3949ab";
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    const hue = Math.abs(hash % 360);
    return `hsl(${hue}, 65%, 55%)`;
  }

  const authLinks = document.getElementById("auth-links") || document.querySelector(".auth-links");
  const userInfo = document.getElementById("user-info") || document.querySelector(".user-info");
  const userNameSpan = document.getElementById("user-name") || document.querySelector(".user-name");
  const avatar = document.getElementById("user-avatar") || document.querySelector(".user-avatar");
  const logoutBtn = document.getElementById("logout-btn") || document.querySelector("[data-logout]");

  function hideAuthLinks() {
    if (authLinks) authLinks.classList.add("hidden");
    if (userInfo) userInfo.classList.remove("hidden");
  }
  function showAuthLinks() {
    if (authLinks) authLinks.classList.remove("hidden");
    if (userInfo) userInfo.classList.add("hidden");
  }

  function renderLoggedIn(user) {
    console.log("auth: renderLoggedIn", user);
    hideAuthLinks();

    if (userNameSpan) userNameSpan.textContent = user?.name || user?.email || "Hi";
    if (avatar) {
      const initials = getInitials(user?.name, user?.email);
      avatar.textContent = initials;
      avatar.style.backgroundColor = colorFromString((user?.email || user?.name || ""));
    }

    if (logoutBtn) {
      logoutBtn.onclick = async (e) => {
        e && e.preventDefault();
        try {
          await fetch(`${BACKEND}/auth/logout`, { method: "POST", credentials: "include" });
        } catch (err) {
          console.warn("auth: logout failed", err);
        }
        localStorage.removeItem("user");
        window.dispatchEvent(new CustomEvent("auth:update", { detail: null }));
      };
    }
  }

  function renderLoggedOut() {
    console.log("auth: renderLoggedOut");
    showAuthLinks();
    if (logoutBtn) logoutBtn.onclick = null;
  }

  async function tryVerify() {
    try {
      const res = await fetch(`${BACKEND}/auth/verify`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (err) {
      console.warn("auth: verify request failed", err);
      return null;
    }
  }

  function parseStoredUser() {
    try {
      const raw = localStorage.getItem("user");
      if (!raw || raw === "null" || raw === "undefined") return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (e) {
      return null;
    }
  }

  async function handleAuthUpdate(evt) {
    if (evt && evt.detail) {
      if (evt.detail) {
        renderLoggedIn(evt.detail);
        return;
      } else {
        renderLoggedOut();
        return;
      }
    }

    const serverUser = await tryVerify();
    if (serverUser) {
      renderLoggedIn(serverUser);
      return;
    }

    const stored = parseStoredUser();
    if (stored) {
      renderLoggedIn(stored);
      return;
    }

    renderLoggedOut();
  }

  window.addEventListener("auth:update", handleAuthUpdate);

  window.addEventListener("storage", (e) => {
    if (e.key === "user") {
      let newUser = null;
      try { newUser = e.newValue ? JSON.parse(e.newValue) : null; } catch { newUser = null; }
      if (newUser) renderLoggedIn(newUser);
      else renderLoggedOut();
    }
  });

  window.__authRefresh = () => handleAuthUpdate();

  document.addEventListener("DOMContentLoaded", () => {
    handleAuthUpdate();
  });
})();
