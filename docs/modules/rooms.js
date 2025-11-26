const BACKEND_HOST = "https://cp317-group-18-project.onrender.com"; // <- replace if needed
const API_BASE = `${BACKEND_HOST}/api/rooms`;
const WS_URL = `${(BACKEND_HOST.startsWith("https") ? "wss" : "ws")}://${BACKEND_HOST.replace(/^https?:\/\//,'')}/api/rooms/ws`;

let rooms = [];       
let joinedRooms = []; 
const $ = sel => document.querySelector(sel);

function normalizeRoom(r) {
  return {
    id: r.room_id || r.id || r.uuid || r.roomId || String(r.id || r.room_id || Date.now()),
    name: r.name || r.room_name || r.destination || `Room ${r.room_id || r.id || ''}`,
    members: r.members ?? (Array.isArray(r.users) ? r.users.length : (r.count ?? 0)),
    meetTime: r.meetTime || r.meet_time || r.meeting_time || r.meet_time_iso || r.meetTime || null,
    startLocation: r.startLocation || r.start_location || r.start || '',
    destination: r.destination || r.dest || r.destination || '',
    raw: r
  };
}

function getCurrentUserId() {
  try {
    const u = JSON.parse(localStorage.getItem("user") || "null");
    if (!u) return `guest-${Math.floor(Math.random()*100000)}`;
    return u.id || u.user_id || u.email || u.name || `user-${Math.floor(Math.random()*100000)}`;
  } catch { return `guest-${Math.floor(Math.random()*100000)}`; }
}

function showMessage(text, err=false) {
  const box = $("#message");
  if (!box) return console.log(text);
  box.textContent = text;
  box.className = err ? "msg-box error" : "msg-box";
  box.style.display = "block";
  setTimeout(() => box.style.display = "none", 2500);
}

function renderJoinedRooms() {
  const container = $("#joined-rooms-list");
  container.innerHTML = "";
  if (!joinedRooms.length) {
    container.innerHTML = `<p style="color:#777;font-size:14px;">You haven't joined any rooms yet.</p>`;
    return;
  }
  joinedRooms.forEach(roomId => {
    const room = rooms.find(r => (r.id === roomId || r.name === roomId));
    if (!room) return;
    const div = document.createElement("div");
    div.classList.add("room-card");
    div.innerHTML = `
      <h3 class="room-title">${escapeHtml(room.name)}</h3>
      <div class="room-meta">
        <p><strong>Meeting:</strong> ${room.meetTime ? new Date(room.meetTime).toLocaleString() : "TBD"}</p>
      </div>
      <button class="btn secondary" data-enter="${room.id}">Enter Chat</button>
    `;
    container.appendChild(div);
  });
}

function renderRooms() {
  const list = $("#room-list");
  const empty = $("#no-rooms-message");
  if (!rooms.length) {
    if (empty) empty.style.display = "block";
    if (list) list.innerHTML = "";
    return;
  }
  if (empty) empty.style.display = "none";
  if (list) list.innerHTML = "";
  rooms.forEach(room => {
    const div = document.createElement("div");
    div.classList.add("room-card");
    div.innerHTML = `
      <h3 class="room-title">${escapeHtml(room.name)}</h3>
      <div class="room-meta">
        <p><strong>Members:</strong> ${room.members ?? 0}</p>
        <p><strong>Meeting Time:</strong> ${room.meetTime ? new Date(room.meetTime).toLocaleString() : "TBD"}</p>
        <p><strong>Start Location:</strong> ${escapeHtml(room.startLocation || "")}</p>
        <p><strong>Destination:</strong> ${escapeHtml(room.destination || "")}</p>
      </div>
      <button class="btn secondary" data-join="${room.id}">Join Room</button>
    `;
    list.appendChild(div);
  });
}

function escapeHtml(s){ return String(s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function loadLocalBackup() {
  try {
    rooms = JSON.parse(localStorage.getItem("rooms") || "[]").map(normalizeRoom);
    joinedRooms = JSON.parse(localStorage.getItem("joinedRooms") || "[]");
  } catch (e) {
    rooms = []; joinedRooms = [];
  }
  renderJoinedRooms();
  renderRooms();
}

function saveLocalBackup() {
  try {
    localStorage.setItem("rooms", JSON.stringify(rooms.map(r=>r.raw || r)));
    localStorage.setItem("joinedRooms", JSON.stringify(joinedRooms));
  } catch (e) {}
}

async function fetchRoomsFromServer() {
  try {
    const res = await fetch(`${API_BASE}/list`, { credentials: "include" });
    if (!res.ok) throw new Error("Failed to fetch rooms");
    const j = await res.json();
    const serverRooms = Array.isArray(j.rooms) ? j.rooms.map(normalizeRoom) : [];
    rooms = serverRooms;
    saveLocalBackup();
    renderJoinedRooms();
    renderRooms();
    return true;
  } catch (e) {
    console.warn("fetchRoomsFromServer failed:", e);
    loadLocalBackup();
    return false;
  }
}

async function createRoomOnServer(roomPayload) {
  try {
    const res = await fetch(`${API_BASE}/create`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(roomPayload)
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "create failed");
    }
    const j = await res.json();
    const created = normalizeRoom(j.room || j);
    if (!rooms.find(r => r.id === created.id)) rooms.unshift(created);
    saveLocalBackup();
    renderJoinedRooms();
    renderRooms();
    return created;
  } catch (e) {
    showMessage("Failed to create room (server). Using local fallback.", true);
    console.warn(e);
    const created = normalizeRoom({
      id: `local-${Date.now()}`,
      name: roomPayload.room_name || roomPayload.destination || roomPayload.name,
      members: 1,
      meetTime: roomPayload.meetTime || roomPayload.meet_time || null,
      startLocation: roomPayload.start_coord || roomPayload.startLocation || "",
      destination: roomPayload.destination || ""
    });
    rooms.unshift(created);
    saveLocalBackup();
    renderRooms();
    return created;
  }
}

async function joinRoomOnServer(roomId, userId) {
  try {
    const res = await fetch(`${API_BASE}/join`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room_id: roomId, user_id: userId })
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || "join failed");
    }
    const j = await res.json();
    const updated = normalizeRoom(j.room || j);
    rooms = rooms.map(r => r.id === updated.id ? updated : r);
    if (!joinedRooms.includes(updated.id)) joinedRooms.push(updated.id);
    saveLocalBackup();
    renderJoinedRooms();
    renderRooms();
    return updated;
  } catch (e) {
    showMessage("Failed to join on server, falling back to local.", true);
    if (!joinedRooms.includes(roomId)) joinedRooms.push(roomId);
    saveLocalBackup();
    renderJoinedRooms();
    return null;
  }
}

let ws;
function connectRoomsSocket() {
  const url = WS_URL;
  try {
    ws = new WebSocket(url);
  } catch (e) {
    console.warn("WebSocket connect failed", e);
    return;
  }

  ws.addEventListener("open", () => console.log("rooms socket open", url));
  ws.addEventListener("message", ev => {
    try {
      const data = JSON.parse(ev.data);
      if (!data || !data.type) return;
      console.log("rooms socket message", data);
      if (data.type === "room:new") {
        const r = normalizeRoom(data.room || data);
        if (!rooms.find(x => x.id === r.id)) rooms.unshift(r);
        saveLocalBackup();
        renderRooms();
      } else if (["room:update", "room:join", "room:leave"].includes(data.type)) {
        const r = normalizeRoom(data.room || data);
        rooms = rooms.map(x => x.id === r.id ? r : x);
        saveLocalBackup();
        renderRooms();
        renderJoinedRooms();
      }
    } catch (err) {
      console.warn("invalid rooms socket message", err);
    }
  });
  ws.addEventListener("close", () => {
    console.log("rooms socket closed — will attempt reconnect in 3s");
    setTimeout(connectRoomsSocket, 3000);
  });
  ws.addEventListener("error", e => console.warn("rooms socket error", e));
}

function wireUI() {
  $("#btn-create-room")?.addEventListener("click", async () => {
    const name = $("#room-name")?.value?.trim();
    const meet = $("#meet-time")?.value?.trim();
    const start = $("#start-location")?.value?.trim();
    const dest = $("#destination")?.value?.trim();
    if (!name || !meet || !start || !dest) return showMessage("Fill in all fields.", true);
    if (!isValidMeetTime(meet)) return showMessage("Invalid date.", true);

    const payload = {
      user_id: getCurrentUserId(),
      destination: dest,
      start_coord: [0,0],
      dest_coord: [0,0],
      max_members: 10,
      room_name: name,
      meetTime: meet,
      startLocation: start
    };

    $("#create-room-form").style.display = "none";
    showMessage("Creating room...");
    const created = await createRoomOnServer(payload);
    if (created) {
      showMessage("Room created.");
      await joinRoomOnServer(created.id, getCurrentUserId());
    } else {
      showMessage("Room created locally.", true);
    }
  });

  document.addEventListener("click", async (ev) => {
    const joinId = ev.target?.dataset?.join;
    const enterId = ev.target?.dataset?.enter;
    if (joinId) {
      ev.preventDefault();
      await joinRoomOnServer(joinId, getCurrentUserId());
      return;
    }
    if (enterId) {
      ev.preventDefault();
      const room = rooms.find(r => r.id === enterId);
      if (room) {
        localStorage.setItem("currentRoom", JSON.stringify(room.raw || room));
        // mark joined if not present
        if (!joinedRooms.includes(room.id)) {
          joinedRooms.push(room.id);
          saveLocalBackup();
        }
        window.location.href = "chat.html";
      }
      return;
    }
  });

  $("#toggle-create-room-form")?.addEventListener("click", () => {
    const form = $("#create-room-form");
    form.style.display = (form.style.display === "none" || !form.style.display) ? "block" : "none";
  });
}

function isValidMeetTime(raw) {
  if (!raw || !raw.includes("-")) return false;
  const year = raw.split("-")[0];
  if (!/^\d{4}$/.test(year)) return false;
  const d = new Date(raw);
  if (isNaN(d.getTime())) return false;
  const y = d.getFullYear();
  return y >= 2020 && y <= 2100;
}

(async function init() {
  loadLocalBackup();
  connectRoomsSocket();
  await fetchRoomsFromServer();
  wireUI();
  renderJoinedRooms();
  renderRooms();
})();
