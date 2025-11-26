const storedUser = JSON.parse(localStorage.getItem("user") || "null");

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

if (storedUser) {
  if (authLinks) authLinks.style.display = "none";
  if (userInfo) userInfo.style.display = "inline-flex";

  if (userNameSpan) {
    userNameSpan.textContent = storedUser.name || storedUser.email;
  }

  if (avatar) {
    const initials = getInitials(storedUser.name, storedUser.email);
    avatar.textContent = initials;
    avatar.style.backgroundColor = colorFromString(storedUser.email || storedUser.name || "");
  }

  if (logoutBtn) {
    logoutBtn.onclick = async (e) => {
      e.preventDefault();
      try {
        await fetch("https://cp317-group-18-project.onrender.com/auth/logout", {
          method: "POST",
          credentials: "include",
        });
      } catch {}
      localStorage.removeItem("user");
      window.location.href = "login.html";
    };
  }
} else {
  if (authLinks) authLinks.style.display = "inline-flex";
  if (userInfo) userInfo.style.display = "none";
}
