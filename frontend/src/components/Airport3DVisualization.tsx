import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, LayersControl } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface DronePosition {
  frame: number;
  timestamp: number;
  latitude: number;
  longitude: number;
  elevation: number;
}

interface ReferencePoint {
  latitude: number;
  longitude: number;
  elevation: number;
  point_type: string;
}

interface RunwayData {
  name: string;
  heading: number;
  length: number;
  width: number;
  start_lat: number | null;
  start_lon: number | null;
  threshold_elevation: number | null;
  end_lat: number | null;
  end_lon: number | null;
}

interface Airport3DVisualizationProps {
  dronePositions: DronePosition[];
  referencePoints: { [key: string]: ReferencePoint };
  runway: RunwayData | null;
}

// Fix Leaflet default marker icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

// Custom marker icons
const createColoredIcon = (color: string) => {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      background-color: ${color};
      width: 24px;
      height: 24px;
      border-radius: 50%;
      border: 3px solid white;
      box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

const papiIcon = createColoredIcon('#ef4444'); // Red for PAPI A
const papiIconB = createColoredIcon('#f97316'); // Orange for PAPI B
const papiIconC = createColoredIcon('#eab308'); // Yellow for PAPI C
const papiIconD = createColoredIcon('#22c55e'); // Green for PAPI D
const papiIconE = createColoredIcon('#14b8a6'); // Teal for PAPI E
const papiIconF = createColoredIcon('#3b82f6'); // Blue for PAPI F
const papiIconG = createColoredIcon('#8b5cf6'); // Purple for PAPI G
const papiIconH = createColoredIcon('#ec4899'); // Pink for PAPI H
const touchPointIcon = createColoredIcon('#8b5cf6'); // Purple for touch point
const droneStartIcon = createColoredIcon('#22c55e'); // Green for drone start
const droneEndIcon = createColoredIcon('#ef4444'); // Red for drone end

// Component to fit map bounds
function FitBounds({ bounds }: { bounds: L.LatLngBoundsExpression | null }) {
  const map = useMap();

  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [bounds, map]);

  return null;
}

export default function Airport3DVisualization({ dronePositions, referencePoints, runway }: Airport3DVisualizationProps) {
  // Debug: Log reference points to see what we're receiving
  useEffect(() => {
    console.log('Reference Points:', referencePoints);
    console.log('Reference Point Keys:', Object.keys(referencePoints));
  }, [referencePoints]);

  // Calculate bounds to fit all markers
  const bounds = useMemo(() => {
    const allPoints: [number, number][] = [];

    // Add drone positions
    dronePositions.forEach(pos => {
      if (pos.latitude && pos.longitude) {
        allPoints.push([pos.latitude, pos.longitude]);
      }
    });

    // Add reference points
    Object.values(referencePoints).forEach(point => {
      if (point.latitude && point.longitude) {
        allPoints.push([point.latitude, point.longitude]);
      }
    });

    // Add runway points
    if (runway?.start_lat && runway?.start_lon) {
      allPoints.push([runway.start_lat, runway.start_lon]);
    }
    if (runway?.end_lat && runway?.end_lon) {
      allPoints.push([runway.end_lat, runway.end_lon]);
    }

    if (allPoints.length === 0) {
      return null;
    }

    return L.latLngBounds(allPoints);
  }, [dronePositions, referencePoints, runway]);

  // Calculate center
  const center: [number, number] = useMemo(() => {
    if (bounds) {
      const boundsCenter = bounds.getCenter();
      return [boundsCenter.lat, boundsCenter.lng];
    }
    return [48.8650, 17.9867]; // Default fallback
  }, [bounds]);

  // Drone path coordinates
  const dronePathCoords: [number, number][] = useMemo(() => {
    return dronePositions
      .filter(pos => pos.latitude && pos.longitude)
      .map(pos => [pos.latitude, pos.longitude] as [number, number]);
  }, [dronePositions]);

  // Get PAPI light icon based on name
  const getPAPIIcon = (lightName: string) => {
    const iconMap: { [key: string]: L.DivIcon } = {
      'PAPI_A': papiIcon,
      'PAPI_B': papiIconB,
      'PAPI_C': papiIconC,
      'PAPI_D': papiIconD,
      'PAPI_E': papiIconE,
      'PAPI_F': papiIconF,
      'PAPI_G': papiIconG,
      'PAPI_H': papiIconH,
    };
    return iconMap[lightName] || papiIcon;
  };

  return (
    <div className="w-full h-96 rounded-lg overflow-hidden">
      <MapContainer
        center={center}
        zoom={15}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
      >
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Street Map">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite">
            <TileLayer
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={19}
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        {/* Fit bounds to show all markers */}
        <FitBounds bounds={bounds} />

        {/* Drone flight path */}
        {dronePathCoords.length > 0 && (
          <Polyline
            positions={dronePathCoords}
            color="#00ffff"
            weight={3}
            opacity={0.7}
          >
            <Popup>
              <div className="text-sm">
                <strong>Drone Flight Path</strong><br />
                {dronePositions.length} positions recorded
              </div>
            </Popup>
          </Polyline>
        )}

        {/* Drone start position */}
        {dronePositions.length > 0 && dronePositions[0].latitude && dronePositions[0].longitude && (
          <Marker
            position={[dronePositions[0].latitude, dronePositions[0].longitude]}
            icon={droneStartIcon}
          >
            <Popup>
              <div className="text-sm">
                <strong>Drone Start Position</strong><br />
                Elevation: {dronePositions[0].elevation.toFixed(1)}m<br />
                Time: {dronePositions[0].timestamp.toFixed(2)}s
              </div>
            </Popup>
          </Marker>
        )}

        {/* Drone end position */}
        {dronePositions.length > 1 && (
          <Marker
            position={[
              dronePositions[dronePositions.length - 1].latitude,
              dronePositions[dronePositions.length - 1].longitude
            ]}
            icon={droneEndIcon}
          >
            <Popup>
              <div className="text-sm">
                <strong>Drone End Position</strong><br />
                Elevation: {dronePositions[dronePositions.length - 1].elevation.toFixed(1)}m<br />
                Time: {dronePositions[dronePositions.length - 1].timestamp.toFixed(2)}s
              </div>
            </Popup>
          </Marker>
        )}

        {/* Direct line from drone start to end (green) */}
        {dronePositions.length > 1 &&
         dronePositions[0].latitude && dronePositions[0].longitude &&
         dronePositions[dronePositions.length - 1].latitude &&
         dronePositions[dronePositions.length - 1].longitude && (
          <Polyline
            positions={[
              [dronePositions[0].latitude, dronePositions[0].longitude],
              [dronePositions[dronePositions.length - 1].latitude, dronePositions[dronePositions.length - 1].longitude]
            ]}
            color="#22c55e"
            weight={4}
            opacity={0.8}
            dashArray="10, 10"
          >
            <Popup>
              <div className="text-sm">
                <strong>Direct Path (Start to End)</strong><br />
                Shows straight line from drone start to end position
              </div>
            </Popup>
          </Polyline>
        )}

        {/* PAPI lights and other reference points */}
        {Object.entries(referencePoints).map(([pointId, point]) => {
          // More flexible PAPI detection - case insensitive and checks for PAPI followed by A-H
          const upperPointId = pointId.toUpperCase();
          const isPAPI = upperPointId.match(/PAPI[_\s-]?([A-H])/i);
          const isTouchPoint = upperPointId.includes('TOUCH');

          if (!point.latitude || !point.longitude) {
            console.log(`Skipping point ${pointId}: missing coordinates`, point);
            return null;
          }

          let icon;
          let label;

          if (isPAPI) {
            const lightName = `PAPI_${isPAPI[1].toUpperCase()}`;
            icon = getPAPIIcon(lightName);
            label = lightName;
            console.log(`Rendering PAPI light: ${label} at [${point.latitude}, ${point.longitude}]`);
          } else if (isTouchPoint) {
            icon = touchPointIcon;
            label = 'Touch Point';
            console.log(`Rendering Touch Point at [${point.latitude}, ${point.longitude}]`);
          } else {
            console.log(`Skipping unknown point type: ${pointId}`);
            return null; // Skip other reference points
          }

          return (
            <Marker
              key={pointId}
              position={[point.latitude, point.longitude]}
              icon={icon}
            >
              <Popup>
                <div className="text-sm">
                  <strong>{label}</strong><br />
                  ID: {pointId}<br />
                  Lat: {point.latitude != null ? Number(point.latitude).toFixed(8) : 'N/A'}<br />
                  Lon: {point.longitude != null ? Number(point.longitude).toFixed(8) : 'N/A'}<br />
                  Elevation: {point.elevation != null ? Number(point.elevation).toFixed(1) : 'N/A'}m
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
