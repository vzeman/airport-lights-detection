"""
API endpoints for drone image metadata extraction.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List

from app.core.deps import get_current_user
from app.models import User
from app.services.image_metadata_extractor import ImageMetadataExtractor

router = APIRouter(prefix="/drone-metadata", tags=["Drone Metadata"])

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.dng', '.tiff', '.tif'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILES = 10


@router.post("/extract")
async def extract_metadata(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Extract metadata from uploaded drone images.

    Args:
        files: List of uploaded image files
        current_user: Authenticated user

    Returns:
        Dictionary containing extracted metadata for all images
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {MAX_FILES} files allowed per request"
        )

    results = []
    successful = 0
    failed = 0

    for file in files:
        try:
            # Validate file extension
            file_ext = f".{file.filename.rsplit('.', 1)[-1].lower()}" if '.' in file.filename else ''
            if file_ext not in ALLOWED_EXTENSIONS:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
                })
                failed += 1
                continue

            # Read file content
            file_bytes = await file.read()

            # Validate file size
            if len(file_bytes) > MAX_FILE_SIZE:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB"
                })
                failed += 1
                continue

            # Extract metadata
            metadata = ImageMetadataExtractor.extract_all_metadata(file_bytes, file.filename)
            metadata["success"] = True
            results.append(metadata)
            successful += 1

        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": f"Failed to process file: {str(e)}"
            })
            failed += 1

    return {
        "images": results,
        "total_images": len(files),
        "successful": successful,
        "failed": failed
    }
