import { useState } from "react";

import type {
  AutomationCapabilities,
  Campaign,
  CampaignRun,
  ProductFamily,
  WorkspaceSettings,
} from "../types";
import { CampaignAutomationTab } from "./CampaignAutomationTab";
import { CampaignCreateTab } from "./CampaignCreateTab";
import { CampaignRegisterTab } from "./CampaignRegisterTab";
import { CampaignSocialTab } from "./CampaignSocialTab";
import { PageHeader, TaskPanel, TaskTabs } from "./DesignSystem";

interface CampaignWorkspaceProps {
  initialTask?: "campaigns" | "create";
  campaigns: Campaign[];
  campaignRuns: CampaignRun[];
  capabilities: AutomationCapabilities | null;
  settings: WorkspaceSettings | null;
  productFamilies: ProductFamily[];
}

type CampaignTask = "campaigns" | "create" | "automation" | "social";

export function CampaignWorkspace({
  initialTask = "campaigns",
  campaigns,
  campaignRuns,
  capabilities,
  settings,
  productFamilies,
}: CampaignWorkspaceProps) {
  const [activeTask, setActiveTask] = useState<CampaignTask>(initialTask);

  return (
    <>
      <PageHeader
        eyebrow="Campaign management"
        title="Campaigns"
        description="Create, revise, pause and duplicate focused local campaign definitions."
      />

      <TaskTabs
        id="campaign-tasks"
        label="Campaign tasks"
        activeId={activeTask}
        onChange={(task) => setActiveTask(task as CampaignTask)}
        items={[
          { id: "campaigns", label: "Campaigns", count: campaigns.length },
          { id: "create", label: "Create campaign" },
          { id: "automation", label: "Run automation", count: campaignRuns.length },
          { id: "social", label: "Social leads" },
        ]}
      />

      {activeTask === "create" ? (
        <TaskPanel id="campaign-tasks" tabId="create">
          <CampaignCreateTab
            capabilities={capabilities}
            settings={settings}
            productFamilies={productFamilies}
            onCreated={() => setActiveTask("campaigns")}
          />
        </TaskPanel>
      ) : null}

      {activeTask === "campaigns" ? (
        <TaskPanel id="campaign-tasks" tabId="campaigns">
          <CampaignRegisterTab
            campaigns={campaigns}
            campaignRuns={campaignRuns}
            capabilities={capabilities}
            productFamilies={productFamilies}
          />
        </TaskPanel>
      ) : null}

      {activeTask === "automation" ? (
        <TaskPanel id="campaign-tasks" tabId="automation">
          <CampaignAutomationTab
            campaigns={campaigns}
            campaignRuns={campaignRuns}
            capabilities={capabilities}
          />
        </TaskPanel>
      ) : null}

      {activeTask === "social" ? (
        <TaskPanel id="campaign-tasks" tabId="social">
          <CampaignSocialTab campaigns={campaigns} capabilities={capabilities} />
        </TaskPanel>
      ) : null}
    </>
  );
}
