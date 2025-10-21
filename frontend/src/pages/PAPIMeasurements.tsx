import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Upload, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import api from '../services/api';
import MeasurementDataDisplay from '../components/MeasurementDataDisplay';

interface Airport {
  icao_code: string;
  name: string;
  runways: Array<{ code: string; id: string }>;
}

interface MeasurementSession {
  session_id: string;
  status: string;
  preview_url?: string;
  detected_lights?: any;
  report_url?: string;
  html_report_url?: string;
  html_report_content_url?: string;
  video_urls?: any;
  frames_processed?: number;
  total_frames?: number;
  progress_percentage?: number;
  current_phase?: string;
}

const PAPIMeasurements: React.FC = () => {
  const [step, setStep] = useState<'select' | 'upload' | 'preview' | 'processing' | 'results' | 'error'>('select');
  const [airports, setAirports] = useState<Airport[]>([]);
  const [selectedAirport, setSelectedAirport] = useState<string>('');
  const [selectedRunway, setSelectedRunway] = useState<string>('');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [session, setSession] = useState<MeasurementSession | null>(null);
  const [processing, setProcessing] = useState(false);
  const [lightPositions, setLightPositions] = useState<any>({});
  const [previewImageUrl, setPreviewImageUrl] = useState<string>('');
  const [dragging, setDragging] = useState<string | null>(null);
  const [imageElement, setImageElement] = useState<HTMLImageElement | null>(null);
  const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    fetchAirports();
  }, []);

  const fetchAirports = async () => {
    try {
      const response = await api.get('/papi-measurements/airports-with-runways');
      setAirports(response.data);
    } catch (error) {
      console.error('Failed to fetch airports:', error);
    }
  };

  const handleAirportSelect = (icao: string) => {
    setSelectedAirport(icao);
    setSelectedRunway('');
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setVideoFile(file);
      setStep('upload');
    }
  };

  const handleUpload = async () => {
    if (!videoFile || !selectedAirport || !selectedRunway) return;

    setProcessing(true);
    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('airport_icao', selectedAirport);
    formData.append('runway_code', selectedRunway);

    try {
      const response = await api.post('/papi-measurements/upload-video', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      setSession(response.data);
      setStep('preview');
      
      // Poll for preview
      setTimeout(() => fetchPreview(response.data.session_id), 2000);
    } catch (error) {
      console.error('Upload failed:', error);
      setProcessing(false);
    }
  };

  const fetchPreview = async (sessionId: string) => {
    try {
      const response = await api.get(`/papi-measurements/session/${sessionId}/preview`);
      
      setSession(response.data);
      
      // Process detected lights or set defaults
      const detectedLights = response.data.detected_lights || {};
      console.log('Detected lights from backend:', detectedLights);
      
      if (Object.keys(detectedLights).length > 0) {
        // Convert detected lights to our format if needed
        const processedLights: any = {};
        Object.entries(detectedLights).forEach(([lightId, data]: [string, any]) => {
          processedLights[lightId] = {
            x: data.x || data.center_x || 50,
            y: data.y || data.center_y || 50,
            size: data.size || data.width || 8
          };
        });
        setLightPositions(processedLights);
      } else {
        // Set default positions if no lights detected
        setLightPositions({
          PAPI_A: { x: 20, y: 50, size: 8 },
          PAPI_B: { x: 40, y: 50, size: 8 },
          PAPI_C: { x: 60, y: 50, size: 8 },
          PAPI_D: { x: 80, y: 50, size: 8 }
        });
      }
      
      // Fetch the preview image with authentication
      if (response.data.preview_url) {
        try {
          const imageResponse = await api.get(response.data.preview_url, {
            responseType: 'blob'
          });
          const imageUrl = URL.createObjectURL(imageResponse.data);
          setPreviewImageUrl(imageUrl);
        } catch (imageError) {
          console.error('Failed to fetch preview image:', imageError);
        }
      }
      
      setProcessing(false);
    } catch (error) {
      // Retry if preview not ready
      setTimeout(() => fetchPreview(sessionId), 2000);
    }
  };

  const confirmLights = async () => {
    if (!session) return;

    setProcessing(true);
    try {
      await api.post(
        `/papi-measurements/session/${session.session_id}/confirm-lights`,
        lightPositions
      );
      
      setStep('processing');
      pollProcessingStatus();
    } catch (error) {
      console.error('Failed to confirm lights:', error);
      setProcessing(false);
    }
  };

  const pollProcessingStatus = async () => {
    if (!session) return;

    const interval = setInterval(async () => {
      try {
        const response = await api.get(
          `/papi-measurements/session/${session.session_id}/status`
        );
        
        if (response.data.status === 'completed') {
          clearInterval(interval);
          setSession(response.data);
          setStep('results');
          setProcessing(false);
        } else if (response.data.status === 'error') {
          clearInterval(interval);
          setSession(response.data);
          setErrorMessage(response.data.error_message || 'Unknown error occurred');
          setProcessing(false);
          setStep('error');
        } else {
          // Update session with progress information
          setSession(prev => prev ? { ...prev, ...response.data } : response.data);
        }
      } catch (error) {
        console.error('Status check failed:', error);
      }
    }, 3000);
  };

  const selectedAirportData = airports.find(a => a.icao_code === selectedAirport);

  const handleImageLoad = (event: React.SyntheticEvent<HTMLImageElement>) => {
    const img = event.target as HTMLImageElement;
    setImageElement(img);
    
    // Create canvas for image analysis
    const canvasEl = document.createElement('canvas');
    canvasEl.width = img.naturalWidth;
    canvasEl.height = img.naturalHeight;
    const ctx = canvasEl.getContext('2d');
    if (ctx) {
      ctx.drawImage(img, 0, 0);
      setCanvas(canvasEl);
    }
  };

  const findBrightestSpot = (centerX: number, centerY: number, size: number) => {
    if (!canvas || !imageElement) return { x: centerX, y: centerY };
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return { x: centerX, y: centerY };
    
    // Convert percentage coordinates to actual pixel coordinates
    const imgWidth = canvas.width;
    const imgHeight = canvas.height;
    const pixelX = Math.round((centerX / 100) * imgWidth);
    const pixelY = Math.round((centerY / 100) * imgHeight);
    const pixelSize = Math.round((size / 100) * imgWidth);
    
    // Define search area (square area)
    const searchArea = {
      x: Math.max(0, pixelX - pixelSize / 2),
      y: Math.max(0, pixelY - pixelSize / 2),
      width: Math.min(pixelSize, imgWidth - pixelX + pixelSize / 2),
      height: Math.min(pixelSize, imgHeight - pixelY + pixelSize / 2)
    };
    
    try {
      const imageData = ctx.getImageData(searchArea.x, searchArea.y, searchArea.width, searchArea.height);
      const data = imageData.data;
      
      let maxBrightness = 0;
      let brightestX = centerX;
      let brightestY = centerY;
      
      // Analyze pixels to find brightest spot
      for (let y = 0; y < searchArea.height; y++) {
        for (let x = 0; x < searchArea.width; x++) {
          const idx = (y * searchArea.width + x) * 4;
          const r = data[idx];
          const g = data[idx + 1];
          const b = data[idx + 2];
          
          // Calculate brightness (luminance)
          const brightness = 0.299 * r + 0.587 * g + 0.114 * b;
          
          if (brightness > maxBrightness) {
            maxBrightness = brightness;
            // Convert back to percentage coordinates
            brightestX = ((searchArea.x + x) / imgWidth) * 100;
            brightestY = ((searchArea.y + y) / imgHeight) * 100;
          }
        }
      }
      
      return { x: brightestX, y: brightestY };
    } catch (error) {
      console.warn('Could not analyze image for light detection:', error);
      return { x: centerX, y: centerY };
    }
  };

  const handleMouseDown = (lightId: string, event: React.MouseEvent) => {
    event.preventDefault();
    setDragging(lightId);
  };

  const handleMouseMove = (event: React.MouseEvent) => {
    if (!dragging) return;
    
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    
    setLightPositions((prev: any) => ({
      ...prev,
      [dragging]: {
        ...prev[dragging],
        x: Math.max(0, Math.min(95, x)), // Keep within bounds
        y: Math.max(0, Math.min(95, y))
      }
    }));
  };

  const handleMouseUp = () => {
    if (dragging) {
      // Auto-center the square on the brightest spot in the area
      const currentPosition = lightPositions[dragging];
      if (currentPosition) {
        const brightestSpot = findBrightestSpot(
          currentPosition.x,
          currentPosition.y,
          currentPosition.size || 8
        );
        
        setLightPositions((prev: any) => ({
          ...prev,
          [dragging]: {
            ...prev[dragging],
            x: brightestSpot.x,
            y: brightestSpot.y
          }
        }));
      }
    }
    setDragging(null);
  };


  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">PAPI Light Measurements</h1>

      {step === 'select' && (
        <Card>
          <CardHeader>
            <CardTitle>Step 1: Select Airport and Runway</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Select Airport</label>
              <Select value={selectedAirport} onValueChange={handleAirportSelect}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose an airport" />
                </SelectTrigger>
                <SelectContent>
                  {airports.map(airport => (
                    <SelectItem key={airport.icao_code} value={airport.icao_code}>
                      {airport.name} ({airport.icao_code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedAirportData && (
              <div>
                <label className="block text-sm font-medium mb-2">Select Runway</label>
                <Select value={selectedRunway} onValueChange={setSelectedRunway}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Choose a runway" />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedAirportData.runways.map(runway => (
                      <SelectItem key={runway.id} value={runway.code}>
                        Runway {runway.code}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {selectedRunway && (
              <div>
                <label className="block text-sm font-medium mb-2">Upload Video</label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                  <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                  <p className="text-sm text-gray-600 mb-2">
                    Select drone video for runway {selectedRunway}
                  </p>
                  <input
                    type="file"
                    accept="video/*"
                    onChange={handleFileSelect}
                    className="hidden"
                    id="video-upload"
                  />
                  <Button variant="outline" asChild>
                    <label htmlFor="video-upload" className="cursor-pointer">
                      Choose Video
                    </label>
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {step === 'upload' && (
        <Card>
          <CardHeader>
            <CardTitle>Step 2: Upload Video</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-gray-50 p-4 rounded">
              <p className="font-medium">Selected:</p>
              <p>Airport: {selectedAirport}</p>
              <p>Runway: {selectedRunway}</p>
              <p>Video: {videoFile?.name}</p>
            </div>
            <Button onClick={handleUpload} disabled={processing} className="w-full">
              {processing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  Upload and Process
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {step === 'preview' && (
        <Card>
          <CardHeader>
            <CardTitle>Step 3: Confirm PAPI Light Positions</CardTitle>
          </CardHeader>
          <CardContent>
            {previewImageUrl ? (
              <div className="space-y-4">
                <div 
                  className="relative cursor-pointer select-none"
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                >
                  <img 
                    src={previewImageUrl} 
                    alt="First frame" 
                    className="w-full" 
                    onLoad={handleImageLoad}
                    draggable={false}
                  />
                  
                  {/* PAPI Light Position Overlays */}
                  {Object.entries(lightPositions).map(([lightId, position]: [string, any]) => (
                    <div
                      key={lightId}
                      className={`absolute border-2 rounded cursor-move transition-colors ${
                        dragging === lightId 
                          ? 'border-blue-500 bg-blue-200 bg-opacity-30' 
                          : 'border-red-500 bg-red-200 bg-opacity-20 hover:bg-red-300 hover:bg-opacity-30'
                      }`}
                      style={{
                        left: `${position.x}%`,
                        top: `${position.y}%`,
                        width: `${position.size || 8}%`,
                        height: `${position.size || 8}%`,
                        transform: 'translate(-50%, -50%)'
                      }}
                      onMouseDown={(e) => handleMouseDown(lightId, e)}
                    >
                      <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 bg-black bg-opacity-70 text-white text-xs px-1 py-0.5 rounded">
                        {lightId.replace('PAPI_', '')}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="bg-blue-50 p-4 rounded">
                  <p className="text-sm mb-2">
                    <strong>Instructions:</strong>
                  </p>
                  <ul className="text-sm space-y-1">
                    <li>• Red squares show detected PAPI light positions (A, B, C, D)</li>
                    <li>• <strong>Drag squares</strong> to adjust positions if they're not accurate</li>
                    <li>• Each light should be clearly visible within its square</li>
                    <li>• Click "Confirm and Start Processing" when positions are correct</li>
                  </ul>
                </div>
                
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    onClick={() => setLightPositions({
                      PAPI_A: { x: 20, y: 50, size: 8 },
                      PAPI_B: { x: 40, y: 50, size: 8 },
                      PAPI_C: { x: 60, y: 50, size: 8 },
                      PAPI_D: { x: 80, y: 50, size: 8 }
                    })}
                    className="flex-1"
                  >
                    Reset Positions
                  </Button>
                  <Button onClick={confirmLights} disabled={processing} className="flex-2">
                    {processing ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Starting Processing...
                      </>
                    ) : (
                      <>
                        <CheckCircle className="w-4 h-4 mr-2" />
                        Confirm and Start Processing
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <Loader2 className="w-8 h-8 mx-auto animate-spin" />
                <p className="mt-2">Extracting first frame...</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {step === 'processing' && (
        <Card>
          <CardHeader>
            <CardTitle>Processing Video</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-center py-8">
              <Loader2 className="w-12 h-12 mx-auto animate-spin mb-4" />
              <p className="text-lg font-medium">Analyzing PAPI lights...</p>
              
              {/* Progress Bar */}
              {session && session.progress_percentage !== undefined && (
                <div className="mt-4 space-y-2">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                      style={{ width: `${Math.min(100, Math.max(0, session.progress_percentage))}%` }}
                    ></div>
                  </div>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>{session.progress_percentage?.toFixed(1)}% complete</p>
                    {session.current_phase && (
                      <p className="capitalize">Phase: {session.current_phase.replace('_', ' ')}</p>
                    )}
                    {session.frames_processed !== undefined && session.total_frames !== undefined && (
                      <p>Frame {session.frames_processed} of {session.total_frames}</p>
                    )}
                  </div>
                </div>
              )}
              
              <p className="text-sm text-gray-600 mt-4">
                This may take several minutes depending on video length
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 'results' && session && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Measurement Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-green-50 p-4 rounded flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                <span>Processing completed successfully!</span>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <Button
                  variant="outline"
                  onClick={() => setStep('select')}
                >
                  New Measurement
                </Button>
              </div>

              {session.video_urls && (
                <div>
                  <h3 className="font-medium mb-2">Individual PAPI Light Videos:</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(session.video_urls).map(([light, url]) => (
                      <div key={light} className="text-center">
                        <h4 className="font-medium mb-2">{light}</h4>
                        <video 
                          width="100" 
                          height="100" 
                          controls 
                          className="mx-auto border rounded"
                          src={url as string}
                        >
                          Your browser does not support the video tag.
                        </video>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Direct Data Display */}
          <MeasurementDataDisplay sessionId={session.session_id} />
        </div>
      )}

      {step === 'error' && (
        <Card>
          <CardHeader>
            <CardTitle>Processing Failed</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-red-50 p-4 rounded flex items-center">
              <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
              <span>Video processing failed</span>
            </div>
            
            {errorMessage && (
              <div className="bg-gray-50 p-4 rounded">
                <h3 className="font-medium mb-2">Error Details:</h3>
                <div className="text-sm bg-white p-3 rounded border">
                  <pre className="whitespace-pre-wrap text-xs font-mono text-gray-700">
                    {errorMessage}
                  </pre>
                </div>
              </div>
            )}
            
            <div className="bg-gray-50 p-4 rounded">
              <h3 className="font-medium mb-2">Common causes:</h3>
              <ul className="text-sm space-y-1">
                <li>• Video format not supported</li>
                <li>• Video file corrupted or incomplete</li>
                <li>• No PAPI lights detected in the video</li>
                <li>• Video quality too low for light detection</li>
                <li>• Server processing error</li>
              </ul>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <Button
                variant="outline"
                onClick={() => {
                  setStep('select');
                  setVideoFile(null);
                  setSession(null);
                  setPreviewImageUrl('');
                  setLightPositions({});
                  setErrorMessage('');
                }}
              >
                Try Again
              </Button>
              <Button
                onClick={() => {
                  setStep('select');
                  setErrorMessage('');
                }}
              >
                New Measurement
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default PAPIMeasurements;