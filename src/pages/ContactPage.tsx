import { ExternalLink, Mail } from "lucide-react";
import { contactLinks, socialLinks, type LinkItem } from "../content";

export function ContactPage() {
  return (
    <section className="page-shell contact-page">
      <h1>Links & Commissions</h1>
      <p className="subhead">Pay & Send Links | Contact Links | Custom Video Commission Form</p>
      <LinkSection title="Send Tribute Links" links={contactLinks} />
      <LinkSection title="Contact via DMs or Email" links={socialLinks} />
      <div className="text-card contact-note">
        <Mail size={22} />
        <p>
          Commission forms should include preferred style, vocal direction, video theme, length, repetition notes, budget, timeline, and any
          boundaries. Final payment and file delivery happen through external providers.
        </p>
      </div>
    </section>
  );
}



function LinkSection({ title, links }: { title: string; links: LinkItem[] }) {
  return (
    <section className="link-section">
      <h2>{title}</h2>
      <div className="link-list">
        {links.map((link) => (
          <a className="link-row" href={link.href} key={link.label} aria-disabled={link.pending}>
            <span>{link.label}</span>
            {link.pending ? <small>Pending URL</small> : null}
            <ExternalLink size={22} />
          </a>
        ))}
      </div>
    </section>
  );
}



