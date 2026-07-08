import { navigateTo } from "../app/routing";

export function NotFoundPage() {
  return (
    <section className="page-shell centered-card-page">
      <div className="status-card">
        <h1>404: Page Not Found</h1>
        <p>The page requested can't be found.</p>
        <button className="primary-button" onClick={() => navigateTo("/")}>
          Get entranced.
        </button>
      </div>
    </section>
  );
}



