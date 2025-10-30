import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import {
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle,
  MapPin,
  Camera,
  Plane
} from 'lucide-react';
import CoordinateCopyButton from './CoordinateCopyButton';

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

interface ImageMetadataDisplayProps {
  images: ImageMetadata[];
}

const ImageMetadataDisplay: React.FC<ImageMetadataDisplayProps> = ({ images }) => {
  const [expandedImages, setExpandedImages] = useState<Set<number>>(new Set());

  const toggleExpanded = (index: number) => {
    setExpandedImages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  return (
    <div className="space-y-4">
      {images.map((image, index) => (
        <Card key={index} className={image.success ? 'border-green-200' : 'border-red-200'}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {image.success ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-red-500" />
                )}
                <div>
                  <CardTitle className="text-base">{image.filename}</CardTitle>
                  {image.file_size_mb && (
                    <p className="text-sm text-muted-foreground">
                      {image.file_size_mb} MB
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {image.success && (
                  <Badge variant="default" className="bg-green-500">Success</Badge>
                )}
                {!image.success && (
                  <Badge variant="destructive">Failed</Badge>
                )}
                <button
                  onClick={() => toggleExpanded(index)}
                  className="p-2 hover:bg-gray-100 rounded"
                >
                  {expandedImages.has(index) ? (
                    <ChevronUp className="w-5 h-5" />
                  ) : (
                    <ChevronDown className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          </CardHeader>

          {expandedImages.has(index) && (
            <CardContent className="pt-0">
              {/* Error Messages */}
              {image.error && (
                <Alert variant="destructive" className="mb-4">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{image.error}</AlertDescription>
                </Alert>
              )}

              {image.processing_errors && image.processing_errors.length > 0 && (
                <Alert className="mb-4 border-yellow-200 bg-yellow-50">
                  <AlertCircle className="h-4 w-4 text-yellow-600" />
                  <AlertDescription>
                    <ul className="list-disc list-inside">
                      {image.processing_errors.map((err, i) => (
                        <li key={i} className="text-yellow-800">{err}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              {/* GPS Data */}
              {image.gps_data && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <MapPin className="w-5 h-5 text-blue-600" />
                    <h3 className="font-semibold text-lg">GPS Coordinates</h3>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Latitude */}
                      <div>
                        <label className="text-sm font-medium text-gray-700">Latitude</label>
                        <div className="space-y-2 mt-1">
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={image.gps_data.latitude.decimal}
                              readOnly
                              className="flex-1 px-3 py-2 border rounded-md bg-white text-sm"
                            />
                            <CoordinateCopyButton value={image.gps_data.latitude.decimal} label="Decimal" />
                          </div>
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={image.gps_data.latitude.dms}
                              readOnly
                              className="flex-1 px-3 py-2 border rounded-md bg-white text-sm"
                            />
                            <CoordinateCopyButton value={image.gps_data.latitude.dms} label="DMS" />
                          </div>
                        </div>
                      </div>

                      {/* Longitude */}
                      <div>
                        <label className="text-sm font-medium text-gray-700">Longitude</label>
                        <div className="space-y-2 mt-1">
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={image.gps_data.longitude.decimal}
                              readOnly
                              className="flex-1 px-3 py-2 border rounded-md bg-white text-sm"
                            />
                            <CoordinateCopyButton value={image.gps_data.longitude.decimal} label="Decimal" />
                          </div>
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={image.gps_data.longitude.dms}
                              readOnly
                              className="flex-1 px-3 py-2 border rounded-md bg-white text-sm"
                            />
                            <CoordinateCopyButton value={image.gps_data.longitude.dms} label="DMS" />
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Altitude */}
                    {image.gps_data.altitude && (
                      <div className="pt-2 border-t">
                        <label className="text-sm font-medium text-gray-700">Altitude</label>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-600 w-16">Meters:</span>
                            <input
                              type="text"
                              value={image.gps_data.altitude.meters}
                              readOnly
                              className="flex-1 px-3 py-2 border rounded-md bg-white text-sm"
                            />
                            <CoordinateCopyButton value={image.gps_data.altitude.meters} label="Copy" />
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-600 w-16">Feet:</span>
                            <input
                              type="text"
                              value={image.gps_data.altitude.feet}
                              readOnly
                              className="flex-1 px-3 py-2 border rounded-md bg-white text-sm"
                            />
                            <CoordinateCopyButton value={image.gps_data.altitude.feet} label="Copy" />
                          </div>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">{image.gps_data.altitude_ref}</p>
                      </div>
                    )}

                    {/* Copy All Coordinates */}
                    <div className="pt-2 border-t">
                      <CoordinateCopyButton
                        value={`${image.gps_data.latitude.decimal}, ${image.gps_data.longitude.decimal}`}
                        label="Copy Lat, Lon (Decimal)"
                        variant="secondary"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Drone Metadata */}
              {image.drone_metadata && Object.keys(image.drone_metadata).length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Plane className="w-5 h-5 text-blue-600" />
                    <h3 className="font-semibold text-lg">Drone Information</h3>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2">
                      {image.drone_metadata.make && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Make:</dt>
                          <dd className="text-sm text-gray-900">{image.drone_metadata.make}</dd>
                        </>
                      )}
                      {image.drone_metadata.model && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Model:</dt>
                          <dd className="text-sm text-gray-900">{image.drone_metadata.model}</dd>
                        </>
                      )}
                      {image.drone_metadata.gimbal_pitch && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Gimbal Pitch:</dt>
                          <dd className="text-sm text-gray-900">{image.drone_metadata.gimbal_pitch}°</dd>
                        </>
                      )}
                      {image.drone_metadata.gimbal_roll && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Gimbal Roll:</dt>
                          <dd className="text-sm text-gray-900">{image.drone_metadata.gimbal_roll}°</dd>
                        </>
                      )}
                      {image.drone_metadata.gimbal_yaw && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Gimbal Yaw:</dt>
                          <dd className="text-sm text-gray-900">{image.drone_metadata.gimbal_yaw}°</dd>
                        </>
                      )}
                      {image.drone_metadata.relative_altitude && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Relative Altitude:</dt>
                          <dd className="text-sm text-gray-900">{image.drone_metadata.relative_altitude}m</dd>
                        </>
                      )}
                    </dl>
                  </div>
                </div>
              )}

              {/* Camera Metadata */}
              {image.camera_metadata && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Camera className="w-5 h-5 text-blue-600" />
                    <h3 className="font-semibold text-lg">Camera Settings</h3>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2">
                      {image.camera_metadata.make && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Camera Make:</dt>
                          <dd className="text-sm text-gray-900">{image.camera_metadata.make}</dd>
                        </>
                      )}
                      {image.camera_metadata.model && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Camera Model:</dt>
                          <dd className="text-sm text-gray-900">{image.camera_metadata.model}</dd>
                        </>
                      )}
                      {image.camera_metadata.iso && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">ISO:</dt>
                          <dd className="text-sm text-gray-900">{image.camera_metadata.iso}</dd>
                        </>
                      )}
                      {image.camera_metadata.shutter_speed && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Shutter Speed:</dt>
                          <dd className="text-sm text-gray-900">{image.camera_metadata.shutter_speed}s</dd>
                        </>
                      )}
                      {image.camera_metadata.aperture && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Aperture:</dt>
                          <dd className="text-sm text-gray-900">f/{image.camera_metadata.aperture}</dd>
                        </>
                      )}
                      {image.camera_metadata.focal_length && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Focal Length:</dt>
                          <dd className="text-sm text-gray-900">{image.camera_metadata.focal_length}mm</dd>
                        </>
                      )}
                    </dl>
                  </div>
                </div>
              )}

              {/* Capture Metadata */}
              {image.capture_metadata && (
                <div>
                  <h3 className="font-semibold text-lg mb-3">Capture Information</h3>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2">
                      {image.capture_metadata.datetime_original && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Date Taken:</dt>
                          <dd className="text-sm text-gray-900">{image.capture_metadata.datetime_original}</dd>
                        </>
                      )}
                      {image.capture_metadata.width && image.capture_metadata.height && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Resolution:</dt>
                          <dd className="text-sm text-gray-900">
                            {image.capture_metadata.width} × {image.capture_metadata.height}
                          </dd>
                        </>
                      )}
                      {image.capture_metadata.software && (
                        <>
                          <dt className="text-sm font-medium text-gray-700">Software:</dt>
                          <dd className="text-sm text-gray-900">{image.capture_metadata.software}</dd>
                        </>
                      )}
                    </dl>
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
};

export default ImageMetadataDisplay;
