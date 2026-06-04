import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { withBasePath } from "@lib/urls";

type PropertyMapProps = {
  dataUrl: string;
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
  features: PointFeature[];
};

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

export default function PropertyMap({ dataUrl, styleUrl }: PropertyMapProps) {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [status, setStatus] = useState("Loading property layer");

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

        const geojson = (await response.json()) as FeatureCollection;

        if (!map.getSource("properties")) {
          map.addSource("properties", {
            type: "geojson",
            data: geojson
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
          const confidence = properties.confidence_level || "uncertain";
          const statusValue = properties.current_status || "Status not listed";
          const popupContent = document.createElement("div");
          popupContent.className = "p-3";

          const title = document.createElement("strong");
          title.className = "mb-1 block text-sm";
          title.textContent = String(address);
          popupContent.append(title);

          const meta = document.createElement("span");
          meta.className = "mb-2 block text-xs uppercase";
          meta.textContent = `${confidence} | ${statusValue}`;
          popupContent.append(meta);

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

        const coordinates = geojson.features
          .filter((feature) => feature.geometry?.type === "Point")
          .map((feature) => feature.geometry.coordinates);

        if (coordinates.length > 0) {
          const bounds = coordinates.reduce(
            (currentBounds, coordinate) => currentBounds.extend(coordinate),
            new maplibregl.LngLatBounds(coordinates[0], coordinates[0])
          );
          map.fitBounds(bounds, { padding: 56, maxZoom: 14 });
          setStatus(`${coordinates.length.toLocaleString()} mapped properties`);
        } else {
          setStatus("No mapped property records yet");
        }
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
  }, [dataUrl, styleUrl]);

  return (
    <section className="relative h-[68vh] min-h-[480px] w-full overflow-hidden border-y border-line bg-white">
      <div ref={mapContainer} className="h-full w-full" aria-label="Property map" />
      <div className="absolute left-4 top-4 rounded border border-line bg-white px-3 py-2 text-sm font-semibold text-ink shadow-sm">
        {status}
      </div>
      <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 rounded border border-line bg-white p-2 text-xs font-semibold text-ink shadow-sm">
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-green" />Confirmed</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-gold" />Likely</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-lake" />Uncertain</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-civic-clay" />Excluded</span>
      </div>
    </section>
  );
}
