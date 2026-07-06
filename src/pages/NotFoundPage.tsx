import { navigateTo } from "../app/routing";

export function NotFoundPage() {
  return (
    <section className="page-shell centered-card-page">
      <div className="status-card">
        <h1>Page Not Found</h1>
        <p>The requested page is not part of the HH88TRANCE route set.</p>
        <button className="primary-button" onClick={() => navigateTo("/")}>
          Return Home
        </button>
      </div>
    </section>
  );
}



