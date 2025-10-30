import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Upload, AlertCircle, Image as ImageIcon, RefreshCw } from 'lucide-react';
import api from '../services/api';
import ImageMetadataDisplay from '../components/ImageMetadataDisplay';

interface ImageMetadata {
  filename: string;
  success: boolean;
  error?: string;
  file_size_mb?: number;
  gps_data?: {
    latitude: {
      decimal: string;
      dms: string;
      raw: string;
    };
    longitude: {
      decimal: string;
      dms: string;
      raw: string;
    };
    altitude?: {
      meters: string;
      feet: string;
      raw: string;
    };
    altitude_ref: string;
  };
  drone_metadata?: {
    model: string;
    make: string;
    gimbal_pitch?: string;
    gimbal_roll?: string;
    gimbal_yaw?: string;
    flight_pitch?: string;
    flight_roll?: string;
    flight_yaw?: string;
    relative_altitude?: string;
    absolute_altitude?: string;
  };
  camera_metadata?: {
    make: string;
    model: string;
    lens_model: string;
    iso: string;
    shutter_speed: string;
    aperture: string;
    focal_length: string;
  };
  capture_metadata?: {
    datetime_original: string;
    datetime_digitized: string;
    width: number;
    height: number;
    orientation: string;
    software: string;
  };
  processing_errors?: string[];
}

interface ExtractionResponse {
  images: ImageMetadata[];
  total_images: number;
  successful: number;
  failed: number;
}

const DroneMetadataTools: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ExtractionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const imageFiles = droppedFiles.filter(file =>
      file.type.startsWith('image/') ||
      file.name.toLowerCase().match(/\.(jpg|jpeg|png|dng|tiff|tif)$/)
    );

    if (imageFiles.length > 0) {
      setFiles(prevFiles => [...prevFiles, ...imageFiles]);
      setError(null);
    } else {
      setError('Please drop valid image files (JPG, PNG, DNG, TIFF)');
    }
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles(prevFiles => [...prevFiles, ...selectedFiles]);
      setError(null);
    }
  };

  const removeFile = (index: number) => {
    setFiles(prevFiles => prevFiles.filter((_, i) => i !== index));
  };

  const extractMetadata = async () => {
    if (files.length === 0) {
      setError('Please select at least one image file');
      return;
    }

    if (files.length > 10) {
      setError('Maximum 10 files allowed per extraction');
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const result = await api.extractDroneMetadata(files);
      setResults(result);
      setFiles([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to extract metadata. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setFiles([]);
    setResults(null);
    setError(null);
  };

  return (
    <div className="container mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle>Drone Image Metadata Extractor</CardTitle>
          <CardDescription>
            Upload drone images to extract GPS coordinates, camera settings, and flight data
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Upload Area */}
          {!results && (
            <>
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragActive
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                <p className="text-lg mb-2">
                  Drag and drop images here, or click to browse
                </p>
                <p className="text-sm text-muted-foreground mb-4">
                  Supports JPG, PNG, DNG, TIFF (Max 10 files, 50MB each)
                </p>
                <input
                  type="file"
                  multiple
                  accept=".jpg,.jpeg,.png,.dng,.tiff,.tif"
                  onChange={handleFileInput}
                  className="hidden"
                  id="file-input"
                />
                <label htmlFor="file-input">
                  <Button type="button" variant="outline" asChild>
                    <span>Browse Files</span>
                  </Button>
                </label>
              </div>

              {/* Selected Files List */}
              {files.length > 0 && (
                <div className="mt-6">
                  <h3 className="font-medium mb-3">Selected Files ({files.length})</h3>
                  <div className="space-y-2">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <ImageIcon className="w-5 h-5 text-gray-400" />
                          <div>
                            <p className="font-medium">{file.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {(file.size / (1024 * 1024)).toFixed(2)} MB
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(index)}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>

                  <div className="flex gap-2 mt-4">
                    <Button
                      onClick={extractMetadata}
                      disabled={loading}
                      className="bg-blue-600 hover:bg-blue-700"
                    >
                      {loading ? (
                        <>
                          <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                          Extracting...
                        </>
                      ) : (
                        'Extract Metadata'
                      )}
                    </Button>
                    <Button variant="outline" onClick={reset} disabled={loading}>
                      Clear All
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Error Display */}
          {error && (
            <Alert variant="destructive" className="mt-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Results Display */}
          {results && (
            <div className="mt-6">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="text-lg font-semibold">Extraction Results</h3>
                  <p className="text-sm text-muted-foreground">
                    {results.successful} successful, {results.failed} failed out of{' '}
                    {results.total_images} total
                  </p>
                </div>
                <Button variant="outline" onClick={reset}>
                  Extract More Images
                </Button>
              </div>

              <ImageMetadataDisplay images={results.images} />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default DroneMetadataTools;
