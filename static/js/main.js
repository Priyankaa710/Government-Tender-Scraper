/**
 * Tiny toast helper. Django messages already render server-side (see
 * base.html); this is available for any future fetch()-driven interactions
 * (e.g. AJAX watchlist add/remove) that want a lightweight client-side toast.
 */
function showToast(text, kind = "success") {
  const el = document.createElement("div");
  el.className =
    "fixed bottom-5 right-5 z-50 px-4 py-2 rounded-lg shadow-lg text-sm text-white " +
    (kind === "success" ? "bg-go-600" : "bg-urgent-600");
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
