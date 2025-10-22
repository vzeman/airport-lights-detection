import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, LayerGroup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import api from '../services/api';

// Fix Leaflet default icon issue
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

interface Airport {
  id: string;
  icao_code: string;
  name: string;
  latitude: number;
  longitude: number;
  country: string;
  city: string;
}

interface GlobalMapProps {
  selectedLayers?: {
    airports?: boolean;
    missions?: boolean;
    airspace?: boolean;
    weather?: boolean;
    terrain?: boolean;
  };
  mapStyle?: string;
}

const GlobalMapLeaflet: React.FC<GlobalMapProps> = ({ 
  selectedLayers = { airports: true },
  mapStyle = 'streets'
}) => {
  const [airports, setAirports] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(true);

  // Get tile layer URL based on map style
  const getTileLayerUrl = () => {
    switch (mapStyle) {
      case 'satellite':
        return 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      case 'terrain':
        return 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{z}/{y}/{x}';
      default:
        return 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    }
  };

  // Load airports data
  useEffect(() => {
    const loadAirports = async () => {
      try {
        setLoading(true);
        const response = await api.get('/airports');
        setAirports(response.data || []);
      } catch (error) {
        // console.error('Error loading airports:', error);
        setAirports([]);
      } finally {
        setLoading(false);
      }
    };

    if (selectedLayers.airports) {
      loadAirports();
    }
  }, [selectedLayers.airports]);

  return (
    <div className="h-full w-full">
      <MapContainer
        center={[51.505, -0.09]} // Default center (London)
        zoom={5}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false} // We'll add custom controls
      >
        <TileLayer
          url={getTileLayerUrl()}
          attribution={
            mapStyle === 'satellite' || mapStyle === 'terrain'
              ? '&copy; <a href="https://www.esri.com/">Esri</a>'
              : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          }
        />

        {/* Airports Layer */}
        {selectedLayers.airports && (
          <LayerGroup>
            {airports.map((airport) => (
              <Marker
                key={airport.id}
                position={[airport.latitude, airport.longitude]}
              >
                <Popup>
                  <div>
                    <strong>{airport.icao_code} - {airport.name}</strong>
                    <br />
                    {airport.city}, {airport.country}
                    <br />
                    <small>
                      Lat: {airport.latitude != null ? Number(airport.latitude).toFixed(8) : 'N/A'},
                      Lng: {airport.longitude != null ? Number(airport.longitude).toFixed(8) : 'N/A'}
                    </small>
                  </div>
                </Popup>
              </Marker>
            ))}
          </LayerGroup>
        )}
      </MapContainer>
    </div>
  );
};

export default GlobalMapLeaflet;