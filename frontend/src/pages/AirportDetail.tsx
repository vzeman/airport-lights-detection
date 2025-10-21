import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { LatitudeInput, LongitudeInput } from '../components/ui/coordinate-input';
import { ArrowLeft, Plus, Save, Trash2, Edit2, MapPin } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";

interface Airport {
  id: string;
  icao_code: string;
  name: string;
  full_name?: string;
  city?: string;
  country: string;
  latitude: number;
  longitude: number;
  elevation?: number;
  runway_count: number;
  is_active: boolean;
}

interface Runway {
  id?: string;
  name: string;
  heading: number;
  length: number;
  width: number;
  surface_type: string;
  start_lat?: number;
  start_lon?: number;
  is_active: boolean;
}

interface ReferencePoint {
  id?: string;
  runway_id?: string;
  point_type: 'PAPI_A' | 'PAPI_B' | 'PAPI_C' | 'PAPI_D' | 'TOUCH_POINT';
  latitude: number;
  longitude: number;
  altitude: number;
}

const AirportDetail: React.FC = () => {
  const { airportId } = useParams<{ airportId: string }>();
  const navigate = useNavigate();
  const { isSuperAdmin } = useAuth();
  
  const [loading, setLoading] = useState(true);
  const [airport, setAirport] = useState<Airport | null>(null);
  const [runways, setRunways] = useState<Runway[]>([]);
  const [selectedRunway, setSelectedRunway] = useState<Runway | null>(null);
  const [referencePoints, setReferencePoints] = useState<ReferencePoint[]>([]);
  const [editingRunway, setEditingRunway] = useState<string | null>(null);
  const [editingPoints, setEditingPoints] = useState(false);
  const [showRunwayDialog, setShowRunwayDialog] = useState(false);
  const [showPointsDialog, setShowPointsDialog] = useState(false);
  
  // Form states
  const [runwayForm, setRunwayForm] = useState<Runway>({
    name: '',
    heading: 0,
    length: 0,
    width: 0,
    surface_type: 'asphalt',
    is_active: true
  });

  useEffect(() => {
    if (airportId) {
      fetchAirportDetails();
    }
  }, [airportId]);

  const fetchAirportDetails = async () => {
    try {
      setLoading(true);
      
      // Fetch airport details
      const airportData = await api.getAirport(airportId!);
      setAirport(airportData);
      
      // Fetch runways
      const runwaysData = await api.getAirportRunways(airportId!);
      setRunways(runwaysData.runways || []);
      
    } catch (error) {
      console.error('Failed to fetch airport details:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchReferencePoints = async (runwayId: string) => {
    try {
      const response = await api.getReferencePoints(runwayId);
      const points = response.reference_points || [];
      
      // Ensure we have all required points
      const requiredTypes = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D', 'TOUCH_POINT'];
      const existingTypes = points.map((p: ReferencePoint) => p.point_type);
      
      const allPoints = requiredTypes.map(type => {
        const existing = points.find((p: ReferencePoint) => p.point_type === type);
        if (existing) return existing;
        
        return {
          point_type: type as ReferencePoint['point_type'],
          latitude: airport?.latitude || 0,
          longitude: airport?.longitude || 0,
          altitude: airport?.elevation || 0
        };
      });
      
      setReferencePoints(allPoints);
    } catch (error) {
      console.error('Failed to fetch reference points:', error);
      // Initialize with default points
      const defaultPoints = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D', 'TOUCH_POINT'].map(type => ({
        point_type: type as ReferencePoint['point_type'],
        latitude: airport?.latitude || 0,
        longitude: airport?.longitude || 0,
        altitude: airport?.elevation || 0
      }));
      setReferencePoints(defaultPoints);
    }
  };

  const handleEditRunway = (runway: Runway) => {
    setRunwayForm(runway);
    setEditingRunway(runway.id || null);
    setShowRunwayDialog(true);
  };

  const handleSaveRunway = async () => {
    try {
      if (editingRunway) {
        await api.updateRunway(airportId!, editingRunway, runwayForm);
      } else {
        await api.createRunway(airportId!, runwayForm);
      }
      
      await fetchAirportDetails();
      setShowRunwayDialog(false);
      setEditingRunway(null);
      setRunwayForm({
        name: '',
        heading: 0,
        length: 0,
        width: 0,
        surface_type: 'asphalt',
        is_active: true
      });
    } catch (error) {
      console.error('Failed to save runway:', error);
    }
  };

  const handleDeleteRunway = async (runwayId: string) => {
    if (!window.confirm('Are you sure you want to delete this runway?')) return;
    
    try {
      await api.deleteRunway(airportId!, runwayId);
      await fetchAirportDetails();
    } catch (error) {
      console.error('Failed to delete runway:', error);
    }
  };

  const handleEditReferencePoints = async (runway: Runway) => {
    if (!runway.id) return;
    setSelectedRunway(runway);
    await fetchReferencePoints(runway.id);
    setShowPointsDialog(true);
  };

  const handleSaveAllReferencePoints = async () => {
    if (!selectedRunway?.id) return;
    
    try {
      const pointsToSave = referencePoints.map(point => ({
        point_type: point.point_type,
        latitude: point.latitude,
        longitude: point.longitude,
        altitude: point.altitude
      }));
      
      await api.bulkUpdateReferencePoints(selectedRunway.id, pointsToSave);
      setEditingPoints(false);
      alert('Reference points saved successfully!');
    } catch (error) {
      console.error('Failed to save reference points:', error);
      alert('Failed to save reference points');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!airport) {
    return (
      <div className="p-6">
        <p>Airport not found</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => navigate('/airports')}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{airport.name} ({airport.icao_code})</h1>
            <p className="text-muted-foreground">{airport.city}, {airport.country}</p>
          </div>
        </div>
      </div>

      {/* Airport Info Card */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Airport Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <Label>ICAO Code</Label>
              <p className="font-semibold">{airport.icao_code}</p>
            </div>
            <div>
              <Label>Coordinates</Label>
              <p className="font-semibold">{airport.latitude?.toFixed(4) || 'N/A'}, {airport.longitude?.toFixed(4) || 'N/A'}</p>
            </div>
            <div>
              <Label>Elevation</Label>
              <p className="font-semibold">{airport.elevation || 'N/A'} ft</p>
            </div>
            <div>
              <Label>Status</Label>
              <p className="font-semibold">{airport.is_active ? 'Active' : 'Inactive'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Runways Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Runways</CardTitle>
          {isSuperAdmin && (
            <Button
              onClick={() => {
                setEditingRunway(null);
                setRunwayForm({
                  name: '',
                  heading: 0,
                  length: 0,
                  width: 0,
                  surface_type: 'asphalt',
                  is_active: true
                });
                setShowRunwayDialog(true);
              }}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Runway
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {runways.map((runway) => (
              <div key={runway.id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg">Runway {runway.name}</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-2">
                      <div>
                        <span className="text-sm text-muted-foreground">Heading:</span>
                        <p className="font-medium">{runway.heading}°</p>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Dimensions:</span>
                        <p className="font-medium">{runway.length}m x {runway.width}m</p>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Surface:</span>
                        <p className="font-medium capitalize">{runway.surface_type}</p>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Status:</span>
                        <p className="font-medium">{runway.is_active ? 'Active' : 'Inactive'}</p>
                      </div>
                    </div>
                  </div>
                  {isSuperAdmin && (
                    <div className="flex gap-2 ml-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEditReferencePoints(runway)}
                      >
                        <MapPin className="h-4 w-4 mr-1" />
                        PAPI Lights
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEditRunway(runway)}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDeleteRunway(runway.id!)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {runways.length === 0 && (
              <p className="text-center text-muted-foreground py-8">No runways configured</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Runway Edit Dialog */}
      <Dialog open={showRunwayDialog} onOpenChange={setShowRunwayDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingRunway ? 'Edit' : 'Add'} Runway</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Runway Name (e.g., 09/27)</Label>
              <Input
                value={runwayForm.name}
                onChange={(e) => setRunwayForm({...runwayForm, name: e.target.value})}
                placeholder="09/27"
              />
            </div>
            <div>
              <Label>Heading (degrees)</Label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="360"
                value={runwayForm.heading}
                onChange={(e) => setRunwayForm({...runwayForm, heading: parseFloat(e.target.value) || 0})}
                placeholder="0.0 - 360.0"
              />
            </div>
            <div className="space-y-4">
              <Label className="text-base font-semibold">Runway Start Position (GPS)</Label>
              <div className="grid grid-cols-2 gap-4">
                <LatitudeInput
                  label="Start Latitude"
                  value={runwayForm.start_lat}
                  onChange={(value) => setRunwayForm({...runwayForm, start_lat: value ?? undefined})}
                  placeholder="e.g., 48.123456 or N48°52.01'"
                />
                <LongitudeInput
                  label="Start Longitude"
                  value={runwayForm.start_lon}
                  onChange={(value) => setRunwayForm({...runwayForm, start_lon: value ?? undefined})}
                  placeholder="e.g., 17.123456 or E17°30.5'"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                End coordinates will be automatically calculated based on start position, length, and heading.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Length (m)</Label>
                <Input
                  type="number"
                  value={runwayForm.length}
                  onChange={(e) => setRunwayForm({...runwayForm, length: parseInt(e.target.value)})}
                />
              </div>
              <div>
                <Label>Width (m)</Label>
                <Input
                  type="number"
                  value={runwayForm.width}
                  onChange={(e) => setRunwayForm({...runwayForm, width: parseInt(e.target.value)})}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowRunwayDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleSaveRunway}>
                <Save className="h-4 w-4 mr-2" />
                Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reference Points Dialog */}
      <Dialog open={showPointsDialog} onOpenChange={setShowPointsDialog}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>PAPI Lights & Touch Point - Runway {selectedRunway?.name}</DialogTitle>
            <DialogDescription>
              Configure the GPS positions for PAPI lights (A, B, C, D) and the touch point reference
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D', 'TOUCH_POINT'].map((type) => {
              const point = referencePoints.find(p => p.point_type === type);
              const isEditing = editingPoints;
              
              return (
                <div key={type} className="border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium">{type.replace('_', ' ')}</h4>
                  </div>
                  
                  {point && (
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        {isEditing ? (
                          <LatitudeInput
                            label="Latitude"
                            value={point.latitude}
                            onChange={(value) => {
                              const updated = referencePoints.map(p =>
                                p.point_type === point.point_type
                                  ? {...p, latitude: value || 0}
                                  : p
                              );
                              setReferencePoints(updated);
                            }}
                            showHelp={false}
                          />
                        ) : (
                          <div>
                            <Label className="text-xs">Latitude</Label>
                            <p className="text-sm font-mono">{point.latitude?.toFixed(6) || 'N/A'}</p>
                          </div>
                        )}
                      </div>
                      <div>
                        {isEditing ? (
                          <LongitudeInput
                            label="Longitude"
                            value={point.longitude}
                            onChange={(value) => {
                              const updated = referencePoints.map(p =>
                                p.point_type === point.point_type
                                  ? {...p, longitude: value || 0}
                                  : p
                              );
                              setReferencePoints(updated);
                            }}
                            showHelp={false}
                          />
                        ) : (
                          <div>
                            <Label className="text-xs">Longitude</Label>
                            <p className="text-sm font-mono">{point.longitude?.toFixed(6) || 'N/A'}</p>
                          </div>
                        )}
                      </div>
                      <div>
                        <Label className="text-xs">Altitude (m)</Label>
                        {isEditing ? (
                          <div className="flex gap-1">
                            <Input
                              type="number"
                              value={point.altitude || 0}
                              onChange={(e) => {
                                const updated = referencePoints.map(p =>
                                  p.point_type === point.point_type
                                    ? {...p, altitude: parseFloat(e.target.value) || 0}
                                    : p
                                );
                                setReferencePoints(updated);
                              }}
                            />
                          </div>
                        ) : (
                          <p className="text-sm font-mono">{point.altitude || 0}</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            
            <div className="flex justify-between">
              <Button
                variant="outline"
                onClick={() => setEditingPoints(!editingPoints)}
              >
                {editingPoints ? 'Cancel Edit' : 'Edit Points'}
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowPointsDialog(false)}>
                  Close
                </Button>
                {editingPoints && (
                  <Button onClick={handleSaveAllReferencePoints}>
                    <Save className="h-4 w-4 mr-1" />
                    Save All
                  </Button>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AirportDetail;