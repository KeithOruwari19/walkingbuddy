const BACKEND_BASE = "https://cp317-group-18-project.onrender.com";

const room = JSON.parse(localStorage.getItem("currentRoom") || "null");
if (!room || !room.id) {
  window.location.href = "rooms.html";
}

const user = JSON.parse(localStorage.getItem("user") || "null") || {};

const messagesContainer = document.getElementById("chat-messages");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("chat-send");

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

function appendMessage(text, self = false) {
  const wrapper = document.createElement("div");
  wrapper.classList.add("message-wrapper");
  if (self) wrapper.classList.add("self");

  const avatar = document.createElement("div");
  avatar.classList.add("chat-avatar");

  const initials = getInitials(user.name, user.email);
  avatar.textContent = initials;
  avatar.style.backgroundColor = colorFromString(user.email || user.name || "");

  wrapper.appendChild(avatar);

  const bubble = document.createElement("div");
  bubble.classList.add("message-bubble");
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  messagesContainer.appendChild(wrapper);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function loadMessages() {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/chat/${room.id}/messages`, {
      credentials: "include"
    });
    const data = await res.json();

    messagesContainer.innerHTML = "";

    if (Array.isArray(data.messages)) {
      data.messages.forEach(m => {
        appendMessage(m.content, m.user_id === user.id);
      });
    }
  } catch (e) {}
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  try {
    await fetch(`${BACKEND_BASE}/api/chat/send`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: room.id,
        user_id: user.id,
        content: text        // FIXED
      })
    });

    input.value = "";
    await loadMessages();
  } catch (e) {}
}

sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keypress", e => {
  if (e.key === "Enter") sendMessage();
});

loadMessages();
setInterval(loadMessages, 1500);
