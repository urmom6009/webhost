import { useState } from "react";
import { aboutAccordions } from "../content";

export function AboutPage() {
  return (
    <section className="page-shell about-page">
      <h1>HH88TRANCE</h1>
      <p className="subhead">Findom | Hypno | Trance | ASMR | Music | Ritual | Devotion | Control</p>
      <div className="text-card">
        <p>
          HH88TRANCE is an adult hypnotic video and audio creator specializing in findom, hypno, trance, and ASMR files with dark,
          repetitive visuals, controlled pacing, and an intentionally severe tone.
        </p>
        <p>Work is designed around immersion, pressure, repetition, and a controlled adult fantasy experience that feels heavier than casual entertainment.</p>
        <p>On this site you will find:</p>
        <Accordion />
      </div>
      <h2 className="section-title">Why the Files Work</h2>
      <div className="text-card two-column">
        <p>Repetition, contrast, music, and visual fixation create a focused rhythm that makes each file feel ritualized.</p>
        <p>Custom commissions let clients request structure, tone, pacing, and themes while keeping delivery and payment off-site.</p>
      </div>
    </section>
  );
}



function Accordion() {
  const [open, setOpen] = useState(0);
  return (
    <div className="accordion">
      {aboutAccordions.map((item, index) => (
        <div className="accordion-item" key={item.title}>
          <button onClick={() => setOpen(open === index ? -1 : index)} aria-expanded={open === index}>
            {item.title}
            <span aria-hidden="true">⌄</span>
          </button>
          {open === index ? <p>{item.body}</p> : null}
        </div>
      ))}
    </div>
  );
}



