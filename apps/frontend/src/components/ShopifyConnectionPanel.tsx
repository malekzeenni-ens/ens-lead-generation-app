import { PlugZap, Save, ShoppingBag, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { api } from "../api";
import type { ShopifyConnection } from "../types";
import { LoadingState, StatusPill } from "./DesignSystem";

function message(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Something went wrong. Try again.";
}

/**
 * Settings > Connections > Shopify (ADR-026): the same Shopify custom app the Shopify-to-Etsy
 * app syncs with. Credentials go into the Windows vault and are never shown again.
 */
export function ShopifyConnectionPanel() {
  const [connection, setConnection] = useState<ShopifyConnection | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api.shopifyConnection().then(setConnection).catch((caught: unknown) => setError(message(caught)));
  }, []);

  async function run(action: () => Promise<void>): Promise<void> {
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setWorking(false);
    }
  }

  function save(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = event.currentTarget;
    const value = (name: string) => {
      const field = new FormData(form).get(name);
      return typeof field === "string" ? field.trim() : "";
    };
    void run(async () => {
      const saved = await api.saveShopifyConnection({
        store_domain: value("shopify-store"),
        client_id: value("shopify-client-id") || undefined,
        client_secret: value("shopify-client-secret") || undefined,
        access_token: value("shopify-access-token") || undefined,
      });
      setConnection(saved);
      form.reset();
      const shop = await api.testShopifyConnection();
      setNotice(`Connected to ${shop.shop_name}.`);
    });
  }

  if (!connection) {
    return error ? <p className="form-error" role="alert">{error}</p> : <LoadingState label="Loading Shopify connection" />;
  }

  return (
    <section className="form-panel settings-grid__wide" aria-labelledby="shopify-settings-heading">
      <div className="subsection-heading">
        <div>
          <h3 id="shopify-settings-heading">Shopify</h3>
          <p>Read-only access for syncing the catalogue, using the same Shopify app as the Shopify-to-Etsy app.</p>
        </div>
        <StatusPill tone={connection.configured ? "success" : "neutral"}>
          {connection.configured ? "Connected" : "Not set up"}
        </StatusPill>
      </div>

      {connection.configured ? (
        <div className="provider-connection">
          <p>
            Store <strong>{connection.store_domain}</strong> · API {connection.api_version} ·{" "}
            {connection.method === "access_token" ? "access token" : "client ID and secret"}
          </p>
          <div className="form-actions">
            <button
              type="button"
              className="secondary-action"
              disabled={working}
              onClick={() =>
                void run(async () => {
                  const shop = await api.testShopifyConnection();
                  setNotice(`Connected to ${shop.shop_name}.`);
                })
              }
            >
              <PlugZap size={16} aria-hidden="true" /> Test connection
            </button>
            <button
              type="button"
              className="tertiary-action"
              disabled={working}
              onClick={() => void run(async () => setConnection(await api.removeShopifyConnection()))}
            >
              <Trash2 size={16} aria-hidden="true" /> Remove
            </button>
          </div>
        </div>
      ) : null}

      <form className="form-grid" onSubmit={save}>
        <label>
          Store address
          <input
            id="shopify-store"
            name="shopify-store"
            required
            placeholder="your-store.myshopify.com"
            defaultValue={connection.store_domain ?? ""}
            autoComplete="off"
          />
        </label>
        <label>
          Client ID
          <input id="shopify-client-id" name="shopify-client-id" autoComplete="off" />
        </label>
        <label>
          Client secret
          <input id="shopify-client-secret" name="shopify-client-secret" type="password" autoComplete="off" />
        </label>
        <details>
          <summary>Use an access token instead</summary>
          <label>
            Admin API access token
            <input id="shopify-access-token" name="shopify-access-token" type="password" autoComplete="off" />
          </label>
        </details>
        <p className="form-hint">
          From Shopify admin → Settings → Apps → Develop apps → your app → API credentials. Only
          product read access is used. Saved in Windows' protected storage, never shown again.
        </p>
        <button className="primary-action" type="submit" disabled={working}>
          <Save size={17} aria-hidden="true" />
          {connection.configured ? "Replace and test" : "Save and test"}
        </button>
      </form>

      {notice ? (
        <p className="form-hint" role="status"><ShoppingBag size={14} aria-hidden="true" /> {notice}</p>
      ) : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </section>
  );
}
