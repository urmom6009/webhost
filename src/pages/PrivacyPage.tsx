export function PrivacyPage() {
  return (
    <section className="page-shell privacy-page">
      <div className="section-hero compact">
        <h1>Privacy Policy</h1>
        <p className="subhead">HH88TRANCE</p>
      </div>
      <p className="privacy-intro">
        Your privacy is important. This policy outlines how this static site handles personal information for purchased content, commissions, and the use of purchase links.
      </p>
      {[
        [
          "Purchases",
          "Payment processing is handled via Stripe. This site does not store card details or process payments directly."
        ],
        [
          "Commissions",
          "Commission are available by request only. As such, you may include contact information, project details, budget, and timeline expectations. Provide only the information needed to evaluate and discuss your request."
        ],
        [
          "Sends",
          "Tributes and subscription links redirect to the Stripe payment interface. Their privacy and billing terms apply upon leaving this site."
        ],
        [
          "Content",
          "The 18+ notice caches a local browser cookie for convenience and is erased automatically a few hours upon inactivity. Browsing activity is not tracked or sold to third-parties for marketing or other commerical purposes. Data obtained from the use of this site is solely used by HH88Trance for engagement analytics."
        ]
      ].map(([title, body]) => (
        <article className="text-card privacy-card" key={title}>
          <h2>{title}</h2>
          <p>{body}</p>
        </article>
      ))}
    </section>
  );
}

