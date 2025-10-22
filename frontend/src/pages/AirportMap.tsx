import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import AirportMapLeaflet from '../components/AirportMapLeaflet';
import api from '../services/api';
import { Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '../components/ui/alert';

const AirportMap: React.FC = () => {
  const { airportId } = useParams<{ airportId: string }>();
  const [airport, setAirport] = useState<any>(null);
  const [airportItems, setAirportItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      if (!airportId) return;
      
      setLoading(true);
      setError('');
      
      try {
        // Fetch airport details
        const airportResponse = await api.getAirport(airportId);
        setAirport(airportResponse);
        
        // Fetch airport items
        const itemsResponse = await api.getAirportItems(airportId);
        setAirportItems(itemsResponse.items || []);
      } catch (err: any) {
        setError(err.response?.data?.message || 'Failed to load airport data');
        // console.error('Error loading airport data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [airportId]);

  if (!airportId) {
    return (
      <div className="p-4">
        <Alert variant="destructive">
          <AlertDescription>No airport ID provided</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-100px)]">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-100px)] flex flex-col">
      <div className="px-4 pt-4 pb-2">
        <h1 className="text-2xl font-bold">
          Airport Map: {airport?.name || 'Loading...'}
        </h1>
        <p className="text-sm text-gray-600">
          {airport?.icao_code} {airport?.iata_code && `/ ${airport.iata_code}`}
        </p>
      </div>
      <div className="flex-1 px-4 pb-4">
        <AirportMapLeaflet 
          airport={airport} 
          airportItems={airportItems}
        />
      </div>
    </div>
  );
};

export default AirportMap;