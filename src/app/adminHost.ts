export function isAdminHost() {
  return import.meta.env.DEV && window.location.pathname === "/admin";
}

