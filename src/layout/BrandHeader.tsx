import { aboutSubnav, findomSubnav, navItems, videoSubnav, type NavItem } from "../content";
import { navigateTo, routeSection } from "../app/routing";

export function BrandHeader({ path }: { path: string }) {
  const section = routeSection(path);
  const groupedNav = navItems
    .filter((item) => item.section !== "contact")
    .map((item) => {
      if (item.section === "videos") return { parent: item, children: videoSubnav.slice(1) };
      if (item.section === "findom") return { parent: item, children: findomSubnav.slice(1) };
      if (item.section === "about") return { parent: item, children: aboutSubnav.slice(1) };
      return { parent: item, children: [] };
    });

  return (
    <header className="site-header">
      <button className="money-banner" onClick={() => navigateTo("/")} aria-label="HH88TRANCE home">
        <span className="brand-mark">HH88TRANCE</span>
        <span className="brand-kicker">Adult trance files | Findom systems | Custom commissions</span>
      </button>
      <nav className="main-nav" aria-label="Primary navigation">
        {groupedNav.map(({ parent, children }) => (
          <NavGroup key={parent.href} item={parent} childrenItems={children} path={path} activeSection={section === parent.section} />
        ))}
      </nav>
    </header>
  );
}



export function NavGroup({
  item,
  childrenItems,
  path,
  activeSection
}: {
  item: NavItem;
  childrenItems: NavItem[];
  path: string;
  activeSection: boolean;
}) {
  const active = item.href === path || activeSection;
  return (
    <div className={`nav-group${childrenItems.length ? " has-children" : ""}${activeSection ? " section-open" : ""}`}>
      <NavButton item={item} active={active} />
      {childrenItems.length ? (
        <div className="nav-children" aria-label={`${item.label} pages`}>
          <span className="nav-group-line" aria-hidden="true" />
          {childrenItems.map((child) => (
            <NavButton key={child.href} item={child} active={child.href === path} nested />
          ))}
        </div>
      ) : null}
    </div>
  );
}



export function NavButton({ item, active, nested = false }: { item: NavItem; active: boolean; nested?: boolean }) {
  return (
    <button className={`nav-link accent-${item.accent}${active ? " active" : ""}${nested ? " nested" : ""}`} onClick={() => navigateTo(item.href)}>
      {item.label}
    </button>
  );
}



