import type { ReactNode } from "react";
import { AgeGate } from "./AgeGate";
import { BrandHeader } from "./BrandHeader";
import { Footer } from "./Footer";

export function Shell({ children, path }: { children: ReactNode; path: string }) {
  return (
    <>
      <div className="space-bg" aria-hidden="true" />
      <BrandHeader path={path} />
      <main>{children}</main>
      <Footer />
      <AgeGate />
    </>
  );
}



