"""
S3 Storage Service for Airport Management System
Handles all S3 operations for videos, frame measurements, and reports
"""
import boto3
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
            logger.warning("S3 storage is disabled in configuration")
            return

        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket = settings.S3_BUCKET
        logger.info(f"S3 storage initialized for bucket: {self.bucket}")

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
            logger.info(f"Uploaded video to s3://{self.bucket}/{key}")
            return key
        except Exception as e:
            logger.error(f"Failed to upload video to S3: {e}")
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
            logger.info(f"Uploaded video stream to s3://{self.bucket}/{key}")
            return key
        except Exception as e:
            logger.error(f"Failed to upload video stream to S3: {e}")
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
            logger.info(f"Downloaded video from s3://{self.bucket}/{s3_key} to {local_path}")
        except Exception as e:
            logger.error(f"Failed to download video from S3: {e}")
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
            logger.info(f"Uploaded preview image to s3://{self.bucket}/{key}")
            return key
        except Exception as e:
            logger.error(f"Failed to upload preview image to S3: {e}")
            raise

    async def upload_frame_measurements(
        self,
        session_id: str,
        measurements: List[Dict[str, Any]]
    ) -> str:
        """
        Upload frame measurements as compressed JSON to S3

        Args:
            session_id: Session ID
            measurements: List of frame measurement dictionaries

        Returns:
            S3 key of uploaded file
        """
        key = self._get_frames_key(session_id)

        try:
            # Convert to JSON and compress
            json_str = json.dumps(measurements, default=str)
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
            logger.info(f"Uploaded {len(measurements)} frame measurements to s3://{self.bucket}/{key} ({size_mb:.2f} MB)")
            return key
        except Exception as e:
            logger.error(f"Failed to upload frame measurements to S3: {e}")
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
            measurements = json.loads(json_str)

            logger.info(f"Downloaded {len(measurements)} frame measurements from s3://{self.bucket}/{key}")
            return measurements
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"Frame measurements not found for session {session_id}")
                return []
            logger.error(f"Failed to download frame measurements from S3: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to process frame measurements: {e}")
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
            logger.debug(f"Generated presigned URL for {s3_key} (expires in {expires_in}s)")
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
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
                    logger.info(f"Deleted {len(objects)} objects from {prefix}")
            except Exception as e:
                logger.error(f"Failed to delete objects from {prefix}: {e}")
                # Continue with other prefixes even if one fails

        logger.info(f"Deleted total of {deleted_count} objects for session {session_id}")

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
            logger.info(f"Uploaded report to s3://{self.bucket}/{key}")
            return key
        except Exception as e:
            logger.error(f"Failed to upload report to S3: {e}")
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
