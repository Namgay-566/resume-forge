// Runs before first paint (blocking <script> in index.html) so the page never flashes the
// wrong theme. A file, not inline: the production CSP doesn't allow inline scripts.
// Keep the key and logic in sync with src/features/theme/theme.ts.
;(function () {
  var theme = 'system'
  try {
    theme = localStorage.getItem('rf-theme') || 'system'
  } catch {
    // storage blocked: fall back to the OS setting
  }
  var dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
})()
