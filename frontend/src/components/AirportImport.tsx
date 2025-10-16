import React, { useState } from 'react';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Badge } from './ui/badge';
import { Card, CardContent } from './ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Search, Plus, Plane, MapPin, Loader2 } from 'lucide-react';
import api from '../services/api';
import { extractErrorMessage } from '../utils/errorHandler';

interface AirportSearchResult {
  icao_code: string;
  iata_code?: string;
  name: string;
  full_name?: string;
  country: string;
  country_code?: string;
  city?: string;
  latitude: number;
  longitude: number;
  elevation?: number;
  type?: string;
}

interface AirportImportProps {
  open: boolean;
  onClose: () => void;
  onImport: (airport: AirportSearchResult) => void;
}

const AirportImport: React.FC<AirportImportProps> = ({ open, onClose, onImport }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState('icao');
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');
  const [searchResults, setSearchResults] = useState<AirportSearchResult[]>([]);
  const [selectedAirport, setSelectedAirport] = useState<AirportSearchResult | null>(null);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setSearching(true);
    setError('');
    setSearchResults([]);

    try {
      let response;
      
      if (searchType === 'icao' && searchQuery.length === 4) {
        // Direct ICAO lookup
        response = await api.get(`/airport-import/search/icao/${searchQuery.toUpperCase()}`);
        setSearchResults([response.data]);
      } else if (searchType === 'country' && searchQuery.length === 2) {
        // Country search
        response = await api.get(`/airport-import/search/country/${searchQuery.toUpperCase()}`);
        setSearchResults(response.data.results || []);
      } else {
        // General search
        response = await api.get('/airport-import/search', {
          params: {
            query: searchQuery,
            search_type: searchType,
            limit: 20
          }
        });
        setSearchResults(response.data.results || []);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSearching(false);
    }
  };

  const handleImport = async (airport: AirportSearchResult, includeItems: boolean = false) => {
    setImporting(true);
    setError('');

    try {
      const response = await api.post(
        `/airport-import/import/${airport.icao_code}`,
        null,
        { params: { include_items: includeItems } }
      );
      
      // Show import details
      const data = response.data;
      console.log(`Imported ${data.runways_imported} runways and ${data.items_created} items`);
      
      onImport(airport);
      setSearchResults([]);
      setSearchQuery('');
      onClose();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setImporting(false);
    }
  };

  const handleLoadMajorAirports = async () => {
    setSearching(true);
    setError('');

    try {
      const response = await api.get('/airport-import/major-airports');
      setSearchResults(response.data.results || []);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSearching(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import Airport from Database</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="w-full sm:w-48">
              <Select value={searchType} onValueChange={setSearchType}>
                <SelectTrigger>
                  <SelectValue placeholder="Search By" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="icao">ICAO Code</SelectItem>
                  <SelectItem value="iata">IATA Code</SelectItem>
                  <SelectItem value="name">Name</SelectItem>
                  <SelectItem value="city">City</SelectItem>
                  <SelectItem value="country">Country Code</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex-1 relative">
              <Input
                placeholder={
                  searchType === 'icao' ? 'e.g., KJFK' :
                  searchType === 'iata' ? 'e.g., JFK' :
                  searchType === 'country' ? 'e.g., US' :
                  searchType === 'name' ? 'e.g., Heathrow' :
                  'e.g., London'
                }
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                className="pr-10"
              />
              <Button
                size="sm"
                variant="ghost"
                className="absolute right-0 top-0 h-full px-3"
                onClick={handleSearch}
                disabled={searching}
              >
                {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          <div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleLoadMajorAirports}
              disabled={searching}
            >
              Load Major Airports
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {searchResults.length > 0 && (
          <Card className="max-h-96 overflow-auto">
            <CardContent className="p-0">
              <div className="space-y-0">
                {searchResults.map((airport, index) => (
                  <div
                    key={`${airport.icao_code}-${index}`}
                    className={`p-4 border-b last:border-b-0 cursor-pointer hover:bg-accent ${
                      selectedAirport?.icao_code === airport.icao_code ? 'bg-accent' : ''
                    }`}
                    onClick={() => setSelectedAirport(airport)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Plane className="h-4 w-4" />
                          <span className="font-medium">{airport.name}</span>
                          <Badge variant="outline" className="text-primary border-primary">
                            {airport.icao_code}
                          </Badge>
                          {airport.iata_code && (
                            <Badge variant="outline">
                              {airport.iata_code}
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <MapPin className="h-3 w-3" />
                            {airport.city ? `${airport.city}, ` : ''}{airport.country}
                          </span>
                          <span>
                            Lat: {airport.latitude?.toFixed(4)}, Lon: {airport.longitude?.toFixed(4)}
                          </span>
                          {airport.elevation && (
                            <span>Elevation: {airport.elevation}ft</span>
                          )}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleImport(airport);
                        }}
                        disabled={importing}
                        className="ml-4"
                      >
                        <Plus className="h-4 w-4 mr-1" />
                        Import
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {searching && searchResults.length === 0 && (
          <div className="text-center py-8">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              Searching airports...
            </p>
          </div>
        )}

        {!searching && searchResults.length === 0 && searchQuery && (
          <div className="text-center py-8">
            <p className="text-muted-foreground">
              No airports found for "{searchQuery}"
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Try searching with a different term or search type
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AirportImport;