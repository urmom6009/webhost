import { useState } from "react";

export function AgeGate() {
  const [accepted, setAccepted] = useState(() => localStorage.getItem("hh88-age-ok") === "true");

  if (accepted) return null;

  return (
    <div className="age-gate" role="dialog" aria-modal="true" aria-labelledby="age-title">
      <div className="age-panel">
        <p className="micro-label">Adult content notice</p>
        <h2 id="age-title">18+ Entry Required</h2>
        <p>
          This site is intended for adults and contains adult-oriented audio, video, and financial devotion themes. Enter only if you are
          at least 18 years old and allowed to view this material where you live.
        </p>
        <div className="age-actions">
          <button
            className="primary-button"
            onClick={() => {
              localStorage.setItem("hh88-age-ok", "true");
              setAccepted(true);
            }}
          >
            I am 18+
          </button>
          <a className="secondary-button" href="https://www.google.com">
            Leave
          </a>
        </div>
      </div>
    </div>
  );
}



