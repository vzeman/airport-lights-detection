import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import {
  Plus,
  Edit,
  Trash2,
  Search,
  RefreshCw,
  Eye,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import { extractErrorMessage } from '../utils/errorHandler';
import AirportImport from '../components/AirportImport';

interface Airport {
  id: string;
  icao_code: string;
  iata_code?: string;
  name: string;
  full_name?: string;
  country: string;
  city?: string;
  latitude: number;
  longitude: number;
  elevation?: number;
  timezone: string;
  runway_count: number;
  terminal_count: number;
  compliance_framework: string;
  is_active: boolean;
  created_at: string;
}

const ComplianceFrameworks = ['ICAO', 'FAA', 'EASA', 'LOCAL'];

const Airports: React.FC = () => {
  const navigate = useNavigate();
  const { isSuperAdmin, isAirportAdmin } = useAuth();
  const [airports, setAirports] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage] = useState(10);
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedAirport, setSelectedAirport] = useState<Airport | null>(null);
  const [error, setError] = useState('');
  
  // Form state
  const [formData, setFormData] = useState({
    icao_code: '',
    iata_code: '',
    name: '',
    full_name: '',
    country: '',
    city: '',
    latitude: 0,
    longitude: 0,
    elevation: 0,
    timezone: 'UTC',
    runway_count: 0,
    terminal_count: 0,
    compliance_framework: 'ICAO',
  });

  const fetchAirports = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.getAirports({
        page: page + 1,
        page_size: rowsPerPage,
        search: search || undefined,
      });
      setAirports(response.airports);
      setTotal(response.total);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search]);

  useEffect(() => {
    fetchAirports();
  }, [page, rowsPerPage, fetchAirports]);

  const handleSearch = () => {
    setPage(0);
    fetchAirports();
  };

  const handleAddAirport = () => {
    setSelectedAirport(null);
    setFormData({
      icao_code: '',
      iata_code: '',
      name: '',
      full_name: '',
      country: '',
      city: '',
      latitude: 0,
      longitude: 0,
      elevation: 0,
      timezone: 'UTC',
      runway_count: 0,
      terminal_count: 0,
      compliance_framework: 'ICAO',
    });
    setDialogOpen(true);
  };

  const handleEditAirport = (airport: Airport) => {
    setSelectedAirport(airport);
    setFormData({
      icao_code: airport.icao_code,
      iata_code: airport.iata_code || '',
      name: airport.name,
      full_name: airport.full_name || '',
      country: airport.country,
      city: airport.city || '',
      latitude: airport.latitude,
      longitude: airport.longitude,
      elevation: airport.elevation || 0,
      timezone: airport.timezone,
      runway_count: airport.runway_count,
      terminal_count: airport.terminal_count,
      compliance_framework: airport.compliance_framework,
    });
    setDialogOpen(true);
  };

  const handleDeleteAirport = (airport: Airport) => {
    setSelectedAirport(airport);
    setDeleteDialogOpen(true);
  };

  const handleViewAirport = (airport: Airport) => {
    navigate(`/airports/${airport.id}`);
  };


  const handleSaveAirport = async () => {
    try {
      if (selectedAirport) {
        // Update existing airport
        await api.updateAirport(selectedAirport.id, formData);
      } else {
        // Create new airport
        await api.createAirport(formData);
      }
      setDialogOpen(false);
      fetchAirports();
    } catch (err: any) {
      setError(extractErrorMessage(err));
    }
  };

  const handleConfirmDelete = async () => {
    if (selectedAirport) {
      try {
        await api.deleteAirport(selectedAirport.id);
        setDeleteDialogOpen(false);
        fetchAirports();
      } catch (err) {
        setError(extractErrorMessage(err));
      }
    }
  };


  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">
        Airport Management
      </h1>
      
      {error && (
        <Alert className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="mb-4 p-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search airports..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              className="pl-10"
            />
          </div>
          <Button
            onClick={fetchAirports}
            variant="outline"
            className="flex items-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          {(isSuperAdmin || isAirportAdmin) && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => setImportDialogOpen(true)}
                className="flex items-center gap-2"
              >
                <Search className="h-4 w-4" />
                Import from Database
              </Button>
              <Button
                onClick={handleAddAirport}
                className="flex items-center gap-2"
              >
                <Plus className="h-4 w-4" />
                Add Airport
              </Button>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ICAO</TableHead>
              <TableHead>IATA</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Runways</TableHead>
              <TableHead>Compliance</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8">
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>Loading airports...</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : airports.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                  No airports found
                </TableCell>
              </TableRow>
            ) : (
              airports.map((airport) => (
                <TableRow key={airport.id}>
                  <TableCell>
                    <div className="font-semibold">
                      {airport.icao_code}
                    </div>
                  </TableCell>
                  <TableCell>{airport.iata_code || '-'}</TableCell>
                  <TableCell>
                    <div className="text-sm">{airport.name}</div>
                    {airport.city && (
                      <div className="text-xs text-gray-500">
                        {airport.city}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">{airport.country}</div>
                    <div className="text-xs text-gray-500">
                      {airport.latitude != null ? Number(airport.latitude).toFixed(8) : 'N/A'}, {airport.longitude != null ? Number(airport.longitude).toFixed(8) : 'N/A'}
                    </div>
                  </TableCell>
                  <TableCell>{airport.runway_count}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {airport.compliance_framework}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={airport.is_active ? "default" : "secondary"}>
                      {airport.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleViewAirport(airport)}
                        title="View Details"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      {(isSuperAdmin || isAirportAdmin) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditAirport(airport)}
                          title="Edit"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                      )}
                      {isSuperAdmin && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteAirport(airport)}
                          title="Delete"
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        
        {/* Simple Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t">
          <div className="text-sm text-gray-500">
            Showing {page * rowsPerPage + 1} to {Math.min((page + 1) * rowsPerPage, total)} of {total} results
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page + 1)}
              disabled={(page + 1) * rowsPerPage >= total}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Airport Form Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedAirport ? 'Edit Airport' : 'Add New Airport'}</DialogTitle>
          </DialogHeader>
          
          <div className="pt-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="icao">ICAO Code *</Label>
                <Input
                  id="icao"
                  value={formData.icao_code}
                  onChange={(e) => setFormData({ ...formData, icao_code: e.target.value.toUpperCase() })}
                  maxLength={4}
                  disabled={!!selectedAirport}
                  placeholder="ICAO"
                />
              </div>
              <div>
                <Label htmlFor="iata">IATA Code</Label>
                <Input
                  id="iata"
                  value={formData.iata_code}
                  onChange={(e) => setFormData({ ...formData, iata_code: e.target.value.toUpperCase() })}
                  maxLength={3}
                  placeholder="IATA"
                />
              </div>
              <div>
                <Label htmlFor="name">Airport Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Airport Name"
                  required
                />
              </div>
              <div>
                <Label htmlFor="full_name">Full Name</Label>
                <Input
                  id="full_name"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  placeholder="Full Name"
                />
              </div>
              <div>
                <Label htmlFor="country">Country *</Label>
                <Input
                  id="country"
                  value={formData.country}
                  onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                  placeholder="Country"
                  required
                />
              </div>
              <div>
                <Label htmlFor="city">City</Label>
                <Input
                  id="city"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  placeholder="City"
                />
              </div>
              <div>
                <Label htmlFor="latitude">Latitude *</Label>
                <Input
                  id="latitude"
                  type="number"
                  value={formData.latitude}
                  onChange={(e) => setFormData({ ...formData, latitude: e.target.value ? Number(e.target.value) : 0 })}
                  placeholder="Latitude (8 decimals)"
                  step={0.00000001}
                  min={-90}
                  max={90}
                  required
                />
              </div>
              <div>
                <Label htmlFor="longitude">Longitude *</Label>
                <Input
                  id="longitude"
                  type="number"
                  value={formData.longitude}
                  onChange={(e) => setFormData({ ...formData, longitude: e.target.value ? Number(e.target.value) : 0 })}
                  placeholder="Longitude (8 decimals)"
                  step={0.00000001}
                  min={-180}
                  max={180}
                  required
                />
              </div>
              <div>
                <Label htmlFor="elevation">Elevation (m)</Label>
                <Input
                  id="elevation"
                  type="number"
                  value={formData.elevation}
                  onChange={(e) => setFormData({ ...formData, elevation: parseFloat(e.target.value) })}
                  placeholder="Elevation"
                />
              </div>
              <div>
                <Label htmlFor="timezone">Timezone *</Label>
                <Input
                  id="timezone"
                  value={formData.timezone}
                  onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                  placeholder="Timezone"
                  required
                />
              </div>
              <div>
                <Label htmlFor="runway_count">Runway Count</Label>
                <Input
                  id="runway_count"
                  type="number"
                  value={formData.runway_count}
                  onChange={(e) => setFormData({ ...formData, runway_count: parseInt(e.target.value) })}
                  placeholder="Runway Count"
                  min={0}
                />
              </div>
              <div>
                <Label htmlFor="terminal_count">Terminal Count</Label>
                <Input
                  id="terminal_count"
                  type="number"
                  value={formData.terminal_count}
                  onChange={(e) => setFormData({ ...formData, terminal_count: parseInt(e.target.value) })}
                  placeholder="Terminal Count"
                  min={0}
                />
              </div>
              <div className="col-span-2">
                <Label htmlFor="compliance_framework">Compliance Framework *</Label>
                <Select
                  value={formData.compliance_framework}
                  onValueChange={(value) => setFormData({ ...formData, compliance_framework: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select compliance framework" />
                  </SelectTrigger>
                  <SelectContent>
                    {ComplianceFrameworks.map((framework) => (
                      <SelectItem key={framework} value={framework}>
                        {framework}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveAirport}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Delete</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>
              Are you sure you want to delete airport "{selectedAirport?.name}" ({selectedAirport?.icao_code})?
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import Airport Dialog */}
      <AirportImport
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        onImport={(airport) => {
          setError('');
          fetchAirports();
          setImportDialogOpen(false);
        }}
      />
    </div>
  );
};

export default Airports;