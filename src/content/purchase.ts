const DEFAULT_STOREFRONT_BASE_URL = "https://serve.hh88trance.com";
const PRODUCT_SLUG_RE = /^[A-Za-z0-9_-]{1,64}$/;

export function storefrontBaseUrl() {
  return (import.meta.env.VITE_STOREFRONT_BASE_URL || DEFAULT_STOREFRONT_BASE_URL).replace(/\/+$/, "");
}

export function isValidProductSlug(productSlug: string) {
  return PRODUCT_SLUG_RE.test(productSlug);
}

export function productPurchaseUrl(productSlug: string) {
  if (!isValidProductSlug(productSlug)) {
    throw new Error(`Invalid product slug: ${productSlug}`);
  }

  return `${storefrontBaseUrl()}/buy/${encodeURIComponent(productSlug)}`;
}

export function productCatalogUrl() {
  return `${storefrontBaseUrl()}/catalog`;
}
