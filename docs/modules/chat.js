const BACKEND_BASE = "https://cp317-group-18-project.onrender.com";

const room = JSON.parse(localStorage.getItem("currentRoom") || "null");
if (!room || !room.id) {
  window.location.href = "rooms.html";
}

const rawUser = JSON.parse(localStorage.getItem("user") || "null") || {};
const user = {
  id: rawUser.user_id || rawUser.id || rawUser.userId || rawUser.email || null,
  name: rawUser.name || rawUser.full_name || rawUser.displayName || rawUser.email || "You",
  email: rawUser.email || ""
};

const messagesContainer = document.getElementById("chat-messages");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("chat-send");

function getInitials(name, email) {
  if (name) {
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0][0].toUpperCase();
    return (parts[0][0] + parts[parts.length-1][0]).toUpperCase();
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

function appendMessage(text, opts = {}) {
  const { self = false, authorName = null, authorEmail = null } = opts;
  const wrapper = document.createElement("div");
  wrapper.classList.add("message-wrapper");
  if (self) wrapper.classList.add("self");

  const avatar = document.createElement("div");
  avatar.classList.add("chat-avatar");
  const initials = getInitials(authorName || user.name, authorEmail || user.email);
  avatar.textContent = initials;
  avatar.style.backgroundColor = colorFromString((authorEmail || authorName || ""));

  wrapper.appendChild(avatar);

  const bubble = document.createElement("div");
  bubble.classList.add("message-bubble");
  bubble.textContent = text;

  const meta = document.createElement("div");
  meta.classList.add("message-meta");
  meta.innerHTML = `<strong>${escapeHtml(authorName || (self ? user.name : "Unknown"))}</strong>`;

  wrapper.appendChild(meta);
  wrapper.appendChild(bubble);
  messagesContainer.appendChild(wrapper);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(s){ return String(s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function loadMessages() {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/chat/${encodeURIComponent(room.id)}/messages`, {
      credentials: "include"
    });
    if (!res.ok) {
      console.warn("loadMessages failed:", res.status, await res.text().catch(()=>""));
      return;
    }
    const data = await res.json();
    messagesContainer.innerHTML = "";

    if (Array.isArray(data.messages)) {
      data.messages.forEach(m => {
        const content = m.content ?? m.text ?? "";
        const msgUserId = m.user_id ?? m.userId ?? m.user ?? null;
        const authorName = m.user_name ?? m.name ?? (msgUserId && String(msgUserId) === String(user.id) ? user.name : null);
        const isSelf = msgUserId && user.id && String(msgUserId) === String(user.id);
        appendMessage(content, { self: !!isSelf, authorName, authorEmail: null });
      });
    }
  } catch (e) {
    console.warn("loadMessages exception", e);
  }
}

let sending = false;

async function attemptJoinRoom() {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/rooms/join`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room_id: room.id, user_id: user.id })
    });
    if (!res.ok) {
      console.warn("attemptJoinRoom failed:", res.status, await res.text().catch(()=>""));
      return false;
    }
    try {
      const joined = JSON.parse(localStorage.getItem("joinedRooms") || "[]");
      if (!joined.includes(room.id)) {
        joined.push(room.id);
        localStorage.setItem("joinedRooms", JSON.stringify(joined));
      }
    } catch {}
    return true;
  } catch (e) {
    console.warn("attemptJoinRoom exception", e);
    return false;
  }
}

async function sendMessage() {
  if (sending) return;
  const text = (input.value || "").trim();
  if (!text) return;

  if (!user.id) {
    alert("You must be logged in to send messages.");
    return;
  }

  sending = true;
  sendBtn.disabled = true;

  const payload = { room_id: room.id, user_id: user.id, content: text };

  async function doSend() {
    try {
      const res = await fetch(`${BACKEND_BASE}/api/chat/send`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        await loadMessages();
        input.value = "";
        input.focus();
        return { ok: true };
      } else {
        const bodyText = await res.text().catch(()=>"");
        console.warn("sendMessage failed:", res.status, bodyText);
        return { ok: false, status: res.status, text: bodyText };
      }
    } catch (err) {
      console.warn("sendMessage exception", err);
      return { ok: false, err };
    }
  }

  let r = await doSend();
  if (!r.ok && r.status === 403) {
    console.info("send rejected (403). Attempting to join room and retry...");
    const joined = await attemptJoinRoom();
    if (joined) {
      r = await doSend();
      if (!r.ok) {
        alert("Message send still failed after joining — check console for details.");
      }
    } else {
      alert("Couldn't join the room automatically. Please try joining from Rooms page.");
    }
  } else if (!r.ok) {
    alert("Failed to send message — check console for details.");
  }

  sending = false;
  sendBtn.disabled = false;
}

function wireUI() {
  sendBtn.addEventListener("click", (ev) => {
    ev.preventDefault();
    sendMessage();
  });

  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendMessage();
    }
  });
}

(function init() {
  const userNameEl = document.getElementById("user-name");
  const avatarEl = document.getElementById("user-avatar");
  if (userNameEl) userNameEl.textContent = user.name;
  if (avatarEl) {
    avatarEl.textContent = getInitials(user.name, user.email);
    avatarEl.style.backgroundColor = colorFromString(user.email || user.name || "");
  }

  wireUI();
  loadMessages();
  setInterval(loadMessages, 1500);
})();
