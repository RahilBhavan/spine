// Apply the saved preference before painting. Blocked storage falls back to the OS.
try {
  const theme = localStorage.getItem('spine-theme');
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
} catch {}
