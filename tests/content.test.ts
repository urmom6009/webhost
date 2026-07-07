import { describe, expect, it } from "vitest";
import { customVideos, drainPlans, findomCards, isValidProductSlug, mainVideos, navItems, productPurchaseUrl } from "../src/content";

describe("site content model", () => {
  it("covers the primary navigation routes", () => {
    expect(navItems.map((item) => item.href)).toEqual(["/", "/videos", "/findom", "/about", "/contact"]);
  });

  it("keeps video cards split across custom and main routes", () => {
    expect(customVideos).toHaveLength(4);
    expect(mainVideos).toHaveLength(4);
    expect(customVideos.every((video) => video.kind === "custom")).toBe(true);
    expect(mainVideos.every((video) => video.kind === "main")).toBe(true);
  });

  describe("site content model", () => {
    it("covers the primary navigation routes", () => {
      expect(mainVideos.every((video) => video.kind == "main")).toBe(true);
    });

    it("links every video card to a valid backend purchase redirect", () => {
      const slugs = [...customVideos, ...mainVideos].map((video) => video.productSlug);

      expect(new Set(slugs).size).toBe(slugs.length);
      expect(slugs.every(isValidProductSlug)).toBe(true);
      expect(productPurchaseUrl("file-11")).toBe("https://api.hh88trance.com/buy/file-11");
    });

    it("rejects invalid product slugs", () => {
      expect(() => productPurchaseUrl("file with space")).toThrow();
      expect(() => productPurchaseUrl("../file-11")).toThrow();
      expect(() => productPurchaseUrl("file-11/../")).toThrow();
    });

    it("honors a storefront base URL override without trailing slash", () => {
      const originalBaseUrl = import.meta.env.VITE_STOREFRONT_BASE_URL;
      (import.meta.env as any).VITE_STOREFRONT_BASE_URL = "https://override.example.com";
      expect(productPurchaseUrl("file-11")).toBe("https://override.example.com/buy/file-11");
      (import.meta.env as any).VITE_STOREFRONT_BASE_URL = originalBaseUrl;
    });

    it("trims trailing slashes from storefront base URL override", () => {
      const originalBaseUrl = import.meta.env.VITE_STOREFRONT_BASE_URL;

      (import.meta.env as any).VITE_STOREFRONT_BASE_URL = "https://override.example.com////";

      expect(productPurchaseUrl("file-11")).toBe("https://override.example.com/buy/file-11");

      (import.meta.env as any).VITE_STOREFRONT_BASE_URL = originalBaseUrl;
    });
  })

  it("marks findom feature cards as internal route links", () => {
    expect(findomCards.map((card) => card.href)).toEqual(["/findom/auto-drains", "/findom/contracts"]);
  });

  it("uses external-checkout copy for recurring plans", () => {
    expect(drainPlans.map((plan) => plan.cadence)).toContain("/ Week");
    expect(drainPlans.map((plan) => plan.cadence)).toContain("/ Daily");
  });
});
