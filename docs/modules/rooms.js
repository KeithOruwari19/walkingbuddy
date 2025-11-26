const BACKEND_HOST = "https://cp317-group-18-project.onrender.com";
const API_BASE = `${BACKEND_HOST}/api/rooms`;
const USER_API_BASE = `${BACKEND_HOST}/api/users`;
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
  return u.user_id || u.id || u.userId || u.email || null;
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

  return {
    id: r.room_id || r.id || r.uuid || r.roomId || String(r.id || r.room_id || Date.now()),
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
    const room = rooms.find(r => (r.id === roomId || r.name === roomId));
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
  renderJoinedRooms();
  renderRooms();
}

function saveLocalBackup() {
  try {
    localStorage.setItem("rooms", JSON.stringify(rooms.map(r=>r.raw || r)));
    localStorage.setItem("joinedRooms", JSON.stringify(joinedRooms));
  } catch (e) {}
}

const userCache = new Map();

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, { credentials: 'include', ...opts });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`Fetch ${url} failed: ${res.status} ${res.statusText} ${txt}`);
  }
  return res.json();
}

async function batchFetchUsers(uids) {
  if (!Array.isArray(uids) || uids.length === 0) return {};

  try {
    const body = JSON.stringify(uids);
    const json = await fetchJSON(`${USER_API_BASE}/batch`, { method: 'POST', body, headers: { 'Content-Type': 'application/json' } });
    const result = {};
    for (const uid of uids) {
      const entry = json && (json[uid] || null);
      if (!entry) { result[uid] = null; continue; }
      if (typeof entry === 'string') result[uid] = entry;
      else result[uid] = entry.name || entry.displayName || null;
    }
    return result;
  } catch (err) {
    const map = {};
    await Promise.all(uids.map(async (uid) => {
      try {
        const data = await fetchJSON(`${USER_API_BASE}/${encodeURIComponent(uid)}`);
        map[uid] = data && (data.name || data.displayName || (data.firstName ? `${data.firstName} ${data.lastName||''}`.trim() : null)) || null;
      } catch (e) {
        map[uid] = null;
      }
    }));
    return map;
  }
}

function uidToInitialsFromName(name) {
  if (!name || typeof name !== 'string') return null;
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0,2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function uidToInitials(uid) {
  if (!uid) return '??';
  if (typeof uid === 'string') {
    const clean = uid.replace(/[^a-zA-Z0-9]/g, '');
    if (clean.length <= 4) return clean.toUpperCase();
    return clean.slice(0,4).toUpperCase();
  }
  return String(uid).slice(0,4).toUpperCase();
}

async function getUserName(uid) {
  if (!uid) return 'Unknown';
  const stored = getStoredUser();
  if (stored && (stored.user_id === uid || stored.id === uid || stored.email === uid)) {
    return stored.name || stored.displayName || stored.email || uidToInitials(uid);
  }

  if (userCache.has(uid)) {
    const v = userCache.get(uid);
    if (v instanceof Promise) return v;
    return v;
  }

  const p = (async () => {
    try {
      const data = await fetchJSON(`${USER_API_BASE}/${encodeURIComponent(uid)}`);
      const name = data && (data.name || data.displayName || (data.firstName ? `${data.firstName} ${data.lastName||''}`.trim() : null));
      const final = name || uidToInitials(uid) || 'Unknown';
      userCache.set(uid, final);
      return final;
    } catch (err) {
      const fallback = uidToInitials(uid) || 'Unknown';
      userCache.set(uid, fallback);
      return fallback;
    }
  })();

  userCache.set(uid, p);
  return p;
}

async function resolveNamesForRooms(roomArray) {
  if (!Array.isArray(roomArray) || roomArray.length === 0) return;
  const uids = new Set();
  for (const r of roomArray) {
    if (r && r.creatorId && !r.creatorName) uids.add(String(r.creatorId));
  }
  if (!uids.size) return;

  const uidList = Array.from(uids);
  const map = await batchFetchUsers(uidList);

  for (const uid of uidList) {
    const name = map[uid] || null;
    if (name) userCache.set(uid, name);
    else if (!userCache.has(uid)) userCache.set(uid, uidToInitials(uid));
  }

  for (const r of roomArray) {
    if (r && r.creatorId && !r.creatorName) {
      const found = userCache.get(String(r.creatorId));
      r.creatorName = (found instanceof Promise) ? await found : (found || uidToInitials(r.creatorId));
    }
  }
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

    await resolveNamesForRooms(serverRooms);

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
    const currentUser = getStoredUser();
    if (currentUser) {
      roomPayload.user_id = roomPayload.user_id || (currentUser.id || currentUser.user_id || currentUser.email || currentUser.name);
      roomPayload.creator_name = roomPayload.creator_name || (currentUser.name || currentUser.email || null);
    }
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

    const uid = getCurrentUserId();
    if ((!created.creatorName || created.creatorName === null) && created.creatorId && uid && String(created.creatorId) === String(uid)) {
      created.creatorName = getCurrentUserName();
    }

    await resolveNamesForRooms([created]);

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
      destination: roomPayload.destination || "",
      creatorId: getCurrentUserId(),
      creatorName: getCurrentUserName()
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
      let bodyText = "";
      try { bodyText = await res.text(); } catch (e) { bodyText = "<failed to read body>"; }
      console.warn(`joinRoomOnServer: server responded ${res.status} ${res.statusText} — ${bodyText}`);
      throw new Error(`Join failed: ${res.status} ${res.statusText} - ${bodyText}`);
    }

    let j;
    try { j = await res.json(); } catch (err) {
      console.warn("joinRoomOnServer: response was not JSON, using empty room fallback", err);
      j = {};
    }

    const updated = normalizeRoom(j.room || j);
    await resolveNamesForRooms([updated]);
    rooms = rooms.map(r => r.id === updated.id ? updated : r);
    if (!joinedRooms.includes(updated.id)) joinedRooms.push(updated.id);
    saveLocalBackup();
    renderJoinedRooms();
    renderRooms();
    try { localStorage.setItem("currentRoom", JSON.stringify(j.room || j)); } catch {}
    return updated;
  } catch (e) {
    console.warn("joinRoomOnServer: exception", e);
    showMessage("Failed to join on server, falling back to local.", true);
    if (!joinedRooms.includes(roomId)) joinedRooms.push(roomId);
    saveLocalBackup();
    renderJoinedRooms();
    return null;
  }
}

async function deleteRoomOnServer(roomId) {
  const existingRoom = rooms.find(r => r.id === roomId);
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

    rooms = rooms.filter(r => r.id !== roomId);
    joinedRooms = joinedRooms.filter(n => n !== roomId && n !== String(roomId));
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
        if ((!r.creatorName || r.creatorName === null) && r.creatorId && getCurrentUserId() && String(r.creatorId) === String(getCurrentUserId())) {
          r.creatorName = getCurrentUserName();
        }
        if (!rooms.find(x => x.id === r.id)) rooms.unshift(r);
        resolveNamesForRooms([r]).then(() => {
          saveLocalBackup();
          renderRooms();
        }).catch(() => { saveLocalBackup(); renderRooms(); });
      } else if (data.type === "room:delete") {
        const deletedId = (data.room && (data.room.room_id || data.room.id)) || data.room_id || data.room;
        rooms = rooms.filter(x => x.id !== deletedId);
        joinedRooms = joinedRooms.filter(n => n !== deletedId && n !== String(deletedId));
        saveLocalBackup();
        renderRooms();
        renderJoinedRooms();
      } else if (["room:update", "room:join", "room:leave"].includes(data.type)) {
        const r = normalizeRoom(data.room || data);
        // update or insert
        const idx = rooms.findIndex(x => x.id === r.id);
        if (idx >= 0) rooms[idx] = r; else rooms.unshift(r);
        resolveNamesForRooms([r]).then(() => {
          saveLocalBackup();
          renderRooms();
          renderJoinedRooms();
        }).catch(() => { saveLocalBackup(); renderRooms(); renderJoinedRooms(); });
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
      showMessage("Room created locally.", true);
    }
  });

  document.addEventListener("click", async (ev) => {
    const actionable = ev.target.closest
      ? ev.target.closest('button[data-join], button[data-enter], button[data-leave], button[data-delete], [data-join], [data-enter], [data-leave], [data-delete]')
      : ev.target;

    if (!actionable) return;

    const joinId = actionable.dataset?.join;
    const enterId = actionable.dataset?.enter;
    const deleteId = actionable.dataset?.delete;
    const leaveId = actionable.dataset?.leave;

    if (enterId || joinId || leaveId || deleteId) {
      console.log('rooms UI click ->', { joinId, enterId, leaveId, deleteId, clicked: actionable.tagName, target: ev.target });
    }

    if (joinId) {
      ev.preventDefault();
      await joinRoomOnServer(joinId, getCurrentUserId());
      return;
    }
    if (enterId) {
      ev.preventDefault();
      const room = rooms.find(r => r.id === enterId);
      if (room) {
        try { localStorage.setItem("currentRoom", JSON.stringify(room.raw || room)); } catch {}
        if (!joinedRooms.includes(room.id)) {
          joinedRooms.push(room.id);
          saveLocalBackup();
        }
        setTimeout(() => { window.location.href = "chat.html"; }, 10);
      }
      return;
    }
    if (leaveId) {
      ev.preventDefault();
      joinedRooms = joinedRooms.filter(n => n !== leaveId && n !== String(leaveId));
      saveLocalBackup();
      renderJoinedRooms();
      renderRooms();
      const ok = await leaveRoomOnServer(leaveId, getCurrentUserId());
      if (!ok) showMessage('Failed to leave room on server. Removed locally.', true);
      return;
    }
    if (deleteId) {
      ev.preventDefault();
      const existing = rooms.find(r => r.id === deleteId);
      rooms = rooms.filter(r => r.id !== deleteId);
      joinedRooms = joinedRooms.filter(n => n !== deleteId);
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
