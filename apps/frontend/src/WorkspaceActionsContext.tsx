import { createContext, useContext } from "react";

import type {
  CampaignInput,
  CampaignRunProvider,
  CampaignUpdate,
  LeadInput,
  LeadUpdate,
  ProductFamilyInput,
  ProductFamilyUpdate,
  ProductInput,
  ProductUpdate,
  SocialCandidateInput,
  TemplateInput,
  TemplateUpdate,
} from "./api";
import type {
  BackupResult,
  InstagramProfilePreview,
  ScoringWeights,
  ShopifyImportResult,
  VerificationResult,
  WorkspaceSettings,
} from "./types";

/**
 * Cross-cutting operational actions and status shared by every workspace,
 * provided once from App so individual workspace components don't each need
 * a long list of handler props for functionality they all use the same way.
 * Data specific to a single workspace (campaigns, leads, products, ...) still
 * flows in as ordinary props.
 */
export interface WorkspaceActions {
  busy: boolean;
  loading: boolean;
  manageLead: (leadId: string) => void;
  goToCreateCampaign: () => void;
  goToShortlist: () => void;
  goToCampaigns: () => void;
  goToLeads: () => void;
  goToLeadsNeedingReview: () => void;
  goToCatalogue: () => void;
  createCampaign: (data: CampaignInput) => Promise<boolean>;
  updateCampaign: (campaignId: string, data: CampaignUpdate) => Promise<boolean>;
  duplicateCampaign: (campaignId: string, name: string) => Promise<boolean>;
  runCampaign: (campaignId: string, provider: CampaignRunProvider) => Promise<boolean>;
  runAllCampaigns: (provider: CampaignRunProvider) => Promise<boolean>;
  openSocialSearch: (url: string) => Promise<boolean>;
  captureSocialCandidate: (data: SocialCandidateInput) => Promise<boolean>;
  previewInstagramProfile: (profileUrl: string) => Promise<InstagramProfilePreview | null>;
  importInstagramProfile: (campaignId: string, profileUrl: string) => Promise<boolean>;
  enrichKnownInstagramProfiles: (campaignId: string) => Promise<boolean>;
  cancelCampaignRun: (runId: string) => Promise<boolean>;
  decideDiscoveryCandidate: (
    candidateId: string,
    action: "promote" | "link" | "reject",
    leadId?: string,
  ) => Promise<boolean>;
  createLead: (data: LeadInput) => Promise<boolean>;
  updateLead: (leadId: string, data: LeadUpdate) => Promise<boolean>;
  changeLeadStage: (leadId: string, stage: string, reason?: string) => Promise<boolean>;
  addNote: (leadId: string, content: string) => Promise<boolean>;
  addFollowUp: (leadId: string, data: Record<string, unknown>) => Promise<boolean>;
  completeFollowUp: (leadId: string, followUpId: string) => Promise<boolean>;
  addCommunication: (leadId: string, data: Record<string, unknown>) => Promise<boolean>;
  suppressLead: (leadId: string, data: Record<string, unknown>) => Promise<boolean>;
  liftSuppression: (leadId: string) => Promise<boolean>;
  deleteLead: (leadId: string) => Promise<boolean>;
  calculateScore: (leadId: string, campaignId: string) => Promise<boolean>;
  overrideScore: (leadId: string, finalScore: number, reason: string) => Promise<boolean>;
  createProduct: (data: ProductInput) => Promise<boolean>;
  updateProduct: (productId: string, data: ProductUpdate) => Promise<boolean>;
  importShopifyCsv: (filename: string, content: string) => Promise<ShopifyImportResult | null>;
  updateScoringProfile: (name: string, weights: ScoringWeights) => Promise<boolean>;
  generateShortlist: (campaignId: string, weekStart: string, size: number) => Promise<boolean>;
  shortlistAction: (
    shortlistId: string,
    itemId: string,
    action: string,
    reason?: string,
  ) => Promise<boolean>;
  saveSettings: (data: Partial<WorkspaceSettings>) => Promise<boolean>;
  exportLeads: (format: "csv" | "json") => Promise<boolean>;
  createBackup: (targetDirectory: string) => Promise<BackupResult | null>;
  verifyBackup: (backupPath: string) => Promise<VerificationResult | null>;
  configureMeta: (appId: string, appSecret: string) => Promise<boolean>;
  startMetaAuthorization: () => Promise<boolean>;
  selectMetaAccount: (pageId: string) => Promise<boolean>;
  disconnectMeta: (removeConfiguration?: boolean) => Promise<boolean>;
  createTemplate: (data: TemplateInput) => Promise<boolean>;
  updateTemplate: (templateId: string, data: TemplateUpdate) => Promise<boolean>;
  deleteTemplate: (templateId: string) => Promise<boolean>;
  createProductFamily: (data: ProductFamilyInput) => Promise<boolean>;
  updateProductFamily: (familyId: string, data: ProductFamilyUpdate) => Promise<boolean>;
  deleteProductFamily: (familyId: string) => Promise<boolean>;
  sendContactMessage: (
    leadId: string,
    channel: "whatsapp" | "email" | "instagram",
    url: string,
    channelLabel: string,
    content: string,
    subject?: string,
  ) => Promise<boolean>;
}

export const WorkspaceActionsContext = createContext<WorkspaceActions | null>(null);

export function useWorkspaceActions(): WorkspaceActions {
  const value = useContext(WorkspaceActionsContext);
  if (!value) {
    throw new Error("useWorkspaceActions must be used within a WorkspaceActionsContext.Provider");
  }
  return value;
}
