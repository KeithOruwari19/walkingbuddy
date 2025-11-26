const BACKEND_BASE = "https://cp317-group-18-project.onrender.com";

const room = JSON.parse(localStorage.getItem("currentRoom") || "null");
if (!room || !room.id) {
  window.location.href = "rooms.html";
}

const rawUser = JSON.parse(localStorage.getItem("user") || "null") || {};
const currentUser = {
  id: rawUser.user_id || rawUser.id || rawUser.userId || rawUser.email || null,
  name: rawUser.name || rawUser.full_name || rawUser.displayName || rawUser.email || "You",
  email: rawUser.email || ""
};

const messagesContainer = document.getElementById("chat-messages");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("chat-send");

function escapeHtml(s){ return String(s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function getInitials(name, email){
  if(name && typeof name === "string"){
    const parts = name.trim().split(/\s+/);
    if(parts.length === 1) return parts[0].slice(0,2).toUpperCase();
    return (parts[0][0] + parts[parts.length-1][0]).toUpperCase();
  }
  if(email && typeof email === "string") return email[0].toUpperCase();
  return "??";
}
function colorFromString(str){
  if(!str) return "#3949ab";
  let h=0;
  for(let i=0;i<str.length;i++) h = str.charCodeAt(i) + ((h<<5)-h);
  const hue = Math.abs(h % 360);
  return `hsl(${hue},65%,55%)`;
}

function renderSingleMessage(m){
  const content = m.content ?? m.text ?? m.message ?? "";
  const user_id = m.user_id ?? m.userId ?? m.user ?? null;
  const authorName = m.user_name ?? m.name ?? m.author ?? (user_id && String(user_id) === String(currentUser.id) ? currentUser.name : "Unknown");
  const authorEmail = m.user_email ?? m.email ?? null;
  const ts = m.ts ?? m.timestamp ?? m.created_at ?? m.time ?? null;

  const isSelf = user_id && currentUser.id && String(user_id) === String(currentUser.id);

  const wrapper = document.createElement("div");
  wrapper.className = "message-wrapper" + (isSelf ? " self" : "");

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.textContent = getInitials(authorName, authorEmail);
  avatar.style.backgroundColor = colorFromString(authorEmail || authorName || "");

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.innerHTML = `<strong>${escapeHtml(authorName || (isSelf ? currentUser.name : "Unknown"))}</strong>` + (ts ? ` <span class="chat-ts">${escapeHtml(new Date(ts).toLocaleTimeString())}</span>` : "");

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = content;

  wrapper.appendChild(avatar);
  const textWrap = document.createElement("div");
  textWrap.appendChild(meta);
  textWrap.appendChild(bubble);
  wrapper.appendChild(textWrap);

  return wrapper;
}

function renderMessagesList(list){
  if(!messagesContainer) return;
  messagesContainer.innerHTML = "";
  if(!Array.isArray(list) || list.length === 0){
    messagesContainer.innerHTML = `<p style="color:#777;margin:8px 12px;">No messages yet.</p>`;
    return;
  }
  for(const m of list){
    const el = renderSingleMessage(m);
    messagesContainer.appendChild(el);
  }
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function loadMessages(){
  if(!room || !room.id) return;
  try {
    const res = await fetch(`${BACKEND_BASE}/api/chat/${encodeURIComponent(room.id)}/messages?limit=200`, {
      method: "GET",
      credentials: "include"
    });
    if(!res.ok){
      const txt = await res.text().catch(()=>"");
      console.warn("[chat] loadMessages failed", res.status, txt);
      return;
    }
    const j = await res.json();
    const msgs = Array.isArray(j.messages) ? j.messages : (Array.isArray(j) ? j : []);
    renderMessagesList(msgs);
  } catch (e) {
    console.warn("[chat] loadMessages exception", e);
  }
}

let sending = false;

async function sendMessage(){
  if(sending) return;
  const text = (input.value || "").trim();
  if(!text) return;
  if(!currentUser.id){
    alert("You must be logged in to send messages.");
    return;
  }

  sending = true;
  sendBtn.disabled = true;

  const payload = { room_id: room.id, user_id: currentUser.id, content: text };

  try {
    const res = await fetch(`${BACKEND_BASE}/api/chat/send`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if(!res.ok){
      const body = await res.text().catch(()=>"");
      console.warn("[chat] send failed", res.status, body);
      if(res.status === 403){
        try {
          const jres = await fetch(`${BACKEND_BASE}/api/rooms/join`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room_id: room.id, user_id: currentUser.id })
          });
          if(jres.ok){
            console.info("[chat] joined room automatically, retrying send");
            const retry = await fetch(`${BACKEND_BASE}/api/chat/send`, {
              method: "POST",
              credentials: "include",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
            });
            if(retry.ok){
              await loadMessages();
              input.value = "";
              input.focus();
              sending = false;
              sendBtn.disabled = false;
              return;
            }
          }
        } catch(err){
          console.warn("[chat] auto-join failed", err);
        }
      }
      alert("Failed to send message — check console for details.");
      sending = false;
      sendBtn.disabled = false;
      return;
    }

    const json = await res.json().catch(()=>null);
    await loadMessages();
    input.value = "";
    input.focus();
  } catch (e) {
    console.warn("[chat] sendMessage exception", e);
    alert("Network error sending message (see console).");
  } finally {
    sending = false;
    sendBtn.disabled = false;
  }
}

function wireUI(){
  sendBtn.addEventListener("click", (ev) => { ev.preventDefault(); sendMessage(); });
  input.addEventListener("keydown", (ev) => {
    if(ev.key === "Enter" && !ev.shiftKey){
      ev.preventDefault();
      sendMessage();
    }
  });
}

(function init(){
  const userNameEl = document.getElementById("user-name");
  const avatarEl = document.getElementById("user-avatar");
  if(userNameEl) userNameEl.textContent = currentUser.name;
  if(avatarEl){
    avatarEl.textContent = getInitials(currentUser.name, currentUser.email);
    avatarEl.style.backgroundColor = colorFromString(currentUser.email || currentUser.name || "");
  }

  wireUI();
  loadMessages();
  setInterval(loadMessages, 1500);
})();
