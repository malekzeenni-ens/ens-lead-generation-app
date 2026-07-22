import { ClipboardPaste, RefreshCw, Search, UserPlus } from "lucide-react";
import { type FormEvent, useMemo, useRef, useState } from "react";

import type { AutomationCapabilities, Campaign, InstagramProfilePreview } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { formValue, hashtagValue, pasteFromClipboard } from "./campaignShared";
import { SectionHeading, StatGrid, TaskPanel, TaskTabs } from "./DesignSystem";

interface CampaignSocialTabProps {
  campaigns: Campaign[];
  capabilities: AutomationCapabilities | null;
}

type SocialTask = "instagram" | "search" | "facebook";

export function CampaignSocialTab({ campaigns, capabilities }: CampaignSocialTabProps) {
  const {
    busy,
    openSocialSearch: onOpenSocialSearch,
    captureSocialCandidate: onCaptureSocial,
    previewInstagramProfile: onPreviewInstagram,
    importInstagramProfile: onImportInstagram,
    enrichKnownInstagramProfiles: onEnrichKnownInstagram,
  } = useWorkspaceActions();
  const [socialCampaignId, setSocialCampaignId] = useState("");
  const [socialTask, setSocialTask] = useState<SocialTask>("instagram");
  const [instagramProfileUrl, setInstagramProfileUrl] = useState("");
  const [instagramPreview, setInstagramPreview] =
    useState<InstagramProfilePreview | null>(null);
  const facebookProfileUrlRef = useRef<HTMLInputElement>(null);
  const selectedSocialCampaign = campaigns.find(
    (campaign) =>
      campaign.id === socialCampaignId ||
      (!socialCampaignId && campaign.status === "active"),
  );
  const socialSearches = useMemo(() => {
    if (!selectedSocialCampaign) return [];
    const terms = selectedSocialCampaign.keywords.length
      ? selectedSocialCampaign.keywords.slice(0, 3)
      : [selectedSocialCampaign.segment];
    const location = hashtagValue(selectedSocialCampaign.primary_location.split(",", 1)[0] ?? "");
    return (["instagram", "facebook"] as const).flatMap((platform) =>
      terms.map((term) => {
        const cleanedTerm = hashtagValue(term.replace(/^#/, ""));
        const hashtag = cleanedTerm.includes(location) ? cleanedTerm : `${location}${cleanedTerm}`;
        return {
          platform,
          term,
          hashtag,
          url:
            platform === "instagram"
              ? `https://www.instagram.com/explore/tags/${hashtag}/`
              : `https://www.google.com/search?q=${encodeURIComponent(
                  `site:facebook.com ${term} ${selectedSocialCampaign.primary_location}`,
                )}`,
        };
      }),
    );
  }, [selectedSocialCampaign]);

  async function captureFacebook(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const website = formValue(form, "social-website");
    const phoneNumber = formValue(form, "social-phone");
    const publicEmail = formValue(form, "social-email");
    const publicBio = formValue(form, "social-bio");
    const saved = await onCaptureSocial({
      campaign_id: formValue(form, "social-campaign"),
      platform: "facebook",
      profile_url: formValue(form, "social-profile-url"),
      business_name: formValue(form, "social-business-name"),
      location: formValue(form, "social-location"),
      ...(website ? { website } : {}),
      ...(phoneNumber ? { phone_number: phoneNumber } : {}),
      ...(publicEmail ? { public_email: publicEmail } : {}),
      ...(publicBio ? { public_bio: publicBio } : {}),
    });
    if (saved) formElement.reset();
  }

  async function previewInstagram(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setInstagramPreview(null);
    const profile = await onPreviewInstagram(instagramProfileUrl);
    if (profile) setInstagramPreview(profile);
  }

  async function importInstagram(): Promise<void> {
    if (!selectedSocialCampaign || !instagramPreview) return;
    const saved = await onImportInstagram(
      selectedSocialCampaign.id,
      instagramPreview.profile_url,
    );
    if (saved) {
      setInstagramProfileUrl("");
      setInstagramPreview(null);
    }
  }

  return (
    <section className="workspace-section" aria-labelledby="social-discovery-heading">
      <SectionHeading
        id="social-discovery-heading"
        eyebrow="Social lead acquisition"
        title="Instagram and Facebook leads"
        description="Look up a known Instagram professional profile through Meta, enrich profiles already saved on leads, or use the separate public-search and Facebook capture actions."
        icon={Search}
      />
      <div className="social-campaign-selector">
        <label>
          Active campaign
          <select
            value={selectedSocialCampaign?.id ?? ""}
            onChange={(event) => {
              setSocialCampaignId(event.target.value);
              setInstagramPreview(null);
            }}
          >
            <option value="">Select an active campaign</option>
            {campaigns.filter((campaign) => campaign.status === "active").map((campaign) => (
              <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
            ))}
          </select>
        </label>
      </div>
      <TaskTabs
        id="social-actions"
        label="Social lead actions"
        activeId={socialTask}
        onChange={(task) => setSocialTask(task as SocialTask)}
        items={[
          { id: "instagram", label: "Instagram import" },
          { id: "search", label: "Find profiles" },
          { id: "facebook", label: "Facebook capture" },
        ]}
      />

      {socialTask === "instagram" ? (
        <TaskPanel id="social-actions" tabId="instagram" className="social-action-panel">
          <div className="section-layout social-discovery">
            <div className="form-panel">
              <div className="subsection-heading">
                <div>
                  <h3>Import one Instagram profile</h3>
                  <p>Paste a public professional profile URL; Meta fills the available fields.</p>
                </div>
                <span className="step-badge">01</span>
              </div>
              <form className="form-grid" onSubmit={(event) => void previewInstagram(event)}>
                <label>
                  Instagram profile URL
                  <div className="field-with-action">
                    <input
                      type="url"
                      required
                      value={instagramProfileUrl}
                      placeholder="https://www.instagram.com/example"
                      onChange={(event) => {
                        setInstagramProfileUrl(event.target.value);
                        setInstagramPreview(null);
                      }}
                    />
                    <button
                      type="button"
                      className="icon-button"
                      title="Paste from clipboard"
                      aria-label="Paste Instagram profile URL from clipboard"
                      onClick={() => {
                        void pasteFromClipboard().then((text) => {
                          if (!text) return;
                          setInstagramProfileUrl(text);
                          setInstagramPreview(null);
                        });
                      }}
                    >
                      <ClipboardPaste size={16} aria-hidden="true" />
                    </button>
                  </div>
                </label>
                <p className="form-hint">
                  Consumer, private or unavailable accounts will return a clear review message.
                </p>
                <div className="form-actions">
                  <p>No lead is created until you review the result.</p>
                  <button
                    className="primary-action"
                    type="submit"
                    disabled={busy || !capabilities?.instagram_connected}
                  >
                    <Search size={17} aria-hidden="true" /> Fetch from Meta
                  </button>
                </div>
              </form>
              {instagramPreview ? (
                <article className="instagram-profile-preview" aria-label="Instagram profile preview">
                  <div className="instagram-profile-preview__heading">
                    <div>
                      <p className="eyebrow">Professional profile found</p>
                      <h4>{instagramPreview.business_name}</h4>
                      <a href={instagramPreview.profile_url} target="_blank" rel="noreferrer">
                        @{instagramPreview.username}
                      </a>
                    </div>
                    <span className="status-badge status-badge--success">Meta verified</span>
                  </div>
                  <StatGrid
                    className="instagram-profile-preview__metrics"
                    items={[
                      { label: "Followers", value: instagramPreview.followers_count ?? "Not exposed" },
                      { label: "Posts", value: instagramPreview.media_count ?? "Not exposed" },
                      { label: "Website", value: instagramPreview.website ?? "Not exposed" },
                      {
                        label: "Contact",
                        value: instagramPreview.public_email ?? instagramPreview.public_phone ?? "Not exposed",
                      },
                    ]}
                  />
                  {instagramPreview.biography ? <p>{instagramPreview.biography}</p> : null}
                  <div className="form-actions">
                    <p>The campaign supplies location context; Instagram does not verify radius.</p>
                    <button
                      className="primary-action"
                      type="button"
                      disabled={busy || !selectedSocialCampaign}
                      onClick={() => void importInstagram()}
                    >
                      <UserPlus size={17} aria-hidden="true" /> Import, score and match
                    </button>
                  </div>
                </article>
              ) : null}
            </div>

            <div className="records-panel">
              <div className="subsection-heading">
                <div>
                  <h3>Refresh saved Instagram profiles</h3>
                  <p>Recheck every Instagram handle already attached to this campaign's leads.</p>
                </div>
                <span className="step-badge">02</span>
              </div>
              <div className="social-bulk-action">
                <p>
                  Meta data is attached as an Instagram source, existing leads are reused by
                  handle, and campaign scoring runs once after enrichment.
                </p>
                <button
                  className="secondary-action"
                  type="button"
                  disabled={busy || !selectedSocialCampaign || !capabilities?.instagram_connected}
                  onClick={() => {
                    if (selectedSocialCampaign) {
                      void onEnrichKnownInstagram(selectedSocialCampaign.id);
                    }
                  }}
                >
                  <RefreshCw size={17} aria-hidden="true" /> Enrich saved Instagram profiles
                </button>
              </div>
            </div>
          </div>
        </TaskPanel>
      ) : null}

      {socialTask === "search" ? (
        <TaskPanel id="social-actions" tabId="search" className="social-action-panel">
          <div className="records-panel form-panel--bounded">
            <div className="subsection-heading">
              <div>
                <h3>Find public business profiles</h3>
                <p>Instagram opens campaign hashtags; Facebook opens public web results.</p>
              </div>
            </div>
            <div className="social-search-content">
              <div className="social-search-list">
                {socialSearches.map((search) => (
                  <button
                    className="secondary-action"
                    key={`${search.platform}-${search.term}`}
                    type="button"
                    disabled={busy}
                    onClick={() => void onOpenSocialSearch(search.url)}
                  >
                    {search.platform === "instagram"
                      ? `Open Instagram #${search.hashtag}`
                      : `Search Facebook for ${search.term}`}
                  </button>
                ))}
              </div>
              <p className="form-hint">
                Meta's hashtag results do not expose the post author's account to this app.
                Copy a relevant Instagram profile URL, then use Instagram import. These links do
                not scrape results or send messages.
              </p>
            </div>
          </div>
        </TaskPanel>
      ) : null}

      {socialTask === "facebook" ? (
        <TaskPanel id="social-actions" tabId="facebook" className="social-action-panel">
          <div className="form-panel form-panel--bounded">
            <div className="subsection-heading">
              <div>
                <h3>Capture verified Facebook lead</h3>
                <p>Enter only public business details you verified from the selected profile.</p>
              </div>
            </div>
            <form className="form-grid" onSubmit={(event) => void captureFacebook(event)}>
              <input name="social-campaign" type="hidden" value={selectedSocialCampaign?.id ?? ""} />
              <label>
                Public Facebook profile URL
                <div className="field-with-action">
                  <input
                    ref={facebookProfileUrlRef}
                    name="social-profile-url"
                    type="url"
                    required
                    placeholder="https://www.facebook.com/example"
                  />
                  <button
                    type="button"
                    className="icon-button"
                    title="Paste from clipboard"
                    aria-label="Paste Facebook profile URL from clipboard"
                    onClick={() => {
                      void pasteFromClipboard().then((text) => {
                        if (text && facebookProfileUrlRef.current) {
                          facebookProfileUrlRef.current.value = text;
                        }
                      });
                    }}
                  >
                    <ClipboardPaste size={16} aria-hidden="true" />
                  </button>
                </div>
              </label>
              <div className="field-pair">
                <label>Business name<input name="social-business-name" required maxLength={300} /></label>
                <label>Location<input name="social-location" required defaultValue={selectedSocialCampaign?.primary_location ?? ""} /></label>
              </div>
              <label>Website <span className="optional-label">Optional</span><input name="social-website" type="url" /></label>
              <div className="field-pair">
                <label>Public phone <span className="optional-label">Optional</span><input name="social-phone" type="tel" maxLength={100} /></label>
                <label>Public email <span className="optional-label">Optional</span><input name="social-email" type="email" maxLength={320} /></label>
              </div>
              <label>Public profile bio <span className="optional-label">Optional</span><textarea name="social-bio" rows={3} maxLength={2000} /></label>
              <div className="form-actions">
                <p>Exact profile, website and phone matches reuse the existing lead.</p>
                <button className="primary-action" type="submit" disabled={busy || !selectedSocialCampaign}>
                  <UserPlus size={17} aria-hidden="true" /> Capture, score and match
                </button>
              </div>
            </form>
          </div>
        </TaskPanel>
      ) : null}
    </section>
  );
}
