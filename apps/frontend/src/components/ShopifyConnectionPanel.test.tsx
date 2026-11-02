import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShopifyConnectionPanel } from "./ShopifyConnectionPanel";

vi.mock("../api", () => ({
  api: {
    shopifyConnection: vi.fn(),
    saveShopifyConnection: vi.fn(),
    removeShopifyConnection: vi.fn(),
    testShopifyConnection: vi.fn(),
  },
}));

const { api } = await import("../api");

const notSetUp = { configured: false, store_domain: null, api_version: null, method: null } as const;
const connected = {
  configured: true,
  store_domain: "example-store.myshopify.com",
  api_version: "2026-04",
  method: "client_credentials",
} as const;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ShopifyConnectionPanel", () => {
  it("saves the same app's client ID and secret, then tests the connection", async () => {
    vi.mocked(api.shopifyConnection).mockResolvedValue(notSetUp);
    vi.mocked(api.saveShopifyConnection).mockResolvedValue(connected);
    vi.mocked(api.testShopifyConnection).mockResolvedValue({
      shop_name: "Etch N Shine",
      store_domain: "example-store.myshopify.com",
    });
    const user = userEvent.setup();
    render(<ShopifyConnectionPanel />);
    expect(await screen.findByText("Not set up")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Store address"), "example-store.myshopify.com");
    await user.type(screen.getByLabelText("Client ID"), "client-id");
    await user.type(screen.getByLabelText("Client secret"), "client-secret");
    await user.click(screen.getByRole("button", { name: "Save and test" }));

    expect(api.saveShopifyConnection).toHaveBeenCalledWith({
      store_domain: "example-store.myshopify.com",
      client_id: "client-id",
      client_secret: "client-secret",
      access_token: undefined,
    });
    expect(await screen.findByText(/Connected to Etch N Shine/)).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    // The secret is not kept in the form once saved.
    expect(screen.getByLabelText("Client secret")).toHaveValue("");
  });

  it("shows a failed test and can remove the connection", async () => {
    vi.mocked(api.shopifyConnection).mockResolvedValue(connected);
    vi.mocked(api.testShopifyConnection).mockRejectedValue(new Error("Token exchange failed with HTTP 401"));
    vi.mocked(api.removeShopifyConnection).mockResolvedValue(notSetUp);
    const user = userEvent.setup();
    render(<ShopifyConnectionPanel />);
    await user.click(await screen.findByRole("button", { name: /Test connection/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 401");
    await user.click(screen.getByRole("button", { name: /Remove/ }));
    expect(await screen.findByText("Not set up")).toBeInTheDocument();
  });
});
