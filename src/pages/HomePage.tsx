import { ChevronRight, Play } from "lucide-react";
import { navigateTo } from "../app/routing";

export function HomePage() {
  return (
    <section className="hero home-hero page-shell">
      <div className="hero-frame">
        <div className="hero-copy-block">
          <h1>
            <span>Pressure Engine</span>
            HH88TRANCE
            <span>Obey the Loop</span>
          </h1>
          <p className="hero-copy">
            Adult hypno, ASMR, heavy trance, and findom files built around pressure, repetition, fixation, and ritual surrender. Cold
            visuals, relentless audio, and command-driven pacing for viewers who want the file to take over.
          </p>
          <div className="button-row">
            <button className="primary-button" onClick={() => navigateTo("/videos")}>
              <Play size={18} /> Preview/Buy Videos
            </button>
            <button className="secondary-button" onClick={() => navigateTo("/contact")}>
              Contact HH88TRANCE <ChevronRight size={18} />
            </button>
          </div>
        </div>
        <div className="hero-signal" aria-hidden="true">
          <span>Findom</span>
          <span>Hypno</span>
          <span>Trance</span>
          <span>ASMR</span>
          <span>Control Files</span>
        </div>
      </div>
    </section>
  );
}


