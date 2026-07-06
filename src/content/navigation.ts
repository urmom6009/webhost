import type { NavItem } from "./types";

export const navItems: NavItem[] = [
  { label: "Home", href: "/", section: "home", accent: "red" },
  { label: "Videos", href: "/videos", section: "videos", accent: "cyan" },
  { label: "Findom", href: "/findom", section: "findom", accent: "steel" },
  { label: "About", href: "/about", section: "about", accent: "steel" },
  { label: "Contact", href: "/contact", section: "contact", accent: "amber" }
];

export const videoSubnav: NavItem[] = [
  { label: "Videos", href: "/videos", section: "videos", accent: "cyan" },
  { label: "Customs", href: "/videos/customs", section: "videos", accent: "red" },
  { label: "Main", href: "/videos/main", section: "videos", accent: "red" }
];

export const findomSubnav: NavItem[] = [
  { label: "Findom", href: "/findom", section: "findom", accent: "steel" },
  { label: "Auto-Drains", href: "/findom/auto-drains", section: "findom", accent: "red" },
  { label: "Contracts", href: "/findom/contracts", section: "findom", accent: "amber" }
];

export const aboutSubnav: NavItem[] = [
  { label: "About", href: "/about", section: "about", accent: "steel" },
  { label: "Contact", href: "/contact", section: "about", accent: "red" },
  { label: "Privacy", href: "/privacy", section: "about", accent: "steel" }
];

