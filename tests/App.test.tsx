import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../src/App";

describe("App routing and interactions", () => {
  beforeEach(() => {
    window.localStorage.setItem("hh88-age-ok", "true");
    window.history.pushState({}, "", "/");
  });

  it("renders the home route and navigates to videos", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /hh88trance/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /preview\/buy videos/i }));
    expect(screen.getByRole("button", { name: /customcommission files/i })).toBeInTheDocument();
  });

  it("renders product-specific website purchase links", () => {
    window.history.pushState({}, "", "/videos/main");
    render(<App />);

    expect(
      screen.getByRole("link", { name: /buy file 11 with stripe/i })
    ).toHaveAttribute("href", "https://serve.hh88trance.com/buy/file-11");
  });

  it("renders custom video website purchase links", () => {
    window.history.pushState({}, "", "/videos/custom");
    render(<App />);

    expect(
      screen.getByRole("link", { name: /buy undergoing maintenance with stripe/i })
    ).toHaveAttribute("href", "https://serve.hh88trance.com/buy/under-construction");
  });

  it("uses configurable storefront base URL for website purchasing links", () => {
    const originalBaseUrl = import.meta.env.VITE_STOREFRONT_BASE_URL;
    import.meta.env.VITE_STOREFRONT_BASE_URL = "https://store.example.com";

    try {
      window.history.pushState({}, "", "/videos/main");
      render(<App />);

      expect(
        screen.getByRole("link", { name: /buy file 11 with stripe/i })
      ).toHaveAttribute("href", "https://store.example.com/buy/file-11");
    } finally {
      import.meta.env.VITE_STOREFRONT_BASE_URL = originalBaseUrl;
    }
  });

  it("expands about accordions", () => {
    window.history.pushState({}, "", "/about");
    render(<App />);
    const trigger = screen.getByRole("button", { name: /how you will buy the full files/i });
    fireEvent.click(trigger);
    expect(screen.getByText(/redirect to Stripe to facilitate payment/i)).toBeInTheDocument();
  });

  it("shows the age gate when local approval is absent", () => {
    window.localStorage.removeItem("hh88-age-ok");
    render(<App />);
    expect(screen.getByRole("dialog", { name: /18\+ entry required/i })).toBeInTheDocument();
  });

  it("renders the admin portal and edits a local video draft", () => {
    window.history.pushState({}, "", "/admin");
    render(<App />);

    expect(screen.getByRole("heading", { name: /content control/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^videos$/i }));
    fireEvent.click(screen.getAllByRole("button", { name: /add file/i })[0]);

    expect(screen.getByDisplayValue("New Custom File")).toBeInTheDocument();
    fireEvent.change(screen.getAllByLabelText("Title")[0], { target: { value: "Updated Custom File" } });
    expect(screen.getByDisplayValue("Updated Custom File")).toBeInTheDocument();
  });
});
