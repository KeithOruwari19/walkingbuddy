(() => {
  const BACKEND = "https://cp317-group-18-project.onrender.com";

  function getInitials(name, email) {
    if (name) {
      const parts = name.trim().split(" ");
      if (parts.length === 1) return parts[0][0].toUpperCase();
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return email ? email[0].toUpperCase() : "?";
  }

  function colorFromString(str) {
    if (!str) return "#3949ab";
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash % 360);
    return `hsl(${hue}, 65%, 55%)`;
  }
  
  const authLinks = document.getElementById("auth-links");
  const userInfo = document.getElementById("user-info");
  const userNameSpan = document.getElementById("user-name");
  const avatar = document.getElementById("user-avatar");
  const logoutBtn = document.getElementById("logout-btn");
  function renderLoggedIn(user) {
    if (authLinks) authLinks.style.display = "none";
    if (userInfo) userInfo.style.display = "inline-flex";

    if (userNameSpan) userNameSpan.textContent = user.name || user.email || "Hi";
    if (avatar) {
      const initials = getInitials(user.name, user.email);
      avatar.textContent = initials;
      avatar.style.backgroundColor = colorFromString(user.email || user.name || "");
    }

    if (logoutBtn) {
      logoutBtn.onclick = async (e) => {
        e.preventDefault();
        try {
          await fetch(`${BACKEND}/auth/logout`, {
            method: "POST",
            credentials: "include",
          });
        } catch (err) {
          console.warn("logout error", err);
        }
        localStorage.removeItem("user");
        window.location.reload();
      };
    }
  }

  function renderLoggedOut() {
    if (authLinks) authLinks.style.display = "inline-flex";
    if (userInfo) userInfo.style.display = "none";
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
      console.warn("auth verify request failed", err);
      return null;
    }
  }
  document.addEventListener("DOMContentLoaded", async () => {
    const serverUser = await tryVerify();
    if (serverUser) {
      renderLoggedIn(serverUser);
      return;
    }
    const storedUser = JSON.parse(localStorage.getItem("user") || "null");
    if (storedUser) {
      renderLoggedIn(storedUser);
      return;
    }
    renderLoggedOut();
  });

})();
