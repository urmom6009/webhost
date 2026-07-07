import { useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  Download,
  FileJson,
  FileText,
  Link2,
  Plus,
  RefreshCcw,
  Save,
  Trash2,
  Upload
} from "lucide-react";
import {
  aboutAccordions,
  contactLinks,
  customVideos,
  drainPlans,
  mainVideos,
  socialLinks,
  type AccordianItem,
  type DrainPlan,
  type LinkItem,
  type VideoFile
} from "../../content";

type AdminTab = "overview" | "videos" | "links" | "drains" | "about" | "export";

type AdminContent = {
  customVideos: VideoFile[];
  mainVideos: VideoFile[];
  contactLinks: LinkItem[];
  socialLinks: LinkItem[];
  drainPlans: DrainPlan[];
  aboutAccordions: AccordianItem[];
};

type VideoSection = "customVideos" | "mainVideos";
type LinkSection = "contactLinks" | "socialLinks";
type VideoUpdate = (...args: [VideoSection, number, Partial<VideoFile>]) => void;
type VideoSectionAction = (...args: [VideoSection]) => void;
type VideoRemove = (...args: [VideoSection, number]) => void;
type LinkUpdate = (...args: [LinkSection, number, Partial<LinkItem>]) => void;
type LinkSectionAction = (...args: [LinkSection]) => void;
type LinkRemove = (...args: [LinkSection, number]) => void;
type StringChange = (...args: [string]) => void;
type BooleanChange = (...args: [boolean]) => void;
type TabChange = (...args: [AdminTab]) => void;
type CopyAction = (...args: [string, string]) => void;

type FieldProps = {
  label: string;
  value: string;
  onChange: StringChange;
  multiline?: boolean;
  placeholder?: string;
};

type BooleanFieldProps = {
  label: string;
  checked: boolean;
  onChange: BooleanChange;
};

type VideoGroupProps = {
  title: string;
  section: VideoSection;
  videos: VideoFile[];
  update: VideoUpdate;
  add: VideoSectionAction;
  remove: VideoRemove;
};

type LinkGroupProps = {
  title: string;
  section: LinkSection;
  links: LinkItem[];
  update: LinkUpdate;
  add: LinkSectionAction;
  remove: LinkRemove;
};

type ExportPanelProps = {
  json: string;
  tsSnippet: string;
  importText: string;
  setImportText: StringChange;
  importJson: () => void;
  copy: CopyAction;
};

const STORAGE_KEY = "hh88-admin-content-v1";

const tabs: Array<{ id: AdminTab; label: string }> = [
  { id: "overview", label: "Launch" },
  { id: "videos", label: "Videos" },
  { id: "links", label: "Links" },
  { id: "drains", label: "Drains" },
  { id: "about", label: "About" },
  { id: "export", label: "Export" }
];

const defaultContent: AdminContent = {
  customVideos,
  mainVideos,
  contactLinks,
  socialLinks,
  drainPlans,
  aboutAccordions
};

function cloneContent(content: AdminContent = defaultContent): AdminContent {
  return JSON.parse(JSON.stringify(content)) as AdminContent;
}

function loadContent() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return cloneContent();
    return { ...cloneContent(), ...(JSON.parse(raw) as Partial<AdminContent>) };
  } catch {
    return cloneContent();
  }
}

function toJson(content: AdminContent) {
  return JSON.stringify(content, null, 2);
}

function quoted(value: string | undefined) {
  return JSON.stringify(value ?? "");
}

function contentTs(content: AdminContent) {
  const videos = (items: VideoFile[]) =>
    items
      .map(
        (video) => `  {
    title: ${quoted(video.title)},
    creator: ${quoted(video.creator)},
    meta: [${video.meta.map(quoted).join(", ")}],
    ${video.duration ? `duration: ${quoted(video.duration)},\n    ` : ""}price: ${quoted(video.price)},
    kind: ${quoted(video.kind)},
    visual: ${quoted(video.visual)}
  }`
      )
      .join(",\n");

  const links = (items: LinkItem[]) =>
    items.map((link) => `  { label: ${quoted(link.label)}, href: ${quoted(link.href)}${link.pending ? ", pending: true" : ""} }`).join(",\n");
  const plans = content.drainPlans
    .map(
      (plan) => `  {
    name: ${quoted(plan.name)},
    price: ${quoted(plan.price)},
    cadence: ${quoted(plan.cadence)},
    description: ${quoted(plan.description)}
  }`
    )
    .join(",\n");
  const accordions = content.aboutAccordions
    .map(
      (item) => `  {
    title: ${quoted(item.title)},
    body: ${quoted(item.body)}
  }`
    )
    .join(",\n");

  return `// Paste these array bodies into src/content.ts. Keep the imports, nav arrays, types, and findomCards/icons exports.
export const customVideos: VideoFile[] = [
${videos(content.customVideos)}
];

export const mainVideos: VideoFile[] = [
${videos(content.mainVideos)}
];

export const contactLinks: LinkItem[] = [
${links(content.contactLinks)}
];

export const socialLinks: LinkItem[] = [
${links(content.socialLinks)}
];

export const aboutAccordions: AccordianItem[] = [
${accordions}
];

export const drainPlans: DrainPlan[] = [
${plans}
];`;
}

function splitMeta(value: string) {
  return value
    .split(/[,\n|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function downloadFile(name: string, body: string, type = "application/json") {
  const blob = new Blob([body], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function summarize(content: AdminContent) {
  const allLinks = [...content.contactLinks, ...content.socialLinks];
  const pendingLinks = allLinks.filter((link) => link.pending || link.href.startsWith("#pending")).length;
  const exampleContacts = allLinks.filter((link) => link.href.includes("example.com")).length;
  const emptyVideos = [...content.customVideos, ...content.mainVideos].filter((video) => !video.title.trim() || !video.price.trim()).length;
  return {
    videoCount: content.customVideos.length + content.mainVideos.length,
    pendingLinks,
    exampleContacts,
    emptyVideos,
    ready: pendingLinks === 0 && exampleContacts === 0 && emptyVideos === 0
  };
}

function Field({
  label,
  value,
  onChange,
  multiline = false,
  placeholder
}: FieldProps) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      {multiline ? (
        <textarea value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  );
}

function BooleanField({ label, checked, onChange }: BooleanFieldProps) {
  return (
    <label className="admin-check">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export function AdminPortal() {
  const [content, setContent] = useState(loadContent);
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [importText, setImportText] = useState("");
  const [message, setMessage] = useState("Draft is local to this browser until exported.");
  const summary = useMemo(() => summarize(content), [content]);
  const json = useMemo(() => toJson(content), [content]);
  const tsSnippet = useMemo(() => contentTs(content), [content]);

  function saveDraft() {
    window.localStorage.setItem(STORAGE_KEY, json);
    setMessage("Draft saved in this browser.");
  }

  function resetDraft() {
    const fresh = cloneContent();
    setContent(fresh);
    window.localStorage.removeItem(STORAGE_KEY);
    setMessage("Draft reset to committed site content.");
  }

  async function copy(value: string, label: string) {
    await navigator.clipboard.writeText(value);
    setMessage(`${label} copied.`);
  }

  function importJson() {
    try {
      const parsed = JSON.parse(importText) as Partial<AdminContent>;
      setContent({ ...cloneContent(), ...parsed });
      setMessage("JSON imported into the editor. Save draft or export when ready.");
    } catch {
      setMessage("Import failed. Check that the JSON is valid.");
    }
  }

  return (
    <>
      <div className="space-bg admin-bg" aria-hidden="true" />
      <main className="admin-shell">
        <header className="admin-topbar">
          <button className="admin-brand" type="button" onClick={() => setActiveTab("overview")}>
            HH88TRANCE Admin
          </button>
          <div className="admin-actions">
            <button type="button" onClick={saveDraft}>
              <Save size={17} /> Save Draft
            </button>
            <button type="button" onClick={resetDraft}>
              <RefreshCcw size={17} /> Reset
            </button>
          </div>
        </header>

        <section className="admin-hero compact">
          <div>
            <p className="capsule">admin.hh88trance.com</p>
            <h1>Content Control</h1>
            <p className="admin-copy">
              Edit video cards, payment links, recurring drains, and about-page copy from one private interface. Drafts stay in local
              browser storage; export the generated content when you are ready to publish.
            </p>
          </div>
          <div className={`admin-access-card ${summary.ready ? "ready" : ""}`}>
            {summary.ready ? <CheckCircle2 size={34} /> : <AlertTriangle size={34} />}
            <h2>{summary.ready ? "Launch Ready" : "Needs Review"}</h2>
            <p>
              {summary.videoCount} video cards, {summary.pendingLinks} pending links, {summary.exampleContacts} placeholder contacts.
            </p>
          </div>
        </section>

        <nav className="admin-tabs" aria-label="Admin sections">
          {tabs.map((tab) => (
            <button key={tab.id} className={activeTab === tab.id ? "active" : ""} type="button" onClick={() => setActiveTab(tab.id)}>
              {tab.label}
            </button>
          ))}
        </nav>

        <p className="admin-message" role="status">
          {message}
        </p>

        {activeTab === "overview" ? <OverviewPanel summary={summary} content={content} setActiveTab={setActiveTab} /> : null}
        {activeTab === "videos" ? <VideosPanel content={content} setContent={setContent} /> : null}
        {activeTab === "links" ? <LinksPanel content={content} setContent={setContent} /> : null}
        {activeTab === "drains" ? <DrainsPanel content={content} setContent={setContent} /> : null}
        {activeTab === "about" ? <AboutPanel content={content} setContent={setContent} /> : null}
        {activeTab === "export" ? (
          <ExportPanel
            json={json}
            tsSnippet={tsSnippet}
            importText={importText}
            setImportText={setImportText}
            importJson={importJson}
            copy={copy}
          />
        ) : null}
      </main>
    </>
  );
}

function OverviewPanel({
  summary,
  content,
  setActiveTab
}: {
  summary: ReturnType<typeof summarize>;
  content: AdminContent;
  setActiveTab: TabChange;
}) {
  const checks = [
    { label: "Replace pending payment or social URLs", value: summary.pendingLinks === 0 },
    { label: "Replace example.com commission contact", value: summary.exampleContacts === 0 },
    { label: "Keep every video title and price populated", value: summary.emptyVideos === 0 },
    { label: "Maintain at least one custom and one main file", value: content.customVideos.length > 0 && content.mainVideos.length > 0 }
  ];

  return (
    <section className="admin-grid" aria-label="Launch status">
      <article className="admin-card stat-card">
        <FileText size={28} />
        <h2>{summary.videoCount}</h2>
        <p>Video cards across custom and main routes.</p>
        <button type="button" onClick={() => setActiveTab("videos")}>
          Edit Videos
        </button>
      </article>
      <article className="admin-card stat-card">
        <Link2 size={28} />
        <h2>{summary.pendingLinks}</h2>
        <p>Links still marked pending or pointed at placeholders.</p>
        <button type="button" onClick={() => setActiveTab("links")}>
          Edit Links
        </button>
      </article>
      <article className="admin-card checklist-card">
        <h2>Launch Checklist</h2>
        <div className="admin-checklist">
          {checks.map((check) => (
            <span key={check.label} className={check.value ? "done" : ""}>
              {check.value ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />} {check.label}
            </span>
          ))}
        </div>
      </article>
    </section>
  );
}

function VideosPanel({ content, setContent }: { content: AdminContent; setContent: Dispatch<SetStateAction<AdminContent>> }) {
  function update(section: VideoSection, index: number, patch: Partial<VideoFile>) {
    setContent((current) => ({
      ...current,
      [section]: current[section].map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    }));
  }

  function add(section: VideoSection) {
    const kind = section === "customVideos" ? "custom" : "main";
    setContent((current) => ({
      ...current,
      [section]: [
        ...current[section],
        {
          title: kind === "custom" ? "New Custom File" : "New Main File",
          creator: "HH88TRANCE",
          meta: ["Trance", "Full quality"],
          price: "$80.00",
          duration: kind === "main" ? "1 hour max length" : undefined,
          kind,
          visual: "new file"
        }
      ]
    }));
  }

  function remove(section: VideoSection, index: number) {
    setContent((current) => ({ ...current, [section]: current[section].filter((_, itemIndex) => itemIndex !== index) }));
  }

  return (
    <section className="admin-editor">
      <VideoGroup title="Custom Commission Files" section="customVideos" videos={content.customVideos} update={update} add={add} remove={remove} />
      <VideoGroup title="Main Files" section="mainVideos" videos={content.mainVideos} update={update} add={add} remove={remove} />
    </section>
  );
}

function VideoGroup({
  title,
  section,
  videos,
  update,
  add,
  remove
}: VideoGroupProps) {
  return (
    <article className="admin-panel">
      <div className="panel-heading">
        <h2>{title}</h2>
        <button type="button" onClick={() => add(section)}>
          <Plus size={18} /> Add File
        </button>
      </div>
      <div className="editor-list">
        {videos.map((video, index) => (
          <div className="editor-row" key={`${video.kind}-${index}`}>
            <Field label="Title" value={video.title} onChange={(title) => update(section, index, { title })} />
            <Field label="Creator" value={video.creator} onChange={(creator) => update(section, index, { creator })} />
            <Field label="Price" value={video.price} onChange={(price) => update(section, index, { price })} />
            <Field label="Duration" value={video.duration ?? ""} onChange={(duration) => update(section, index, { duration: duration || undefined })} />
            <Field label="Visual Label" value={video.visual} onChange={(visual) => update(section, index, { visual })} />
            <Field label="Tags" value={video.meta.join(", ")} onChange={(value) => update(section, index, { meta: splitMeta(value) })} />
            <button className="danger-button" type="button" onClick={() => remove(section, index)} aria-label={`Remove ${video.title}`}>
              <Trash2 size={18} /> Remove
            </button>
          </div>
        ))}
      </div>
    </article>
  );
}

function LinksPanel({ content, setContent }: { content: AdminContent; setContent: Dispatch<SetStateAction<AdminContent>> }) {
  function update(section: LinkSection, index: number, patch: Partial<LinkItem>) {
    setContent((current) => ({
      ...current,
      [section]: current[section].map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    }));
  }

  function add(section: LinkSection) {
    setContent((current) => ({
      ...current,
      [section]: [...current[section], { label: "New Link", href: "#pending-new-link", pending: true }]
    }));
  }

  function remove(section: LinkSection, index: number) {
    setContent((current) => ({ ...current, [section]: current[section].filter((_, itemIndex) => itemIndex !== index) }));
  }

  return (
    <section className="admin-editor">
      <LinkGroup title="Send Tribute Links" section="contactLinks" links={content.contactLinks} update={update} add={add} remove={remove} />
      <LinkGroup title="Contact And Social Links" section="socialLinks" links={content.socialLinks} update={update} add={add} remove={remove} />
    </section>
  );
}

function LinkGroup({
  title,
  section,
  links,
  update,
  add,
  remove
}: LinkGroupProps) {
  return (
    <article className="admin-panel">
      <div className="panel-heading">
        <h2>{title}</h2>
        <button type="button" onClick={() => add(section)}>
          <Plus size={18} /> Add Link
        </button>
      </div>
      <div className="editor-list compact">
        {links.map((link, index) => (
          <div className="editor-row link-editor-row" key={`${link.label}-${index}`}>
            <Field label="Label" value={link.label} onChange={(label) => update(section, index, { label })} />
            <Field label="URL" value={link.href} onChange={(href) => update(section, index, { href })} />
            <BooleanField label="Pending URL" checked={Boolean(link.pending)} onChange={(pending) => update(section, index, { pending })} />
            <button className="danger-button" type="button" onClick={() => remove(section, index)} aria-label={`Remove ${link.label}`}>
              <Trash2 size={18} /> Remove
            </button>
          </div>
        ))}
      </div>
    </article>
  );
}

function DrainsPanel({ content, setContent }: { content: AdminContent; setContent: Dispatch<SetStateAction<AdminContent>> }) {
  function update(index: number, patch: Partial<DrainPlan>) {
    setContent((current) => ({
      ...current,
      drainPlans: current.drainPlans.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    }));
  }

  function add() {
    setContent((current) => ({
      ...current,
      drainPlans: [...current.drainPlans, { name: "New Drain", price: "$2.99", cadence: "/ Week", description: "Describe the recurring tribute." }]
    }));
  }

  function remove(index: number) {
    setContent((current) => ({ ...current, drainPlans: current.drainPlans.filter((_, itemIndex) => itemIndex !== index) }));
  }

  return (
    <section className="admin-editor">
      <article className="admin-panel">
        <div className="panel-heading">
          <h2>Recurring Drain Plans</h2>
          <button type="button" onClick={add}>
            <Plus size={18} /> Add Plan
          </button>
        </div>
        <div className="editor-list">
          {content.drainPlans.map((plan, index) => (
            <div className="editor-row" key={`${plan.name}-${index}`}>
              <Field label="Name" value={plan.name} onChange={(name) => update(index, { name })} />
              <Field label="Price" value={plan.price} onChange={(price) => update(index, { price })} />
              <Field label="Cadence" value={plan.cadence} onChange={(cadence) => update(index, { cadence })} />
              <Field label="Description" value={plan.description} onChange={(description) => update(index, { description })} multiline />
              <button className="danger-button" type="button" onClick={() => remove(index)} aria-label={`Remove ${plan.name}`}>
                <Trash2 size={18} /> Remove
              </button>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}

function AboutPanel({ content, setContent }: { content: AdminContent; setContent: Dispatch<SetStateAction<AdminContent>> }) {
  function update(index: number, patch: Partial<AccordianItem>) {
    setContent((current) => ({
      ...current,
      aboutAccordions: current.aboutAccordions.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    }));
  }

  function add() {
    setContent((current) => ({
      ...current,
      aboutAccordions: [...current.aboutAccordions, { title: "New About Item", body: "Add the answer shown in the About page accordion." }]
    }));
  }

  function remove(index: number) {
    setContent((current) => ({ ...current, aboutAccordions: current.aboutAccordions.filter((_, itemIndex) => itemIndex !== index) }));
  }

  return (
    <section className="admin-editor">
      <article className="admin-panel">
        <div className="panel-heading">
          <h2>About Accordion Copy</h2>
          <button type="button" onClick={add}>
            <Plus size={18} /> Add Item
          </button>
        </div>
        <div className="editor-list">
          {content.aboutAccordions.map((item, index) => (
            <div className="editor-row about-editor-row" key={`${item.title}-${index}`}>
              <Field label="Title" value={item.title} onChange={(title) => update(index, { title })} />
              <Field label="Body" value={item.body} onChange={(body) => update(index, { body })} multiline />
              <button className="danger-button" type="button" onClick={() => remove(index)} aria-label={`Remove ${item.title}`}>
                <Trash2 size={18} /> Remove
              </button>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}

function ExportPanel({
  json,
  tsSnippet,
  importText,
  setImportText,
  importJson,
  copy
}: ExportPanelProps) {
  return (
    <section className="admin-editor export-layout">
      <article className="admin-panel">
        <div className="panel-heading">
          <h2>Export Draft</h2>
          <div className="panel-actions">
            <button type="button" onClick={() => copy(json, "JSON")}>
              <Clipboard size={18} /> Copy JSON
            </button>
            <button type="button" onClick={() => downloadFile("hh88-content.json", json)}>
              <Download size={18} /> Download
            </button>
          </div>
        </div>
        <textarea className="admin-code" value={json} readOnly aria-label="Exported admin JSON" />
      </article>
      <article className="admin-panel">
        <div className="panel-heading">
          <h2>Generated Content Arrays</h2>
          <button type="button" onClick={() => copy(tsSnippet, "Content arrays")}>
            <FileText size={18} /> Copy TS
          </button>
        </div>
        <textarea className="admin-code tall" value={tsSnippet} readOnly aria-label="Generated TypeScript content arrays" />
      </article>
      <article className="admin-panel">
        <div className="panel-heading">
          <h2>Import JSON</h2>
          <button type="button" onClick={importJson}>
            <Upload size={18} /> Import
          </button>
        </div>
        <textarea
          className="admin-code"
          value={importText}
          onChange={(event) => setImportText(event.target.value)}
          placeholder="Paste exported JSON here"
          aria-label="Import admin JSON"
        />
        <p className="admin-note">
          Exported JSON is useful for handing edits to a developer. The TypeScript output is the closest match for updating `src/content.ts`.
        </p>
        <FileJson className="panel-watermark" size={72} aria-hidden="true" />
      </article>
    </section>
  );
}
