"""
S3 Storage Service for Airport Management System
Handles all S3 operations for videos, frame measurements, and reports
"""
import boto3
import sys
import gzip
import json
import io
import logging
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO, List, Dict, Any
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3StorageService:
    """Service for managing S3 storage operations"""

    def __init__(self):
        """Initialize S3 client with credentials from config"""
        if not settings.USE_S3_STORAGE:
            sys.stderr.write(f"[WARNING] S3 storage is disabled in configuration\n"); sys.stderr.flush()
            return

        # Force S3v4 signature and use addressing_style='virtual' for presigned URLs
        from botocore.client import Config

        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'virtual'}
            )
        )
        self.bucket = settings.S3_BUCKET
        sys.stderr.write(f"[INFO] S3 storage initialized for bucket: {self.bucket} with S3v4 signatures\n"); sys.stderr.flush()

    def _get_video_key(self, session_id: str, video_type: str = "original", filename: str = None) -> str:
        """Generate S3 key for video files"""
        if filename:
            return f"videos/{video_type}/{session_id}/{filename}"
        return f"videos/{video_type}/{session_id}/{video_type}.mp4"

    def _get_frames_key(self, session_id: str) -> str:
        """Generate S3 key for frame measurements"""
        return f"frames/{session_id}/measurements.json.gz"

    def _get_report_key(self, session_id: str, report_type: str) -> str:
        """Generate S3 key for reports"""
        return f"reports/{session_id}/report.{report_type}"

    async def upload_video(
        self,
        session_id: str,
        file_path: str,
        video_type: str = "original"
    ) -> str:
        """
        Upload video file to S3

        Args:
            session_id: Session ID
            file_path: Local path to video file
            video_type: Type of video (original, processed, enhanced, enhanced_with_audio)

        Returns:
            S3 key of uploaded file
        """
        key = self._get_video_key(session_id, video_type, Path(file_path).name)

        try:
            with open(file_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.bucket,
                    key,
                    ExtraArgs={
                        'ContentType': 'video/mp4',
                        'ServerSideEncryption': 'AES256'
                    }
                )
            sys.stderr.write(f"[INFO] Uploaded video to s3://{self.bucket}/{key}\n"); sys.stderr.flush()
            return key
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to upload video to S3: {e}\n"); sys.stderr.flush()
            raise

    async def upload_video_stream(
        self,
        session_id: str,
        file_obj: BinaryIO,
        filename: str,
        video_type: str = "original"
    ) -> str:
        """
        Upload video from file object/stream to S3

        Args:
            session_id: Session ID
            file_obj: File-like object containing video data
            filename: Original filename
            video_type: Type of video

        Returns:
            S3 key of uploaded file
        """
        key = self._get_video_key(session_id, video_type, filename)

        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket,
                key,
                ExtraArgs={
                    'ContentType': 'video/mp4',
                    'ServerSideEncryption': 'AES256'
                }
            )
            sys.stderr.write(f"[INFO] Uploaded video stream to s3://{self.bucket}/{key}\n"); sys.stderr.flush()
            return key
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to upload video stream to S3: {e}\n"); sys.stderr.flush()
            raise

    async def download_video(self, s3_key: str, local_path: str) -> None:
        """
        Download video from S3 to local file

        Args:
            s3_key: S3 key of the video
            local_path: Local path to save video
        """
        try:
            self.s3_client.download_file(self.bucket, s3_key, local_path)
            sys.stderr.write(f"[INFO] Downloaded video from s3://{self.bucket}/{s3_key} to {local_path}\n"); sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to download video from S3: {e}\n"); sys.stderr.flush()
            raise

    async def upload_preview_image(
        self,
        session_id: str,
        file_path: str
    ) -> str:
        """
        Upload preview image to S3

        Args:
            session_id: Session ID
            file_path: Local path to preview image

        Returns:
            S3 key of uploaded file
        """
        filename = Path(file_path).name
        key = f"previews/{session_id}/{filename}"

        try:
            with open(file_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.bucket,
                    key,
                    ExtraArgs={
                        'ContentType': 'image/jpeg',
                        'ServerSideEncryption': 'AES256'
                    }
                )
            sys.stderr.write(f"[INFO] Uploaded preview image to s3://{self.bucket}/{key}\n"); sys.stderr.flush()
            return key
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to upload preview image to S3: {e}\n"); sys.stderr.flush()
            raise

    async def upload_frame_measurements(
        self,
        session_id: str,
        measurements: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload frame measurements as compressed JSON to S3

        Args:
            session_id: Session ID
            measurements: List of frame measurement dictionaries
            metadata: Optional metadata dict (e.g., transition angles summary)

        Returns:
            S3 key of uploaded file
        """
        key = self._get_frames_key(session_id)

        try:
            # Create JSON structure with frames and optional metadata
            json_data = {
                "frames": measurements,
                "metadata": metadata if metadata else {}
            }

            # Convert to JSON and compress
            json_str = json.dumps(json_data, default=str)
            compressed_data = gzip.compress(json_str.encode('utf-8'))

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=compressed_data,
                ContentType='application/json',
                ContentEncoding='gzip',
                ServerSideEncryption='AES256'
            )

            size_mb = len(compressed_data) / 1024 / 1024
            sys.stderr.write(f"[INFO] Uploaded {len(measurements)} frame measurements to s3://{self.bucket}/{key} ({size_mb:.2f} MB)\n"); sys.stderr.flush()
            return key
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to upload frame measurements to S3: {e}\n"); sys.stderr.flush()
            raise

    async def get_frame_measurements(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Download and decompress frame measurements from S3

        Args:
            session_id: Session ID

        Returns:
            List of frame measurement dictionaries
        """
        key = self._get_frames_key(session_id)

        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            compressed_data = response['Body'].read()
            json_str = gzip.decompress(compressed_data).decode('utf-8')
            json_data = json.loads(json_str)

            # Handle both old format (list) and new format (dict with frames/metadata)
            metadata = {}
            if isinstance(json_data, list):
                # Old format: list of measurements
                measurements = json_data
                sys.stderr.write(f"[INFO] Downloaded {len(measurements)} frame measurements (legacy format) from s3://{self.bucket}/{key}\n"); sys.stderr.flush()
            elif isinstance(json_data, dict) and 'frames' in json_data:
                # New format: dict with frames and metadata
                measurements = json_data['frames']
                metadata = json_data.get('metadata', {})
                sys.stderr.write(f"[INFO] Downloaded {len(measurements)} frame measurements with metadata from s3://{self.bucket}/{key}\n"); sys.stderr.flush()
                if metadata:
                    sys.stderr.write(f"[INFO] Metadata keys: {list(metadata.keys())}\n"); sys.stderr.flush()
            else:
                # Unknown format
                sys.stderr.write(f"[WARNING] Unknown JSON format, attempting to use as-is\n"); sys.stderr.flush()
                measurements = json_data if isinstance(json_data, list) else []

            # Fix initial frames with white RGB values (255, 255, 255) and invalid intensity - for old stored data
            if len(measurements) >= 2:
                for papi_light in ['papi_a', 'papi_b', 'papi_c', 'papi_d']:
                    first_valid_data = None
                    first_valid_index = -1

                    # Find first frame with valid RGB (not white 255, 255, 255)
                    for idx, frame in enumerate(measurements):
                        papi_data = frame.get(papi_light)
                        if papi_data and isinstance(papi_data, dict):
                            rgb = papi_data.get('rgb')
                            if (rgb and isinstance(rgb, dict) and
                                not (rgb.get('r') == 255 and rgb.get('g') == 255 and rgb.get('b') == 255)):
                                first_valid_data = {
                                    'rgb': rgb,
                                    'intensity': papi_data.get('intensity')
                                }
                                first_valid_index = idx
                                break

                    # If we found valid data, replace all previous white/invalid values
                    if first_valid_data is not None and first_valid_index > 0:
                        for idx in range(first_valid_index):
                            frame = measurements[idx]
                            papi_data = frame.get(papi_light)
                            if papi_data and isinstance(papi_data, dict):
                                current_rgb = papi_data.get('rgb')
                                if (current_rgb and isinstance(current_rgb, dict) and
                                    current_rgb.get('r') == 255 and current_rgb.get('g') == 255 and current_rgb.get('b') == 255):
                                    papi_data['rgb'] = first_valid_data['rgb'].copy()  # Copy to avoid reference issues
                                    if first_valid_data['intensity'] is not None:
                                        papi_data['intensity'] = first_valid_data['intensity']

                        sys.stderr.write(f"[INFO] Fixed {papi_light} in loaded data: replaced {first_valid_index} white RGB/intensity frames\n"); sys.stderr.flush()

            # Return dict with frames and metadata for backward compatibility
            return {'frames': measurements, 'metadata': metadata}
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                sys.stderr.write(f"[WARNING] Frame measurements not found for session {session_id}\n"); sys.stderr.flush()
                return {'frames': [], 'metadata': {}}
            sys.stderr.write(f"[ERROR] Failed to download frame measurements from S3: {e}\n"); sys.stderr.flush()
            raise
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to process frame measurements: {e}\n"); sys.stderr.flush()
            raise

    def generate_presigned_url(
        self,
        s3_key: str,
        expires_in: int = None,
        content_disposition: str = None
    ) -> str:
        """
        Generate presigned URL for secure temporary access to S3 object

        Args:
            s3_key: S3 key of the object
            expires_in: Expiration time in seconds (default from config)
            content_disposition: Content-Disposition header for downloads

        Returns:
            Presigned URL
        """
        if expires_in is None:
            expires_in = settings.S3_PRESIGNED_URL_EXPIRATION

        try:
            params = {
                'Bucket': self.bucket,
                'Key': s3_key
            }

            if content_disposition:
                params['ResponseContentDisposition'] = content_disposition

            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expires_in
            )
            sys.stderr.write(f"[DEBUG] Generated presigned URL for {s3_key} (expires in {expires_in}s)\n"); sys.stderr.flush()
            return url
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to generate presigned URL: {e}\n"); sys.stderr.flush()
            raise

    async def delete_session_data(self, session_id: str) -> None:
        """
        Delete all S3 data for a session

        Args:
            session_id: Session ID
        """
        prefixes = [
            f"videos/original/{session_id}/",
            f"videos/processed/{session_id}/",
            f"videos/enhanced/{session_id}/",
            f"frames/{session_id}/",
            f"reports/{session_id}/",
            f"temp/{session_id}/"
        ]

        deleted_count = 0
        for prefix in prefixes:
            try:
                # List objects with prefix
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=prefix
                )

                if 'Contents' in response:
                    # Delete objects
                    objects = [{'Key': obj['Key']} for obj in response['Contents']]
                    self.s3_client.delete_objects(
                        Bucket=self.bucket,
                        Delete={'Objects': objects}
                    )
                    deleted_count += len(objects)
                    sys.stderr.write(f"[INFO] Deleted {len(objects)} objects from {prefix}\n"); sys.stderr.flush()
            except Exception as e:
                sys.stderr.write(f"[ERROR] Failed to delete objects from {prefix}: {e}\n"); sys.stderr.flush()
                # Continue with other prefixes even if one fails

        sys.stderr.write(f"[INFO] Deleted total of {deleted_count} objects for session {session_id}\n"); sys.stderr.flush()

    async def upload_report(
        self,
        session_id: str,
        file_path: str,
        report_type: str
    ) -> str:
        """
        Upload report file to S3

        Args:
            session_id: Session ID
            file_path: Local path to report file
            report_type: Type of report (pdf, html, csv)

        Returns:
            S3 key of uploaded file
        """
        key = self._get_report_key(session_id, report_type)

        content_types = {
            'pdf': 'application/pdf',
            'html': 'text/html',
            'csv': 'text/csv'
        }

        try:
            with open(file_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.bucket,
                    key,
                    ExtraArgs={
                        'ContentType': content_types.get(report_type, 'application/octet-stream'),
                        'ServerSideEncryption': 'AES256'
                    }
                )
            sys.stderr.write(f"[INFO] Uploaded report to s3://{self.bucket}/{key}\n"); sys.stderr.flush()
            return key
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to upload report to S3: {e}\n"); sys.stderr.flush()
            raise

    def check_object_exists(self, s3_key: str) -> bool:
        """
        Check if an object exists in S3

        Args:
            s3_key: S3 key to check

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise


# Singleton instance
s3_storage = S3StorageService() if settings.USE_S3_STORAGE else None


def get_s3_storage() -> Optional[S3StorageService]:
    """Get S3 storage service instance"""
    if not settings.USE_S3_STORAGE:
        raise RuntimeError("S3 storage is not enabled in configuration")
    return s3_storage
