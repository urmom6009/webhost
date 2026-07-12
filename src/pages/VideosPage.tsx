import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, Play, Radio, RefreshCw } from "lucide-react";
import { customVideos, mainVideos, productCatalogUrl, productPurchaseUrl, type VideoFile } from "../content";
import { navigateTo } from "../app/routing";

export function VideosLanding() {
  const catalog = useLiveCatalog();

  return (
    <section className="videos-overview page-shell">
      <h1 className="sr-only">Videos</h1>
      <CatalogStatus catalog={catalog} />
      <div className="split-cards">
        <LandingCard
          label="Custom"
          detail="Commission Files"
          count={catalog.customVideos.length}
          kind="custom"
          onClick={() => navigateTo("/videos/customs")}
        />
        <LandingCard
          label="Main"
          detail="Files"
          count={catalog.mainVideos.length}
          kind="main"
          onClick={() => navigateTo("/videos/main")}
        />
      </div>
    </section>
  );
}



export function VideoPage({ type }: { type: "custom" | "main" }) {
  const catalog = useLiveCatalog();
  const videos = type === "custom" ? catalog.customVideos : catalog.mainVideos;
  const title = type === "custom" ? "Custom Commission Files" : "Main Files";
  const alternate = type === "custom" ? "Main Files" : "Custom Commission Files";

  return (
    <section className="page-shell listing-page videos-page">
      <CatalogStatus catalog={catalog} />
      <InfoPanel
        title={title}
        copy={
          type === "custom"
            ? "Custom commission files are paid requests for individual clients or groups. Choose the pressure level, vocal approach, theme, final length up to 30 minutes, and whether the file should grind through repetition or stay tightly scripted."
            : "Main files are HH88TRANCE releases built for immersion, obedience, visual fixation, and repeat playback. Each full file is delivered in full quality through external purchase or subscription services."
        }
        strong={type === "custom" ? "Custom commission files are available to request for $200." : "All listed files are $80 unless marked otherwise."}
        count={videos.length}
      />
      {videos.length > 0 ? (
        <div className="video-grid">
          {videos.map((video) => (
            <VideoCard key={video.productSlug} video={video} />
          ))}
        </div>
      ) : (
        <EmptyVideos title={title} isLive={catalog.source === "live"} />
      )}
      <button className="sticky-switch" onClick={() => navigateTo(type === "custom" ? "/videos/main" : "/videos/customs")}>
        <ChevronLeft size={18} />
        View {alternate}
      </button>
    </section>
  );
}



type CatalogProduct = {
  slug: string;
  title: string;
  description?: string | null;
  preview_caption?: string | null;
  price_cents: number;
  currency: string;
  updated_at?: string | null;
};

type CatalogResponse = {
  products: CatalogProduct[];
  count: number;
};

type LiveCatalog = {
  customVideos: VideoFile[];
  mainVideos: VideoFile[];
  source: "static" | "live";
  status: "syncing" | "live" | "offline";
  total: number;
  lastUpdated?: Date;
};

const staticVideos = [...customVideos, ...mainVideos];
const staticBySlug = new Map(staticVideos.map((video) => [video.productSlug, video]));

function useLiveCatalog(): LiveCatalog {
  const liveCatalogDisabled = import.meta.env.MODE === "test" || typeof fetch !== "function";
  const [remoteProducts, setRemoteProducts] = useState<CatalogProduct[] | null>(null);
  const [status, setStatus] = useState<LiveCatalog["status"]>(liveCatalogDisabled ? "offline" : "syncing");
  const [lastUpdated, setLastUpdated] = useState<Date | undefined>();

  useEffect(() => {
    if (liveCatalogDisabled) return;

    let mounted = true;
    let controller: AbortController | undefined;

    const sync = async () => {
      controller?.abort();
      controller = new AbortController();

      try {
        const response = await fetch(productCatalogUrl(), {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error(`catalog returned ${response.status}`);

        const catalog = (await response.json()) as CatalogResponse;
        if (!mounted) return;
        setRemoteProducts(Array.isArray(catalog.products) ? catalog.products : []);
        setStatus("live");
        setLastUpdated(new Date());
      } catch (error) {
        if (!mounted || (error instanceof DOMException && error.name === "AbortError")) return;
        setStatus("offline");
      }
    };

    const syncCatalog = () => {
      void sync();
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") void sync();
    };

    void sync();
    const interval = window.setInterval(sync, 15000);
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", syncCatalog);

    return () => {
      mounted = false;
      controller?.abort();
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", syncCatalog);
    };
  }, [liveCatalogDisabled]);

  return useMemo(() => {
    if (remoteProducts === null) {
      return {
        customVideos,
        mainVideos,
        source: "static",
        status,
        total: customVideos.length + mainVideos.length,
        lastUpdated,
      };
    }

    const liveVideos = remoteProducts.map(productToVideo);
    const custom = liveVideos.filter((video) => video.kind === "custom");
    const main = liveVideos.filter((video) => video.kind === "main");

    return {
      customVideos: custom,
      mainVideos: main,
      source: "live",
      status,
      total: liveVideos.length,
      lastUpdated,
    };
  }, [lastUpdated, remoteProducts, status]);
}

function productToVideo(product: CatalogProduct): VideoFile {
  const existing = staticBySlug.get(product.slug);
  const kind = existing?.kind ?? productKind(product);
  const summary = product.preview_caption || product.description;

  return {
    title: product.title || existing?.title || product.slug,
    creator: existing?.creator ?? "HH88TRANCE",
    meta: summary ? [summary] : existing?.meta ?? ["Active catalog file"],
    duration: existing?.duration,
    price: formatCatalogPrice(product.price_cents, product.currency),
    kind,
    visual: existing?.visual ?? product.title ?? product.slug,
    productSlug: product.slug,
  };
}

function productKind(product: CatalogProduct): VideoFile["kind"] {
  const value = `${product.slug} ${product.title}`.toLowerCase();
  return value.includes("custom") ? "custom" : "main";
}

function formatCatalogPrice(priceCents: number, currency: string) {
  const amount = Number.isFinite(priceCents) ? priceCents / 100 : 0;
  const normalizedCurrency = currency.toUpperCase();
  if (normalizedCurrency === "USD") return `$${amount.toFixed(2)}`;
  return `${amount.toFixed(2)} ${normalizedCurrency}`;
}

function LandingCard({
  label,
  detail,
  count,
  kind,
  onClick,
}: {
  label: string;
  detail: string;
  count: number;
  kind: VideoFile["kind"];
  onClick: () => void;
}) {
  return (
    <button className={`landing-card ${kind}-card`} onClick={onClick}>
      <span>{label}</span>
      <small>{detail}</small>
      <em>{count > 0 ? `${count} available now` : "No files listed right now"}</em>
    </button>
  );
}

function CatalogStatus({ catalog }: { catalog: LiveCatalog }) {
  const label =
    catalog.status === "live" ? "Live Catalog" : catalog.status === "syncing" ? "Syncing Catalog" : "Static Fallback";
  const availability = catalog.total > 0 ? `${catalog.total} available now` : "No files are listed right now";

  return (
    <div className={`catalog-status status-${catalog.status}`} aria-live="polite">
      <div>
        <Radio size={18} />
        <span>{label}</span>
      </div>
      <strong>{availability}</strong>
      <small>{catalog.lastUpdated ? `Updated ${catalog.lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Watching for changes"}</small>
    </div>
  );
}

function InfoPanel({ title, copy, strong, count }: { title: string; copy: string; strong?: string; count: number }) {
  return (
    <div className="info-panel">
      <div className="info-heading">
        <h1>{title}</h1>
        <span>{count > 0 ? `${count} listed` : "None listed"}</span>
      </div>
      <p>
        {copy} {strong ? <strong>{strong}</strong> : null}
      </p>
    </div>
  );
}



function EmptyVideos({ title, isLive }: { title: string; isLive: boolean }) {
  return (
    <div className="empty-videos">
      <RefreshCw size={34} />
      <h2>No files are listed right now</h2>
      <p>
        {isLive
          ? `${title} will appear here automatically when active products are added in the storefront.`
          : "The live catalog is not reachable, so the page is holding the local fallback list until it can sync again."}
      </p>
    </div>
  );
}



function VideoCard({ video }: { video: VideoFile }) {
  const purchaseUrl = productPurchaseUrl(video.productSlug);

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
        <a
          className="buy-button"
          href={purchaseUrl}
          target="_blank"
          rel="noreferrer"
          aria-label={`Buy ${video.title} with Stripe`}
        >
          Buy with Stripe {video.price}
        </a>
      </div>
    </article>
  );
}
