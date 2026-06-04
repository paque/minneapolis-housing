import { readFile } from "node:fs/promises";
import path from "node:path";

import type { ConfidenceLevel } from "./confidence";
import { withBasePath } from "./urls";

const DATA_DIR = path.join(process.cwd(), "public", "data");

export type PropertyRecord = {
  property_id: string;
  canonical_address: string;
  city: string;
  state: string;
  zip: string;
  parcel_id: string;
  latitude: number | null;
  longitude: number | null;
  current_owner_name: string;
  current_taxpayer_name: string;
  property_type: string;
  estimated_unit_count: number | null;
  current_status: string;
  confidence_level: ConfidenceLevel;
  confidence_score: number;
  public_notes: string;
  first_seen_date: string;
  last_seen_date: string;
  is_current: boolean;
  detail_url_slug: string;
};

export type PublicDataEnvelope = {
  schema_version: string;
  generated_at: string | null;
  properties: PropertyRecord[];
};

export type SourceRecord = {
  source_id: string;
  source_name: string;
  source_agency: string;
  source_type: string;
  source_url: string;
  retrieved_at: string;
  record_date: string;
  raw_file_uri: string;
  sha256_hash: string;
  public_citation_text: string;
};

export type EvidenceRecord = {
  evidence_id: string;
  property_id: string;
  source_id: string;
  claim_type: string;
  claim_value: string;
  confidence_contribution: number;
  evidence_note: string;
};

export type ChangeEvent = {
  event_id: string;
  property_id: string;
  event_date: string;
  event_type: string;
  old_value: string;
  new_value: string;
  source_id: string;
  public_note: string;
};

export type SourcesEnvelope = {
  schema_version: string;
  generated_at: string | null;
  source_records: SourceRecord[];
  property_evidence: EvidenceRecord[];
};

export type HistoryEnvelope = {
  schema_version: string;
  generated_at: string | null;
  property_versions: unknown[];
  change_events: ChangeEvent[];
};

export type ChangelogEnvelope = {
  schema_version: string;
  generated_at: string | null;
  changes: ChangeEvent[];
};

export type PropertyFact = {
  property_id: string;
  parcel_id: string;
  source_ids: string;
  sale_date: string;
  sale_value: number | null;
  assessed_land_value: number | null;
  assessed_building_value: number | null;
  assessed_total_value: number | null;
  tax_year: number | null;
  market_year: number | null;
  total_tax: number | null;
  use_classes: string;
  zoning: string;
  land_use: string;
  parcel_area_sqft: number | null;
  acres: number | null;
  year_built: number | null;
  finished_sqft: number | null;
  above_ground_area: number | null;
  below_ground_area: number | null;
  total_units: number | null;
  building_use: string;
};

export type PropertyPermit = {
  property_id: string;
  parcel_id: string;
  permit_number: string;
  permit_type: string;
  work_type: string;
  occupancy_type: string;
  status: string;
  milestone: string;
  value: number | null;
  dwelling_units_new: number | null;
  dwelling_units_eliminated: number | null;
  issue_date: string;
  complete_date: string;
  work_description: string;
  match_method: string;
  source_id: string;
};

export type PropertyFactsEnvelope = {
  schema_version: string;
  generated_at: string | null;
  property_facts: PropertyFact[];
};

export type PropertyPermitsEnvelope = {
  schema_version: string;
  generated_at: string | null;
  property_permits: PropertyPermit[];
};

async function readJsonFile<T>(filename: string, fallback: T): Promise<T> {
  try {
    const body = await readFile(path.join(DATA_DIR, filename), "utf8");
    return JSON.parse(body) as T;
  } catch {
    return fallback;
  }
}

export async function getPropertiesPayload(): Promise<PublicDataEnvelope> {
  return readJsonFile<PublicDataEnvelope>("properties.json", {
    schema_version: "1.0.0",
    generated_at: null,
    properties: []
  });
}

export async function getProperties(): Promise<PropertyRecord[]> {
  const payload = await getPropertiesPayload();
  return payload.properties;
}

export async function getPropertyBySlug(
  slug: string
): Promise<PropertyRecord | undefined> {
  const properties = await getProperties();
  return properties.find(
    (property) =>
      property.detail_url_slug === slug || property.property_id === slug
  );
}

export async function getSources(): Promise<SourcesEnvelope> {
  return readJsonFile<SourcesEnvelope>("sources.json", {
    schema_version: "1.0.0",
    generated_at: null,
    source_records: [],
    property_evidence: []
  });
}

export async function getPropertyHistory(): Promise<HistoryEnvelope> {
  return readJsonFile<HistoryEnvelope>("property-history.json", {
    schema_version: "1.0.0",
    generated_at: null,
    property_versions: [],
    change_events: []
  });
}

export async function getChangelog(): Promise<ChangelogEnvelope> {
  return readJsonFile<ChangelogEnvelope>("changelog.json", {
    schema_version: "1.0.0",
    generated_at: null,
    changes: []
  });
}

export async function getPropertyFacts(): Promise<PropertyFactsEnvelope> {
  return readJsonFile<PropertyFactsEnvelope>("property-facts.json", {
    schema_version: "1.0.0",
    generated_at: null,
    property_facts: []
  });
}

export async function getPropertyPermits(): Promise<PropertyPermitsEnvelope> {
  return readJsonFile<PropertyPermitsEnvelope>("property-permits.json", {
    schema_version: "1.0.0",
    generated_at: null,
    property_permits: []
  });
}

export async function getPropertyFactByPropertyId(propertyId: string): Promise<PropertyFact | undefined> {
  const payload = await getPropertyFacts();
  return payload.property_facts.find((fact) => fact.property_id === propertyId);
}

export async function getPropertyPermitsByPropertyId(propertyId: string): Promise<PropertyPermit[]> {
  const payload = await getPropertyPermits();
  return payload.property_permits
    .filter((permit) => permit.property_id === propertyId)
    .sort((left, right) => {
      const rightDate = right.issue_date || right.complete_date;
      const leftDate = left.issue_date || left.complete_date;
      return rightDate.localeCompare(leftDate) || right.permit_number.localeCompare(left.permit_number);
    });
}

export function formatGeneratedAt(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function formatCurrency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "Not listed";
  }
  const numericValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numericValue)) {
    return "Not listed";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(numericValue);
}

export function formatNumber(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "Not listed";
  }
  const numericValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numericValue)) {
    return "Not listed";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(numericValue);
}

export function formatPublicDate(value: string | null | undefined): string {
  if (!value) {
    return "Not listed";
  }
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) {
    return "Not listed";
  }
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(
    new Date(year, month - 1, day)
  );
}

export function getPropertyHref(property: Pick<PropertyRecord, "detail_url_slug" | "property_id">): string {
  return withBasePath(`/properties/${property.detail_url_slug || property.property_id}/`);
}

export function getMinneapolisParcelUrl(parcelId: string): string | null {
  const normalized = parcelId.replace(/[^0-9A-Za-z]/g, "").replace(/^p/i, "");
  if (!normalized) {
    return null;
  }
  return `https://apps.ci.minneapolis.mn.us/PIApp/Home/PropertySummary/${normalized}`;
}

export function formatChangeEventType(value: string): string {
  const labels: Record<string, string> = {
    owner_name_changed: "Owner name updated",
    taxpayer_name_changed: "Taxpayer name updated",
    property_type_changed: "Property classification updated",
    estimated_unit_count_changed: "Estimated unit count updated",
    status_changed: "Status updated",
    confidence_changed: "Confidence label updated"
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

export function formatClaimType(value: string): string {
  const labels: Record<string, string> = {
    official_scattered_site_listing: "Official scattered-site listing",
    owner_taxpayer_match: "Owner or taxpayer match",
    parcel_match: "Parcel match",
    portfolio_context: "Portfolio context",
    public_housing_property_record: "Public housing property record"
  };
  return labels[value] ?? value.replaceAll("_", " ");
}
