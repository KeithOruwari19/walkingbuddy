// Get rooms from localStorage or set default
let rooms = JSON.parse(localStorage.getItem("rooms")) || [];

// Render the rooms
function renderRooms() {
  const roomList = document.getElementById("room-list");
  const noRoomsMessage = document.getElementById("no-rooms-message");

  if (rooms.length === 0) {
    noRoomsMessage.style.display = "block"; // Show "No rooms" message
  } else {
    noRoomsMessage.style.display = "none"; // Hide the "no rooms" message
    roomList.innerHTML = ""; // Clear the list before re-rendering

    rooms.forEach(room => {
      const roomCard = document.createElement("div");
      roomCard.classList.add("room-card");

      roomCard.innerHTML = `
        <h3 class="room-title">${room.name}</h3>
        <div class="room-meta">
          <p><strong>Members:</strong> ${room.members}</p>
          <p><strong>Meeting Time:</strong> ${new Date(room.meetTime).toLocaleString()}</p>
          <p><strong>Start Location:</strong> ${room.startLocation}</p>
          <p><strong>Destination:</strong> ${room.destination}</p>
        </div>
        <button class="btn secondary" onclick="joinRoom('${room.name}')">Join Room</button>
        <button class="btn outline" onclick="deleteRoom('${room.name}')">Delete Room</button>
      `;

      roomList.appendChild(roomCard);
    });
  }
}

// Handle room creation
document.getElementById("btn-create-room").addEventListener("click", function() {
  const roomName = document.getElementById("room-name").value.trim();
  const meetTime = document.getElementById("meet-time").value;
  const startLocation = document.getElementById("start-location").value.trim();
  const destination = document.getElementById("destination").value.trim();

  // Form validation
  if (!roomName || !meetTime || !startLocation || !destination) {
    alert("Please fill in all fields.");
    return;
  }

  // Create new room object
  const newRoom = {
    name: roomName,
    meetTime: meetTime,
    startLocation: startLocation,
    destination: destination,
    members: 1, // Start with 1 member (the creator)
  };

  // Add the new room to rooms array
  rooms.push(newRoom);

  // Save the updated rooms list to localStorage
  localStorage.setItem("rooms", JSON.stringify(rooms));

  // Reload the rooms list
  renderRooms();

  // Hide the form after creating room
  document.getElementById("create-room-form").style.display = "none";
});

// Handle room joining
function joinRoom(roomName) {
  const room = rooms.find(r => r.name === roomName);
  if (room) {
    room.members += 1; // Increase member count when joining

    // Update rooms in localStorage
    localStorage.setItem("rooms", JSON.stringify(rooms));

    // Save the current room data for the user (can be used in the chat page)
    localStorage.setItem("currentRoom", JSON.stringify(room));

    // Redirect to the chat page
    window.location.href = "chat.html";
  }
}

// Handle room deletion
function deleteRoom(roomName) {
  const roomIndex = rooms.findIndex(r => r.name === roomName);
  if (roomIndex > -1) {
    rooms.splice(roomIndex, 1); // Remove the room from the list

    // Update rooms in localStorage
    localStorage.setItem("rooms", JSON.stringify(rooms));

    // Re-render the rooms list
    renderRooms();
  }
}

// Render rooms on page load
renderRooms();
