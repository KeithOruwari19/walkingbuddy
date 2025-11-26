(() => {
  const BACKEND_BASE = "https://cp317-group-18-project.onrender.com";

  async function verify() {
    try {
      const res = await fetch(`${BACKEND_BASE}/auth/verify`, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      console.warn('auth verify failed', e);
      return null;
    }
  }

  function buildLoggedOutNav(nav) {
    nav.innerHTML = `
      <a href="index.html" class="active">Navigation</a>
      <a href="rooms.html">Rooms</a>
      <a href="login.html">Login</a>
      <a href="signup.html">Sign Up</a>
    `;
  }

  function buildLoggedInNav(nav, user) {
    nav.innerHTML = '';
    const home = document.createElement('a');
    home.href = 'index.html';
    home.className = 'active';
    home.textContent = 'Navigation';
    nav.appendChild(home);

    const rooms = document.createElement('a');
    rooms.href = 'rooms.html';
    rooms.textContent = 'Rooms';
    nav.appendChild(rooms);

    const greet = document.createElement('span');
    greet.className = 'wb-auth-greeting';
    greet.textContent = user.name ? `Hi, ${user.name}` : 'Hi';
    greet.style.marginLeft = '8px';
    greet.style.fontWeight = '600';
    nav.appendChild(greet);

    const logout = document.createElement('a');
    logout.href = '#';
    logout.textContent = 'Logout';
    logout.style.marginLeft = '10px';
    logout.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        await fetch(`${BACKEND_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
      } catch (err) { console.warn('logout failed', err); }
      window.location.reload();
    });
    nav.appendChild(logout);
  }

  document.addEventListener('DOMContentLoaded', async () => {
    const nav = document.querySelector('.nav-links');
    if (!nav) return;

    const user = await verify();
    if (user) {
      buildLoggedInNav(nav, user);
    } else {
      buildLoggedOutNav(nav);
    }
  });
})();
