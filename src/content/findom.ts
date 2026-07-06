import { ClipboardSignature, WalletCards } from "lucide-react";
import type { ComponentType } from "react";
import type { DrainPlan } from "./types";

export const drainPlans: DrainPlan[] = [
  {
    name: "Drip Drain",
    price: "$2.99",
    cadence: "/ Week",
    description: "Slow recurring tribute that keeps the ritual active week after week."
  },
  {
    name: "Good Boy Drain",
    price: "$4.99",
    cadence: "/ Week",
    description: "A steady recurring tribute for followers who want stricter commitment."
  },
  {
    name: "Devoted Drain",
    price: "$2.99",
    cadence: "/ Daily",
    description: "A daily recurring send built for consistent financial devotion."
  },
  {
    name: "Loyal Leak",
    price: "$4.99",
    cadence: "/ Daily",
    description: "A higher-frequency tribute for a more disciplined routine."
  }
];

export const findomCards: Array<{
  title: string;
  description: string;
  href: string;
  cta: string;
  Icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}> = [
  {
    title: "Auto-Drains",
    description: "Set up automated recurring tributes through external providers. This site does not collect payment details.",
    href: "/findom/auto-drains",
    cta: "Configure Drain",
    Icon: WalletCards
  },
  {
    title: "Contracts",
    description: "Review structured devotion terms and future agreement options before anything is signed.",
    href: "/findom/contracts",
    cta: "View Contracts",
    Icon: ClipboardSignature
  }
];

