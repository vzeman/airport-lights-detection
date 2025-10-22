import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default markers not showing in React-Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

interface AirportMapLeafletProps {
  airport: any;
  airportItems?: any[];
}

const AirportMapLeaflet: React.FC<AirportMapLeafletProps> = ({ airport, airportItems = [] }) => {
  // Default center coordinates (can be overridden by airport data)
  const defaultCenter = { lat: 40.7128, lng: -74.0060 }; // New York
  
  // Use airport coordinates if available
  const center = airport?.latitude && airport?.longitude 
    ? { lat: airport.latitude, lng: airport.longitude }
    : defaultCenter;

  // Different item type colors
  const getItemColor = (itemType: string) => {
    switch (itemType?.toLowerCase()) {
      case 'runway_light':
        return '#ef4444'; // red
      case 'taxiway_light':
        return '#3b82f6'; // blue
      case 'approach_light':
        return '#10b981'; // green
      case 'navigation_aid':
        return '#f59e0b'; // amber
      default:
        return '#6b7280'; // gray
    }
  };

  return (
    <div className="w-full h-[600px] rounded-lg overflow-hidden border border-gray-200">
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={airport ? 14 : 10}
        style={{ height: '100%', width: '100%' }}
        className="z-10"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        />
        
        {/* Airport center marker */}
        {airport && airport.latitude && airport.longitude && (
          <Marker position={[airport.latitude, airport.longitude]}>
            <Popup>
              <div className="p-2">
                <h3 className="font-bold">{airport.name}</h3>
                <p className="text-sm">ICAO: {airport.icao_code}</p>
                <p className="text-sm">IATA: {airport.iata_code}</p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Airport items */}
        {airportItems.map((item, index) => {
          if (!item.latitude || !item.longitude) return null;
          
          return (
            <Circle
              key={item.id || index}
              center={[item.latitude, item.longitude]}
              radius={10} // 10 meters radius
              pathOptions={{
                color: getItemColor(item.item_type),
                fillColor: getItemColor(item.item_type),
                fillOpacity: 0.6,
              }}
            >
              <Popup>
                <div className="p-2">
                  <p className="font-semibold">{item.name || item.identifier}</p>
                  <p className="text-sm">Type: {item.item_type}</p>
                  <p className="text-sm">Status: {item.status || 'Active'}</p>
                </div>
              </Popup>
            </Circle>
          );
        })}
      </MapContainer>
      
      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-white p-3 rounded shadow-lg z-20">
        <h4 className="font-semibold mb-2 text-sm">Legend</h4>
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span className="text-xs">Runway Lights</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-xs">Taxiway Lights</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="text-xs">Approach Lights</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <span className="text-xs">Navigation Aids</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AirportMapLeaflet;