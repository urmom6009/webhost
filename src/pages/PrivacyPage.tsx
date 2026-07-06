export function PrivacyPage() {
  return (
    <section className="page-shell privacy-page">
      <h1>Privacy Policy</h1>
      <p className="subhead">HH88TRANCE</p>
      <p className="privacy-intro">
        Your privacy is important. This policy outlines how this static site handles personal information for adult-oriented content,
        commissions, and external purchase links.
      </p>
      {[
        ["Purchases", "Payment processing is handled through external providers. This site does not store card details or process payments directly."],
        [
          "Commissions",
          "Commission requests may include contact information, project details, budget, and timeline. Use only the information needed to evaluate and discuss the request."
        ],
        ["Sends", "Tribute and subscription links point to third-party services. Their privacy and billing terms apply once you leave this site."],
        ["Age Gate", "The 18+ notice stores a local browser preference only. It is not sent to a server by this static site."]
      ].map(([title, body]) => (
        <article className="text-card privacy-card" key={title}>
          <h2>{title}</h2>
          <p>{body}</p>
        </article>
      ))}
    </section>
  );
}


