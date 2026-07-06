export function isAdminHost() {
  return window.location.hostname.toLowerCase() === "admin.hh88trance.com" || (import.meta.env.DEV && window.location.pathname === "/admin");
}


