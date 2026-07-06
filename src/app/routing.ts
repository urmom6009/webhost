import { useEffect, useState } from "react";
import type { NavItem } from "../content";

export const routeMap: Record<string, string> = {
  "/": "home",
  "/videos": "videos",
  "/videos/customs": "customs",
  "/videos/main": "main",
  "/findom": "findom",
  "/findom/auto-drains": "auto-drains",
  "/findom/contracts": "contracts",
  "/about": "about",
  "/contact": "contact",
  "/privacy": "privacy"
};

export function usePathname() {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const handleLocation = () => setPath(window.location.pathname);
    window.addEventListener("popstate", handleLocation);
    window.addEventListener("hh88:navigate", handleLocation);
    return () => {
      window.removeEventListener("popstate", handleLocation);
      window.removeEventListener("hh88:navigate", handleLocation);
    };
  }, []);

  return path;
}



export function navigateTo(href: string) {
  if (href === window.location.pathname) {
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  window.history.pushState({}, "", href);
  window.dispatchEvent(new Event("hh88:navigate"));
  window.scrollTo({ top: 0, behavior: "instant" });
}



export function routeSection(path: string): NavItem["section"] {
  if (path.startsWith("/videos")) return "videos";
  if (path.startsWith("/findom")) return "findom";
  if (path === "/about" || path === "/contact" || path === "/privacy") return "about";
  return "home";
}



