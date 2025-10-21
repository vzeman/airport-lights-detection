import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
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
      intensities: number[];
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
      nominal_angle?: number;
      tolerance?: number;
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

  const calculateTouchPointAngle = (dronePos: any, touchPoint: any, groundElevation: number, debug: boolean = false): number => {
    if (!dronePos || !touchPoint) {
      if (debug) console.log('[Calc Debug] Missing dronePos or touchPoint');
      return 0;
    }

    // Check for valid coordinates
    if (!dronePos.latitude || !dronePos.longitude || !dronePos.elevation) {
      if (debug) console.log('[Calc Debug] Invalid drone position data:', dronePos);
      return 0;
    }

    if (!touchPoint.latitude || !touchPoint.longitude) {
      if (debug) console.log('[Calc Debug] Invalid touch point coordinates:', touchPoint);
      return 0;
    }

    // Use ground elevation if touch point elevation is null
    const touchPointElevation = touchPoint.elevation ?? groundElevation;

    if (debug) {
      console.log('[Calc Debug] Touch point elevation:', touchPoint.elevation, 'Using:', touchPointElevation);
    }

    // Haversine formula to calculate horizontal distance
    const R = 6371000; // Earth's radius in meters
    const lat1 = dronePos.latitude * Math.PI / 180;
    const lat2 = touchPoint.latitude * Math.PI / 180;
    const deltaLat = (touchPoint.latitude - dronePos.latitude) * Math.PI / 180;
    const deltaLon = (touchPoint.longitude - dronePos.longitude) * Math.PI / 180;

    const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
              Math.cos(lat1) * Math.cos(lat2) *
              Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const horizontalDistance = R * c;

    // Calculate vertical distance (from touch point UP to drone)
    const verticalDistance = dronePos.elevation - touchPointElevation;

    // Calculate elevation angle in degrees
    const angleRadians = Math.atan2(verticalDistance, horizontalDistance);
    const angleDegrees = angleRadians * 180 / Math.PI;

    if (debug) {
      console.log('[Calc Debug] Calculation details:');
      console.log('  Drone lat/lon/elev:', dronePos.latitude, dronePos.longitude, dronePos.elevation);
      console.log('  Touch lat/lon/elev (raw):', touchPoint.latitude, touchPoint.longitude, touchPoint.elevation);
      console.log('  Touch elevation used:', touchPointElevation);
      console.log('  Ground elevation fallback:', groundElevation);
      console.log('  Delta lat:', touchPoint.latitude - dronePos.latitude);
      console.log('  Delta lon:', touchPoint.longitude - dronePos.longitude);
      console.log('  Horizontal distance (m):', horizontalDistance.toFixed(2));
      console.log('  Vertical distance (m):', verticalDistance.toFixed(2));
      console.log('  atan2 inputs: atan2(' + verticalDistance.toFixed(2) + ', ' + horizontalDistance.toFixed(2) + ')');
      console.log('  Angle (degrees):', angleDegrees.toFixed(2));
    }

    return angleDegrees;
  };

  const formatRGBChartData = (lightName: string) => {
    if (!data || !data.papi_data[lightName]) return [];

    const lightData = data.papi_data[lightName];

    // Find touch point by searching for key that contains 'TOUCH_POINT'
    let touchPoint = null;
    if (data.reference_points) {
      const touchPointKey = Object.keys(data.reference_points).find(key =>
        key.includes('TOUCH_POINT') || key.includes('ReferencePointType.TOUCH_POINT')
      );
      if (touchPointKey) {
        touchPoint = data.reference_points[touchPointKey];
      }
    }

    // Calculate ground elevation from PAPI lights for fallback
    let groundElevation = 0;
    if (data.reference_points) {
      const papiKeys = Object.keys(data.reference_points).filter(key =>
        key.includes('PAPI_A') || key.includes('PAPI_B') ||
        key.includes('PAPI_C') || key.includes('PAPI_D')
      );

      if (lightName === 'PAPI_A') {
        console.log('[Ground Elevation Debug] PAPI keys found:', papiKeys);
        console.log('[Ground Elevation Debug] PAPI reference data:',
          papiKeys.map(key => ({ key, data: data.reference_points[key] }))
        );
      }

      const papiElevations = papiKeys
        .map(key => data.reference_points[key]?.elevation)
        .filter(elev => elev !== null && elev !== undefined);

      if (lightName === 'PAPI_A') {
        console.log('[Ground Elevation Debug] PAPI elevations extracted:', papiElevations);
      }

      if (papiElevations.length > 0) {
        groundElevation = papiElevations.reduce((sum, elev) => sum + elev, 0) / papiElevations.length;
      }
    }

    // Debug: Check available reference points
    if (lightName === 'PAPI_A') {
      console.log('[Touch Point Debug] Available reference points:', Object.keys(data.reference_points || {}));
      console.log('[Touch Point Debug] Selected touch point:', touchPoint);
      console.log('[Touch Point Debug] Calculated ground elevation:', groundElevation);
      if (data.drone_positions && data.drone_positions[0]) {
        console.log('[Touch Point Debug] First drone position:', data.drone_positions[0]);
      }
    }

    return lightData.timestamps.map((timestamp, index) => {
      const rgb = lightData.rgb_values[index] || [0, 0, 0];
      const [r, g, b] = Array.isArray(rgb) ? rgb : [0, 0, 0];

      // Calculate chromaticity (normalized RGB)
      const sum = r + g + b;
      const redChromaticity = sum > 0 ? r / sum : 0;
      const greenChromaticity = sum > 0 ? g / sum : 0;
      const blueChromaticity = sum > 0 ? b / sum : 0;

      // Scale chromaticity to 0-100 for better visualization (0-1 range scaled up)
      const redChroma = redChromaticity * 100;
      const greenChroma = greenChromaticity * 100;
      const blueChroma = blueChromaticity * 100;

      // Calculate intensity from RGB if not available in API response (backward compatibility)
      let intensity = 0;
      if (lightData.intensities && lightData.intensities[index] !== undefined) {
        intensity = lightData.intensities[index];
      } else {
        // Fallback: calculate intensity as mean of RGB
        intensity = (r + g + b) / 3;
      }

      // Calculate touch point angle
      const dronePos = data.drone_positions[index];
      let touchPointAngle = 0;

      if (touchPoint && dronePos) {
        // Enable debug logging for first calculation
        const enableDebug = lightName === 'PAPI_A' && index === 0;
        touchPointAngle = calculateTouchPointAngle(dronePos, touchPoint, groundElevation, enableDebug);

        if (enableDebug) {
          console.log('[Touch Point Debug] First calculation result:', touchPointAngle);
        }
      } else {
        if (lightName === 'PAPI_A' && index === 0) {
          console.log('[Touch Point Debug] Missing data - touchPoint:', !!touchPoint, 'dronePos:', !!dronePos);
        }
      }

      return {
        timestamp: timestamp ?? 0,
        time: (timestamp ?? 0).toFixed(2),
        red: r ?? 0,
        green: g ?? 0,
        blue: b ?? 0,
        intensity: intensity,
        redChromaticity: redChroma,
        greenChromaticity: greenChroma,
        blueChromaticity: blueChroma,
        angle: lightData.angles[index] ?? 0,
        touchPointAngle: touchPointAngle
      };
    });
  };

  const findColorTransitionPoints = (lightName: string): number[] => {
    if (!data || !data.papi_data[lightName]) return [];

    const lightData = data.papi_data[lightName];
    const transitionPoints: number[] = [];

    // Use the backend's status data directly - it already knows red vs white!
    // Look for sustained status changes: red <-> white
    const minSustainedFrames = 3; // Require new status to be sustained for 3 frames

    let currentStatus = lightData.statuses[0];
    let statusStartIndex = 0;
    let frameCount = 0;

    for (let i = 1; i < lightData.statuses.length; i++) {
      const status = lightData.statuses[i];

      if (status === currentStatus) {
        frameCount++;
      } else {
        // Status changed - check if it's a meaningful transition
        if (frameCount >= minSustainedFrames &&
            ((currentStatus === 'red' && status === 'white') ||
             (currentStatus === 'white' && status === 'red'))) {
          transitionPoints.push(lightData.timestamps[i]);
        }

        currentStatus = status;
        statusStartIndex = i;
        frameCount = 1;
      }
    }

    console.log(`[${lightName}] Status values present:`, [...new Set(lightData.statuses)]);
    console.log(`[${lightName}] Raw transitions detected: ${transitionPoints.length}`);

    // Group nearby transitions (within 1.5 seconds) and keep only the first one
    const groupedTransitions: number[] = [];
    const groupWindow = 1.5; // seconds (balanced)

    for (let i = 0; i < transitionPoints.length; i++) {
      const currentPoint = transitionPoints[i];

      // Check if this point is close to any already grouped point
      const isNearExisting = groupedTransitions.some(
        existingPoint => Math.abs(currentPoint - existingPoint) < groupWindow
      );

      if (!isNearExisting) {
        groupedTransitions.push(currentPoint);
      }
    }

    // Debug logging
    console.log(`[${lightName}] Detected ${groupedTransitions.length} final transitions:`, groupedTransitions);

    return groupedTransitions.sort((a, b) => a - b);
  };

  const formatComparisonChartData = () => {
    if (!data) return [];

    // Get the longest timestamp array to use as base
    const allLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'];
    const baseLight = allLights.find(light => data.papi_data[light]?.timestamps?.length > 0);
    if (!baseLight) return [];

    const baseTimestamps = data.papi_data[baseLight].timestamps;

    // Find touch point for angle calculation
    let touchPoint = null;
    if (data.reference_points) {
      const touchPointKey = Object.keys(data.reference_points).find(key =>
        key.includes('TOUCH_POINT') || key.includes('ReferencePointType.TOUCH_POINT')
      );
      if (touchPointKey) {
        touchPoint = data.reference_points[touchPointKey];
      }
    }

    // Calculate ground elevation from PAPI lights for fallback
    let groundElevation = 0;
    if (data.reference_points) {
      const papiKeys = Object.keys(data.reference_points).filter(key =>
        key.includes('PAPI_A') || key.includes('PAPI_B') ||
        key.includes('PAPI_C') || key.includes('PAPI_D')
      );
      const papiElevations = papiKeys
        .map(key => data.reference_points[key]?.elevation)
        .filter(elev => elev !== null && elev !== undefined);
      if (papiElevations.length > 0) {
        groundElevation = papiElevations.reduce((sum, elev) => sum + elev, 0) / papiElevations.length;
      }
    }

    return baseTimestamps.map((timestamp, index) => {
      const dataPoint: any = {
        timestamp: timestamp ?? 0,
        time: (timestamp ?? 0).toFixed(2),
      };

      // Add data for each PAPI light
      allLights.forEach(lightName => {
        const lightData = data.papi_data[lightName];
        if (lightData && lightData.timestamps[index] !== undefined) {
          const rgb = lightData.rgb_values[index] || [0, 0, 0];
          const [r, g, b] = Array.isArray(rgb) ? rgb : [0, 0, 0];
          const sum = r + g + b;
          const redChromaticity = sum > 0 ? (r / sum) * 100 : 0;

          // Calculate intensity from RGB if not available in API response (backward compatibility)
          let intensity = 0;
          if (lightData.intensities && lightData.intensities[index] !== undefined) {
            intensity = lightData.intensities[index];
          } else {
            // Fallback: calculate intensity as mean of RGB
            intensity = (r + g + b) / 3;
          }

          // Get angle
          const angle = lightData.angles[index] ?? 0;

          dataPoint[`${lightName}_redChroma`] = redChromaticity;
          dataPoint[`${lightName}_intensity`] = intensity;
          dataPoint[`${lightName}_angle`] = angle;
        }
      });

      // Calculate touch point angle
      const dronePos = data.drone_positions[index];
      if (touchPoint && dronePos) {
        const touchPointAngle = calculateTouchPointAngle(dronePos, touchPoint, groundElevation, false);
        dataPoint['touchPoint_angle'] = touchPointAngle;
      } else {
        dataPoint['touchPoint_angle'] = 0;
      }

      return dataPoint;
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
          {/* Comparison Charts - All PAPI Lights */}
          <Card>
            <CardHeader>
              <CardTitle>All PAPI Lights Comparison</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Chromaticity Comparison Chart */}
              <div>
                <h4 className="text-sm font-medium mb-3">Red Chromaticity and Elevation Angles - All Lights</h4>
                <p className="text-xs text-gray-600 mb-2">
                  Compare color quality and elevation angles across all PAPI lights. Red light ≈ 50-70%, White light ≈ 33%
                </p>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={formatComparisonChartData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    {/* Left Y-axis for Red Chromaticity */}
                    <YAxis
                      yAxisId="chroma"
                      label={{ value: 'Red Chromaticity (%)', angle: -90, position: 'insideLeft' }}
                      domain={['dataMin - 5', 'dataMax + 5']}
                    />
                    {/* Right Y-axis for Angles */}
                    <YAxis
                      yAxisId="angle"
                      orientation="right"
                      label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                      domain={['dataMin - 1', 'dataMax + 1']}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => {
                        if (value == null) return ['N/A', name];
                        if (name.includes('Angle') || name === 'Touch Pt Angle') return [`${value.toFixed(2)}°`, name];
                        return [`${value.toFixed(1)}%`, name];
                      }}
                      labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                    />
                    <Legend />
                    {/* Reference line at 33% (balanced white light) */}
                    <ReferenceLine
                      yAxisId="chroma"
                      y={33.33}
                      stroke="#94a3b8"
                      strokeDasharray="3 3"
                      label={{
                        value: 'White (33%)',
                        position: 'right',
                        fill: '#64748b',
                        fontSize: 11
                      }}
                    />
                    {/* Nominal angle reference lines for each PAPI light */}
                    {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].map((lightName) => {
                      const lightPoint = Object.entries(data.reference_points).find(([key, point]) =>
                        key.includes(lightName)
                      );
                      if (lightPoint && lightPoint[1].nominal_angle) {
                        const colors = { 'PAPI_A': '#ef4444', 'PAPI_B': '#f97316', 'PAPI_C': '#eab308', 'PAPI_D': '#22c55e' };
                        return (
                          <ReferenceLine
                            key={`nominal-${lightName}`}
                            yAxisId="angle"
                            y={lightPoint[1].nominal_angle}
                            stroke={colors[lightName as keyof typeof colors]}
                            strokeDasharray="2 2"
                            strokeWidth={1.5}
                            label={{
                              value: `${lightName.split('_')[1]} nom`,
                              position: 'right',
                              fill: colors[lightName as keyof typeof colors],
                              fontSize: 9
                            }}
                          />
                        );
                      }
                      return null;
                    })}
                    {/* Chromaticity Lines on left axis */}
                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_A_redChroma" stroke="#ef4444" strokeWidth={2} dot={false} name="PAPI A Red Chroma" />
                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_B_redChroma" stroke="#f97316" strokeWidth={2} dot={false} name="PAPI B Red Chroma" />
                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_C_redChroma" stroke="#eab308" strokeWidth={2} dot={false} name="PAPI C Red Chroma" />
                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_D_redChroma" stroke="#22c55e" strokeWidth={2} dot={false} name="PAPI D Red Chroma" />
                    {/* Angle Lines on right axis (dashed to differentiate) */}
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_A_angle" stroke="#ef4444" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI A Angle" />
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_B_angle" stroke="#f97316" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI B Angle" />
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_C_angle" stroke="#eab308" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI C Angle" />
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_D_angle" stroke="#22c55e" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI D Angle" />
                    {/* Touch Point Angle */}
                    <Line yAxisId="angle" type="monotone" dataKey="touchPoint_angle" stroke="#8b5cf6" strokeWidth={3} dot={false} name="Touch Pt Angle" />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Intensity Comparison Chart */}
              <div>
                <h4 className="text-sm font-medium mb-3">Luminosity (Intensity) and Elevation Angles - All Lights</h4>
                <p className="text-xs text-gray-600 mb-2">
                  Compare brightness levels and elevation angles across all PAPI lights over time
                </p>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={formatComparisonChartData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    {/* Left Y-axis for Intensity */}
                    <YAxis
                      yAxisId="intensity"
                      label={{ value: 'Intensity', angle: -90, position: 'insideLeft' }}
                      domain={['dataMin - 10', 'dataMax + 10']}
                    />
                    {/* Right Y-axis for Angles */}
                    <YAxis
                      yAxisId="angle"
                      orientation="right"
                      label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                      domain={['dataMin - 1', 'dataMax + 1']}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => {
                        if (value == null) return ['N/A', name];
                        if (name.includes('Angle') || name === 'Touch Pt Angle') return [`${value.toFixed(2)}°`, name];
                        return [`${Math.round(value)}`, name];
                      }}
                      labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                    />
                    <Legend />
                    {/* Reference line at 30 (not visible threshold) */}
                    <ReferenceLine
                      yAxisId="intensity"
                      y={30}
                      stroke="#94a3b8"
                      strokeDasharray="3 3"
                      label={{
                        value: 'Not Visible (30)',
                        position: 'right',
                        fill: '#64748b',
                        fontSize: 11
                      }}
                    />
                    {/* Nominal angle reference lines for each PAPI light */}
                    {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].map((lightName) => {
                      const lightPoint = Object.entries(data.reference_points).find(([key, point]) =>
                        key.includes(lightName)
                      );
                      if (lightPoint && lightPoint[1].nominal_angle) {
                        const colors = { 'PAPI_A': '#ef4444', 'PAPI_B': '#f97316', 'PAPI_C': '#eab308', 'PAPI_D': '#22c55e' };
                        return (
                          <ReferenceLine
                            key={`nominal-${lightName}`}
                            yAxisId="angle"
                            y={lightPoint[1].nominal_angle}
                            stroke={colors[lightName as keyof typeof colors]}
                            strokeDasharray="2 2"
                            strokeWidth={1.5}
                            label={{
                              value: `${lightName.split('_')[1]} nom`,
                              position: 'right',
                              fill: colors[lightName as keyof typeof colors],
                              fontSize: 9
                            }}
                          />
                        );
                      }
                      return null;
                    })}
                    {/* Intensity Lines on left axis */}
                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_A_intensity" stroke="#ef4444" strokeWidth={2} dot={false} name="PAPI A Intensity" />
                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_B_intensity" stroke="#f97316" strokeWidth={2} dot={false} name="PAPI B Intensity" />
                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_C_intensity" stroke="#eab308" strokeWidth={2} dot={false} name="PAPI C Intensity" />
                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_D_intensity" stroke="#22c55e" strokeWidth={2} dot={false} name="PAPI D Intensity" />
                    {/* Angle Lines on right axis (dashed to differentiate) */}
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_A_angle" stroke="#ef4444" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI A Angle" />
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_B_angle" stroke="#f97316" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI B Angle" />
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_C_angle" stroke="#eab308" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI C Angle" />
                    <Line yAxisId="angle" type="monotone" dataKey="PAPI_D_angle" stroke="#22c55e" strokeWidth={2} strokeDasharray="5 5" dot={false} name="PAPI D Angle" />
                    {/* Touch Point Angle */}
                    <Line yAxisId="angle" type="monotone" dataKey="touchPoint_angle" stroke="#8b5cf6" strokeWidth={3} dot={false} name="Touch Pt Angle" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* PAPI Analysis Charts - One for each light */}
          {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].map((lightName) => {
            const rgbData = formatRGBChartData(lightName);
            const transitionPoints = findColorTransitionPoints(lightName);
            const lightColor = {
              'PAPI_A': '#ef4444',
              'PAPI_B': '#f97316',
              'PAPI_C': '#eab308',
              'PAPI_D': '#22c55e'
            }[lightName];

            // Get nominal angle for this PAPI light
            const lightPoint = Object.entries(data.reference_points).find(([key, point]) =>
              key.includes(lightName)
            );
            const nominalAngle = lightPoint?.[1]?.nominal_angle;

            return (
              <Card key={lightName}>
                <CardHeader>
                  <CardTitle>{lightName} Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Combined RGB Values and Elevation Angles Chart */}
                  <div className="mb-6">
                    <h4 className="text-sm font-medium mb-3">RGB Values and Elevation Angles Over Time</h4>
                    {transitionPoints.length > 0 ? (
                      <p className="text-xs text-gray-600 mb-2">
                        Color transition points marked at: {transitionPoints.map(t => t.toFixed(2) + 's').join(', ')}
                      </p>
                    ) : (
                      <p className="text-xs text-gray-500 mb-2">
                        No color transitions detected (light remained stable)
                      </p>
                    )}
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
                          label={{ value: 'RGB Value', angle: -90, position: 'insideLeft' }}
                          domain={['dataMin - 10', 'dataMax + 10']}
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
                            if (name === 'Angle' || name === 'Touch Pt Angle') return [`${value.toFixed(2)}°`, name];
                            if (['red', 'green', 'blue'].includes(name)) return [`${Math.round(value)}`, name.toUpperCase()];
                            if (name === 'intensity') return [`${Math.round(value)}`, 'Intensity'];
                            return [`${value.toFixed(2)}`, name];
                          }}
                          labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                        />
                        <Legend />
                        {/* Transition Point Markers */}
                        {transitionPoints.map((timestamp, idx) => (
                          <ReferenceLine
                            key={`transition-${idx}`}
                            x={timestamp}
                            stroke="#9333ea"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            label={{
                              value: 'Transition',
                              position: 'top',
                              fill: '#9333ea',
                              fontSize: 12
                            }}
                          />
                        ))}
                        {/* Nominal angle reference line */}
                        {nominalAngle && (
                          <ReferenceLine
                            yAxisId="angle"
                            y={nominalAngle}
                            stroke={lightColor}
                            strokeDasharray="2 2"
                            strokeWidth={2}
                            label={{
                              value: `Nominal (${nominalAngle.toFixed(2)}°)`,
                              position: 'right',
                              fill: lightColor,
                              fontSize: 11
                            }}
                          />
                        )}
                        {/* RGB Lines on left axis */}
                        <Line yAxisId="rgb" type="monotone" dataKey="red" stroke="#dc2626" strokeWidth={2} dot={false} name="Red" />
                        <Line yAxisId="rgb" type="monotone" dataKey="green" stroke="#16a34a" strokeWidth={2} dot={false} name="Green" />
                        <Line yAxisId="rgb" type="monotone" dataKey="blue" stroke="#2563eb" strokeWidth={2} dot={false} name="Blue" />
                        <Line yAxisId="rgb" type="monotone" dataKey="intensity" stroke="#a855f7" strokeWidth={2} strokeDasharray="3 3" dot={false} name="Intensity" />
                        {/* Angle Lines on right axis */}
                        <Line yAxisId="angle" type="monotone" dataKey="angle" stroke={lightColor} strokeWidth={3} dot={false} name="Angle" />
                        <Line yAxisId="angle" type="monotone" dataKey="touchPointAngle" stroke="#8b5cf6" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Touch Pt Angle" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Chromaticity Chart */}
                  <div>
                    <h4 className="text-sm font-medium mb-3">Chromaticity (Normalized RGB) and Elevation Angle Over Time</h4>
                    <p className="text-xs text-gray-600 mb-2">
                      Red light: red chromaticity ≈ 50-70% | White light: all chromaticity ≈ 33% (balanced)
                    </p>
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={rgbData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="timestamp"
                          label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                        />
                        {/* Left Y-axis for Chromaticity */}
                        <YAxis
                          yAxisId="chroma"
                          label={{ value: 'Chromaticity (%)', angle: -90, position: 'insideLeft' }}
                          domain={['dataMin - 5', 'dataMax + 5']}
                        />
                        {/* Right Y-axis for Angle */}
                        <YAxis
                          yAxisId="angle"
                          orientation="right"
                          label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                          domain={['dataMin - 1', 'dataMax + 1']}
                        />
                        <Tooltip
                          formatter={(value: any, name: string) => {
                            if (value == null) return ['N/A', name];
                            if (name === 'Angle' || name === 'Touch Pt Angle') return [`${value.toFixed(2)}°`, name];
                            return [`${value.toFixed(1)}%`, name];
                          }}
                          labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                        />
                        <Legend />
                        {/* Transition Point Markers */}
                        {transitionPoints.map((timestamp, idx) => (
                          <ReferenceLine
                            key={`chroma-transition-${idx}`}
                            x={timestamp}
                            stroke="#9333ea"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            label={{
                              value: 'Transition',
                              position: 'top',
                              fill: '#9333ea',
                              fontSize: 12
                            }}
                          />
                        ))}
                        {/* Reference line at 33% (balanced white light) */}
                        <ReferenceLine
                          yAxisId="chroma"
                          y={33.33}
                          stroke="#94a3b8"
                          strokeDasharray="3 3"
                          label={{
                            value: 'White (33%)',
                            position: 'right',
                            fill: '#64748b',
                            fontSize: 11
                          }}
                        />
                        {/* Nominal angle reference line */}
                        {nominalAngle && (
                          <ReferenceLine
                            yAxisId="angle"
                            y={nominalAngle}
                            stroke={lightColor}
                            strokeDasharray="2 2"
                            strokeWidth={2}
                            label={{
                              value: `Nominal (${nominalAngle.toFixed(2)}°)`,
                              position: 'right',
                              fill: lightColor,
                              fontSize: 11
                            }}
                          />
                        )}
                        {/* Chromaticity Lines on left axis */}
                        <Line yAxisId="chroma" type="monotone" dataKey="redChromaticity" stroke="#dc2626" strokeWidth={2} dot={false} name="Red Chroma" />
                        <Line yAxisId="chroma" type="monotone" dataKey="greenChromaticity" stroke="#16a34a" strokeWidth={2} dot={false} name="Green Chroma" />
                        <Line yAxisId="chroma" type="monotone" dataKey="blueChromaticity" stroke="#2563eb" strokeWidth={2} dot={false} name="Blue Chroma" />
                        {/* Angle Lines on right axis */}
                        <Line yAxisId="angle" type="monotone" dataKey="angle" stroke={lightColor} strokeWidth={3} dot={false} name="Angle" />
                        <Line yAxisId="angle" type="monotone" dataKey="touchPointAngle" stroke="#8b5cf6" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Touch Pt Angle" />
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
                    {point.nominal_angle !== undefined && point.nominal_angle !== null && (
                      <p className="font-medium text-blue-600">Nominal Angle: {point.nominal_angle.toFixed(2)}°</p>
                    )}
                    {point.tolerance !== undefined && point.tolerance !== null && (
                      <p className="font-medium text-orange-600">Tolerance: ±{point.tolerance.toFixed(2)}°</p>
                    )}
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