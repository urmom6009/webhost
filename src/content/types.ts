export type Accent = "red" | "blue" | "steel" | "amber" | "white" | "cyan";

export type NavItem = {
  label: string;
  href: string;
  section: "home" | "videos" | "findom" | "about" | "contact";
  accent: Accent;
};

export type VideoFile = {
  title: string;
  creator: string;
  meta: string[];
  price: string;
  duration?: string;
  kind: "custom" | "main";
  visual: string;
};

export type LinkItem = {
  label: string;
  href: string;
  pending?: boolean;
};

export type AccordianItem = {
  title: string;
  body: string;
};

export type DrainPlan = {
  name: string;
  price: string;
  cadence: string;
  description: string;
};

