import { ChevronLeft, Play } from "lucide-react";
import { customVideos, mainVideos, type VideoFile } from "../content";
import { navigateTo } from "../app/routing";

export function VideosLanding() {
  return (
    <section className="split-cards page-shell">
      <h1 className="sr-only">Videos</h1>
      <button className="landing-card custom-card" onClick={() => navigateTo("/videos/customs")}>
        <span>Custom</span>
        <small>Commission Files</small>
      </button>
      <button className="landing-card main-card" onClick={() => navigateTo("/videos/main")}>
        <span>Main</span>
        <small>Files</small>
      </button>
    </section>
  );
}



export function VideoPage({ type }: { type: "custom" | "main" }) {
  const videos = type === "custom" ? customVideos : mainVideos;
  return (
    <section className="page-shell listing-page">
      <InfoPanel
        title={type === "custom" ? "Custom Commission Files" : "Main Files"}
        copy={
          type === "custom"
            ? "Custom commission files are paid requests for individual clients or groups. Choose the pressure level, vocal approach, theme, final length up to 30 minutes, and whether the file should grind through repetition or stay tightly scripted."
            : "Main files are HH88TRANCE releases built for immersion, obedience, visual fixation, and repeat playback. Each full file is delivered in full quality through external purchase or subscription services."
        }
        strong={type === "custom" ? "Custom commission files are available to request for $200." : "All listed files are $80 unless marked otherwise."}
      />
      <div className="video-grid">
        {videos.map((video) => (
          <VideoCard key={video.title} video={video} />
        ))}
      </div>
      <button className="sticky-switch" onClick={() => navigateTo(type === "custom" ? "/videos/main" : "/videos/customs")}>
        <ChevronLeft size={18} />
        View {type === "custom" ? "Main Files" : "Custom Commission Files"}
      </button>
    </section>
  );
}



function InfoPanel({ title, copy, strong }: { title: string; copy: string; strong?: string }) {
  return (
    <div className="info-panel">
      <h1>{title}</h1>
      <p>
        {copy} {strong ? <strong>{strong}</strong> : null}
      </p>
    </div>
  );
}



function VideoCard({ video }: { video: VideoFile }) {
  return (
    <article className="video-card">
      <div className={`video-still still-${video.kind}`}>
        <span className="price-pill">{video.price}</span>
        <span className="visual-text">{video.visual}</span>
        <div className="fake-controls">
          <Play size={16} />
          <span>0:00</span>
          <span className="control-line" />
        </div>
      </div>
      <div className="video-body">
        <h2>{video.title}</h2>
        <p className="creator">{video.creator}</p>
        {video.duration ? <span className="duration">{video.duration}</span> : null}
        <p className="meta">{video.meta.join(" | ")}</p>
        <a className="buy-button" href="#pending-video-payment" aria-label={`${video.title} payment link pending`}>
          Buy Now {video.price}
        </a>
      </div>
    </article>
  );
}



