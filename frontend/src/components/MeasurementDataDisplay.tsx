import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Loader2, Download, Map, BarChart3, Lightbulb, Video } from 'lucide-react';
import api from '../services/api';
import Airport3DVisualization from './Airport3DVisualization';

interface MeasurementData {
  summary: {
    total_frames: number;
    duration: number;
    session_info: {
      id: string;
      airport_code: string;
      runway_code: string;
      created_at: string;
      video_file: string;
    };
  };
  papi_data: {
    [key: string]: {
      timestamps: number[];
      statuses: string[];
      angles: number[];
      distances: number[];
      rgb_values: Array<[number, number, number]>;
    };
  };
  drone_positions: Array<{
    frame: number;
    timestamp: number;
    latitude: number;
    longitude: number;
    elevation: number;
    gimbal_pitch?: number;
    gimbal_roll?: number;
    gimbal_yaw?: number;
  }>;
  reference_points: {
    [key: string]: {
      latitude: number;
      longitude: number;
      elevation: number;
      point_type: string;
    };
  };
  video_urls?: {
    PAPI_A: string;
    PAPI_B: string;
    PAPI_C: string;
    PAPI_D: string;
    enhanced_main: string;
    original: string;
  };
}

interface Props {
  sessionId: string;
}

const MeasurementDataDisplay: React.FC<Props> = ({ sessionId }) => {
  const [data, setData] = useState<MeasurementData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'overview' | 'charts' | 'positions' | 'videos'>('overview');

  useEffect(() => {
    fetchMeasurementData();
  }, [sessionId]);

  const fetchMeasurementData = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/papi-measurements/session/${sessionId}/measurements-data`);
      setData(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load measurement data');
    } finally {
      setLoading(false);
    }
  };

  const downloadCSV = () => {
    if (!data) return;
    
    const csvLines = ['Frame,Timestamp,PAPI_A_Status,PAPI_A_Angle,PAPI_B_Status,PAPI_B_Angle,PAPI_C_Status,PAPI_C_Angle,PAPI_D_Status,PAPI_D_Angle,Drone_Lat,Drone_Lon,Drone_Height_AGL,Drone_Elevation_MSL'];
    
    // Calculate ground elevation reference
    let groundElevation = 0;
    if (data.reference_points.TOUCH_POINT) {
      groundElevation = data.reference_points.TOUCH_POINT.elevation;
    } else {
      const papiElevations = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']
        .map(light => data.reference_points[light]?.elevation)
        .filter(elev => elev !== undefined);
      if (papiElevations.length > 0) {
        groundElevation = papiElevations.reduce((sum, elev) => sum + elev, 0) / papiElevations.length;
      }
    }
    
    data.drone_positions.forEach((pos, index) => {
      const row = [
        pos.frame ?? 0,
        (pos.timestamp ?? 0).toFixed(2),
        data.papi_data.PAPI_A?.statuses[index] || 'unknown',
        (data.papi_data.PAPI_A?.angles[index] ?? 0).toFixed(2),
        data.papi_data.PAPI_B?.statuses[index] || 'unknown',
        (data.papi_data.PAPI_B?.angles[index] ?? 0).toFixed(2),
        data.papi_data.PAPI_C?.statuses[index] || 'unknown',
        (data.papi_data.PAPI_C?.angles[index] ?? 0).toFixed(2),
        data.papi_data.PAPI_D?.statuses[index] || 'unknown',
        (data.papi_data.PAPI_D?.angles[index] ?? 0).toFixed(2),
        (pos.latitude ?? 0).toFixed(6),
        (pos.longitude ?? 0).toFixed(6),
        ((pos.elevation ?? 0) - groundElevation).toFixed(1), // Height above ground level
        (pos.elevation ?? 0).toFixed(1) // Absolute elevation above sea level
      ];
      csvLines.push(row.join(','));
    });
    
    const csvContent = csvLines.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `papi_measurement_${sessionId}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const formatChartData = () => {
    if (!data) return [];
    
    // Calculate ground elevation reference (use TOUCH_POINT or average of PAPI lights)
    let groundElevation = 0;
    if (data.reference_points.TOUCH_POINT) {
      groundElevation = data.reference_points.TOUCH_POINT.elevation;
    } else {
      // Use average elevation of PAPI lights as reference
      const papiElevations = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']
        .map(light => data.reference_points[light]?.elevation)
        .filter(elev => elev !== undefined);
      if (papiElevations.length > 0) {
        groundElevation = papiElevations.reduce((sum, elev) => sum + elev, 0) / papiElevations.length;
      }
    }
    
    return data.drone_positions.map((pos, index) => ({
      frame: pos.frame ?? 0,
      timestamp: pos.timestamp ?? 0,
      PAPI_A: data.papi_data.PAPI_A?.angles[index] ?? 0,
      PAPI_B: data.papi_data.PAPI_B?.angles[index] ?? 0,
      PAPI_C: data.papi_data.PAPI_C?.angles[index] ?? 0,
      PAPI_D: data.papi_data.PAPI_D?.angles[index] ?? 0,
      latitude: pos.latitude ?? 0,
      longitude: pos.longitude ?? 0,
      elevation: (pos.elevation ?? 0) - groundElevation, // Show height above ground level
      elevationAbsolute: pos.elevation ?? 0, // Absolute elevation from GPS
      elevationExact: pos.elevation ?? 0 // Exact drone elevation for the height profile chart
    }));
  };

  const formatRGBChartData = (lightName: string) => {
    if (!data || !data.papi_data[lightName]) return [];

    const lightData = data.papi_data[lightName];
    return lightData.timestamps.map((timestamp, index) => {
      const rgb = lightData.rgb_values[index] || [0, 0, 0];
      const [r, g, b] = Array.isArray(rgb) ? rgb : [0, 0, 0];


      return {
        timestamp: timestamp ?? 0,
        time: (timestamp ?? 0).toFixed(2),
        red: r ?? 0,
        green: g ?? 0,
        blue: b ?? 0,
        angle: lightData.angles[index] ?? 0
      };
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'red': return 'text-red-600 bg-red-100';
      case 'white': return 'text-gray-800 bg-gray-100';
      case 'transition': return 'text-yellow-600 bg-yellow-100';
      default: return 'text-gray-400 bg-gray-50';
    }
  };

  const getStatusCounts = (papiName: string) => {
    if (!data?.papi_data[papiName]) return { red: 0, white: 0, transition: 0, not_visible: 0 };
    
    const counts = { red: 0, white: 0, transition: 0, not_visible: 0 };
    data.papi_data[papiName].statuses.forEach(status => {
      counts[status as keyof typeof counts]++;
    });
    return counts;
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin mr-2" />
          <span>Loading measurement data...</span>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="text-center text-red-600">
            <p>Error loading data: {error}</p>
            <Button onClick={fetchMeasurementData} className="mt-4">
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const chartData = formatChartData();

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Measurement Analysis</CardTitle>
            <Button onClick={downloadCSV} variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex space-x-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'overview' 
                  ? 'bg-white text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <BarChart3 className="w-4 h-4 inline mr-2" />
              Overview
            </button>
            <button
              onClick={() => setActiveTab('charts')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'charts' 
                  ? 'bg-white text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Lightbulb className="w-4 h-4 inline mr-2" />
              PAPI Analysis
            </button>
            <button
              onClick={() => setActiveTab('positions')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'positions' 
                  ? 'bg-white text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Map className="w-4 h-4 inline mr-2" />
              Drone Path
            </button>
            <button
              onClick={() => setActiveTab('videos')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'videos' 
                  ? 'bg-white text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Video className="w-4 h-4 inline mr-2" />
              Videos
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Session Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Session Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium">Airport:</span>
                  <p className="text-gray-600">{data.summary.session_info.airport_code}</p>
                </div>
                <div>
                  <span className="font-medium">Runway:</span>
                  <p className="text-gray-600">{data.summary.session_info.runway_code}</p>
                </div>
                <div>
                  <span className="font-medium">Duration:</span>
                  <p className="text-gray-600">{(data.summary.duration ?? 0).toFixed(1)}s</p>
                </div>
                <div>
                  <span className="font-medium">Total Frames:</span>
                  <p className="text-gray-600">{data.summary.total_frames}</p>
                </div>
                <div className="col-span-2">
                  <span className="font-medium">Video File:</span>
                  <p className="text-gray-600 text-xs">{data.summary.session_info.video_file}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* PAPI Light Status Summary */}
          <Card>
            <CardHeader>
              <CardTitle>PAPI Light Status Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 text-sm">
                {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].map(papi => {
                  const counts = getStatusCounts(papi);
                  const total = Object.values(counts).reduce((a, b) => a + b, 0);
                  return (
                    <div key={papi} className="space-y-2">
                      <h4 className="font-medium">{papi.replace('_', ' ')}</h4>
                      <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-red-600">Red:</span>
                          <span>{counts.red} ({total > 0 ? ((counts.red / total) * 100).toFixed(1) : 0}%)</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">White:</span>
                          <span>{counts.white} ({total > 0 ? ((counts.white / total) * 100).toFixed(1) : 0}%)</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-yellow-600">Transition:</span>
                          <span>{counts.transition} ({total > 0 ? ((counts.transition / total) * 100).toFixed(1) : 0}%)</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'charts' && (
        <div className="space-y-6">
          {/* PAPI Analysis Charts - One for each light */}
          {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].map((lightName) => {
            const rgbData = formatRGBChartData(lightName);
            const lightColor = {
              'PAPI_A': '#ef4444',
              'PAPI_B': '#f97316', 
              'PAPI_C': '#eab308',
              'PAPI_D': '#22c55e'
            }[lightName];
            
            return (
              <Card key={lightName}>
                <CardHeader>
                  <CardTitle>{lightName} Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Combined RGB Values and Elevation Angles Chart */}
                  <div>
                    <h4 className="text-sm font-medium mb-3">RGB Values and Elevation Angles Over Time</h4>
                    <ResponsiveContainer width="100%" height={400}>
                      <LineChart data={rgbData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis 
                          dataKey="timestamp" 
                          label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }} 
                        />
                        {/* Left Y-axis for RGB values */}
                        <YAxis 
                          yAxisId="rgb"
                          label={{ value: 'RGB Value (0-255)', angle: -90, position: 'insideLeft' }}
                          domain={[0, 255]}
                        />
                        {/* Right Y-axis for angles */}
                        <YAxis
                          yAxisId="angle"
                          orientation="right"
                          label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                          domain={['dataMin - 1', 'dataMax + 1']}
                        />
                        <Tooltip
                          formatter={(value: any, name: string) => {
                            if (value == null) return ['N/A', name];
                            if (name === 'angle') return [`${value.toFixed(2)}°`, 'Angle'];
                            if (['red', 'green', 'blue'].includes(name)) return [`${Math.round(value)}`, name.toUpperCase()];
                            return [`${value.toFixed(2)}`, name];
                          }}
                          labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                        />
                        <Legend />
                        {/* RGB Lines on left axis */}
                        <Line yAxisId="rgb" type="monotone" dataKey="red" stroke="#dc2626" strokeWidth={2} dot={false} name="Red" />
                        <Line yAxisId="rgb" type="monotone" dataKey="green" stroke="#16a34a" strokeWidth={2} dot={false} name="Green" />
                        <Line yAxisId="rgb" type="monotone" dataKey="blue" stroke="#2563eb" strokeWidth={2} dot={false} name="Blue" />
                        {/* Angle Line on right axis */}
                        <Line yAxisId="angle" type="monotone" dataKey="angle" stroke={lightColor} strokeWidth={3} dot={false} name="Angle" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {activeTab === 'positions' && (
        <div className="space-y-6">
          {/* 3D Airport Visualization */}
          <Card>
            <CardHeader>
              <CardTitle>3D Airport Visualization</CardTitle>
              <p className="text-sm text-gray-600">
                Interactive 3D view showing runway, PAPI lights, reference points, and drone flight path
              </p>
            </CardHeader>
            <CardContent>
              <Airport3DVisualization 
                dronePositions={data.drone_positions}
                referencePoints={data.reference_points}
              />
              
              {/* Legend */}
              <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-cyan-400 rounded"></div>
                  <span>Drone Flight Path</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded"></div>
                  <span>Start Position</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-red-500 rounded"></div>
                  <span>End Position / Touch Point</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-yellow-500 rounded"></div>
                  <span>Animated Drone</span>
                </div>
              </div>
              
              <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-red-500 rounded"></div>
                  <span>PAPI A</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-orange-500 rounded"></div>
                  <span>PAPI B</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-yellow-500 rounded"></div>
                  <span>PAPI C</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded"></div>
                  <span>PAPI D</span>
                </div>
              </div>
              
              <div className="mt-4 text-xs text-gray-500">
                💡 Use mouse to rotate, zoom, and pan the 3D view
              </div>
            </CardContent>
          </Card>
          
          {/* Height Profile Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Drone Height Profile (Exact Elevation)</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="timestamp" label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }} />
                  <YAxis 
                    label={{ value: 'Exact Elevation (m)', angle: -90, position: 'insideLeft' }}
                    domain={['dataMin - 5', 'dataMax + 5']}
                  />
                  <Tooltip
                    formatter={(value: any) => [`${(value ?? 0).toFixed(1)}m`, 'Exact Elevation']}
                    labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                  />
                  <Line type="monotone" dataKey="elevationExact" stroke="#3b82f6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'videos' && data?.video_urls && (
        <div className="space-y-6">
          {/* Enhanced Main Video */}
          <Card>
            <CardHeader>
              <CardTitle>Enhanced Main Video</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="aspect-video">
                <video
                  key={data.video_urls?.enhanced_main}
                  width="100%"
                  height="100%"
                  controls
                  preload="metadata"
                  className="rounded-lg border"
                  src={data.video_urls?.enhanced_main}
                  onError={(e) => {
                    const video = e.currentTarget as HTMLVideoElement;
                    console.error('Enhanced video error:', {
                      error: video.error,
                      code: video.error?.code,
                      message: video.error?.message,
                      networkState: video.networkState,
                      readyState: video.readyState,
                      src: data.video_urls?.enhanced_main
                    });
                  }}
                  onLoadedMetadata={() => console.log('Video loaded:', data.video_urls?.enhanced_main)}
                >
                  Your browser does not support the video tag.
                </video>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                Enhanced video with drone position overlays, PAPI light rectangles, and angle information
              </p>
            </CardContent>
          </Card>

          {/* Individual PAPI Light Videos */}
          <Card>
            <CardHeader>
              <CardTitle>Individual PAPI Light Videos</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].map((light) => (
                  <div key={light} className="space-y-3">
                    <h4 className="font-medium text-center">{light.replace('_', ' ')}</h4>
                    <div className="aspect-video">
                      <video
                        key={data.video_urls?.[light as keyof typeof data.video_urls]}
                        width="100%"
                        height="100%"
                        controls
                        preload="metadata"
                        className="rounded border"
                        src={data.video_urls?.[light as keyof typeof data.video_urls]}
                        onError={(e) => {
                          const video = e.currentTarget as HTMLVideoElement;
                          console.error('Video error:', light, {
                            error: video.error,
                            networkState: video.networkState,
                            readyState: video.readyState,
                            src: data.video_urls?.[light as keyof typeof data.video_urls]
                          });
                        }}
                        onLoadedMetadata={() => console.log('Video loaded:', light)}
                      >
                        Your browser does not support the video tag.
                      </video>
                    </div>
                    <p className="text-xs text-gray-600 text-center">
                      Isolated view of {light.replace('_', ' ')} light with status changes
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

        </div>
      )}

      {/* Reference Points */}
      {Object.keys(data.reference_points).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Reference Points</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              {Object.entries(data.reference_points).map(([pointId, point]) => (
                <div key={pointId} className="bg-gray-50 p-3 rounded">
                  <h4 className="font-medium">{pointId.replace('_', ' ')}</h4>
                  <div className="mt-2 space-y-1 text-xs text-gray-600">
                    <p>Lat: {(point.latitude ?? 0).toFixed(6)}</p>
                    <p>Lon: {(point.longitude ?? 0).toFixed(6)}</p>
                    <p>Elev: {(point.elevation ?? 0).toFixed(1)}m</p>
                    <p className="capitalize">Type: {point.point_type?.replace('_', ' ') ?? 'unknown'}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default MeasurementDataDisplay;