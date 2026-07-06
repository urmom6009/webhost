import { fireEvent, render, screen } from "@testing-library/react";
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

  it("expands about accordions", () => {
    window.history.pushState({}, "", "/about");
    render(<App />);
    const trigger = screen.getByRole("button", { name: /how you will buy the full files/i });
    fireEvent.click(trigger);
    expect(screen.getByText(/external payment or delivery services/i)).toBeInTheDocument();
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
