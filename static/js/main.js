// ── Toast notification helper ───
/**
 * Show a small popup notification.
 * @param {string} message  - text to display
 * @param {'success'|'error'|'info'} type
 */
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const icons = { success: "✅", error: "❌", info: "ℹ️" };

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || "💬"}</span><span>${message}</span>`;
  container.appendChild(toast);

  // Auto-remove after 3.5 seconds
  setTimeout(() => toast.remove(), 3500);
}

// ── Auth helpers ───
/**
 * Fetch the current logged-in user from the server.
 * Returns { logged_in, user_id, username } or { logged_in: false }
 */
async function getCurrentUser() {
  try {
    const res = await fetch("/me");
    return await res.json();
  } catch {
    return { logged_in: false };
  }
}

/**
 * Update the navbar based on whether the user is logged in.
 */
async function initNavbar() {
  const user = await getCurrentUser();
  const navAuth = document.getElementById("nav-auth");
  if (!navAuth) return;

  if (user.logged_in) {
    navAuth.innerHTML = `
      <a href="/profile" class="btn btn-outline btn-sm">👤 ${user.username}</a>
      <a href="/logout" class="btn btn-outline btn-sm">Logout</a>
    `;
  } else {
    navAuth.innerHTML = `
      <a href="/login"  class="btn btn-outline btn-sm">Login</a>
      <a href="/signup" class="btn btn-primary btn-sm">Sign Up</a>
    `;
  }
}

// ── Like button helper ───
/**
 * Toggle a like and update the button UI.
 * @param {number} artworkId
 * @param {HTMLElement} btn  - the like button element
 */
async function toggleLike(artworkId, btn) {
  const user = await getCurrentUser();
  if (!user.logged_in) {
    showToast("Please log in to like artwork", "error");
    return;
  }

  try {
    const res  = await fetch(`/like/${artworkId}`, { method: "POST" });
    const data = await res.json();

    if (res.ok) {
      btn.querySelector(".like-count").textContent = data.like_count;
      btn.classList.toggle("liked", data.liked);
    } else {
      showToast(data.error || "Something went wrong", "error");
    }
  } catch {
    showToast("Network error", "error");
  }
}

// ── Format date helper ───
/**
 * Format an ISO date string into "Jan 5, 2025" style.
 * @param {string} isoStr
 */
function formatDate(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

// ── Build one artwork card HTML ───
/**
 * Build the HTML string for a single artwork card.
 * Used on the home page gallery and profile page.
 * @param {Object} art  - artwork data from /artworks
 */
function buildArtCard(art) {
  return `
    <div class="art-card" data-id="${art.id}">
      <img
        src="${art.image_path}"
        alt="${art.title}"
        loading="lazy"
        onclick="window.location='/artwork/${art.id}'"
      />
      <div class="art-card-body">
        <div class="art-card-title">${art.title}</div>
        <div class="art-card-meta">by ${art.username || "Unknown"} · ${formatDate(art.created_at)}</div>
      </div>
      <div class="art-card-footer">
        <button
          class="like-btn ${art.liked ? "liked" : ""}"
          onclick="toggleLike(${art.id}, this)"
          title="Like"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="${art.liked ? 'currentColor' : 'none'}">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
          <span class="like-count">${art.like_count}</span>
        </button>
        <span class="category-badge">${art.category}</span>
      </div>
    </div>
  `;
}

// Run navbar update on every page load
document.addEventListener("DOMContentLoaded", initNavbar);