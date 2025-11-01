import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Button } from './ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Loader2, Download, Printer, RefreshCw, Edit2 } from 'lucide-react';
import api from '../services/api';
import Airport3DVisualization from './Airport3DVisualization';
import NotesEditorDialog from './NotesEditorDialog';
import RichTextEditor from './RichTextEditor';

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
      recording_date?: string;
      original_video_filename?: string;
      notes?: string;
    };
    glide_path_angles?: {
      average_all_lights: number[];
      average_middle_lights: number[];
      transition_based: number[];
      num_lights: number;
      to_touch_point?: number[];
      touch_point_at_avg_all?: number;
      touch_point_at_avg_middle?: number;
      touch_point_at_transition?: number;
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
      area_values: number[];
      chromaticity_red: number[];
      chromaticity_green: number[];
      chromaticity_blue: number[];
      transition_timestamps: number[];
      transition_widths: number[];
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
  chromacity_transition_angles?: {
    [key: string]: {
      transition_angle_min: number | null;
      transition_angle_max: number | null;
      transition_angle_middle: number | null;
      transition_frames_count: number;
      chromaRG_min: number | null;
      chromaRG_max: number | null;
      middle_chromaRG: number | null;
    };
  };
  touch_point_angles?: number[];
}

interface Props {
  sessionId: string;
}

const MeasurementDataDisplay: React.FC<Props> = ({ sessionId }) => {
  const [data, setData] = useState<MeasurementData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [reprocessing, setReprocessing] = useState(false);
  const [notes, setNotes] = useState<string>('');
  const [notesDialogOpen, setNotesDialogOpen] = useState(false);

  useEffect(() => {
    fetchMeasurementData();
  }, [sessionId]);

  const fetchMeasurementData = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/papi-measurements/session/${sessionId}/measurements-data`);
      setData(response.data);
      // Load notes from session_info (default to empty string if not present)
      const loadedNotes = response.data?.summary?.session_info?.notes || '';
      setNotes(loadedNotes);
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

  const handlePrint = () => {
    window.print();
  };

  const reprocessVideo = async () => {
    if (!window.confirm('Are you sure you want to reprocess this video? This will delete all existing measurements and regenerate them.')) {
      return;
    }

    try {
      setReprocessing(true);
      await api.post(`/papi-measurements/session/${sessionId}/reprocess`);
      // Navigate to main PAPI measurements page with session ID to show processing status
      window.location.href = `/papi-measurements?session=${sessionId}`;
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start reprocessing');
      setReprocessing(false);
    }
  };

  const handleNotesSaved = (savedNotes: string) => {
    setNotes(savedNotes);
    // Update the data to reflect the new notes
    if (data) {
      setData({
        ...data,
        summary: {
          ...data.summary,
          session_info: {
            ...data.summary.session_info,
            notes: savedNotes
          }
        }
      });
    }
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

      // Get chromaticity from API (already calculated on backend)
      const redChroma = lightData.chromaticity_red?.[index] ?? 0;
      const greenChroma = lightData.chromaticity_green?.[index] ?? 0;
      const blueChroma = lightData.chromaticity_blue?.[index] ?? 0;

      // Get intensity from API
      const intensity = lightData.intensities?.[index] ?? 0;

      // Get touch point angle from API
      const touchPointAngle = data.touch_point_angles?.[index] ?? 0;

      // Calculate chromaRG (Red - Green chromaticity difference)
      const chromaRG = redChroma - greenChroma;

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
        chromaRG: chromaRG,
        angle: lightData.angles[index] ?? 0,
        touchPointAngle: touchPointAngle
      };
    });
  };

  const findColorTransitionPoints = (lightName: string): number[] => {
    if (!data || !data.papi_data[lightName]) return [];

    // Get transition timestamps directly from API
    const lightData = data.papi_data[lightName];
    return lightData.transition_timestamps || [];
  };

  const findColorTransitionWidths = (lightName: string): number[] => {
    if (!data || !data.papi_data[lightName]) return [];

    // Get transition widths directly from API
    const lightData = data.papi_data[lightName];
    return lightData.transition_widths || [];
  };

  const formatComparisonChartData = () => {
    if (!data) return [];

    // Get the longest timestamp array to use as base
    const allLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'];
    const baseLight = allLights.find(light => data.papi_data[light]?.timestamps?.length > 0);
    if (!baseLight) return [];

    const baseTimestamps = data.papi_data[baseLight].timestamps;

    return baseTimestamps.map((timestamp, index) => {
      const dataPoint: any = {
        timestamp: timestamp ?? 0,
        time: (timestamp ?? 0).toFixed(2),
      };

      // Add data for each PAPI light
      allLights.forEach(lightName => {
        const lightData = data.papi_data[lightName];
        if (lightData && lightData.timestamps[index] !== undefined) {
          // Get all values from API (already calculated on backend)
          const redChromaticity = lightData.chromaticity_red?.[index] ?? 0;
          const greenChromaticity = lightData.chromaticity_green?.[index] ?? 0;
          const colorDiff = redChromaticity - greenChromaticity;
          const intensity = lightData.intensities?.[index] ?? 0;
          const angle = lightData.angles[index] ?? 0;
          const area = lightData.area_values?.[index] ?? 0;

          dataPoint[`${lightName}_redChroma`] = redChromaticity;
          dataPoint[`${lightName}_greenChroma`] = greenChromaticity;
          dataPoint[`${lightName}_colorDiff`] = colorDiff;
          dataPoint[`${lightName}_intensity`] = intensity;
          dataPoint[`${lightName}_angle`] = angle;
          dataPoint[`${lightName}_area`] = area;
        }
      });

      // Add glide path angles if available
      if (data.summary.glide_path_angles) {
        dataPoint['gp_avg_all'] = data.summary.glide_path_angles.average_all_lights[index] ?? 0;
        dataPoint['gp_avg_middle'] = data.summary.glide_path_angles.average_middle_lights[index] ?? 0;
      }

      // Get touch point angle from API
      dataPoint['touchPoint_angle'] = data.touch_point_angles?.[index] ?? 0;

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
    <>
      <style>{`
        @media print {
          /* Hide navigation elements and buttons during print */
          button:not(.no-print-hide),
          .no-print,
          video {
            display: none !important;
          }

          /* Hide sidebar completely */
          [data-sidebar="sidebar"],
          aside {
            display: none !important;
          }

          /* Optimize page layout for printing */
          body {
            margin: 0;
            padding: 0;
            font-size: 10pt;
          }

          /* Ensure main content takes full width */
          main,
          [data-sidebar="inset"],
          .flex.flex-1.flex-col {
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 0.5cm !important;
          }

          /* Page setup */
          @page {
            size: A4 landscape;
            margin: 1cm;
          }

          /* Ensure cards and content display properly */
          .space-y-4 > * {
            page-break-inside: avoid;
            margin-bottom: 0.5cm;
          }

          /* Critical: Force all chart containers to have fixed dimensions */
          div[style*="position: relative"] {
            position: relative !important;
            width: 100% !important;
            height: 400px !important;
          }

          /* Make charts visible and properly sized for print */
          .recharts-wrapper {
            page-break-inside: avoid !important;
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            width: 100% !important;
            height: 400px !important;
            min-height: 400px !important;
            max-width: 100% !important;
            position: relative !important;
          }

          .recharts-wrapper svg {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            width: 100% !important;
            height: 400px !important;
            min-height: 400px !important;
          }

          /* Ensure ResponsiveContainer fits on page */
          .recharts-responsive-container {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            width: 100% !important;
            height: 400px !important;
            min-height: 400px !important;
            max-width: 100% !important;
            position: relative !important;
          }

          .recharts-responsive-container > div {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            width: 100% !important;
            height: 400px !important;
          }

          .recharts-responsive-container svg {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            width: 100% !important;
            height: 400px !important;
          }

          /* Make chart surface visible */
          .recharts-surface {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
          }

          /* Make chart legends visible and properly sized */
          .recharts-legend-wrapper {
            position: relative !important;
            width: 100% !important;
            height: auto !important;
            margin-top: 0.3cm !important;
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
          }

          /* Ensure all chart components are visible */
          .recharts-cartesian-grid,
          .recharts-cartesian-grid-horizontal,
          .recharts-cartesian-grid-vertical,
          .recharts-xAxis,
          .recharts-yAxis,
          .recharts-line,
          .recharts-line-curve,
          .recharts-tooltip,
          .recharts-legend-item,
          .recharts-layer {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
          }

          /* Ensure paths and lines are visible */
          svg path,
          svg line,
          svg text,
          svg g {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
          }

          /* Optimize table printing */
          table {
            page-break-inside: auto;
            font-size: 9pt;
          }

          tr {
            page-break-inside: avoid;
            page-break-after: auto;
          }

          th, td {
            padding: 0.1cm !important;
          }

          /* Add page breaks between major sections */
          .print-page-break {
            page-break-before: always;
          }

          /* Print section styling */
          .print-section {
            page-break-before: always;
            margin-top: 0;
          }

          .print-section:first-child {
            page-break-before: avoid;
          }

          .print-section-title {
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 0.3cm;
            border-bottom: 2px solid #333;
            padding-bottom: 0.2cm;
          }

          /* Card styling for print */
          .bg-card {
            border: 1px solid #ddd !important;
            margin-bottom: 0.4cm !important;
          }

          /* Ensure good contrast in print */
          * {
            color-adjust: exact;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
        }

      `}</style>
      <div className="space-y-4">
        {/* Report Header */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Measurement Analysis</CardTitle>
              <div className="flex gap-2">
                <Button onClick={handlePrint} variant="outline" size="sm">
                  <Printer className="w-4 h-4 mr-2" />
                  Print Report
                </Button>
                <Button onClick={downloadCSV} variant="outline" size="sm">
                  <Download className="w-4 h-4 mr-2" />
                  Export CSV
                </Button>
                <Button onClick={reprocessVideo} variant="outline" size="sm" disabled={reprocessing}>
                  {reprocessing ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4 mr-2" />
                  )}
                  Reprocess Video
                </Button>
              </div>
            </div>
          </CardHeader>
        </Card>

      {/* Overview Section */}
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Session Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Session Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium text-base">Airport:</span>
                  <p className="text-gray-900 font-bold text-2xl">{data.summary.session_info.airport_code}</p>
                </div>
                <div>
                  <span className="font-medium text-base">Runway:</span>
                  <p className="text-gray-900 font-bold text-2xl">{data.summary.session_info.runway_code}</p>
                </div>
                <div>
                  <span className="font-medium">Report Created:</span>
                  <p className="text-gray-600">{new Date().toLocaleString()}</p>
                </div>
                <div>
                  <span className="font-medium">Video Recorded:</span>
                  <p className="text-gray-600">
                    {data.summary.session_info.recording_date
                      ? new Date(data.summary.session_info.recording_date).toLocaleString()
                      : (data.summary.session_info.created_at ? new Date(data.summary.session_info.created_at).toLocaleString() : 'N/A')}
                  </p>
                </div>
                <div>
                  <span className="font-medium">Duration:</span>
                  <p className="text-gray-600">{(data.summary.duration ?? 0).toFixed(1)}s</p>
                </div>
                <div>
                  <span className="font-medium">Total Frames:</span>
                  <p className="text-gray-600">{data.summary.total_frames}</p>
                </div>
                {data.summary.session_info.original_video_filename && (
                  <div className="col-span-2">
                    <span className="font-medium">Original Filename:</span>
                    <p className="text-gray-600 text-sm font-semibold">
                      {data.summary.session_info.original_video_filename}
                    </p>
                  </div>
                )}
                <div className="col-span-2">
                  <span className="font-medium">Video File:</span>
                  <p className="text-gray-600 text-xs">
                    {data.summary.session_info.video_file}
                  </p>
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

                    {/* Transition-Based GP Angle */}
                    <div className="border-2 rounded-lg p-6 bg-purple-50 border-purple-200 max-w-md mx-auto">
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
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Measurement Notes Section */}
      <Card className="mt-6">
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Measurement Notes</CardTitle>
              <CardDescription>
                Detailed notes about this measurement session
              </CardDescription>
            </div>
            <Button onClick={() => setNotesDialogOpen(true)} variant="outline" size="sm">
              <Edit2 className="w-4 h-4 mr-2" />
              Edit Notes
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {notes ? (
            <RichTextEditor
              content={notes}
              onChange={() => {}}
              editable={false}
            />
          ) : (
            <div className="p-4 bg-gray-50 rounded-md text-gray-500 italic">
              No notes added yet. Click "Edit Notes" to add notes about this measurement.
            </div>
          )}
        </CardContent>
      </Card>

      {/* PAPI Vertical Analysis Section */}
      <div className="space-y-6">
        <h2 className="print-section-title">PAPI Vertical Analysis</h2>
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
                  <LineChart data={formatComparisonChartData()} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    {/* Left Y-axis for Red Chromaticity */}
                    <YAxis
                      yAxisId="chroma"
                      label={{ value: 'Red Chromaticity', angle: -90, position: 'insideLeft', dx: 15 }}
                      domain={['dataMin - 5', 'dataMax + 5']}
                      tick={false}
                    />
                    {/* Right Y-axis for Angles */}
                    <YAxis
                      yAxisId="angle"
                      orientation="right"
                      label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                      domain={['dataMin - 1', 'dataMax + 1']}
                      tickFormatter={(value) => value.toFixed(2)}
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
                  <LineChart data={formatComparisonChartData()} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    {/* Left Y-axis for Intensity */}
                    <YAxis
                      yAxisId="intensity"
                      label={{ value: 'Intensity', angle: -90, position: 'insideLeft', dx: 15 }}
                      domain={['dataMin - 10', 'dataMax + 10']}
                      tick={false}
                    />
                    {/* Right Y-axis for Angles */}
                    <YAxis
                      yAxisId="angle"
                      orientation="right"
                      label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                      domain={['dataMin - 1', 'dataMax + 1']}
                      tickFormatter={(value) => value.toFixed(2)}
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

              {/* Color Diff Chart */}
              <div>
                <h4 className="text-sm font-medium mb-3">Color Diff (Red - Green) - All Lights</h4>
                <p className="text-xs text-gray-600 mb-2">
                  Shows the difference between red and green chromaticity for each PAPI light over time
                </p>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={formatComparisonChartData()} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis
                      label={{ value: 'Color Diff', angle: -90, position: 'insideLeft', dx: 15 }}
                      domain={['dataMin - 5', 'dataMax + 5']}
                      tick={false}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => {
                        if (value == null) return ['N/A', name];
                        return [`${value.toFixed(1)}%`, name];
                      }}
                      labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="PAPI_A_colorDiff" stroke="#ef4444" strokeWidth={2} dot={false} name="PAPI A Color Diff" />
                    <Line type="monotone" dataKey="PAPI_B_colorDiff" stroke="#f97316" strokeWidth={2} dot={false} name="PAPI B Color Diff" />
                    <Line type="monotone" dataKey="PAPI_C_colorDiff" stroke="#eab308" strokeWidth={2} dot={false} name="PAPI C Color Diff" />
                    <Line type="monotone" dataKey="PAPI_D_colorDiff" stroke="#22c55e" strokeWidth={2} dot={false} name="PAPI D Color Diff" />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Light Area Chart */}
              <div>
                <h4 className="text-sm font-medium mb-3">Light Area (Pixels²) - All Lights</h4>
                <p className="text-xs text-gray-600 mb-2">
                  Shows the area of the lit region (≥ 85% red intensity) for each PAPI light over time. Larger area indicates stronger or more spread out light.
                </p>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={formatComparisonChartData()} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis
                      label={{ value: 'Area (px²)', angle: -90, position: 'insideLeft', dx: 15 }}
                      domain={[0, 'dataMax + 100']}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => {
                        if (value == null) return ['N/A', name];
                        return [`${Math.round(value)} px²`, name];
                      }}
                      labelFormatter={(value: any) => `Time: ${(value ?? 0).toFixed(2)}s`}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="PAPI_A_area" stroke="#ef4444" strokeWidth={2} dot={false} name="PAPI A Area" />
                    <Line type="monotone" dataKey="PAPI_B_area" stroke="#f97316" strokeWidth={2} dot={false} name="PAPI B Area" />
                    <Line type="monotone" dataKey="PAPI_C_area" stroke="#eab308" strokeWidth={2} dot={false} name="PAPI C Area" />
                    <Line type="monotone" dataKey="PAPI_D_area" stroke="#22c55e" strokeWidth={2} dot={false} name="PAPI D Area" />
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
            let transitionInfo = transitionPoints.map(timestamp => {
              const dataPoint = rgbData.find(d => Math.abs(d.timestamp - timestamp) < 0.01);
              return {
                timestamp,
                angle: dataPoint?.angle ?? 0
              };
            });

            // If there are multiple transitions and we have a nominal angle, keep only the one closest to nominal
            if (transitionInfo.length > 1 && nominalAngle !== undefined && nominalAngle !== null) {
              transitionInfo = [transitionInfo.reduce((closest, current) => {
                const closestDiff = Math.abs(closest.angle - nominalAngle);
                const currentDiff = Math.abs(current.angle - nominalAngle);
                return currentDiff < closestDiff ? current : closest;
              })];
            }

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
                          Color transition angles: {transitionInfo.map(t => `${t.angle.toFixed(3)}° @ ${t.timestamp.toFixed(2)}s`).join(', ')}
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
                      <LineChart data={rgbData} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="timestamp"
                          label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                        />
                        {/* Left Y-axis for RGB values */}
                        <YAxis
                          yAxisId="rgb"
                          label={{ value: 'RGB Value', angle: -90, position: 'insideLeft', dx: 15 }}
                          domain={['dataMin - 10', 'dataMax + 10']}
                          tick={false}
                        />
                        {/* Right Y-axis for angles */}
                        <YAxis
                          yAxisId="angle"
                          orientation="right"
                          label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                          domain={['dataMin - 1', 'dataMax + 1']}
                          tickFormatter={(value) => value.toFixed(2)}
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
                          let label = `Transition @ ${transition.angle.toFixed(3)}°`;
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
                      <LineChart data={rgbData} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="timestamp"
                          label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                        />
                        {/* Left Y-axis for Chromaticity */}
                        <YAxis
                          yAxisId="chroma"
                          label={{ value: 'Chromaticity', angle: -90, position: 'insideLeft', dx: 15 }}
                          domain={['dataMin - 5', 'dataMax + 5']}
                          tick={false}
                        />
                        {/* Right Y-axis for Angle */}
                        <YAxis
                          yAxisId="angle"
                          orientation="right"
                          label={{ value: 'Elevation Angle (°)', angle: 90, position: 'insideRight' }}
                          domain={['dataMin - 1', 'dataMax + 1']}
                          tickFormatter={(value) => value.toFixed(2)}
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
                          let label = `Transition @ ${transition.angle.toFixed(3)}°`;
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
                        <Line yAxisId="chroma" type="monotone" dataKey="chromaRG" stroke="#f59e0b" strokeWidth={2.5} strokeDasharray="3 3" dot={false} name="ChromaRG (R-G)" />
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
      </div>

      {/* PAPI Horizontal Analysis Section */}
      <div className="space-y-6">
        <h2 className="print-section-title">PAPI Horizontal Analysis</h2>
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
                  })()} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis
                      yAxisId="chroma"
                      label={{ value: 'Red Chromaticity', angle: -90, position: 'insideLeft', dx: 15 }}
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
                  })()} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis
                      yAxisId="intensity"
                      label={{ value: 'Luminosity (0-255)', angle: -90, position: 'insideLeft', dx: 15 }}
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
      </div>

      {/* Drone Path Section */}
      <div className="space-y-6">
        <h2 className="print-section-title">Drone Path</h2>
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
                <LineChart data={chartData} margin={{ left: 50, right: 20, top: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="timestamp" label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }} />
                  <YAxis
                    label={{ value: 'Exact Elevation (m)', angle: -90, position: 'insideLeft', dx: 15 }}
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
      </div>

      {/* Videos Section */}
      {data?.video_urls && (
        <div className="space-y-6 no-print">
          <h2 className="print-section-title">Videos</h2>
          <div className="space-y-6">
          {/* Original Video */}
          {data.video_urls?.original && (
            <Card>
              <CardHeader>
                <CardTitle>Original Video</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="aspect-video">
                  <video
                    key={data.video_urls?.original}
                    width="100%"
                    height="100%"
                    controls
                    preload="metadata"
                    className="rounded-lg border"
                    src={data.video_urls?.original}
                  >
                    Your browser does not support the video tag.
                  </video>
                </div>
                <div className="mt-4 text-center text-sm text-gray-500">
                  Unprocessed drone footage as originally captured
                </div>
              </CardContent>
            </Card>
          )}

          {/* Enhanced Main Video */}
          <Card>
            <CardHeader>
              <CardTitle>Enhanced Main Video</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
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
                    //   error: video.error,
                    //   code: video.error?.code,
                    //   message: video.error?.message,
                    //   networkState: video.networkState,
                    //   readyState: video.readyState,
                    //   src: data.video_urls?.enhanced_main
                    // });
                  }}
                >
                  Your browser does not support the video tag.
                </video>
              </div>

              {/* Video Information Footer Panel */}
              <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-4 border border-gray-200">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Session Info */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-300 pb-1">
                      Session Info
                    </h4>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Airport:</span>
                        <span className="font-semibold text-gray-900">{data.summary.session_info.airport_code}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Runway:</span>
                        <span className="font-semibold text-gray-900">{data.summary.session_info.runway_code}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Duration:</span>
                        <span className="font-mono text-gray-900">{(data.summary.duration ?? 0).toFixed(1)}s</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Total Frames:</span>
                        <span className="font-mono text-gray-900">{data.summary.total_frames}</span>
                      </div>
                    </div>
                  </div>

                  {/* PAPI Angles */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-300 pb-1">
                      PAPI Vertical Angles
                    </h4>
                    <div className="space-y-1 text-sm">
                      {Object.entries(data.reference_points)
                        .filter(([key]) => key.includes('PAPI_'))
                        .sort(([a], [b]) => a.localeCompare(b))
                        .map(([pointId, point]) => {
                          const lightName = pointId.includes('PAPI_A') ? 'PAPI_A' :
                                          pointId.includes('PAPI_B') ? 'PAPI_B' :
                                          pointId.includes('PAPI_C') ? 'PAPI_C' :
                                          pointId.includes('PAPI_D') ? 'PAPI_D' :
                                          pointId.includes('PAPI_E') ? 'PAPI_E' :
                                          pointId.includes('PAPI_F') ? 'PAPI_F' :
                                          pointId.includes('PAPI_G') ? 'PAPI_G' :
                                          pointId.includes('PAPI_H') ? 'PAPI_H' : '';

                          const colors: { [key: string]: string } = {
                            'PAPI_A': 'text-blue-600',
                            'PAPI_B': 'text-green-600',
                            'PAPI_C': 'text-orange-600',
                            'PAPI_D': 'text-purple-600',
                            'PAPI_E': 'text-pink-600',
                            'PAPI_F': 'text-teal-600',
                            'PAPI_G': 'text-indigo-600',
                            'PAPI_H': 'text-red-600',
                          };

                          return (
                            <div key={pointId} className="flex justify-between items-center">
                              <span className="text-gray-600">{lightName.replace('_', ' ')}:</span>
                              <span className={`font-bold font-mono ${colors[lightName] || 'text-gray-900'}`}>
                                {point.nominal_angle !== undefined && point.nominal_angle !== null
                                  ? `${point.nominal_angle.toFixed(2)}°`
                                  : 'N/A'}
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  </div>

                  {/* Glide Path Info */}
                  {data.summary.glide_path_angles && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-300 pb-1">
                        Glide Path Angle
                      </h4>
                      <div className="space-y-3">
                        {data.summary.glide_path_angles.transition_based &&
                         data.summary.glide_path_angles.transition_based.filter(a => a !== 0).length > 0 && (
                          <div className="bg-purple-50 rounded-md p-3 border border-purple-200">
                            <div className="text-xs text-gray-600 mb-1">GP to PAPI Lights</div>
                            <div className="text-2xl font-bold text-purple-900 font-mono">
                              {(data.summary.glide_path_angles.transition_based
                                .filter(a => a !== 0)
                                .reduce((a, b) => a + b, 0) /
                                data.summary.glide_path_angles.transition_based.filter(a => a !== 0).length
                              ).toFixed(3)}°
                            </div>
                          </div>
                        )}
                        {data.summary.glide_path_angles.touch_point_at_transition !== undefined &&
                         data.summary.glide_path_angles.touch_point_at_transition !== 0 && (
                          <div className="bg-indigo-50 rounded-md p-3 border border-indigo-200">
                            <div className="text-xs text-gray-600 mb-1">GP to Touch Point</div>
                            <div className="text-xl font-bold text-indigo-700 font-mono">
                              {data.summary.glide_path_angles.touch_point_at_transition.toFixed(3)}°
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer note */}
                <div className="mt-4 pt-3 border-t border-gray-300">
                  <p className="text-xs text-gray-500 text-center">
                    Video shows drone position overlays, PAPI light rectangles, and real-time angle measurements
                  </p>
                </div>
              </div>
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
                          //   error: video.error,
                          //   networkState: video.networkState,
                          //   readyState: video.readyState,
                          //   src: data.video_urls?.[light as keyof typeof data.video_urls]
                          // });
                        }}
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
                      <th className="text-right p-2 font-semibold">Transition Width</th>
                      <th className="text-right p-2 font-semibold" title="Chromacity-based transition start angle">Transition Start</th>
                      <th className="text-right p-2 font-semibold" title="Chromacity-based middle transition angle">Transition Angle</th>
                      <th className="text-right p-2 font-semibold" title="Chromacity-based transition end angle">Transition End</th>
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

                          // If there are multiple transitions and we have a nominal angle, keep only the one closest to nominal
                          if (transitionAngles.length > 1 && point.nominal_angle !== undefined && point.nominal_angle !== null) {
                            // Find the index of the closest angle
                            let closestIndex = 0;
                            let minDiff = Math.abs(transitionAngles[0] - point.nominal_angle);
                            for (let i = 1; i < transitionAngles.length; i++) {
                              const diff = Math.abs(transitionAngles[i] - point.nominal_angle);
                              if (diff < minDiff) {
                                minDiff = diff;
                                closestIndex = i;
                              }
                            }
                            // Keep only the closest angle and its corresponding width
                            transitionAngles = [transitionAngles[closestIndex]];
                            if (transitionWidths.length > closestIndex) {
                              transitionWidths = [transitionWidths[closestIndex]];
                            }
                          }

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

                        // Get chromacity-based transition angles from API data (min, middle, max)
                        let chromacityTransitionAngleMin: number | null = null;
                        let chromacityTransitionAngleMiddle: number | null = null;
                        let chromacityTransitionAngleMax: number | null = null;
                        if (isPAPILight && data.chromacity_transition_angles && data.chromacity_transition_angles[lightName]) {
                          chromacityTransitionAngleMin = data.chromacity_transition_angles[lightName].transition_angle_min;
                          chromacityTransitionAngleMiddle = data.chromacity_transition_angles[lightName].transition_angle_middle;
                          chromacityTransitionAngleMax = data.chromacity_transition_angles[lightName].transition_angle_max;
                        }

                        let correction: number | null = null;
                        let isWithinTolerance = false;
                        if (chromacityTransitionAngleMiddle !== null && point.nominal_angle !== undefined && point.nominal_angle !== null) {
                          correction = point.nominal_angle - chromacityTransitionAngleMiddle;
                          isWithinTolerance = Math.abs(chromacityTransitionAngleMiddle - point.nominal_angle) <= (point.tolerance ?? 0.25);
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
                            <td className="p-2 text-right text-indigo-600 font-medium">
                              {transitionWidth !== null ? `${transitionWidth.toFixed(3)}°` : '-'}
                            </td>
                            <td className="p-2 text-right text-pink-600 font-medium" title="Chromacity-based transition start angle">
                              {chromacityTransitionAngleMin !== null ? `${chromacityTransitionAngleMin.toFixed(3)}°` : '-'}
                            </td>
                            <td className="p-2 text-right text-purple-600 font-medium" title="Chromacity-based transition middle angle">
                              {chromacityTransitionAngleMiddle !== null ? `${chromacityTransitionAngleMiddle.toFixed(3)}°` : '-'}
                            </td>
                            <td className="p-2 text-right text-pink-600 font-medium" title="Chromacity-based transition end angle">
                              {chromacityTransitionAngleMax !== null ? `${chromacityTransitionAngleMax.toFixed(3)}°` : '-'}
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
                // Get transition angles for all PAPI lights from chromacity data
                const papiLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D', 'PAPI_E', 'PAPI_F', 'PAPI_G', 'PAPI_H'];
                const papiTransitionData: { [key: string]: number | null } = {};

                papiLights.forEach(lightName => {
                  // Check if this PAPI light exists in the chromacity transition angles data
                  if (data.chromacity_transition_angles && data.chromacity_transition_angles[lightName]) {
                    papiTransitionData[lightName] = data.chromacity_transition_angles[lightName].transition_angle_middle;
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
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Explanation
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {pairs.map((pair, idx) => {
                          const isWithinTolerance = pair.difference >= minAcceptable && pair.difference <= maxAcceptable;

                          // Determine explanation based on the difference
                          let explanation: string;
                          if (pair.difference < 0) {
                            explanation = 'Negative difference (reverse order)';
                          } else if (pair.difference < minAcceptable) {
                            explanation = `Too small (< ${minAcceptable.toFixed(2)}°) - lights too close`;
                          } else if (pair.difference > maxAcceptable) {
                            explanation = `Too large (> ${maxAcceptable.toFixed(2)}°) - lights too far apart`;
                          } else {
                            explanation = 'Within acceptable range';
                          }

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
                              <td className="px-4 py-3 text-sm text-gray-600 italic">
                                {explanation}
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
              <CardDescription>
                The difference between minimum and maximum luminosity values can be up to 50%.
              </CardDescription>
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
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Difference (%)
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

                          // Calculate difference between max and min as percentage
                          const differencePercent = item.max > 0 ? ((item.max - item.min) / item.max) * 100 : 0;
                          const differenceFailed = differencePercent > 50;

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
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-bold">
                                <span className={differenceFailed ? "text-red-600" : "text-green-600"}>
                                  {differencePercent.toFixed(1)}%
                                </span>
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

      {/* Notes Editor Dialog */}
      <NotesEditorDialog
        open={notesDialogOpen}
        onOpenChange={setNotesDialogOpen}
        sessionId={sessionId}
        initialNotes={notes}
        onNotesSaved={handleNotesSaved}
      />
    </>
  );
};

export default MeasurementDataDisplay;