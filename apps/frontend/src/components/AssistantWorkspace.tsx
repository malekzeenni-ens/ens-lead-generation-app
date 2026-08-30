import type {
  AssistantContextSelection,
  AutomationCapabilities,
  Campaign,
  Lead,
  OutreachBatch,
  ProductFamily,
  Shortlist,
} from "../types";
import { CampaignAssistantTab } from "./CampaignAssistantTab";
import { PageHeader } from "./DesignSystem";

interface AssistantWorkspaceProps {
  capabilities: AutomationCapabilities | null;
  productFamilies: ProductFamily[];
  onCampaignApproved: () => void;
  campaigns: Campaign[];
  leads: Lead[];
  batches: OutreachBatch[];
  shortlists: Shortlist[];
  initialContext: AssistantContextSelection;
}

export function AssistantWorkspace({
  capabilities,
  productFamilies,
  onCampaignApproved,
  campaigns,
  leads,
  batches,
  shortlists,
  initialContext,
}: AssistantWorkspaceProps) {
  return (
    <>
      <PageHeader
        eyebrow="Private local AI"
        title="AI assistant"
        description="Use live local workspace context to review campaigns, leads and next actions, or prepare a controlled campaign draft."
      />

      <CampaignAssistantTab
        capabilities={capabilities}
        productFamilies={productFamilies}
        onApproved={onCampaignApproved}
        campaigns={campaigns}
        leads={leads}
        batches={batches}
        shortlists={shortlists}
        initialContext={initialContext}
      />
    </>
  );
}
