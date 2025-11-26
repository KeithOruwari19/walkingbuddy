const BACKEND_HOST = "https://cp317-group-18-project-onrender.com";
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
  } catch { return null; }
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

function normalizeId(id) {
  if (id === null || id === undefined) return null;
  return String(id);
}

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

  const rawId = (r.room_id ?? r.id ?? r.uuid ?? r.roomId ?? (r.raw && (r.raw.room_id ?? r.raw.id ?? r.raw.uuid))) ?? null;
  const canonicalId = rawId != null ? String(rawId) : `local-${Date.now()}`;

  return {
    id: canonicalId,
    name: r.name || r.room_name || r.destination || r.title || `Room ${rawId || ''}`,
    members: Array.isArray(r.members) ? r.members.length : (r.members ?? (Array.isArray(r.users) ? r.users.length : (r.count ?? 0))),
    meetTime: meet,
    startLocation: r.startLocation || r.start_location || r.start || r.startAddr || '',
    destination: r.destination || r.dest || r.to || '',
    creatorId: creatorId,
    creatorName: creatorName,
    raw: r
  };
}

function roomMatches(a, b) {
  if (!a || !b) return false;
  const aid = normalizeId(a.id);
  const bid = normalizeId(b.id);
  if (aid && bid && aid === bid) return true;

  const aRaw = a.raw || {};
  const bRaw = b.raw || {};
  const aRoomId = normalizeId(aRaw.room_id || aRaw.id || aRaw.uuid);
  const bRoomId = normalizeId(bRaw.room_id || bRaw.id || bRaw.uuid);
  if (aRoomId && bRoomId && aRoomId === bRoomId) return true;

  const aSig = `${normalizeId(a.name)}|${normalizeId(a.creatorId)}`;
  const bSig = `${normalizeId(b.name)}|${normalizeId(b.creatorId)}`;
  if (aSig && bSig && aSig === bSig) return true;

  return false;
}

function ensureRoomInserted(newRoom, { toTop = false } = {}) {
  if (!newRoom || !newRoom.id) return;
  const out = [];
  let seen = false;
  for (const r of rooms) {
    if (roomMatches(r, newRoom)) {
      if (!seen) { out.push(newRoom); seen = true; }
    } else out.push(r);
  }
  if (!seen) {
    if (toTop) out.unshift(newRoom); else out.push(newRoom);
  } else if (toTop) {
    const idx = out.findIndex(x => roomM
