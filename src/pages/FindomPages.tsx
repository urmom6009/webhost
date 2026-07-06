import { BadgeDollarSign, ChevronLeft, FileLock2 } from "lucide-react";
import { drainPlans, findomCards } from "../content";
import { navigateTo } from "../app/routing";

export function FindomLanding() {
  return (
    <section className="page-shell findom-landing">
      <p className="capsule">Financial Domination</p>
      <h1>Submit to the Process</h1>
      <p className="lead">
        Structured tribute systems, recurring drains, and contract status pages for adult financial devotion with clear boundaries and off-site
        processing.
      </p>
      <div className="feature-grid">
        {findomCards.map(({ title, description, href, cta, Icon }) => (
          <article className="feature-card" key={title}>
            <div className="icon-box">
              <Icon size={31} />
            </div>
            <h2>{title}</h2>
            <p>{description}</p>
            <button className="primary-button small" onClick={() => navigateTo(href)}>
              {cta} <span aria-hidden="true">→</span>
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}



export function AutoDrainsPage() {
  return (
    <section className="page-shell drains-page">
      <h1>
        <span>Auto</span>
        <BadgeDollarSign size={54} />
        <em>Drains</em>
      </h1>
      <p className="drain-tagline">Automatic. Recurring. External.</p>
      <div className="drain-list">
        {drainPlans.map((plan) => (
          <article className="drain-row" key={plan.name}>
            <div>
              <h2>{plan.name}</h2>
              <p>{plan.description}</p>
            </div>
            <div className="drain-price">
              <strong>{plan.price}</strong>
              <span>{plan.cadence}</span>
              <small>External checkout pending</small>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}



export function ContractsPage() {
  return (
    <section className="page-shell centered-card-page">
      <div className="status-card">
        <div className="icon-box">
          <FileLock2 size={35} />
        </div>
        <h1>Drafting Terms</h1>
        <p>Agreement templates are currently being reviewed. No signatures, payments, or identity documents are collected on this site.</p>
        <span className="status-pill">Under Construction</span>
        <button className="secondary-button" onClick={() => navigateTo("/findom")}>
          <ChevronLeft size={18} /> Return to Findom
        </button>
      </div>
    </section>
  );
}



