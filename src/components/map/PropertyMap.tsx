import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  getSourceCategory,
  sourceCategoryLabels,
  visibleSourceCategories
} from "@lib/sourceCategories";
import { withBasePath } from "@lib/urls";

type PropertyMapProps = {
  dataUrl: string;
  boundaryDataUrl: string;
  sourceDataUrl: string;
  styleUrl: string;
};

type PointFeature = {
  type: "Feature";
  properties: Record<string, string | number | boolean | null>;
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
};

type FeatureCollection = {
  type: "FeatureCollection";
  metadata?: Record<string, unknown>;
  features: PointFeature[];
};

type BoundaryFeature = {
  type: "Feature";
  properties: {
    layer_id?: string;
    layer_name?: string;
    name?: string;
    label?: string;
    source_id?: string;
  };
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: number[][][] | number[][][][];
  };
};

type BoundaryFeatureCollection = {
  type: "FeatureCollection";
  metadata?: Record<string, unknown>;
  features: BoundaryFeature[];
};

type EvidenceRecord = {
  property_id: string;
  source_id: string;
  claim_type: string;
};

type SourcesEnvelope = {
  property_evidence: EvidenceRecord[];
};

type FilterState = {
  confidence: string;
  status: string;
  source: string;
  units: string;
  ward: string;
  neighborhood: string;
  community: string;
  precinct: string;
  sector: string;
};

const defaultFilters: FilterState = {
  confidence: "",
  status: "",
  source: "",
  units: "",
  ward: "",
  neighborhood: "",
  community: "",
  precinct: "",
  sector: ""
};

type OverlayKey = "city_limits" | "wards" | "neighborhoods" | "communities" | "police_precincts" | "police_sectors";

type OverlayState = Record<OverlayKey, boolean>;

const defaultOverlays: OverlayState = {
  city_limits: true,
  wards: true,
  neighborhoods: false,
  communities: false,
  police_precincts: false,
  police_sectors: false
};

type CivicOptions = {
  wards: string[];
  neighborhoods: string[];
  communities: string[];
  precincts: string[];
  sectors: string[];
};

const defaultCivicOptions: CivicOptions = {
  wards: [],
  neighborhoods: [],
  communities: [],
  precincts: [],
  sectors: []
};

const boundaryLayerConfigs: {
  key: OverlayKey;
  layerId: string;
  label: string;
  color: string;
  fillOpacity: number;
  labelMinZoom: number;
  lineWidth: [number, number];
}[] = [
  { key: "city_limits", layerId: "city_limits", label: "City limits", color: "#1f2937", fillOpacity: 0.01, labelMinZoom: 9, lineWidth: [2.4, 4] },
  { key: "wards", layerId: "wards", label: "Wards", color: "#2f7d5a", fillOpacity: 0.08, labelMinZoom: 9, lineWidth: [1.6, 3] },
  { key: "neighborhoods", layerId: "neighborhoods", label: "Neighborhoods", color: "#356d8c", fillOpacity: 0.06, labelMinZoom: 11, lineWidth: [0.8, 1.8] },
  { key: "communities", layerId: "communities", label: "Communities", color: "#8a6b25", fillOpacity: 0.05, labelMinZoom: 9.5, lineWidth: [1.1, 2.2] },
  { key: "police_precincts", layerId: "police_precincts", label: "Police precincts", color: "#8b4d36", fillOpacity: 0.05, labelMinZoom: 9.5, lineWidth: [1.1, 2.2] },
  { key: "police_sectors", layerId: "police_sectors", label: "MPD sectors", color: "#5a5f72", fillOpacity: 0.04, labelMinZoom: 10, lineWidth: [0.9, 1.9] }
];

const confidenceColor = [
  "match",
  ["get", "confidence_level"],
  "confirmed",
  "#255f4a",
  "likely",
  "#c79238",
  "uncertain",
  "#356d8c",
  "excluded",
  "#a75f45",
  "#356d8c"
];

function getNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

function getString(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function featureMatchesFilters(feature: PointFeature, filters: FilterState): boolean {
  const properties = feature.properties;

  if (filters.confidence && getString(properties.confidence_level) !== filters.confidence) {
    return false;
  }

  if (filters.status) {
    const currentValue = properties.is_current;
    const isCurrent = currentValue === true || currentValue === "true" || currentValue === 1;
    if (filters.status === "current" && !isCurrent) {
      return false;
    }
    if (filters.status === "historical" && isCurrent) {
      return false;
    }
  }

  if (filters.source) {
    const sourceCategories = getString(properties.source_categories);
    if (!sourceCategories.includes(`|${filters.source}|`)) {
      return false;
    }
  }

  if (filters.units) {
    const units = getNumber(properties.estimated_unit_count);
    if (filters.units === "unknown") {
      return units === null;
    }
    if (units === null) {
      return false;
    }
    if (filters.units === "zero") {
      return units === 0;
    }
    if (filters.units === "one") {
      return units === 1;
    }
    if (filters.units === "two_to_four") {
      return units >= 2 && units <= 4;
    }
    if (filters.units === "five_plus") {
      return units >= 5;
    }
  }

  if (filters.ward && getString(properties.ward) !== filters.ward) {
    return false;
  }

  if (filters.neighborhood && getString(properties.neighborhood) !== filters.neighborhood) {
    return false;
  }

  if (filters.community && getString(properties.community) !== filters.community) {
    return false;
  }

  if (filters.precinct && getString(properties.police_precinct) !== filters.precinct) {
    return false;
  }

  if (filters.sector && getString(properties.police_sector) !== filters.sector) {
    return false;
  }

  return true;
}

function filterFeatureCollection(geojson: FeatureCollection, filters: FilterState): FeatureCollection {
  return {
    ...geojson,
    features: geojson.features.filter((feature) => featureMatchesFilters(feature, filters))
  };
}

function getStatusText(visibleCount: number, totalCount: number): string {
  if (totalCount === 0) {
    return "No mapped property records yet";
  }
  if (visibleCount === 0) {
    return "No mapped properties match filters";
  }
  if (visibleCount === totalCount) {
    return `${totalCount.toLocaleString()} mapped properties`;
  }
  return `${visibleCount.toLocaleString()} of ${totalCount.toLocaleString()} mapped properties`;
}

function fitToFeatures(map: maplibregl.Map, features: PointFeature[]) {
  const coordinates = features
    .filter((feature) => feature.geometry?.type === "Point")
    .map((feature) => feature.geometry.coordinates);

  if (coordinates.length === 0) {
    return;
  }

  const bounds = coordinates.reduce(
    (currentBounds, coordinate) => currentBounds.extend(coordinate),
    new maplibregl.LngLatBounds(coordinates[0], coordinates[0])
  );
  map.fitBounds(bounds, { padding: 56, maxZoom: 14 });
}

function uniqueSorted(features: PointFeature[], field: string): string[] {
  return Array.from(
    new Set(
      features
        .map((feature) => getString(feature.properties[field]))
        .filter(Boolean)
    )
  ).sort((left, right) => left.localeCompare(right, "en-US", { numeric: true, sensitivity: "base" }));
}

function getCivicOptions(features: PointFeature[]): CivicOptions {
  return {
    wards: uniqueSorted(features, "ward"),
    neighborhoods: uniqueSorted(features, "neighborhood"),
    communities: uniqueSorted(features, "community"),
    precincts: uniqueSorted(features, "police_precinct"),
    sectors: uniqueSorted(features, "police_sector")
  };
}

function setBoundaryVisibility(map: maplibregl.Map, overlays: OverlayState) {
  for (const config of boundaryLayerConfigs) {
    const visibility = overlays[config.key] ? "visible" : "none";
    for (const suffix of ["fill", "line", "label"]) {
      const id = `boundary-${config.key}-${suffix}`;
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, "visibility", visibility);
      }
    }
  }
}

function addBoundaryLayers(
  map: maplibregl.Map,
  boundaries: BoundaryFeatureCollection,
  overlays: OverlayState
) {
  if (!map.getSource("civic-boundaries")) {
    map.addSource("civic-boundaries", {
      type: "geojson",
      data: boundaries as any
    });
  }

  for (const config of boundaryLayerConfigs) {
    const filter = ["==", ["get", "layer_id"], config.layerId] as any;
    const visibility = overlays[config.key] ? "visible" : "none";
    const fillLayerId = `boundary-${config.key}-fill`;
    const lineLayerId = `boundary-${config.key}-line`;
    const labelLayerId = `boundary-${config.key}-label`;

    if (!map.getLayer(fillLayerId)) {
      map.addLayer({
        id: fillLayerId,
        type: "fill",
        source: "civic-boundaries",
        filter,
        layout: { visibility },
        paint: {
          "fill-color": config.color,
          "fill-opacity": config.fillOpacity
        }
      });
    }

    if (!map.getLayer(lineLayerId)) {
      map.addLayer({
        id: lineLayerId,
        type: "line",
        source: "civic-boundaries",
        filter,
        layout: { visibility },
        paint: {
          "line-color": config.color,
          "line-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            9,
            config.lineWidth[0],
            14,
            config.lineWidth[1]
          ],
          "line-opacity": 0.86
        }
      });
    }

    if (!map.getLayer(labelLayerId)) {
      map.addLayer({
        id: labelLayerId,
        type: "symbol",
        source: "civic-boundaries",
        filter,
        minzoom: config.labelMinZoom,
        layout: {
          visibility,
          "text-field": ["get", "label"],
          "text-font": ["Open Sans Regular"],
          "text-size": [
            "interpolate",
            ["linear"],
            ["zoom"],
            9,
            config.key === "city_limits" ? 14 : 11,
            14,
            config.key === "city_limits" ? 18 : 15
          ],
          "text-allow-overlap": false,
          "text-ignore-placement": false,
          "symbol-placement": "point"
        },
        paint: {
          "text-color": config.color,
          "text-halo-color": "#ffffff",
          "text-halo-width": 1.25,
          "text-opacity": 0.94
        }
      });
    }
  }
}

function enrichFeaturesWithSources(
  geojson: FeatureCollection,
  sources: SourcesEnvelope
): FeatureCollection {
  const categoriesByProperty = new Map<string, Set<string>>();

  for (const evidence of sources.property_evidence ?? []) {
    const categories = categoriesByProperty.get(evidence.property_id) ?? new Set<string>();
    categories.add(getSourceCategory(evidence));
    categoriesByProperty.set(evidence.property_id, categories);
  }

  return {
    ...geojson,
    features: geojson.features.map((feature) => {
      const propertyId = getString(feature.properties.property_id);
      const categories = Array.from(categoriesByProperty.get(propertyId) ?? []);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          source_categories: categories.length > 0 ? `|${categories.join("|")}|` : ""
        }
      };
    })
  };
}

export default function PropertyMap({ dataUrl, boundaryDataUrl, sourceDataUrl, styleUrl }: PropertyMapProps) {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const allGeojsonRef = useRef<FeatureCollection | null>(null);
  const filtersRef = useRef<FilterState>(defaultFilters);
  const overlaysRef = useRef<OverlayState>(defaultOverlays);
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [overlays, setOverlays] = useState<OverlayState>(defaultOverlays);
  const [civicOptions, setCivicOptions] = useState<CivicOptions>(defaultCivicOptions);
  const [status, setStatus] = useState("Loading property layer");
  const hasActiveFilters = Object.values(filters).some(Boolean);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    overlaysRef.current = overlays;
    const map = mapRef.current;
    if (map) {
      setBoundaryVisibility(map, overlays);
    }
  }, [overlays]);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: styleUrl,
      center: [-93.265, 44.9778],
      zoom: 10.8,
      attributionControl: false
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "Public records data"
      }),
      "bottom-right"
    );

    let isDisposed = false;
    let isLoadingProperties = false;
    let didLoadProperties = false;

    const loadProperties = async () => {
      if (isDisposed || isLoadingProperties || didLoadProperties) {
        return;
      }

      isLoadingProperties = true;

      try {
        const response = await fetch(dataUrl);
        if (!response.ok) {
          throw new Error(`Could not load ${dataUrl}`);
        }

        const sourceResponse = await fetch(sourceDataUrl);
        if (!sourceResponse.ok) {
          throw new Error(`Could not load ${sourceDataUrl}`);
        }

        let boundaries: BoundaryFeatureCollection = {
          type: "FeatureCollection",
          features: []
        };
        try {
          const boundaryResponse = await fetch(boundaryDataUrl);
          if (boundaryResponse.ok) {
            boundaries = (await boundaryResponse.json()) as BoundaryFeatureCollection;
          }
        } catch {
          boundaries = {
            type: "FeatureCollection",
            features: []
          };
        }

        const geojson = (await response.json()) as FeatureCollection;
        const sources = (await sourceResponse.json()) as SourcesEnvelope;
        const enrichedGeojson = enrichFeaturesWithSources(geojson, sources);
        const filteredGeojson = filterFeatureCollection(enrichedGeojson, filtersRef.current);
        allGeojsonRef.current = enrichedGeojson;
        setCivicOptions(getCivicOptions(enrichedGeojson.features));

        addBoundaryLayers(map, boundaries, overlaysRef.current);

        if (!map.getSource("properties")) {
          map.addSource("properties", {
            type: "geojson",
            data: filteredGeojson as any
          });
        }

        if (!map.getLayer("property-points")) {
          map.addLayer({
            id: "property-points",
            type: "circle",
            source: "properties",
            paint: {
              "circle-color": confidenceColor as any,
              "circle-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                9,
                4,
                14,
                8
              ],
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 1.5,
              "circle-opacity": 0.92
            }
          });
        }

        map.on("mouseenter", "property-points", () => {
          map.getCanvas().style.cursor = "pointer";
        });

        map.on("mouseleave", "property-points", () => {
          map.getCanvas().style.cursor = "";
        });

        map.on("click", "property-points", (event) => {
          const feature = event.features?.[0];
          if (!feature || feature.geometry.type !== "Point") {
            return;
          }

          const coordinates = feature.geometry.coordinates as [number, number];
          const properties = feature.properties ?? {};
          const slug = properties.detail_url_slug || properties.property_id;
          const address = properties.canonical_address || "Address unavailable";
          const officialName = properties.official_property_name;
          const officialAddress = properties.official_listed_address;
          const confidence = properties.confidence_level || "uncertain";
          const statusValue = properties.current_status || "Status not listed";
          const units = getString(properties.estimated_unit_count);
          const unitBasis = getString(properties.unit_count_confidence);
          const geography = [
            getString(properties.ward),
            getString(properties.neighborhood),
            getString(properties.police_precinct)
          ].filter(Boolean).join(" | ");
          const popupContent = document.createElement("div");
          popupContent.className = "p-3";

          const title = document.createElement("strong");
          title.className = "mb-1 block text-sm";
          title.textContent = String(officialName || address);
          popupContent.append(title);

          if (officialName) {
            const addressLine = document.createElement("span");
            addressLine.className = "mb-1 block text-xs";
            addressLine.textContent = String(address);
            popupContent.append(addressLine);
          }

          if (officialAddress && String(officialAddress).toLowerCase() !== String(address).toLowerCase()) {
            const aliasLine = document.createElement("span");
            aliasLine.className = "mb-1 block text-xs";
            aliasLine.textContent = `MPHA listed address: ${officialAddress}`;
            popupContent.append(aliasLine);
          }

          const meta = document.createElement("span");
          meta.className = "mb-2 block text-xs uppercase";
          meta.textContent = `${confidence} | ${statusValue}`;
          popupContent.append(meta);

          if (geography) {
            const geographyLine = document.createElement("span");
            geographyLine.className = "mb-1 block text-xs";
            geographyLine.textContent = geography;
            popupContent.append(geographyLine);
          }

          if (units) {
            const unitLine = document.createElement("span");
            unitLine.className = "mb-2 block text-xs";
            unitLine.textContent = `${units} unit${units === "1" ? "" : "s"}${unitBasis ? ` (${unitBasis})` : ""}`;
            popupContent.append(unitLine);
          }

          const link = document.createElement("a");
          link.href = withBasePath(`/properties/${slug}/`);
          link.className = "font-bold text-civic-green underline";
          link.textContent = "Open property record";
          popupContent.append(link);

          new maplibregl.Popup({ closeButton: true, maxWidth: "320px" })
            .setLngLat(coordinates)
            .setDOMContent(popupContent)
            .addTo(map);
        });

        fitToFeatures(map, filteredGeojson.features);
        setStatus(getStatusText(filteredGeojson.features.length, enrichedGeojson.features.length));
      } catch (error) {
        const message = error instanceof Error ? error.message : "Map data failed to load";
        if (!message.toLowerCase().includes("style is not done loading")) {
          setStatus(message);
        }
        isLoadingProperties = false;
        return;
      }

      didLoadProperties = true;
      isLoadingProperties = false;
    };

    map.on("styledata", () => {
      void loadProperties();
    });
    map.on("load", () => {
      void loadProperties();
    });

    const fallbackTimer = window.setTimeout(() => {
      void loadProperties();
    }, 750);

    return () => {
      isDisposed = true;
      window.clearTimeout(fallbackTimer);
      map.remove();
      mapRef.current = null;
    };
  }, [dataUrl, boundaryDataUrl, sourceDataUrl, styleUrl]);

  useEffect(() => {
    const map = mapRef.current;
    const geojson = allGeojsonRef.current;
    if (!map || !geojson) {
      return;
    }

    const source = map.getSource("properties") as maplibregl.GeoJSONSource | undefined;
    if (!source) {
      return;
    }

    const filteredGeojson = filterFeatureCollection(geojson, filters);
    source.setData(filteredGeojson as any);
    fitToFeatures(map, filteredGeojson.features);
    setStatus(getStatusText(filteredGeojson.features.length, geojson.features.length));
  }, [filters]);

  function updateFilter(field: keyof FilterState, value: string) {
    setFilters((currentFilters) => ({
      ...currentFilters,
      [field]: value
    }));
  }

  function updateOverlay(field: OverlayKey, value: boolean) {
    setOverlays((currentOverlays) => ({
      ...currentOverlays,
      [field]: value
    }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  return (
    <section className="border-y border-line bg-white">
      <div className="border-b border-line bg-paper px-4 py-4 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
          <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Confidence</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.confidence}
                onChange={(event) => updateFilter("confidence", event.target.value)}
              >
                <option value="">All labels</option>
                <option value="confirmed">Confirmed</option>
                <option value="likely">Likely</option>
                <option value="uncertain">Uncertain</option>
                <option value="excluded">Excluded</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Record Status</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.status}
                onChange={(event) => updateFilter("status", event.target.value)}
              >
                <option value="">All records</option>
                <option value="current">Current</option>
                <option value="historical">Historical</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Source Type</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.source}
                onChange={(event) => updateFilter("source", event.target.value)}
              >
                <option value="">All sources</option>
                {visibleSourceCategories.map((value) => (
                  <option key={value} value={value}>{sourceCategoryLabels[value]}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Units</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.units}
                onChange={(event) => updateFilter("units", event.target.value)}
              >
                <option value="">Any units</option>
                <option value="zero">0 units</option>
                <option value="one">1 unit</option>
                <option value="two_to_four">2-4 units</option>
                <option value="five_plus">5+ units</option>
                <option value="unknown">Not listed</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Ward</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.ward}
                onChange={(event) => updateFilter("ward", event.target.value)}
              >
                <option value="">All wards</option>
                {civicOptions.wards.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Neighborhood</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.neighborhood}
                onChange={(event) => updateFilter("neighborhood", event.target.value)}
              >
                <option value="">All neighborhoods</option>
                {civicOptions.neighborhoods.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Community</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.community}
                onChange={(event) => updateFilter("community", event.target.value)}
              >
                <option value="">All communities</option>
                {civicOptions.communities.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">Precinct</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.precinct}
                onChange={(event) => updateFilter("precinct", event.target.value)}
              >
                <option value="">All precincts</option>
                {civicOptions.precincts.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-normal text-ink/55">MPD Sector</span>
              <select
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm shadow-sm focus:shadow-focus"
                value={filters.sector}
                onChange={(event) => updateFilter("sector", event.target.value)}
              >
                <option value="">All sectors</option>
                {civicOptions.sectors.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
          </div>
          <fieldset className="rounded border border-line bg-white px-3 py-2 text-sm shadow-sm">
            <legend className="px-1 text-xs font-bold uppercase tracking-normal text-ink/55">Overlays</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {boundaryLayerConfigs.map((config) => (
                <label key={config.key} className="inline-flex items-center gap-2">
                  <input
                    checked={overlays[config.key]}
                    className="h-4 w-4 rounded border-line text-civic-green focus:shadow-focus"
                    onChange={(event) => updateOverlay(config.key, event.target.checked)}
                    type="checkbox"
                  />
                  <span>{config.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center lg:justify-end">
            <p className="text-sm font-semibold text-ink/65" aria-live="polite">{status}</p>
            <button
              className="rounded border border-line bg-white px-3 py-2 text-sm font-bold text-ink hover:border-civic-green hover:text-civic-green disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!hasActiveFilters}
              onClick={resetFilters}
              type="button"
            >
              Reset
            </button>
          </div>
        </div>
      </div>
      <div className="relative h-[68vh] min-h-[480px] w-full overflow-hidden bg-white">
        <div ref={mapContainer} className="h-full w-full" aria-label="Property map" />
        <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 rounded border border-line bg-white p-2 text-xs font-semibold text-ink shadow-sm">
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-green" />Confirmed</span>
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-gold" />Likely</span>
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-lake" />Uncertain</span>
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-clay" />Excluded</span>
        </div>
      </div>
    </section>
  );
}
