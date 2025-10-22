import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Loader2, Download, Map, BarChart3, Lightbulb, Video } from 'lucide-react';
import api from '../services/api';
import Airport3DVisualization from './Airport3DVisualization';

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
    glide_path_angles?: {
      average_all_lights: number[];
      average_middle_lights: number[];
      transition_based: number[];
      num_lights: number;
    };
  };
  papi_data: {
    [key: string]: {
      timestamps: number[];
      statuses: string[];
      angles: number[];
      horizontal_angles: number[];
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
  runway: RunwayData | null;
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
  const [activeTab, setActiveTab] = useState<'overview' | 'charts' | 'horizontal' | 'positions' | 'videos'>('overview');

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
        (data.papi_data.PAPI_A?.angles[index] ?? 0).toFixed(3),
        data.papi_data.PAPI_B?.statuses[index] || 'unknown',
        (data.papi_data.PAPI_B?.angles[index] ?? 0).toFixed(3),
        data.papi_data.PAPI_C?.statuses[index] || 'unknown',
        (data.papi_data.PAPI_C?.angles[index] ?? 0).toFixed(3),
        data.papi_data.PAPI_D?.statuses[index] || 'unknown',
        (data.papi_data.PAPI_D?.angles[index] ?? 0).toFixed(3),
        (Number(pos.latitude ?? 0)).toFixed(8),
        (Number(pos.longitude ?? 0)).toFixed(8),
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
      // if (debug) console.log('[Calc Debug] Missing dronePos or touchPoint');
      return 0;
    }

    // Check for valid coordinates
    if (!dronePos.latitude || !dronePos.longitude || !dronePos.elevation) {
      // if (debug) console.log('[Calc Debug] Invalid drone position data:', dronePos);
      return 0;
    }

    if (!touchPoint.latitude || !touchPoint.longitude) {
      // if (debug) console.log('[Calc Debug] Invalid touch point coordinates:', touchPoint);
      return 0;
    }

    // Use ground elevation if touch point elevation is null
    const touchPointElevation = touchPoint.elevation ?? groundElevation;

    if (debug) {
      // console.log('[Calc Debug] Touch point elevation:', touchPoint.elevation, 'Using:', touchPointElevation);
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

    return angleDegrees;
  };

  const formatRGBChartData = (lightName: string) => {
    if (!data || !data.papi_data[lightName]) return [];

    const lightData = data.papi_data[lightName];

    // Find touch point by searching for key that contains 'TOUCH_POINT'
    let touchPoint: {
      latitude: number;
      longitude: number;
      elevation: number;
      point_type: string;
      nominal_angle?: number;
      tolerance?: number;
    } | null = null;
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

      if (lightName === 'PAPI_A') {
        // console.log('[Ground Elevation Debug] PAPI elevations extracted:', papiElevations);
      }

      if (papiElevations.length > 0) {
        groundElevation = papiElevations.reduce((sum, elev) => sum + elev, 0) / papiElevations.length;
      }
    }

    // Debug: Check available reference points
    if (lightName === 'PAPI_A') {
      // console.log('[Touch Point Debug] Available reference points:', Object.keys(data.reference_points || {}));
      // console.log('[Touch Point Debug] Selected touch point:', touchPoint);
      // console.log('[Touch Point Debug] Calculated ground elevation:', groundElevation);
      if (data.drone_positions && data.drone_positions[0]) {
        // console.log('[Touch Point Debug] First drone position:', data.drone_positions[0]);
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
          // console.log('[Touch Point Debug] First calculation result:', touchPointAngle);
        }
      } else {
        if (lightName === 'PAPI_A' && index === 0) {
          // console.log('[Touch Point Debug] Missing data - touchPoint:', !!touchPoint, 'dronePos:', !!dronePos);
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

    // New algorithm: compute 2*R - G - B for each frame
    const colorMetrics: number[] = [];

    for (let i = 0; i < lightData.rgb_values.length; i++) {
      const rgb = lightData.rgb_values[i] || [0, 0, 0];
      const [r, g, b] = Array.isArray(rgb) ? rgb : [0, 0, 0];

      // Calculate the color transition metric: 2*R - G - B
      const metric = 2 * r - g - b;
      colorMetrics.push(metric);
    }

    // Find minimum and maximum values
    const minMetric = Math.min(...colorMetrics);
    const maxMetric = Math.max(...colorMetrics);

    // Calculate 50% threshold value
    const threshold = minMetric + (maxMetric - minMetric) * 0.5;

    // console.log(`[${lightName}] Color metric range: [${minMetric.toFixed(2)}, ${maxMetric.toFixed(2)}]`);
    // console.log(`[${lightName}] Transition threshold (50%): ${threshold.toFixed(2)}`);

    // Find all transition points where the metric crosses the threshold
    for (let i = 1; i < colorMetrics.length; i++) {
      const prevMetric = colorMetrics[i - 1];
      const currMetric = colorMetrics[i];

      // Check if the metric crossed the threshold (in either direction)
      if ((prevMetric < threshold && currMetric >= threshold) ||
          (prevMetric > threshold && currMetric <= threshold)) {
        transitionPoints.push(lightData.timestamps[i]);
      }
    }

    // console.log(`[${lightName}] Raw transitions detected: ${transitionPoints.length}`);

    // Group nearby transitions (within 1.5 seconds) and keep only the first one
    const groupedTransitions: number[] = [];
    const groupWindow = 1.5; // seconds

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
    // console.log(`[${lightName}] Detected ${groupedTransitions.length} final transitions:`, groupedTransitions);

    return groupedTransitions.sort((a, b) => a - b);
  };

  const findColorTransitionWidths = (lightName: string): number[] => {
    if (!data || !data.papi_data[lightName]) return [];

    const lightData = data.papi_data[lightName];

    // Get transition points first (timestamps where transitions occur)
    const transitionPoints = findColorTransitionPoints(lightName);
    if (transitionPoints.length === 0) return [];

    // Compute color metrics for each frame (same as in findColorTransitionPoints)
    const colorMetrics: number[] = [];
    for (let i = 0; i < lightData.rgb_values.length; i++) {
      const rgb = lightData.rgb_values[i] || [0, 0, 0];
      const [r, g, b] = Array.isArray(rgb) ? rgb : [0, 0, 0];
      const metric = 2 * r - g - b;
      colorMetrics.push(metric);
    }

    // Find minimum and maximum values
    const minMetric = Math.min(...colorMetrics);
    const maxMetric = Math.max(...colorMetrics);
    const range = maxMetric - minMetric;

    // Define transition zone thresholds (20% to 80% of the range)
    const lowerThreshold = minMetric + range * 0.2;
    const upperThreshold = minMetric + range * 0.8;

    // For each transition point, find the corresponding transition width
    const transitionWidths: number[] = [];
    const searchWindow = 2.0; // seconds - window to search for transition zone around each transition point

    for (const transitionTimestamp of transitionPoints) {
      // Find the frame index closest to this transition point
      let transitionIdx = 0;
      let minTimeDiff = Infinity;
      for (let i = 0; i < lightData.timestamps.length; i++) {
        const timeDiff = Math.abs(lightData.timestamps[i] - transitionTimestamp);
        if (timeDiff < minTimeDiff) {
          minTimeDiff = timeDiff;
          transitionIdx = i;
        }
      }

      // Find the extent of the transition zone around this point
      let startIdx = transitionIdx;
      let endIdx = transitionIdx;

      // Search backwards for the start of the transition zone
      for (let i = transitionIdx; i >= 0; i--) {
        const timeDiff = Math.abs(lightData.timestamps[i] - transitionTimestamp);
        if (timeDiff > searchWindow) break; // Too far from transition point

        const metric = colorMetrics[i];
        if (metric > lowerThreshold && metric < upperThreshold) {
          startIdx = i;
        } else if (i < transitionIdx) {
          // We've exited the transition zone going backwards
          break;
        }
      }

      // Search forwards for the end of the transition zone
      for (let i = transitionIdx; i < colorMetrics.length; i++) {
        const timeDiff = Math.abs(lightData.timestamps[i] - transitionTimestamp);
        if (timeDiff > searchWindow) break; // Too far from transition point

        const metric = colorMetrics[i];
        if (metric > lowerThreshold && metric < upperThreshold) {
          endIdx = i;
        } else if (i > transitionIdx) {
          // We've exited the transition zone going forwards
          break;
        }
      }

      // Calculate the maximum width within this transition zone
      let maxWidth = 0;
      const angles: number[] = [];
      for (let i = startIdx; i <= endIdx; i++) {
        const angle = lightData.angles[i];
        if (angle !== undefined && angle !== null) {
          angles.push(angle);
        }
      }

      if (angles.length > 0) {
        const minAngle = Math.min(...angles);
        const maxAngle = Math.max(...angles);
        maxWidth = maxAngle - minAngle;
      }

      transitionWidths.push(maxWidth);
    }

    return transitionWidths;
  };

  const formatComparisonChartData = () => {
    if (!data) return [];

    // Get the longest timestamp array to use as base
    const allLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'];
    const baseLight = allLights.find(light => data.papi_data[light]?.timestamps?.length > 0);
    if (!baseLight) return [];

    const baseTimestamps = data.papi_data[baseLight].timestamps;

    // Find touch point for angle calculation
    let touchPoint: {
      latitude: number;
      longitude: number;
      elevation: number;
      point_type: string;
      nominal_angle?: number;
      tolerance?: number;
    } | null = null;
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

      // Add glide path angles if available (including touch point angle calculated in backend)
      if (data.summary.glide_path_angles) {
        dataPoint['gp_avg_all'] = data.summary.glide_path_angles.average_all_lights[index] ?? 0;
        dataPoint['gp_avg_middle'] = data.summary.glide_path_angles.average_middle_lights[index] ?? 0;
        dataPoint['touchPoint_angle'] = data.summary.glide_path_angles.to_touch_point?.[index] ?? 0;
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
              PAPI Vertical Analysis
            </button>
            <button
              onClick={() => setActiveTab('horizontal')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'horizontal'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <BarChart3 className="w-4 h-4 inline mr-2" />
              PAPI Horizontal Analysis
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

          {/* Glide Path Angles Summary */}
          {data.summary.glide_path_angles && (
            <Card>
              <CardHeader>
                <CardTitle>Glide Path Angle (Runway)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="text-sm">
                    <p className="text-gray-600 mb-4">
                      Calculated from {data.summary.glide_path_angles.num_lights} PAPI lights' vertical angles
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* Algorithm 1: Average All Lights */}
                      <div className="border-2 rounded-lg p-6 bg-blue-50 border-blue-200">
                        <h4 className="font-semibold text-blue-900 mb-1">GP Angle - All Lights</h4>
                        <p className="text-xs text-gray-600 mb-4">
                          Average of all {data.summary.glide_path_angles.num_lights} PAPI lights
                        </p>
                        {data.summary.glide_path_angles.average_all_lights.length > 0 && (
                          <div className="text-center space-y-2">
                            <div>
                              <div className="text-xs text-gray-600 mb-1">GP to PAPI Lights</div>
                              <div className="text-3xl font-bold text-blue-900 font-mono">
                                {(data.summary.glide_path_angles.average_all_lights.reduce((a, b) => a + b, 0) /
                                  data.summary.glide_path_angles.average_all_lights.length).toFixed(3)}°
                              </div>
                            </div>
                            {data.summary.glide_path_angles.touch_point_at_avg_all !== undefined && data.summary.glide_path_angles.touch_point_at_avg_all !== 0 && (
                              <div className="pt-2 border-t border-blue-300">
                                <div className="text-xs text-gray-600 mb-1">GP to Touch Point</div>
                                <div className="text-2xl font-bold text-indigo-700 font-mono">
                                  {data.summary.glide_path_angles.touch_point_at_avg_all.toFixed(3)}°
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Algorithm 2: Average Middle Lights */}
                      <div className="border-2 rounded-lg p-6 bg-green-50 border-green-200">
                        <h4 className="font-semibold text-green-900 mb-1">GP Angle - Middle Lights</h4>
                        <p className="text-xs text-gray-600 mb-4">
                          {data.summary.glide_path_angles.num_lights === 4 && "Average of PAPI_B and PAPI_C"}
                          {data.summary.glide_path_angles.num_lights === 2 && "Average of PAPI_A and PAPI_B"}
                          {data.summary.glide_path_angles.num_lights >= 8 && "Average of PAPI_B, PAPI_C, PAPI_F, PAPI_G"}
                        </p>
                        {data.summary.glide_path_angles.average_middle_lights.length > 0 && (
                          <div className="text-center space-y-2">
                            <div>
                              <div className="text-xs text-gray-600 mb-1">GP to PAPI Lights</div>
                              <div className="text-3xl font-bold text-green-900 font-mono">
                                {(data.summary.glide_path_angles.average_middle_lights.reduce((a, b) => a + b, 0) /
                                  data.summary.glide_path_angles.average_middle_lights.length).toFixed(3)}°
                              </div>
                            </div>
                            {data.summary.glide_path_angles.touch_point_at_avg_middle !== undefined && data.summary.glide_path_angles.touch_point_at_avg_middle !== 0 && (
                              <div className="pt-2 border-t border-green-300">
                                <div className="text-xs text-gray-600 mb-1">GP to Touch Point</div>
                                <div className="text-2xl font-bold text-indigo-700 font-mono">
                                  {data.summary.glide_path_angles.touch_point_at_avg_middle.toFixed(3)}°
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Algorithm 3: Transition-Based */}
                      <div className="border-2 rounded-lg p-6 bg-purple-50 border-purple-200">
                        <h4 className="font-semibold text-purple-900 mb-1">GP Angle - Transition</h4>
                        <p className="text-xs text-gray-600 mb-4">
                          {data.summary.glide_path_angles.num_lights === 2 && "When PAPI_A white & PAPI_B red"}
                          {data.summary.glide_path_angles.num_lights === 4 && "When PAPI_B white & PAPI_C red"}
                          {data.summary.glide_path_angles.num_lights >= 8 && "When B/F white & C/G red"}
                        </p>
                        {data.summary.glide_path_angles.transition_based && data.summary.glide_path_angles.transition_based.length > 0 && (() => {
                          const validAngles = data.summary.glide_path_angles.transition_based.filter(a => a !== 0);
                          return validAngles.length > 0 ? (
                            <div className="text-center space-y-2">
                              <div>
                                <div className="text-xs text-gray-600 mb-1">GP to PAPI Lights</div>
                                <div className="text-3xl font-bold text-purple-900 font-mono">
                                  {(validAngles.reduce((a, b) => a + b, 0) / validAngles.length).toFixed(3)}°
                                </div>
                              </div>
                              {data.summary.glide_path_angles.touch_point_at_transition !== undefined && data.summary.glide_path_angles.touch_point_at_transition !== 0 && (
                                <div className="pt-2 border-t border-purple-300">
                                  <div className="text-xs text-gray-600 mb-1">GP to Touch Point</div>
                                  <div className="text-2xl font-bold text-indigo-700 font-mono">
                                    {data.summary.glide_path_angles.touch_point_at_transition.toFixed(3)}°
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-center text-gray-500 text-sm">No transitions detected</div>
                          );
                        })()}
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
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
                        if (name.includes('Angle') || name === 'Touch Pt Angle') return [`${value.toFixed(3)}°`, name];
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
                        if (name.includes('Angle') || name === 'Touch Pt Angle') return [`${value.toFixed(3)}°`, name];
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

          {/* PAPI Vertical Analysis Charts - One for each light */}
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

            // Get angle at each transition point
            const transitionInfo = transitionPoints.map(timestamp => {
              const dataPoint = rgbData.find(d => Math.abs(d.timestamp - timestamp) < 0.01);
              return {
                timestamp,
                angle: dataPoint?.angle ?? 0
              };
            });

            // Check if transitions are within tolerance
            const tolerance = lightPoint?.[1]?.tolerance ?? 0.25; // Default 0.25° if not specified
            const allTransitionsValid = transitionInfo.every(t => {
              if (!nominalAngle) return true; // Can't validate without nominal angle
              const deviation = Math.abs(t.angle - nominalAngle);
              return deviation <= tolerance;
            });

            const hasTransitions = transitionInfo.length > 0;
            const canValidate = nominalAngle !== undefined && nominalAngle !== null;

            return (
              <Card key={lightName}>
                <CardHeader>
                  <CardTitle>{lightName} Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Combined RGB Values and Elevation Angles Chart */}
                  <div className="mb-6">
                    <h4 className="text-sm font-medium mb-3">RGB Values and Elevation Angles Over Time</h4>
                    {hasTransitions ? (
                      <div className="mb-2">
                        <p className="text-xs text-gray-600 inline">
                          Color transition points: {transitionInfo.map(t => `${t.timestamp.toFixed(2)}s @ ${t.angle.toFixed(3)}°`).join(', ')}
                        </p>
                        {canValidate && (
                          <span className="ml-3">
                            {allTransitionsValid ? (
                              <span className="text-green-600 font-bold text-sm">✓ CORRECT</span>
                            ) : (
                              <span className="text-red-600 font-bold text-lg">✗ FAILED</span>
                            )}
                          </span>
                        )}
                      </div>
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
                            if (name === 'Angle' || name === 'Touch Pt Angle') return [`${value.toFixed(3)}°`, name];
                            if (['red', 'green', 'blue'].includes(name)) return [`${Math.round(value)}`, name.toUpperCase()];
                            if (name === 'intensity') return [`${Math.round(value)}`, 'Intensity'];
                            return [`${value.toFixed(2)}`, name];
                          }}
                          labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                        />
                        <Legend />
                        {/* Transition Point Markers - horizontal lines at the angle */}
                        {transitionInfo.map((transition, idx) => {
                          let label = `Transition @ ${transition.timestamp.toFixed(2)}s`;
                          if (nominalAngle !== undefined && nominalAngle !== null) {
                            const deviation = transition.angle - nominalAngle;
                            const sign = deviation >= 0 ? '+' : '';
                            label += ` (Δ ${sign}${deviation.toFixed(3)}°)`;
                          }
                          return (
                            <ReferenceLine
                              key={`transition-${idx}`}
                              yAxisId="angle"
                              y={transition.angle}
                              stroke="#9333ea"
                              strokeWidth={2}
                              strokeDasharray="5 5"
                              label={{
                                value: label,
                                position: 'right',
                                fill: '#9333ea',
                                fontSize: 10
                              }}
                            />
                          );
                        })}
                        {/* Nominal angle reference line */}
                        {nominalAngle && (
                          <ReferenceLine
                            yAxisId="angle"
                            y={nominalAngle}
                            stroke={lightColor}
                            strokeDasharray="2 2"
                            strokeWidth={2}
                            label={{
                              value: `Nominal (${nominalAngle.toFixed(3)}°)`,
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
                    {hasTransitions ? (
                      <div className="mb-2">
                        <p className="text-xs text-gray-600 inline">
                          Red light: red chromaticity ≈ 50-70% | White light: all chromaticity ≈ 33% (balanced)
                        </p>
                        {canValidate && (
                          <span className="ml-3">
                            {allTransitionsValid ? (
                              <span className="text-green-600 font-bold text-sm">✓ CORRECT</span>
                            ) : (
                              <span className="text-red-600 font-bold text-lg">✗ FAILED</span>
                            )}
                          </span>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-600 mb-2">
                        Red light: red chromaticity ≈ 50-70% | White light: all chromaticity ≈ 33% (balanced)
                      </p>
                    )}
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
                            if (name === 'Angle' || name === 'Touch Pt Angle') return [`${value.toFixed(3)}°`, name];
                            return [`${value.toFixed(1)}%`, name];
                          }}
                          labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                        />
                        <Legend />
                        {/* Transition Point Markers - horizontal lines at the angle */}
                        {transitionInfo.map((transition, idx) => {
                          let label = `Transition @ ${transition.timestamp.toFixed(2)}s`;
                          if (nominalAngle !== undefined && nominalAngle !== null) {
                            const deviation = transition.angle - nominalAngle;
                            const sign = deviation >= 0 ? '+' : '';
                            label += ` (Δ ${sign}${deviation.toFixed(3)}°)`;
                          }
                          return (
                            <ReferenceLine
                              key={`chroma-transition-${idx}`}
                              yAxisId="angle"
                              y={transition.angle}
                              stroke="#9333ea"
                              strokeWidth={2}
                              strokeDasharray="5 5"
                              label={{
                                value: label,
                                position: 'right',
                                fill: '#9333ea',
                                fontSize: 10
                              }}
                            />
                          );
                        })}
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
                              value: `Nominal (${nominalAngle.toFixed(3)}°)`,
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

      {activeTab === 'horizontal' && (
        <div className="space-y-6">
          {/* Maximum Luminosity Analysis Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Light Direction Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600 mb-4">
                Horizontal angle where each PAPI light achieves maximum luminosity (indicates the direction each light is aimed):
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].map(lightName => {
                  const lightData = data.papi_data[lightName];
                  if (!lightData || !lightData.intensities || !lightData.horizontal_angles) {
                    return null;
                  }

                  // Find index of maximum intensity
                  let maxIntensity = 0;
                  let maxIntensityIndex = 0;
                  lightData.intensities.forEach((intensity: number, idx: number) => {
                    if (intensity > maxIntensity) {
                      maxIntensity = intensity;
                      maxIntensityIndex = idx;
                    }
                  });

                  const maxLuminosityAngle = lightData.horizontal_angles[maxIntensityIndex];

                  return (
                    <div key={lightName} className="p-3 bg-gray-50 rounded-lg">
                      <div className="text-xs text-gray-500 mb-1">{lightName.replace('_', ' ')}</div>
                      <div className="text-lg font-bold text-blue-600">
                        {maxLuminosityAngle != null ? `${maxLuminosityAngle.toFixed(3)}°` : 'N/A'}
                      </div>
                      <div className="text-xs text-gray-500">
                        Luminosity: {Math.round(maxIntensity)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Horizontal Analysis - All PAPI Lights */}
          <Card>
            <CardHeader>
              <CardTitle>Horizontal Angle Analysis - All PAPI Lights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Chromaticity vs Horizontal Angle */}
              <div>
                <h4 className="text-sm font-medium mb-3">Red Chromaticity vs Horizontal Angle</h4>
                <p className="text-xs text-gray-600 mb-2">
                  Color quality across horizontal deviation from runway centerline. Red light ≈ 50-70%, White light ≈ 33%
                </p>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={(() => {
                    const chartData: any[] = [];
                    const lightsArray = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'];

                    // Get max length
                    const maxLength = Math.max(...lightsArray.map(light => data.papi_data[light]?.timestamps.length || 0));

                    for (let i = 0; i < maxLength; i++) {
                      const point: any = { timestamp: data.papi_data['PAPI_A']?.timestamps[i] || i };

                      lightsArray.forEach(light => {
                        const lightData = data.papi_data[light];
                        if (lightData && lightData.horizontal_angles && lightData.horizontal_angles[i] != null) {
                          const rgb = lightData.rgb_values[i];
                          if (rgb) {
                            const [r, g, b] = rgb;
                            const total = r + g + b;
                            const redChroma = total > 0 ? (r / total) * 100 : 0;
                            point[`${light}_chroma`] = redChroma;
                            point[`${light}_horizontal_angle`] = lightData.horizontal_angles[i];
                          }
                        }
                      });

                      chartData.push(point);
                    }

                    return chartData;
                  })()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis
                      yAxisId="chroma"
                      label={{ value: 'Red Chromaticity (%)', angle: -90, position: 'insideLeft' }}
                      domain={['dataMin - 5', 'dataMax + 5']}
                    />
                    <YAxis
                      yAxisId="horizontal"
                      orientation="right"
                      label={{ value: 'Horizontal Angle (°)', angle: 90, position: 'insideRight' }}
                      domain={['dataMin - 5', 'dataMax + 5']}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => {
                        if (value == null) return ['N/A', name];
                        if (name.includes('horizontal_angle')) return [`${value.toFixed(3)}°`, name];
                        return [`${value.toFixed(1)}%`, name];
                      }}
                      labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                    />
                    <Legend />
                    <ReferenceLine
                      yAxisId="chroma"
                      y={33.33}
                      stroke="#94a3b8"
                      strokeDasharray="3 3"
                      label={{ value: 'White (33%)', position: 'right', fill: '#64748b', fontSize: 12 }}
                    />
                    <ReferenceLine
                      yAxisId="horizontal"
                      x={0}
                      stroke="#94a3b8"
                      strokeDasharray="3 3"
                      label={{ value: 'Centerline', position: 'top', fill: '#64748b', fontSize: 12 }}
                    />

                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_A_chroma" stroke="#fbbf24" name="PAPI A Chroma" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_A_horizontal_angle" stroke="#f59e0b" name="PAPI A H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />

                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_B_chroma" stroke="#f97316" name="PAPI B Chroma" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_B_horizontal_angle" stroke="#ea580c" name="PAPI B H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />

                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_C_chroma" stroke="#ec4899" name="PAPI C Chroma" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_C_horizontal_angle" stroke="#db2777" name="PAPI C H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />

                    <Line yAxisId="chroma" type="monotone" dataKey="PAPI_D_chroma" stroke="#22c55e" name="PAPI D Chroma" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_D_horizontal_angle" stroke="#16a34a" name="PAPI D H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Luminosity vs Horizontal Angle */}
              <div>
                <h4 className="text-sm font-medium mb-3">Luminosity (Intensity) vs Horizontal Angle</h4>
                <p className="text-xs text-gray-600 mb-2">
                  Light intensity across horizontal deviation from runway centerline
                </p>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={(() => {
                    const chartData: any[] = [];
                    const lightsArray = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'];

                    const maxLength = Math.max(...lightsArray.map(light => data.papi_data[light]?.timestamps.length || 0));

                    for (let i = 0; i < maxLength; i++) {
                      const point: any = { timestamp: data.papi_data['PAPI_A']?.timestamps[i] || i };

                      lightsArray.forEach(light => {
                        const lightData = data.papi_data[light];
                        if (lightData && lightData.horizontal_angles && lightData.horizontal_angles[i] != null) {
                          point[`${light}_intensity`] = lightData.intensities[i];
                          point[`${light}_horizontal_angle`] = lightData.horizontal_angles[i];
                        }
                      });

                      chartData.push(point);
                    }

                    return chartData;
                  })()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis
                      yAxisId="intensity"
                      label={{ value: 'Luminosity (0-255)', angle: -90, position: 'insideLeft' }}
                      domain={[0, 255]}
                    />
                    <YAxis
                      yAxisId="horizontal"
                      orientation="right"
                      label={{ value: 'Horizontal Angle (°)', angle: 90, position: 'insideRight' }}
                      domain={['dataMin - 5', 'dataMax + 5']}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => {
                        if (value == null) return ['N/A', name];
                        if (name.includes('horizontal_angle')) return [`${value.toFixed(3)}°`, name];
                        if (name.includes('intensity')) return [`${value.toFixed(0)}`, name];
                        return [value, name];
                      }}
                      labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                    />
                    <Legend />
                    <ReferenceLine
                      yAxisId="horizontal"
                      x={0}
                      stroke="#94a3b8"
                      strokeDasharray="3 3"
                      label={{ value: 'Centerline', position: 'top', fill: '#64748b', fontSize: 12 }}
                    />

                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_A_intensity" stroke="#fbbf24" name="PAPI A Intensity" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_A_horizontal_angle" stroke="#f59e0b" name="PAPI A H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />

                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_B_intensity" stroke="#f97316" name="PAPI B Intensity" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_B_horizontal_angle" stroke="#ea580c" name="PAPI B H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />

                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_C_intensity" stroke="#ec4899" name="PAPI C Intensity" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_C_horizontal_angle" stroke="#db2777" name="PAPI C H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />

                    <Line yAxisId="intensity" type="monotone" dataKey="PAPI_D_intensity" stroke="#22c55e" name="PAPI D Intensity" strokeWidth={2} dot={false} />
                    <Line yAxisId="horizontal" type="monotone" dataKey="PAPI_D_horizontal_angle" stroke="#16a34a" name="PAPI D H-Angle" strokeWidth={1} strokeDasharray="5 5" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'positions' && (
        <div className="space-y-6">
          {/* 3D Airport Visualization */}
          <Card>
            <CardHeader>
              <CardTitle>Map Visualization</CardTitle>
              <p className="text-sm text-gray-600">
                Interactive OpenStreetMap view showing PAPI lights, touch point, and drone flight path
              </p>
            </CardHeader>
            <CardContent>
              <Airport3DVisualization
                dronePositions={data.drone_positions}
                referencePoints={data.reference_points}
                runway={data.runway}
              />

              {/* Legend */}
              <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-cyan-400 rounded-full"></div>
                  <span>Drone Flight Path</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-0.5 bg-green-500" style={{borderTop: '2px dashed #22c55e'}}></div>
                  <span>Direct Line (Start-End)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full border-2 border-white"></div>
                  <span>Drone Start</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-red-500 rounded-full border-2 border-white"></div>
                  <span>Drone End</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-purple-500 rounded-full border-2 border-white"></div>
                  <span>Touch Point</span>
                </div>
              </div>

              <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-red-500 rounded-full border-2 border-white"></div>
                  <span>PAPI A</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-orange-500 rounded-full border-2 border-white"></div>
                  <span>PAPI B</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-yellow-500 rounded-full border-2 border-white"></div>
                  <span>PAPI C</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full border-2 border-white"></div>
                  <span>PAPI D</span>
                </div>
              </div>

              <div className="mt-4 text-xs text-gray-500">
                💡 Click on markers for details. Scroll to zoom. Drag to pan. Use layer control (top right) to switch between Street and Satellite view.
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
                    // console.error('Enhanced video error:', {
                    //   error: video.error,
                    //   code: video.error?.code,
                    //   message: video.error?.message,
                    //   networkState: video.networkState,
                    //   readyState: video.readyState,
                    //   src: data.video_urls?.enhanced_main
                    // });
                  }}
                  // onLoadedMetadata={() => console.log('Video loaded:', data.video_urls?.enhanced_main)}
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
                          // console.error('Video error:', light, {
                          //   error: video.error,
                          //   networkState: video.networkState,
                          //   readyState: video.readyState,
                          //   src: data.video_urls?.[light as keyof typeof data.video_urls]
                          // });
                        }}
                        // onLoadedMetadata={() => console.log('Video loaded:', light)}
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
        <>
          <Card>
            <CardHeader>
              <CardTitle>Reference Points</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b-2 border-gray-300">
                      <th className="text-left p-2 font-semibold">Type</th>
                      <th className="text-right p-2 font-semibold">Coordinates</th>
                      <th className="text-right p-2 font-semibold">Elevation</th>
                      <th className="text-right p-2 font-semibold">Nominal Angle</th>
                      <th className="text-right p-2 font-semibold">Tolerance</th>
                      <th className="text-right p-2 font-semibold">Transition Angle</th>
                      <th className="text-right p-2 font-semibold">Transition Width</th>
                      <th className="text-right p-2 font-semibold">Correction</th>
                      <th className="text-right p-2 font-semibold">Max Lum. H-Angle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.reference_points)
                      .sort(([, a], [, b]) => {
                        // Sort by point_type alphabetically
                        const typeA = a.point_type ?? '';
                        const typeB = b.point_type ?? '';
                        return typeA.localeCompare(typeB);
                      })
                      .map(([pointId, point]) => {
                        // Check if this is a PAPI light
                        const isPAPILight = pointId.includes('PAPI_A') || pointId.includes('PAPI_B') ||
                                           pointId.includes('PAPI_C') || pointId.includes('PAPI_D') ||
                                           pointId.includes('PAPI_E') || pointId.includes('PAPI_F') ||
                                           pointId.includes('PAPI_G') || pointId.includes('PAPI_H');

                        let lightName = '';
                        let transitionAngles: number[] = [];
                        let transitionWidths: number[] = [];
                        let maxLuminosityAngle: number | null = null;
                        let maxIntensity = 0;

                        if (isPAPILight) {
                          // Extract light name (e.g., "PAPI_A")
                          if (pointId.includes('PAPI_A')) lightName = 'PAPI_A';
                          else if (pointId.includes('PAPI_B')) lightName = 'PAPI_B';
                          else if (pointId.includes('PAPI_C')) lightName = 'PAPI_C';
                          else if (pointId.includes('PAPI_D')) lightName = 'PAPI_D';
                          else if (pointId.includes('PAPI_E')) lightName = 'PAPI_E';
                          else if (pointId.includes('PAPI_F')) lightName = 'PAPI_F';
                          else if (pointId.includes('PAPI_G')) lightName = 'PAPI_G';
                          else if (pointId.includes('PAPI_H')) lightName = 'PAPI_H';

                          // Calculate transition angles for this light
                          const transitionPoints = findColorTransitionPoints(lightName);
                          const rgbData = formatRGBChartData(lightName);
                          transitionAngles = transitionPoints.map(timestamp => {
                            const dataPoint = rgbData.find(d => Math.abs(d.timestamp - timestamp) < 0.01);
                            return dataPoint?.angle ?? 0;
                          });

                          // Calculate transition widths for this light
                          transitionWidths = findColorTransitionWidths(lightName);

                          // Calculate max luminosity horizontal angle
                          const lightData = data.papi_data[lightName as 'PAPI_A' | 'PAPI_B' | 'PAPI_C' | 'PAPI_D'];
                          if (lightData && lightData.intensities && lightData.horizontal_angles) {
                            let maxIntensityIndex = 0;
                            lightData.intensities.forEach((intensity: number, idx: number) => {
                              if (intensity > maxIntensity) {
                                maxIntensity = intensity;
                                maxIntensityIndex = idx;
                              }
                            });
                            maxLuminosityAngle = lightData.horizontal_angles[maxIntensityIndex];
                          }
                        }

                        const transitionAngle = transitionAngles.length > 0 ? transitionAngles[0] : null;
                        const transitionWidth = transitionWidths.length > 0 ? transitionWidths[0] : null;

                        let correction: number | null = null;
                        let isWithinTolerance = false;
                        if (transitionAngle !== null && point.nominal_angle !== undefined && point.nominal_angle !== null) {
                          correction = point.nominal_angle - transitionAngle;
                          isWithinTolerance = Math.abs(transitionAngle - point.nominal_angle) <= (point.tolerance ?? 0.25);
                        }

                        return (
                          <tr key={pointId} className="border-b border-gray-200 hover:bg-gray-50">
                            <td className="p-2 capitalize font-medium">{point.point_type?.replace('_', ' ') ?? 'unknown'}</td>
                            <td className="p-2 text-right font-mono text-xs">
                              <div>{Number(point.latitude ?? 0).toFixed(8)}</div>
                              <div>{Number(point.longitude ?? 0).toFixed(8)}</div>
                            </td>
                            <td className="p-2 text-right">{(point.elevation ?? 0).toFixed(3)}m</td>
                            <td className="p-2 text-right text-blue-600 font-medium">
                              {point.nominal_angle !== undefined && point.nominal_angle !== null ? `${point.nominal_angle.toFixed(3)}°` : '-'}
                            </td>
                            <td className="p-2 text-right text-orange-600">
                              {point.tolerance !== undefined && point.tolerance !== null ? `±${point.tolerance.toFixed(3)}°` : '-'}
                            </td>
                            <td className="p-2 text-right text-purple-600 font-medium">
                              {transitionAngle !== null ? `${transitionAngle.toFixed(3)}°` : '-'}
                            </td>
                            <td className="p-2 text-right text-indigo-600 font-medium">
                              {transitionWidth !== null ? `${transitionWidth.toFixed(3)}°` : '-'}
                            </td>
                            <td className={`p-2 text-right font-bold ${correction !== null ? (isWithinTolerance ? 'text-green-600' : 'text-red-600') : ''}`}>
                              {correction !== null ? `${correction >= 0 ? '+' : ''}${correction.toFixed(3)}° ${isWithinTolerance ? '✓' : '✗'}` : '-'}
                            </td>
                            <td className="p-2 text-right text-teal-600">
                              {maxLuminosityAngle !== null ? `${maxLuminosityAngle.toFixed(3)}°` : '-'}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* PAPI Transition Angle Differences Table */}
          <Card>
            <CardHeader>
              <CardTitle>PAPI Light Transition Angle Differences</CardTitle>
            </CardHeader>
            <CardContent>
              {(() => {
                // Get transition angles for all PAPI lights
                const papiLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D', 'PAPI_E', 'PAPI_F', 'PAPI_G', 'PAPI_H'];
                const papiTransitionData: { [key: string]: number | null } = {};

                papiLights.forEach(lightName => {
                  // Check if this PAPI light exists in the data
                  const hasData = data.papi_data && data.papi_data[lightName];
                  if (!hasData) {
                    papiTransitionData[lightName] = null;
                    return;
                  }

                  const transitionPoints = findColorTransitionPoints(lightName);
                  const rgbData = formatRGBChartData(lightName);

                  if (transitionPoints.length > 0) {
                    const dataPoint = rgbData.find(d => Math.abs(d.timestamp - transitionPoints[0]) < 0.01);
                    papiTransitionData[lightName] = dataPoint?.angle ?? null;
                  } else {
                    papiTransitionData[lightName] = null;
                  }
                });

                // Calculate differences between consecutive pairs
                const pairs: Array<{ light1: string; light2: string; angle1: number; angle2: number; difference: number }> = [];
                const consecutivePairs = [
                  ['PAPI_A', 'PAPI_B'],
                  ['PAPI_B', 'PAPI_C'],
                  ['PAPI_C', 'PAPI_D'],
                  ['PAPI_D', 'PAPI_E'],
                  ['PAPI_E', 'PAPI_F'],
                  ['PAPI_F', 'PAPI_G'],
                  ['PAPI_G', 'PAPI_H']
                ];

                consecutivePairs.forEach(([light1, light2]) => {
                  const angle1 = papiTransitionData[light1];
                  const angle2 = papiTransitionData[light2];

                  if (angle1 !== null && angle2 !== null) {
                    pairs.push({
                      light1,
                      light2,
                      angle1,
                      angle2,
                      difference: angle2 - angle1
                    });
                  }
                });

                if (pairs.length === 0) {
                  return (
                    <p className="text-sm text-gray-500">No consecutive PAPI light pairs found with transition data.</p>
                  );
                }

                // Define tolerance for differences
                const nominalDifference = 0.33; // degrees
                const differenceTolerance = 0.1; // degrees
                const minAcceptable = nominalDifference - differenceTolerance; // 0.23°
                const maxAcceptable = nominalDifference + differenceTolerance; // 0.43°

                return (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            PAPI Pair
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            First Light Angle
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Second Light Angle
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Difference
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Tolerance
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {pairs.map((pair, idx) => {
                          const absDifference = Math.abs(pair.difference);
                          const isWithinTolerance = absDifference >= minAcceptable && absDifference <= maxAcceptable;

                          return (
                            <tr key={idx} className="hover:bg-gray-50">
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                                {pair.light1.replace('_', ' ')} → {pair.light2.replace('_', ' ')}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                                {pair.angle1.toFixed(3)}°
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                                {pair.angle2.toFixed(3)}°
                              </td>
                              <td className={`px-4 py-3 whitespace-nowrap text-sm font-bold ${
                                isWithinTolerance ? 'text-blue-600' :
                                Math.abs(pair.difference) < 0.1 ? 'text-green-600' :
                                Math.abs(pair.difference) < 0.5 ? 'text-orange-600' :
                                'text-red-600'
                              }`}>
                                {pair.difference >= 0 ? '+' : ''}{pair.difference.toFixed(3)}°
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                                0.33 ± 0.1°
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-bold">
                                {isWithinTolerance ? (
                                  <span className="text-green-600">✓ CORRECT</span>
                                ) : (
                                  <span className="text-red-600 text-base">✗ FAILED</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })()}
            </CardContent>
          </Card>

          {/* Red Chromaticity Comparison Table */}
          <Card>
            <CardHeader>
              <CardTitle>PAPI Light Red Chromaticity Comparison</CardTitle>
            </CardHeader>
            <CardContent>
              {(() => {
                // Get chromaticity data for all PAPI lights
                const papiLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D', 'PAPI_E', 'PAPI_F', 'PAPI_G', 'PAPI_H'];
                const chromaData: Array<{ light: string; min: number; max: number }> = [];

                papiLights.forEach(lightName => {
                  // Check if this PAPI light exists in the data
                  const hasData = data.papi_data && data.papi_data[lightName];
                  if (!hasData) return;

                  const rgbData = formatRGBChartData(lightName);
                  if (rgbData.length === 0) return;

                  const chromaticities = rgbData.map(d => d.redChromaticity);
                  const minChroma = Math.min(...chromaticities);
                  const maxChroma = Math.max(...chromaticities);

                  chromaData.push({ light: lightName, min: minChroma, max: maxChroma });
                });

                if (chromaData.length === 0) {
                  return <p className="text-sm text-gray-500">No PAPI light chromaticity data available.</p>;
                }

                // Calculate average min and max across all lights for comparison
                const allMins = chromaData.map(d => d.min);
                const allMaxs = chromaData.map(d => d.max);
                const avgMin = allMins.reduce((a, b) => a + b, 0) / allMins.length;
                const avgMax = allMaxs.reduce((a, b) => a + b, 0) / allMaxs.length;

                return (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            PAPI Light
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Min Red Chromaticity
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Min Status
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Max Red Chromaticity
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Max Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {chromaData.map((item) => {
                          // Check if min/max deviate by more than 10% from average
                          const minDeviationPercent = Math.abs((item.min - avgMin) / avgMin) * 100;
                          const maxDeviationPercent = Math.abs((item.max - avgMax) / avgMax) * 100;
                          const minFailed = minDeviationPercent > 10;
                          const maxFailed = maxDeviationPercent > 10;

                          return (
                            <tr key={item.light} className="hover:bg-gray-50">
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                                {item.light.replace('_', ' ')}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                                {item.min.toFixed(1)}%
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-bold">
                                {minFailed ? (
                                  <span className="text-red-600 text-base">✗ FAILED</span>
                                ) : (
                                  <span className="text-green-600">✓ CORRECT</span>
                                )}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                                {item.max.toFixed(1)}%
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-bold">
                                {maxFailed ? (
                                  <span className="text-red-600 text-base">✗ FAILED</span>
                                ) : (
                                  <span className="text-green-600">✓ CORRECT</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })()}
            </CardContent>
          </Card>

          {/* Luminosity (Intensity) Comparison Table */}
          <Card>
            <CardHeader>
              <CardTitle>PAPI Light Luminosity (Intensity) Comparison</CardTitle>
            </CardHeader>
            <CardContent>
              {(() => {
                // Get intensity data for all PAPI lights
                const papiLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D', 'PAPI_E', 'PAPI_F', 'PAPI_G', 'PAPI_H'];
                const intensityData: Array<{ light: string; min: number; max: number }> = [];

                papiLights.forEach(lightName => {
                  // Check if this PAPI light exists in the data
                  const hasData = data.papi_data && data.papi_data[lightName];
                  if (!hasData) return;

                  const rgbData = formatRGBChartData(lightName);
                  if (rgbData.length === 0) return;

                  const intensities = rgbData.map(d => d.intensity);
                  const minIntensity = Math.min(...intensities);
                  const maxIntensity = Math.max(...intensities);

                  intensityData.push({ light: lightName, min: minIntensity, max: maxIntensity });
                });

                if (intensityData.length === 0) {
                  return <p className="text-sm text-gray-500">No PAPI light intensity data available.</p>;
                }

                // Calculate average min and max across all lights for comparison
                const allMins = intensityData.map(d => d.min);
                const allMaxs = intensityData.map(d => d.max);
                const avgMin = allMins.reduce((a, b) => a + b, 0) / allMins.length;
                const avgMax = allMaxs.reduce((a, b) => a + b, 0) / allMaxs.length;

                return (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            PAPI Light
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Min Intensity
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Min Status
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Max Intensity
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Max Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {intensityData.map((item) => {
                          // Check if min/max deviate by more than 10% from average
                          const minDeviationPercent = Math.abs((item.min - avgMin) / avgMin) * 100;
                          const maxDeviationPercent = Math.abs((item.max - avgMax) / avgMax) * 100;
                          const minFailed = minDeviationPercent > 10;
                          const maxFailed = maxDeviationPercent > 10;

                          return (
                            <tr key={item.light} className="hover:bg-gray-50">
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                                {item.light.replace('_', ' ')}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                                {Math.round(item.min)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-bold">
                                {minFailed ? (
                                  <span className="text-red-600 text-base">✗ FAILED</span>
                                ) : (
                                  <span className="text-green-600">✓ CORRECT</span>
                                )}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                                {Math.round(item.max)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-bold">
                                {maxFailed ? (
                                  <span className="text-red-600 text-base">✗ FAILED</span>
                                ) : (
                                  <span className="text-green-600">✓ CORRECT</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};

export default MeasurementDataDisplay;