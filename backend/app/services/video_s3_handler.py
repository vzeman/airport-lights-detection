"""
Video S3 Handler - Manages video and frame measurement storage with S3
This module provides a clean interface for video processing with S3 integration
"""
import os
import sys
import logging
import tempfile
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.core.config import settings
from app.services.s3_storage import get_s3_storage
from app.schemas.frame_measurement import convert_flat_dict_to_nested

logger = logging.getLogger(__name__)


class VideoS3Handler:
    """Handles video storage with S3 integration"""

    def __init__(self):
        self.s3 = get_s3_storage()
        sys.stderr.write(f"[INFO] VideoS3Handler initialized with S3 storage\n"); sys.stderr.flush()

    async def save_uploaded_video(
        self,
        session_id: str,
        video_content: bytes,
        filename: str
    ) -> tuple[str, Optional[str]]:
        """
        Save uploaded video - to S3 if enabled, otherwise locally

        Args:
            session_id: Session ID
            video_content: Video file content as bytes
            filename: Original filename

        Returns:
            Tuple of (local_temp_path, s3_key)
            local_temp_path: Temporary local path for processing
            s3_key: S3 key if uploaded to S3, None otherwise
        """
        # Create temp file for processing
        temp_dir = Path(settings.TEMP_PATH) / session_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_path = temp_dir / filename

        # Save locally first (needed for processing)
        with open(local_path, 'wb') as f:
            f.write(video_content)

        sys.stderr.write(f"[INFO] Saved video locally to {local_path}\n"); sys.stderr.flush()

        # Upload to S3
        s3_key = await self.s3.upload_video(
            session_id=session_id,
            file_path=str(local_path),
            video_type="original"
        )
        sys.stderr.write(f"[INFO] Uploaded original video to S3: {s3_key}\n"); sys.stderr.flush()

        return str(local_path), s3_key

    async def save_processed_video(
        self,
        session_id: str,
        video_path: str,
        video_type: str
    ) -> str:
        """
        Save processed video to S3

        Args:
            session_id: Session ID
            video_path: Local path to processed video
            video_type: Type of video (enhanced, enhanced_with_audio, etc.)

        Returns:
            S3 key
        """
        s3_key = await self.s3.upload_video(
            session_id=session_id,
            file_path=video_path,
            video_type=video_type
        )
        sys.stderr.write(f"[INFO] Uploaded {video_type} video to S3: {s3_key}\n"); sys.stderr.flush()
        return s3_key

    async def save_frame_measurements(
        self,
        session_id: str,
        measurements: List[Any]
    ) -> str:
        """
        Save frame measurements to S3 as compressed JSON

        Args:
            session_id: Session ID
            measurements: List of measurement dicts

        Returns:
            S3 key
        """
        # Convert flat dict structure to nested format
        measurements_dict = []
        for m in measurements:
            if isinstance(m, dict) and 'papi_a_status' in m:
                # Flat dict structure - convert to nested
                measurements_dict.append(convert_flat_dict_to_nested(m))
            else:
                # Already in nested format
                measurements_dict.append(m)

        # Fix initial frames with white RGB values (255, 255, 255) and invalid intensity
        # Find first frame with valid color and apply to all previous white frames
        if len(measurements_dict) >= 2:
            # Track first valid data for each PAPI light
            for papi_light in ['papi_a', 'papi_b', 'papi_c', 'papi_d']:
                first_valid_data = None
                first_valid_index = -1

                # Find first frame with valid RGB (not white 255, 255, 255)
                for idx, frame in enumerate(measurements_dict):
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
                        frame = measurements_dict[idx]
                        papi_data = frame.get(papi_light)
                        if papi_data and isinstance(papi_data, dict):
                            current_rgb = papi_data.get('rgb')
                            if (current_rgb and isinstance(current_rgb, dict) and
                                current_rgb.get('r') == 255 and current_rgb.get('g') == 255 and current_rgb.get('b') == 255):
                                papi_data['rgb'] = first_valid_data['rgb']
                                if first_valid_data['intensity'] is not None:
                                    papi_data['intensity'] = first_valid_data['intensity']

                    sys.stderr.write(f"[INFO] Fixed {papi_light}: replaced {first_valid_index} white RGB/intensity frames\n"); sys.stderr.flush()

        s3_key = await self.s3.upload_frame_measurements(
            session_id=session_id,
            measurements=measurements_dict
        )
        sys.stderr.write(f"[INFO] Uploaded {len(measurements_dict)} frame measurements to S3: {s3_key}\n"); sys.stderr.flush()
        return s3_key

    async def get_frame_measurements(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get frame measurements from S3

        Args:
            session_id: Session ID

        Returns:
            List of frame measurement dicts
        """
        measurements = await self.s3.get_frame_measurements(session_id)
        sys.stderr.write(f"[INFO] Retrieved {len(measurements)} frame measurements from S3\n"); sys.stderr.flush()
        return measurements

    def cleanup_local_files(
        self,
        session_id: str,
        *file_paths: str
    ) -> None:
        """
        Clean up local files after S3 upload

        Args:
            session_id: Session ID
            *file_paths: Variable number of file paths to delete
        """
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    sys.stderr.write(f"[INFO] Deleted local file: {file_path}\n"); sys.stderr.flush()
                except Exception as e:
                    sys.stderr.write(f"[WARNING] Failed to delete local file {file_path}: {e}\n"); sys.stderr.flush()

        # Clean up temp directory if empty
        temp_dir = Path(settings.TEMP_PATH) / session_id
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
                sys.stderr.write(f"[INFO] Deleted temp directory: {temp_dir}\n"); sys.stderr.flush()
            except OSError:
                # Directory not empty, that's okay
                pass

    def get_video_url(
        self,
        session: Any,
        video_type: str = "enhanced"
    ) -> Optional[str]:
        """
        Get video URL - presigned URL for S3, local path otherwise

        Args:
            session: MeasurementSession object
            video_type: Type of video (original, enhanced, enhanced_with_audio)

        Returns:
            Video URL or None
        """
        if session.storage_type == "s3":
            # Map video type to S3 key field
            key_map = {
                "original": session.original_video_s3_key,
                "enhanced": session.enhanced_video_s3_key,
                "enhanced_with_audio": session.enhanced_audio_video_s3_key,
                "papi_a": session.papi_a_video_s3_key,
                "papi_b": session.papi_b_video_s3_key,
                "papi_c": session.papi_c_video_s3_key,
                "papi_d": session.papi_d_video_s3_key
            }

            s3_key = key_map.get(video_type)
            if not s3_key:
                return None

            try:
                # Generate presigned URL (valid for 1 hour)
                url = self.s3.generate_presigned_url(
                    s3_key,
                    expires_in=3600
                )
                return url
            except Exception as e:
                sys.stderr.write(f"[ERROR] Failed to generate presigned URL: {e}\n"); sys.stderr.flush()
                return None
        else:
            # Return local file path
            if video_type == "original":
                return session.video_file_path
            else:
                # Construct local path
                video_dir = Path(settings.VIDEO_PATH) / session.id
                filename_map = {
                    "enhanced": "enhanced.mp4",
                    "enhanced_with_audio": "enhanced_with_audio.mp4"
                }
                filename = filename_map.get(video_type, f"{video_type}.mp4")
                return str(video_dir / filename)

    async def delete_session_data(self, session_id: str) -> None:
        """
        Delete all session data from S3

        Args:
            session_id: Session ID
        """
        try:
            await self.s3.delete_session_data(session_id)
            sys.stderr.write(f"[INFO] Deleted S3 data for session {session_id}\n"); sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to delete S3 data for session {session_id}: {e}\n"); sys.stderr.flush()


# Singleton instance
video_s3_handler = VideoS3Handler()


def get_video_s3_handler() -> VideoS3Handler:
    """Get video S3 handler instance"""
    return video_s3_handler
