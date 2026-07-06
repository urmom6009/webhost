import type { LinkItem } from "./types";

export const contactLinks: LinkItem[] = [
  { label: "$2.99 forever Stripe subscription", href: "#pending-stripe-subscription", pending: true },
  { label: "Cash App", href: "#pending-cashapp", pending: true },
  { label: "Any amount Stripe send", href: "#pending-stripe-send", pending: true },
  { label: "Throne", href: "#pending-throne", pending: true },
  { label: "Patreon - unlock all full audio files", href: "#pending-patreon", pending: true }
];

export const socialLinks: LinkItem[] = [
  { label: "Main X account", href: "#pending-main-x", pending: true },
  { label: "Backup X account", href: "#pending-backup-x", pending: true },
  { label: "Email for commissions", href: "mailto:commissions@example.com", pending: true }
];

