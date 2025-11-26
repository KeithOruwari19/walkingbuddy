(() => {
  const BACKEND = "https://cp317-group-18-project.onrender.com";

  function getInitials(name, email) {
    if (name) {
      const parts = name.trim().split(/\s+/);
      if (parts.length === 1) return parts[0][0].toUpperCase();
      return (parts[0][0] + parts[1][0]).toUpperCase();
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
  function $id(id) { return document.getElementById(id); }
  function findAuthLinks() {
    return $id("auth-links") || document.querySelector(".auth-links") || document.querySelector("nav .auth-links");
  }
  function findUserInfo() {
    return $id("user-info") || document.querySelector(".user-info") || document.querySelector("nav .user-info");
  }
  function findLogoutBtn() {
    return $id("logout-btn") || document.querySelector("[data-logout]") || document.querySelector(".auth-link.logout");
  }

  const authLinks = findAuthLinks();
  const userInfo = findUserInfo();
  const userNameSpan = $id("user-name") || document.querySelector(".user-name");
  const avatar = $id("user-avatar") || document.querySelector(".user-avatar");
  const logoutBtn = findLogoutBtn();

  function renderLoggedIn(user) {
    console.log("auth.js: rendering logged-in UI", user);
    // hide login/signup
    if (authLinks) {
      authLinks.style.display = "none";
      authLinks.style.visibility = "hidden";
    }
    // show user info
    if (userInfo) {
      userInfo.style.display = "inline-flex";
      userInfo.style.visibility = "visible";
    }
    if (userNameSpan) userNameSpan.textContent = user.name || user.email || "Hi";
    if (avatar) {
      const initials = getInitials(user.name, user.email);
      avatar.textContent = initials;
      avatar.style.backgroundColor = colorFromString(user.email || user.name || "");
    }
    if (logoutBtn) {
      logoutBtn.onclick = async (e) => {
        e && e.preventDefault();
        try {
          await fetch(`${BACKEND}/auth/logout`, { method: "POST", credentials: "include" });
        } catch (err) { console.warn("auth.js: logout request failed", err); }
        localStorage.removeItem("user");
        window.location.reload();
      };
    }
  }

  function renderLoggedOut() {
    console.log("auth.js: rendering logged-out UI");
    if (authLinks) {
      authLinks.style.display = "inline-flex";
      authLinks.style.visibility = "visible";
    }
    if (userInfo) {
      userInfo.style.display = "none";
      userInfo.style.visibility = "hidden";
    }
    if (logoutBtn) logoutBtn.onclick = null;
  }

  async function tryVerify() {
    try {
      const res = await fetch(`${BACKEND}/auth/verify`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        console.log("auth.js: verify returned", res.status);
        return null;
      }
      const data = await res.json();
      console.log("auth.js: verify body:", data);
      return data;
    } catch (err) {
      console.warn("auth.js: verify request failed", err);
      return null;
    }
  }

  function ensureOneVisible() {
    const a = authLinks;
    const u = userInfo;
    const aVis = a && window.getComputedStyle(a).display !== "none" && a.getClientRects().length > 0;
    const uVis = u && window.getComputedStyle(u).display !== "none" && u.getClientRects().length > 0;
    console.log("auth.js: visibility check authLinks:", !!a, aVis, "userInfo:", !!u, uVis);
    if (!aVis && !uVis) {
      // try to show auth-links as a sensible default
      if (a) { a.style.display = "inline-flex"; a.style.visibility = "visible"; console.log("auth.js: forced auth-links visible"); }
      else if (u) { u.style.display = "none"; u.style.visibility = "hidden"; console.log("auth.js: forced user-info hidden"); }
      else console.warn("auth.js: neither auth-links nor user-info present in DOM");
    }
  }


  document.addEventListener("DOMContentLoaded", async () => {
    console.log("auth.js loaded. Elements:", { authLinks: !!authLinks, userInfo: !!userInfo, userNameSpan: !!userNameSpan, avatar: !!avatar, logoutBtn: !!logoutBtn });
    const serverUser = await tryVerify();
    if (serverUser) {
      renderLoggedIn(serverUser);
      ensureOneVisible();
      return;
    }
    let storedUser = null;
    try { storedUser = JSON.parse(localStorage.getItem("user") || "null"); } catch (e) { storedUser = null; console.warn("auth.js: failed parsing localStorage.user", e); }
    if (storedUser) {
      renderLoggedIn(storedUser);
      ensureOneVisible();
      return;
    }
    renderLoggedOut();
    ensureOneVisible();
  });
})();
