import { Play } from "lucide-react";
import { navigateTo } from "../app/routing";

export function HomePage() {
  return (
    <section className="hero page-shell">
      <p className="capsule">Findom | Hypno | Trance | ASMR | Control Files</p>
      <h1>
        <span>Pressure Engine</span>
        HH88TRANCE
        <span>Obey the Loop</span>
      </h1>
      <p className="hero-copy">
        Adult hypno, ASMR, heavy trance, and findom files built around pressure, repetition, fixation, and ritual surrender. Cold visuals,
        relentless audio, and command-driven pacing for viewers who want the file to take over.
      </p>
      <div className="button-row">
        <button className="primary-button" onClick={() => navigateTo("/videos")}>
          <Play size={18} /> Preview/Buy Videos
        </button>
        <button className="secondary-button" onClick={() => navigateTo("/contact")}>
          Contact HH88TRANCE
        </button>
      </div>
    </section>
  );
}



