import React, { useState, useEffect, useCallback } from 'react';
// Replaced MUI imports with shadcn/ui components
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Checkbox } from '../components/ui/checkbox';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Table, TableBody, TableCell, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Slider } from '../components/ui/slider';
import api from '../services/api';
// Replaced MUI icons with simple Unicode emojis for now
const Icons = {
  FlightTakeoff: ({ className }: { className?: string }) => <span className={className}>✈️</span>,
  Map: ({ className }: { className?: string }) => <span className={className}>🗺️</span>,
  Schedule: ({ className }: { className?: string }) => <span className={className}>📅</span>,
  Battery80: ({ className }: { className?: string }) => <span className={className}>🔋</span>,
  Cloud: ({ className }: { className?: string }) => <span className={className}>☁️</span>,
  Warning: ({ className }: { className?: string }) => <span className={className}>⚠️</span>,
  CheckCircle: ({ className }: { className?: string }) => <span className={className}>✅</span>,
  PlayArrow: ({ className }: { className?: string }) => <span className={className}>▶️</span>,
  Save: ({ className }: { className?: string }) => <span className={className}>💾</span>,
  Download: ({ className }: { className?: string }) => <span className={className}>⬇️</span>,
  Visibility: ({ className }: { className?: string }) => <span className={className}>👁️</span>,
  NavigateNext: ({ className }: { className?: string }) => <span className={className}>➡️</span>,
  WbIncandescent: ({ className }: { className?: string }) => <span className={className}>💡</span>,
  Architecture: ({ className }: { className?: string }) => <span className={className}>🏗️</span>,
  Assessment: ({ className }: { className?: string }) => <span className={className}>📋</span>,
  PhotoCamera: ({ className }: { className?: string }) => <span className={className}>📷</span>,
  Radar: ({ className }: { className?: string }) => <span className={className}>📡</span>,
  ThermalImage: ({ className }: { className?: string }) => <span className={className}>🌡️</span>,
};

const { FlightTakeoff, Map, Schedule, Battery80, Cloud, Warning, CheckCircle, PlayArrow, Save, Download } = Icons;
// import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
// import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
// import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
// Temporarily commented out due to three.js dependency issues
// import FlightPath3DViewer from '../components/FlightPath3DViewer';

interface AirportItem {
  id: string;
  name: string;
  type: string;
  latitude: number;
  longitude: number;
  elevation_msl: number;
  status: string;
  last_inspection?: string;
  next_inspection?: string;
  priority?: string;
}

interface MaintenanceTask {
  id: string;
  name: string;
  code: string;
  task_type: string;
  priority: string;
  frequency_days: number;
  duration_minutes: number;
  required_sensors: string[];
}

interface MissionTemplate {
  id: string;
  name: string;
  mission_type: string;
  altitude_agl_m: number;
  speed_ms: number;
  pattern_params: any;
}

interface SelectedTask {
  item: AirportItem;
  task: MaintenanceTask;
  template?: MissionTemplate;
}

interface FlightPlan {
  id: string;
  name: string;
  missions?: any[];
  mission_sequence?: any[];
  total_distance_m: number;
  total_duration_s: number;
  estimated_batteries: number;
}

const { Visibility, WbIncandescent, NavigateNext, Architecture, Assessment, ThermalImage, PhotoCamera, Radar } = Icons;

const TASK_TYPE_ICONS: Record<string, React.ReactElement> = {
  visual_inspection: <Visibility />,
  light_measurement: <WbIncandescent />,
  papi_calibration: <NavigateNext />,
  marking_check: <Architecture />,
  surface_inspection: <Assessment />,
  thermal_inspection: <ThermalImage />,
  photogrammetry: <PhotoCamera />,
  lidar_scan: <Radar />,
};

const MissionPlanning: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [selectedAirport, setSelectedAirport] = useState<any>(null);
  const [airportItems, setAirportItems] = useState<AirportItem[]>([]);
  const [maintenanceTasks, setMaintenanceTasks] = useState<MaintenanceTask[]>([]);
  const [selectedTasks, setSelectedTasks] = useState<SelectedTask[]>([]);
  const [flightPlan, setFlightPlan] = useState<FlightPlan | null>(null);
  const [showVisualization, setShowVisualization] = useState(false);
  const [loading, setLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterPriority, setFilterPriority] = useState('all');
  const [showOnlyDue, setShowOnlyDue] = useState(false);

  // Mission parameters
  const [missionParams, setMissionParams] = useState({
    plannedDate: new Date(),
    optimization: true,
    maxFlightTime: 20, // minutes
    batteryCapacity: 80, // percentage to use
    weatherConstraints: {
      maxWindSpeed: 10, // m/s
      minVisibility: 5000, // meters
      avoidRain: true,
    },
    safetyParams: {
      minAltitude: 10,
      maxAltitude: 120,
      returnToHomeAlt: 50,
      obstacleAvoidance: true,
    }
  });

  const steps = [
    'Select Airport',
    'Choose Items & Tasks',
    'Configure Mission',
    'Review & Generate',
    'Visualize & Export'
  ];

  const loadAirportItems = useCallback(async () => {
    if (!selectedAirport) return;
    try {
      const response = await api.get(`/airports/${selectedAirport.id}/items`);
      setAirportItems(response.data.items || []);
    } catch (error) {
      console.error('Error loading airport items:', error);
    }
  }, [selectedAirport]);

  const loadMaintenanceTasks = useCallback(async () => {
    try {
      const response = await api.get('/missions/tasks');
      setMaintenanceTasks(response.data.tasks || []);
    } catch (error) {
      console.error('Error loading maintenance tasks:', error);
    }
  }, []);

  useEffect(() => {
    if (selectedAirport) {
      loadAirportItems();
      loadMaintenanceTasks();
    }
  }, [selectedAirport, loadAirportItems, loadMaintenanceTasks]);

  const handleSelectTask = (item: AirportItem, task: MaintenanceTask) => {
    const exists = selectedTasks.find(
      st => st.item.id === item.id && st.task.id === task.id
    );
    
    if (exists) {
      setSelectedTasks(selectedTasks.filter(
        st => !(st.item.id === item.id && st.task.id === task.id)
      ));
    } else {
      setSelectedTasks([...selectedTasks, { item, task }]);
    }
  };

  const generateFlightPlan = async () => {
    setLoading(true);
    try {
      const response = await api.post('/missions/flight-plans/create', {
        airport_id: selectedAirport.id,
        selected_items: selectedTasks.map(st => ({
          item_id: st.item.id,
          task_id: st.task.id,
        })),
        optimization: missionParams.optimization,
        planned_date: missionParams.plannedDate,
        weather_constraints: missionParams.weatherConstraints,
      });
      
      // Load detailed flight plan
      const planResponse = await api.get(`/missions/flight-plans/${response.data.flight_plan_id}`);
      setFlightPlan(planResponse.data);
      setShowVisualization(true);
      setActiveStep(4);
    } catch (error) {
      console.error('Error generating flight plan:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportFlightPlan = async (format: 'mavlink' | 'kml') => {
    if (!flightPlan) return;
    
    try {
      const response = await api.get(
        `/missions/flight-plans/${flightPlan.id}/export/${format}`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `flight_plan.${format === 'mavlink' ? 'waypoints' : 'kml'}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error exporting flight plan:', error);
    }
  };

  const calculateStatistics = () => {
    const stats = {
      totalItems: new Set(selectedTasks.map(st => st.item.id)).size,
      totalTasks: selectedTasks.length,
      estimatedDuration: selectedTasks.reduce((sum, st) => sum + st.task.duration_minutes, 0),
      requiredSensors: new Set(selectedTasks.flatMap(st => st.task.required_sensors)),
    };
    return stats;
  };

  const stats = calculateStatistics();

  const filteredItems = airportItems.filter(item => {
    const matchesCategory = filterCategory === 'all' || item.type.includes(filterCategory);
    const matchesPriority = filterPriority === 'all' || item.priority === filterPriority;
    const matchesDue = !showOnlyDue || (item.next_inspection && 
      new Date(item.next_inspection) <= new Date(Date.now() + 7 * 24 * 60 * 60 * 1000));
    return matchesCategory && matchesPriority && matchesDue;
  });

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6 flex items-center">
        <FlightTakeoff className="mr-2" />
        Mission Planning
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Panel - Steps */}
        <div className="lg:col-span-1">
          <Card className="p-4">
            <h2 className="text-lg font-semibold mb-4">Mission Steps</h2>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div 
                  key={index} 
                  className={`p-2 rounded cursor-pointer ${
                    activeStep === index ? 'bg-blue-100 text-blue-800' : 
                    index < activeStep ? 'bg-green-100 text-green-800' : 
                    'bg-gray-100'
                  }`}
                  onClick={() => setActiveStep(index)}
                >
                  <span className="font-medium">{index + 1}. </span>
                  {step}
                </div>
              ))}
            </div>

            {/* Statistics */}
            <Card className="mt-6 p-4">
              <h3 className="text-md font-semibold mb-3">Mission Statistics</h3>
              <div className="space-y-3">
                <div>
                  <div className="text-sm text-gray-600">Total Items</div>
                  <div className="text-2xl font-bold">{stats.totalItems}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Total Tasks</div>
                  <div className="text-2xl font-bold">{stats.totalTasks}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Estimated Duration</div>
                  <div className="text-2xl font-bold">{stats.estimatedDuration} min</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Required Sensors</div>
                  <div className="mt-1">
                    {Array.from(stats.requiredSensors).map(sensor => (
                      <Badge key={sensor} className="mr-1 mb-1">{sensor}</Badge>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          </Card>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3">
          {activeStep === 0 && (
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">Select Airport</h2>
              <Alert className="mb-4">
                <AlertDescription>
                  Select the airport where you want to plan the inspection mission
                </AlertDescription>
              </Alert>
              <Button
                onClick={() => {
                  setSelectedAirport({ id: 'lzib', name: 'Bratislava Airport' });
                  setActiveStep(1);
                }}
              >
                Select Bratislava Airport (LZIB)
              </Button>
            </Card>
          )}

          {activeStep === 1 && (
            <Card className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">Select Items & Tasks</h2>
                <div className="flex gap-4">
                  <Select value={filterCategory} onValueChange={setFilterCategory}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="Category" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Categories</SelectItem>
                      <SelectItem value="lighting">Lighting</SelectItem>
                      <SelectItem value="marking">Marking</SelectItem>
                      <SelectItem value="navigation">Navigation</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  <Select value={filterPriority} onValueChange={setFilterPriority}>
                    <SelectTrigger className="w-[150px]">
                      <SelectValue placeholder="Priority" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  <label className="flex items-center">
                    <input 
                      type="checkbox" 
                      checked={showOnlyDue} 
                      onChange={(e) => setShowOnlyDue(e.target.checked)}
                      className="mr-2"
                    />
                    Due Soon
                  </label>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredItems.map((item) => (
                  <Card key={item.id} className="p-4">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-semibold">{item.name}</h3>
                      {item.priority && (
                        <Badge 
                          className={
                            item.priority === 'critical' ? 'bg-red-500' :
                            item.priority === 'high' ? 'bg-orange-500' :
                            'bg-gray-500'
                          }
                        >
                          {item.priority}
                        </Badge>
                      )}
                    </div>
                    
                    <p className="text-sm text-gray-600 mb-2">
                      Type: {item.type} | Status: {item.status}
                    </p>
                    
                    {item.next_inspection && (
                      <p className="text-xs text-gray-500 mb-3">
                        Next inspection: {new Date(item.next_inspection).toLocaleDateString()}
                      </p>
                    )}
                    
                    <div>
                      <h4 className="text-sm font-medium mb-2">Available Tasks:</h4>
                      <div className="space-y-1">
                        {maintenanceTasks
                          .filter(task => true) // Filter by item type in real implementation
                          .slice(0, 3)
                          .map((task) => {
                            const isSelected = selectedTasks.find(
                              st => st.item.id === item.id && st.task.id === task.id
                            );
                            return (
                              <div 
                                key={task.id}
                                className="flex items-center p-2 rounded hover:bg-gray-50 cursor-pointer"
                                onClick={() => handleSelectTask(item, task)}
                              >
                                <Checkbox checked={!!isSelected} className="mr-2" />
                                <span className="mr-2">{TASK_TYPE_ICONS[task.task_type] || <CheckCircle />}</span>
                                <div>
                                  <div className="text-sm font-medium">{task.name}</div>
                                  <div className="text-xs text-gray-500">{task.duration_minutes} min</div>
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>

              <div className="mt-6 flex gap-2">
                <Button 
                  onClick={() => setActiveStep(2)}
                  disabled={selectedTasks.length === 0}
                >
                  Continue
                </Button>
                <Button variant="outline" onClick={() => setActiveStep(0)}>
                  Back
                </Button>
              </div>
            </Card>
          )}

          {activeStep === 2 && (
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">Mission Configuration</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-4">
                  <h3 className="text-lg font-semibold mb-3 flex items-center">
                    <Schedule className="mr-2" />
                    Schedule
                  </h3>
                  <Label htmlFor="plannedDate">Planned Date & Time</Label>
                  <Input
                    id="plannedDate"
                    type="datetime-local"
                    value={missionParams.plannedDate.toISOString().slice(0, 16)}
                    onChange={(e) => setMissionParams({
                      ...missionParams,
                      plannedDate: new Date(e.target.value)
                    })}
                  />
                </Card>
                
                <Card className="p-4">
                  <h3 className="text-lg font-semibold mb-3 flex items-center">
                    <Battery80 className="mr-2" />
                    Battery Management
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <Label>Max Flight Time: {missionParams.maxFlightTime} minutes</Label>
                      <Slider
                        value={missionParams.maxFlightTime}
                        onValueChange={(value: number) => setMissionParams({
                          ...missionParams,
                          maxFlightTime: value
                        })}
                        min={5}
                        max={30}
                        step={1}
                        className="mt-2"
                      />
                    </div>
                    <div>
                      <Label>Battery Usage: {missionParams.batteryCapacity}%</Label>
                      <Slider
                        value={missionParams.batteryCapacity}
                        onValueChange={(value: number) => setMissionParams({
                          ...missionParams,
                          batteryCapacity: value
                        })}
                        min={50}
                        max={95}
                        step={1}
                        className="mt-2"
                      />
                    </div>
                  </div>
                </Card>
                
                <Card className="p-4">
                  <h3 className="text-lg font-semibold mb-3 flex items-center">
                    <Cloud className="mr-2" />
                    Weather Constraints
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="maxWindSpeed">Max Wind Speed (m/s)</Label>
                      <Input
                        id="maxWindSpeed"
                        type="number"
                        value={missionParams.weatherConstraints.maxWindSpeed}
                        onChange={(e) => setMissionParams({
                          ...missionParams,
                          weatherConstraints: {
                            ...missionParams.weatherConstraints,
                            maxWindSpeed: parseInt(e.target.value)
                          }
                        })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="minVisibility">Min Visibility (m)</Label>
                      <Input
                        id="minVisibility"
                        type="number"
                        value={missionParams.weatherConstraints.minVisibility}
                        onChange={(e) => setMissionParams({
                          ...missionParams,
                          weatherConstraints: {
                            ...missionParams.weatherConstraints,
                            minVisibility: parseInt(e.target.value)
                          }
                        })}
                      />
                    </div>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={missionParams.weatherConstraints.avoidRain}
                        onChange={(e) => setMissionParams({
                          ...missionParams,
                          weatherConstraints: {
                            ...missionParams.weatherConstraints,
                            avoidRain: e.target.checked
                          }
                        })}
                        className="mr-2"
                      />
                      Avoid Rain
                    </label>
                  </div>
                </Card>
                
                <Card className="p-4">
                  <h3 className="text-lg font-semibold mb-3 flex items-center">
                    <Warning className="mr-2" />
                    Safety Parameters
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="minAltitude">Min Altitude (m)</Label>
                      <Input
                        id="minAltitude"
                        type="number"
                        value={missionParams.safetyParams.minAltitude}
                        onChange={(e) => setMissionParams({
                          ...missionParams,
                          safetyParams: {
                            ...missionParams.safetyParams,
                            minAltitude: parseInt(e.target.value)
                          }
                        })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="maxAltitude">Max Altitude (m)</Label>
                      <Input
                        id="maxAltitude"
                        type="number"
                        value={missionParams.safetyParams.maxAltitude}
                        onChange={(e) => setMissionParams({
                          ...missionParams,
                          safetyParams: {
                            ...missionParams.safetyParams,
                            maxAltitude: parseInt(e.target.value)
                          }
                        })}
                      />
                    </div>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={missionParams.safetyParams.obstacleAvoidance}
                        onChange={(e) => setMissionParams({
                          ...missionParams,
                          safetyParams: {
                            ...missionParams.safetyParams,
                            obstacleAvoidance: e.target.checked
                          }
                        })}
                        className="mr-2"
                      />
                      Obstacle Avoidance
                    </label>
                  </div>
                </Card>
              </div>

              <div className="mt-6 flex gap-2">
                <Button onClick={() => setActiveStep(3)}>
                  Continue
                </Button>
                <Button variant="outline" onClick={() => setActiveStep(1)}>
                  Back
                </Button>
              </div>
            </Card>
          )}

          {activeStep === 3 && (
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">Review Mission Plan</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-4">
                  <h3 className="text-lg font-semibold mb-3">Mission Summary</h3>
                  <Table>
                    <TableBody>
                      <TableRow>
                        <TableCell>Airport</TableCell>
                        <TableCell>{selectedAirport?.name}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Planned Date</TableCell>
                        <TableCell>{missionParams.plannedDate.toLocaleString()}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Total Items</TableCell>
                        <TableCell>{stats.totalItems}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Total Tasks</TableCell>
                        <TableCell>{stats.totalTasks}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Estimated Duration</TableCell>
                        <TableCell>{stats.estimatedDuration} minutes</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Path Optimization</TableCell>
                        <TableCell>
                          <Badge className={missionParams.optimization ? "bg-green-500" : "bg-gray-500"}>
                            {missionParams.optimization ? "Enabled" : "Disabled"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </Card>
                
                <Card className="p-4">
                  <h3 className="text-lg font-semibold mb-3">Safety Checks</h3>
                  <div className="space-y-2">
                    <div className="flex items-center">
                      <CheckCircle className="text-green-500 mr-2" />
                      <span>Altitude limits configured</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="text-green-500 mr-2" />
                      <span>Weather constraints set</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="text-green-500 mr-2" />
                      <span>Battery management configured</span>
                    </div>
                    <div className="flex items-center">
                      {missionParams.safetyParams.obstacleAvoidance ? (
                        <CheckCircle className="text-green-500 mr-2" />
                      ) : (
                        <Warning className="text-orange-500 mr-2" />
                      )}
                      <span>
                        Obstacle avoidance {missionParams.safetyParams.obstacleAvoidance ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                </Card>
              </div>
              
              <div className="mt-6 text-center">
                <Button
                  size="lg"
                  onClick={generateFlightPlan}
                  disabled={loading}
                  className="mr-4"
                >
                  {loading ? (
                    <>Loading...</>
                  ) : (
                    <>
                      <PlayArrow className="mr-2" />
                      Generate Flight Plan
                    </>
                  )}
                </Button>
                <Button variant="outline" onClick={() => setActiveStep(2)}>
                  Back
                </Button>
              </div>
            </Card>
          )}

          {activeStep === 4 && showVisualization && flightPlan && (
            <div>
              <Card className="p-4 mb-4">
                <div className="flex justify-between items-center">
                  <h2 className="text-xl font-semibold">Flight Plan Visualization</h2>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => exportFlightPlan('mavlink')}
                    >
                      <Download className="mr-2" />
                      Export MAVLink
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => exportFlightPlan('kml')}
                    >
                      <Map className="mr-2" />
                      Export KML
                    </Button>
                    <Button variant="outline">
                      <Save className="mr-2" />
                      Save Plan
                    </Button>
                  </div>
                </div>
              </Card>
              
              <Card className="p-6 h-96 flex items-center justify-center">
                <h3 className="text-lg text-gray-500">
                  3D Flight Path Viewer (Temporarily Unavailable)
                </h3>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MissionPlanning;