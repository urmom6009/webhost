import type { ReactNode } from "react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import { AdminPortal } from "../features/admin/AdminPortal";
import { isAdminHost } from "./adminHost";
import { routeMap, usePathname } from "./routing";
import { Shell } from "../layout/Shell";
import { AboutPage } from "../pages/AboutPage";
import { ContactPage } from "../pages/ContactPage";
import { AutoDrainsPage, ContractsPage, FindomLanding } from "../pages/FindomPages";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PrivacyPage } from "../pages/PrivacyPage";
import { VideoPage, VideosLanding } from "../pages/VideosPage";

export function App() {
  const path = usePathname();
  if (isAdminHost()) return <AdminPortal />;

  let page: ReactNode;
  switch (routeMap[path]) {
    case "home":
      page = <HomePage />;
      break;
    case "videos":
      page = <VideosLanding />;
      break;
    case "customs":
      page = <VideoPage type="custom" />;
      break;
    case "main":
      page = <VideoPage type="main" />;
      break;
    case "findom":
      page = <FindomLanding />;
      break;
    case "auto-drains":
      page = <AutoDrainsPage />;
      break;
    case "contracts":
      page = <ContractsPage />;
      break;
    case "about":
      page = <AboutPage />;
      break;
    case "contact":
      page = <ContactPage />;
      break;
    case "privacy":
      page = <PrivacyPage />;
      break;
    default:
      page = <NotFoundPage />;
  }

  return (
    <Shell path={path}>
      {page}
      <SpeedInsights />
    </Shell>
  );
}

