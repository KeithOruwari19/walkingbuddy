const BACKEND_HOST = "https://cp317-group-18-project.onrender.com";
const API_BASE = `${BACKEND_HOST}/api/rooms`;
const WS_URL = BACKEND_HOST.startsWith("https")
  ? `wss://${BACKEND_HOST.replace(/^https?:\/\//, "")}/api/rooms/ws`
  : `ws://${BACKEND_HOST.replace(/^https?:\/\//, "")}/api/rooms/ws`;

let rooms = [];
let joinedRooms = [];
let ws = null;
const $ = sel => document.querySelector(sel);

function getStoredUser() {
  try {
    const raw = localStorage.getItem("user");
    if (!raw || raw === "null") return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function getCurrentUserId() {
  const u = getStoredUser();
  if (!u) return null;
  return u.user_id || u.id || u.userId || null;
}
function getCurrentUserName() {
  const u = getStoredUser();
  if (!u) return null;
  return u.name || u.full_name || u.displayName || u.email || null;
}

function escapeHtml(s){ return String(s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function normalizeRoom(r) {
  r = r || {};
  const creatorId = r.creator_id || r.creator || r.creatorId || r.owner || r.user_id || (r.creator && (r.creator.id || r.creator.user_id)) || null;
  let creatorName = r.creator_name || (r.creator && (r.creator.name || r.creator.email)) || r.owner_name || null;

  const currentUserId = getCurrentUserId();
  if (!creatorName && creatorId && currentUserId && String(creatorId) === String(currentUserId)) {
    creatorName = getCurrentUserName() || creatorName;
  }

  const meet =
    r.meetTime ||
    r.meet_time ||
    r.meeting_time ||
    r.meet_time_iso ||
    r.meet_at ||
    r.meetingAt ||
    r.time ||
    null;

  const canonicalId = String(r.room_id || r.id || r.uuid || r.roomId || (r.raw && (r.raw.room_id || r.raw.id)) || Date.now());

  return {
    id: canonicalId,
    name: r.name || r.room_name || r.destination || r.title || `Room ${r.room_id || r.id || ''}`,
    members: Array.isArray(r.members) ? r.members.length : (r.members ?? (Array.isArray(r.users) ? r.users.length : (r.count ?? 0))),
    meetTime: meet,
    startLocation: r.startLocation || r.start_location || r.start || r.startAddr || '',
    destination: r.destination || r.dest || r.to || '',
    creatorId: creatorId,
    creatorName: creatorName,
    raw: r
  };
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
  if (!container) return;
  container.innerHTML = "";
  if (!joinedRooms.length) {
    container.innerHTML = `<p style="color:#777;font-size:14px;">You haven't joined any rooms yet.</p>`;
    return;
  }
  const currentUserId = getCurrentUserId();
  joinedRooms.forEach(roomId => {
    const room = rooms.find(r => String(r.id) === String(roomId) || String(r.name) === String(roomId));
    if (!room) return;
    const div = document.createElement("div");
    div.classList.add("room-card");
    div.dataset.roomId = room.id;
    div.innerHTML = `
      <h3 class="room-title">${escapeHtml(room.name)}</h3>
      <div class="room-meta">
        <p><strong>Meeting:</strong> ${room.meetTime ? new Date(room.meetTime).toLocaleString() : "TBD"}</p>
        <p><strong>Creator:</strong> ${escapeHtml(room.creatorName || room.creatorId || 'Unknown')}</p>
      </div>
      <button class="btn secondary" data-enter="${room.id}">Enter Chat</button>
      ${String(room.creatorId) === String(currentUserId) ? `<button class="btn outline" data-delete="${room.id}">Delete Room</button>` : ''}
    `;
    container.appendChild(div);
  });
}

function renderRooms() {
  const list = $("#room-list");
  const empty = $("#no-rooms-message");
  if (!list) return;
  if (!rooms.length) {
    if (empty) empty.style.display = "block";
    list.innerHTML = "";
    return;
  }
  if (empty) empty.style.display = "none";
  list.innerHTML = "";
  const currentUserId = getCurrentUserId();
  rooms.forEach(room => {
    const div = document.createElement("div");
    div.classList.add("room-card");
    div.dataset.roomId = room.id;
    const isCreator = room.creatorId && currentUserId && String(room.creatorId) === String(currentUserId);
    div.innerHTML = `
      <h3 class="room-title">${escapeHtml(room.name)}</h3>
      <div class="room-meta">
        <p><strong>Members:</strong> ${room.members ?? 0}</p>
        <p><strong>Meeting Time:</strong> ${room.meetTime ? new Date(room.meetTime).toLocaleString() : "TBD"}</p>
        <p><strong>Start Location:</strong> ${escapeHtml(room.startLocation || "")}</p>
        <p><strong>Destination:</strong> ${escapeHtml(room.destination || "")}</p>
        <p><strong>Creator:</strong> ${escapeHtml(room.creatorName || room.creatorId || 'Unknown')}</p>
      </div>
      <div class="room-actions">
        <button class="btn secondary" data-join="${room.id}">Join Room</button>
        ${isCreator ? `<button class="btn outline" data-delete="${room.id}">Delete Room</button>` : ''}
      </div>
    `;
    list.appendChild(div);
  });
}

function loadLocalBackup() {
  try {
    rooms = JSON.parse(localStorage.getItem("rooms") || "[]").map(normalizeRoom);
    joinedRooms = JSON.parse(localStorage.getItem("joinedRooms") || "[]");
  } catch (e) {
    rooms = []; joinedRooms = [];
  }
  dedupeRooms();
  dedupeJoinedRooms();
  renderJoinedRooms();
  renderRooms();
}

function saveLocalBackup() {
  try {
    localStorage.setItem("rooms", JSON.stringify(rooms.map(r=>r.raw || r)));
    localStorage.setItem("joinedRooms", JSON.stringify(joinedRooms));
  } catch (e) {}
}

function dedupeRooms() {
  const seen = new Set();
  const out = [];
  for (const r of rooms) {
    const id = String(r.id || "");
    if (!id) continue;
    if (!seen.has(id)) {
      seen.add(id);
      out.push(r);
    }
  }
  rooms = out;
}

function dedupeJoinedRooms() {
  joinedRooms = Array.from(new Set((joinedRooms || []).map(x => String(x))));
}

function upsertRoom(r) {
  if (!r) return;
  const normalized = normalizeRoom(r);
  const idx = rooms.findIndex(x => String(x.id) === String(normalized.id));
  if (idx >= 0) {
    rooms[idx] = normalized;
  } else {
    rooms.unshift(normalized);
  }
  dedupeRooms();
}

async function fetchRoomsFromServer() {
  try {
    const res = await fetch(`${API_BASE}/list`, { credentials: "include" });
    if (!res.ok) throw new Error("Failed to fetch rooms");
    const j = await res.json();
    const serverRooms = Array.isArray(j.rooms) ? j.rooms.map(normalizeRoom) : [];
    const userId = getCurrentUserId();
    const userName = getCurrentUserName();
    serverRooms.forEach(r => {
      if ((!r.creatorName || r.creatorName === null) && r.creatorId && userId && String(r.creatorId) === String(userId)) {
        r.creatorName = userName || r.creatorName;
      }
    });
    rooms = serverRooms;
    dedupeRooms();
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
  const createBtn = document.querySelector("#btn-create-room");
  if (createBtn) createBtn.disabled = true;

  try {
    const currentUser = getStoredUser();
    if (currentUser) {
      const explicitId = currentUser.id || currentUser.user_id || currentUser.userId || null;
      if (explicitId) {
        roomPayload.user_id = roomPayload.user_id || explicitId;
      }
      roomPayload.creator_name = roomPayload.creator_name || (currentUser.name || currentUser.email || null);
    }

    const res = await fetch(`${API_BASE}/create`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(roomPayload)
    });

    const text = await res.text().catch(()=>"");
    let j = null;
    try { j = text ? JSON.parse(text) : null; } catch(e){ j = null; }

    if (!res.ok) {
      const possible = j && (j.room || j) ? (j.room || j) : null;
      if (possible && (possible.room_id || possible.id)) {
        upsertRoom(possible);
        if (!joinedRooms.includes(String(possible.room_id || possible.id))) joinedRooms.push(String(possible.room_id || possible.id));
        dedupeJoinedRooms();
        saveLocalBackup();
        renderJoinedRooms();
        renderRooms();
        try { localStorage.setItem("currentRoom", JSON.stringify((possible.raw || possible))); } catch {}
        return normalizeRoom(possible);
      }
      const errText = (j && (j.detail || j.message)) || text || `${res.status} ${res.statusText}`;
      showMessage("Failed to create room on server.", true);
      throw new Error(`Create failed: ${errText}`);
    }

    const roomObj = j && (j.room || j) ? (j.room || j) : null;
    if (!roomObj) {
      showMessage("Server did not return created room.", true);
      throw new Error("Server did not return created room");
    }

    upsertRoom(roomObj);
    if (!joinedRooms.includes(String(roomObj.room_id || roomObj.id))) joinedRooms.push(String(roomObj.room_id || roomObj.id));
    dedupeJoinedRooms();

    saveLocalBackup();
    renderJoinedRooms();
    renderRooms();
    try { localStorage.setItem("currentRoom", JSON.stringify(roomObj.raw || roomObj)); } catch {}
    return normalizeRoom(roomObj);
  } catch (e) {
    console.warn("createRoomOnServer error:", e);
    return null;
  } finally {
    if (createBtn) createBtn.disabled = false;
  }
}


async function joinRoomOnServer(roomId, userId) {
  try {
    const body = { room_id: roomId };
    if (userId) {
      body.user_id = userId;
    }

    const res = await fetch(`${API_BASE}/join`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    const text = await res.text().catch(()=>"");
    let j = null;
    try { j = text ? JSON.parse(text) : null; } catch(e){ j = null; }

    if (!res.ok) {
      const errMsg = (j && (j.detail || j.message)) || text || `HTTP ${res.status} ${res.statusText}`;
      throw new Error(errMsg);
    }

    const updated = normalizeRoom((j && (j.room || j)) ? (j.room || j) : j);
    upsertRoom(updated.raw || updated);
    if (!joinedRooms.includes(String(updated.id))) joinedRooms.push(String(updated.id));
    dedupeJoinedRooms();
    saveLocalBackup();
    renderJoinedRooms();
    renderRooms();
    try { localStorage.setItem("currentRoom", JSON.stringify(j.room || j)); } catch {}
    return updated;
  } catch (e) {
    showMessage("Failed to join on server.", true);
    console.warn("joinRoomOnServer error:", e);
    return null;
  }
}


async function deleteRoomOnServer(roomId) {
  try {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(roomId)}`, {
      method: 'DELETE',
      credentials: 'include'
    });

    const text = await res.text();
    let body = null;
    try { body = JSON.parse(text); } catch(e) { body = text; }

    if (!res.ok) {
      const errMsg = (body && body.detail) || (body && body.message) || (typeof body === 'string' ? body : `HTTP ${res.status}`);
      showMessage(`Failed to delete room: ${errMsg}`, true);
      console.warn('delete failed', res.status, body);
      return false;
    }

    rooms = rooms.filter(r => String(r.id) !== String(roomId));
    joinedRooms = joinedRooms.filter(n => String(n) !== String(roomId));
    dedupeRooms();
    dedupeJoinedRooms();
    saveLocalBackup();
    renderRooms();
    renderJoinedRooms();
    return true;
  } catch (e) {
    showMessage('Network error while deleting room', true);
    console.warn('delete exception', e);
    return false;
  }
}

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
        // update-or-insert
        upsertRoom(r.raw || r);
        saveLocalBackup();
        renderRooms();
      } else if (data.type === "room:delete") {
        const deletedId = String((data.room && (data.room.room_id || data.room.id)) || data.room_id || data.room);
        rooms = rooms.filter(x => String(x.id) !== deletedId);
        joinedRooms = joinedRooms.filter(n => String(n) !== deletedId && n !== String(deletedId));
        dedupeRooms();
        dedupeJoinedRooms();
        saveLocalBackup();
        renderRooms();
        renderJoinedRooms();
      } else if (["room:update", "room:join", "room:leave"].includes(data.type)) {
        const r = normalizeRoom(data.room || data);
        upsertRoom(r.raw || r);
        if (data.type === "room:join") {
          if (!joinedRooms.includes(String(r.id))) joinedRooms.push(String(r.id));
        } else if (data.type === "room:leave") {
          joinedRooms = joinedRooms.filter(n => String(n) !== String(r.id));
        }
        dedupeJoinedRooms();
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
    if (!name || !start || !dest) return showMessage("Fill in name/start/destination.", true);
    if (meet && !isValidMeetTime(meet)) return showMessage("Invalid date.", true);

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
      showMessage("Room creation failed.", true);
    }
  });

  document.addEventListener("click", async (ev) => {
    const joinId = ev.target?.dataset?.join;
    const enterId = ev.target?.dataset?.enter;
    const deleteId = ev.target?.dataset?.delete;
    if (joinId) {
      ev.preventDefault();
      await joinRoomOnServer(joinId, getCurrentUserId());
      return;
    }
    if (enterId) {
      ev.preventDefault();
      const room = rooms.find(r => String(r.id) === String(enterId));
      if (room) {
        localStorage.setItem("currentRoom", JSON.stringify(room.raw || room));
        if (!joinedRooms.includes(String(room.id))) {
          joinedRooms.push(String(room.id));
          dedupeJoinedRooms();
          saveLocalBackup();
        }
        window.location.href = "chat.html";
      }
      return;
    }
    if (deleteId) {
      ev.preventDefault();
      rooms = rooms.filter(r => String(r.id) !== String(deleteId));
      joinedRooms = joinedRooms.filter(n => String(n) !== String(deleteId));
      dedupeRooms();
      dedupeJoinedRooms();
      saveLocalBackup();
      renderRooms();
      renderJoinedRooms();
      const ok = await deleteRoomOnServer(deleteId);
      if (!ok) showMessage('Failed to delete room on server.', true);
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
  const AUTH_WAIT_MS = 2000;
  function getLocalUserSafe() {
    try { return JSON.parse(localStorage.getItem("user") || "null"); } catch { return null; }
  }

  const authReady = new Promise((resolve) => {
    const existing = getLocalUserSafe();
    if (existing) { resolve(existing); return; }

    function onStorage(e) {
      if (e.key === "user") {
        window.removeEventListener("storage", onStorage);
        window.removeEventListener("auth:update", onAuthUpdate);
        try { resolve(e.newValue ? JSON.parse(e.newValue) : null); } catch { resolve(null); }
      }
    }
    function onAuthUpdate(evt) {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("auth:update", onAuthUpdate);
      resolve(evt.detail ?? getLocalUserSafe());
    }
    window.addEventListener("storage", onStorage);
    window.addEventListener("auth:update", onAuthUpdate);
    setTimeout(() => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("auth:update", onAuthUpdate);
      resolve(getLocalUserSafe());
    }, AUTH_WAIT_MS);
  });

  const authUser = await authReady;

  if (!authUser) {
    window.location.href = "login.html";
    return;
  }

  loadLocalBackup();
  connectRoomsSocket();
  await fetchRoomsFromServer();
  wireUI();
  renderJoinedRooms();
  renderRooms();
})();
