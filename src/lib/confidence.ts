export type ConfidenceLevel = "confirmed" | "likely" | "uncertain" | "excluded";

export const confidenceDefinitions: Record<
  ConfidenceLevel,
  { label: string; description: string; className: string }
> = {
  confirmed: {
    label: "Confirmed",
    description:
      "Direct public evidence identifies the property as MPHA/CHR scattered-site housing or an equivalent public housing record.",
    className: "bg-civic-green text-white border-civic-green"
  },
  likely: {
    label: "Likely",
    description:
      "Owner, taxpayer, parcel, or address evidence strongly suggests the property belongs in the portfolio.",
    className: "bg-civic-gold text-ink border-civic-gold"
  },
  uncertain: {
    label: "Uncertain",
    description:
      "The evidence is weak, incomplete, stale, or conflicting and needs additional review.",
    className: "bg-white text-ink border-line"
  },
  excluded: {
    label: "Excluded",
    description:
      "Public evidence suggests the property should not be included in the current scattered-site portfolio.",
    className: "bg-civic-clay text-white border-civic-clay"
  }
};

export function isConfidenceLevel(value: string): value is ConfidenceLevel {
  return ["confirmed", "likely", "uncertain", "excluded"].includes(value);
}

export function getConfidenceDefinition(level: string) {
  return confidenceDefinitions[
    isConfidenceLevel(level) ? level : "uncertain"
  ];
}
