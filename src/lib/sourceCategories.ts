export type EvidenceSourceCategory =
  | "official_mpha"
  | "hud"
  | "parcel"
  | "assessing"
  | "portfolio"
  | "other";

export type SourceCategoryEvidence = {
  property_id?: string;
  source_id: string;
  claim_type: string;
};

export const sourceCategoryLabels: Record<EvidenceSourceCategory, string> = {
  official_mpha: "Official MPHA listing",
  hud: "Direct HUD listing",
  parcel: "Parcel owner/taxpayer",
  assessing: "Annual assessing",
  portfolio: "MPHA context",
  other: "Other source"
};

export const visibleSourceCategories: EvidenceSourceCategory[] = [
  "official_mpha",
  "hud",
  "parcel",
  "assessing",
  "portfolio"
];

export function getSourceCategory(evidence: SourceCategoryEvidence): EvidenceSourceCategory {
  const sourceId = evidence.source_id.toLowerCase();
  const claimType = evidence.claim_type.toLowerCase();

  if (sourceId.includes("mpha") && claimType === "public_housing_property_record") {
    return "official_mpha";
  }
  if (sourceId.includes("hud") || claimType === "official_scattered_site_listing") {
    return "hud";
  }
  if (sourceId.includes("metrogis")) {
    return "parcel";
  }
  if (sourceId.includes("assessing")) {
    return "assessing";
  }
  if (sourceId.includes("mpha") || claimType === "portfolio_context") {
    return "portfolio";
  }
  return "other";
}
