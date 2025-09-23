from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename
from werkzeug.security import safe_join
import os
import json
import shutil
from datetime import datetime, timedelta
import subprocess
import threading
import queue
from pathlib import Path
import logging
import hashlib
import uuid
from PIL import Image
import fcntl
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration from environment or use secure defaults
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['REPORTS_FOLDER'] = os.environ.get('REPORTS_FOLDER', 'reports')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_FILE_SIZE', 16 * 1024 * 1024))  # 16MB default
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
app.config['MAX_IMAGE_DIMENSIONS'] = (4000, 4000)  # Max width, height
app.config['PORT'] = int(os.environ.get('PORT', 5000))
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

# Ensure required directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORTS_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Processing queue and status tracking with thread-safe locks
processing_queue = queue.Queue()
processing_status = {}
processing_status_lock = threading.Lock()
active_processing = {}  # Track active processing jobs
active_processing_lock = threading.Lock()

# File locks for upload operations
upload_locks = {}
upload_locks_lock = threading.Lock()

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def cleanup_old_status():
    """Remove old processing status entries to prevent memory leak"""
    cutoff = datetime.now() - timedelta(hours=1)
    with processing_status_lock:
        jobs_to_remove = []
        for job_id, status in processing_status.items():
            if status.get('started'):
                try:
                    job_time = datetime.fromisoformat(status['started'])
                    if job_time < cutoff and status.get('status') in ['completed', 'error']:
                        jobs_to_remove.append(job_id)
                except (ValueError, TypeError):
                    continue
        
        for job_id in jobs_to_remove:
            del processing_status[job_id]
            logger.info(f"Cleaned up old job: {job_id}")

def validate_image(filepath):
    """Validate image dimensions and format"""
    try:
        img = Image.open(filepath)
        width, height = img.size
        max_width, max_height = app.config['MAX_IMAGE_DIMENSIONS']
        
        if width > max_width or height > max_height:
            return False, f"Image too large. Max dimensions: {max_width}x{max_height}, got {width}x{height}"
        
        # Verify it's actually an image
        img.verify()
        return True, None
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

def get_unique_filename(base_filename):
    """Generate unique filename to avoid conflicts"""
    filename = secure_filename(base_filename)
    name, ext = os.path.splitext(filename)
    # Add timestamp and unique ID
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}_{name}{ext}"

@app.route('/')
def index():
    """Home page with upload interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload with validation and thread safety"""
    if 'file' not in request.files:
        logger.warning("Upload attempt with no file part")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("Upload attempt with no selected file")
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename to prevent conflicts
        filename = get_unique_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save to temporary file first
        temp_file = tempfile.NamedTemporaryFile(delete=False, dir=app.config['UPLOAD_FOLDER'])
        try:
            file.save(temp_file.name)
            
            # Validate image
            valid, error_msg = validate_image(temp_file.name)
            if not valid:
                os.remove(temp_file.name)
                logger.warning(f"Invalid image upload: {error_msg}")
                return jsonify({'error': error_msg}), 400
            
            # Move to final location with file locking
            with upload_locks_lock:
                if filename not in upload_locks:
                    upload_locks[filename] = threading.Lock()
                
            with upload_locks[filename]:
                os.rename(temp_file.name, filepath)
            
            logger.info(f"File uploaded successfully: {filename}")
            return jsonify({
                'success': True,
                'filename': filename,
                'filepath': filepath,
                'message': f'File {filename} uploaded successfully'
            }), 200
            
        except Exception as e:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            logger.error(f"Upload error: {str(e)}")
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    
    logger.warning(f"Invalid file type attempted: {file.filename}")
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/gallery')
def gallery():
    """Display uploaded images gallery"""
    images = []
    upload_dir = app.config['UPLOAD_FOLDER']
    
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            if allowed_file(filename):
                filepath = os.path.join(upload_dir, filename)
                images.append({
                    'filename': filename,
                    'path': filepath,
                    'size': os.path.getsize(filepath),
                    'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
                })
    
    # Sort by modification time, newest first
    images.sort(key=lambda x: x['modified'], reverse=True)
    
    return render_template('gallery.html', images=images)

@app.route('/process/<filename>')
def process_image(filename):
    """Process a single image with duplicate checking"""
    # Validate filename
    filename = secure_filename(filename)
    filepath = safe_join(app.config['UPLOAD_FOLDER'], filename)
    
    if not filepath or not os.path.exists(filepath):
        logger.warning(f"Process request for non-existent file: {filename}")
        flash('Image not found', 'error')
        return redirect(url_for('gallery'))
    
    # Check if already processing
    with active_processing_lock:
        if filename in active_processing:
            job_id = active_processing[filename]
            logger.info(f"Image already processing: {filename} with job {job_id}")
            return render_template('process.html', job_id=job_id, filename=filename)
    
    # Add to processing queue
    job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    with processing_status_lock:
        processing_status[job_id] = {
            'status': 'queued',
            'filename': filename,
            'started': datetime.now().isoformat(),
            'progress': 0
        }
    
    with active_processing_lock:
        active_processing[filename] = job_id
    
    # Clean up old status entries periodically
    cleanup_old_status()
    
    # Start processing in background thread
    thread = threading.Thread(target=process_image_background, args=(job_id, filepath, filename))
    thread.daemon = False  # Allow proper cleanup
    thread.start()
    
    logger.info(f"Started processing job {job_id} for {filename}")
    return render_template('process.html', job_id=job_id, filename=filename)

def process_image_background(job_id, filepath, filename):
    """Background processing of image with improved error handling"""
    try:
        with processing_status_lock:
            processing_status[job_id]['status'] = 'processing'
            processing_status[job_id]['progress'] = 25
        
        logger.info(f"Processing started for job {job_id}")
        
        # Create reports directory for this job
        reports_dir = app.config['REPORTS_FOLDER']
        os.makedirs(reports_dir, exist_ok=True)
        
        with processing_status_lock:
            processing_status[job_id]['progress'] = 50
        
        # Run the main processing script with correct arguments
        result = subprocess.run(
            ['python', 'main.py', '--image', filepath, '--output', reports_dir],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        with processing_status_lock:
            processing_status[job_id]['progress'] = 75
        
        if result.returncode == 0:
            # Find the generated report (it will be in a subdirectory)
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            
            # Look for HTML reports in subdirectories
            report_found = False
            for root, dirs, files in os.walk(reports_dir):
                for file in files:
                    if file.endswith('.html') and base_name in file:
                        # Store the relative path from reports directory
                        rel_path = os.path.relpath(os.path.join(root, file), reports_dir)
                        with processing_status_lock:
                            processing_status[job_id]['report'] = rel_path
                        report_found = True
                        break
                if report_found:
                    break
            
            with processing_status_lock:
                processing_status[job_id]['status'] = 'completed'
                processing_status[job_id]['progress'] = 100
                processing_status[job_id]['message'] = 'Processing completed successfully'
                processing_status[job_id]['output'] = result.stdout[:1000]  # Limit output size
            
            logger.info(f"Processing completed for job {job_id}")
        else:
            error_msg = result.stderr or result.stdout
            
            # Parse specific error types for better user messages
            if "FileNotFoundError" in error_msg:
                user_msg = "Image file not found during processing"
            elif "MemoryError" in error_msg:
                user_msg = "Insufficient memory to process image"
            elif "timeout" in error_msg.lower():
                user_msg = "Processing timeout - image may be too complex"
            else:
                user_msg = f"Processing failed: {error_msg[:200]}"
            
            with processing_status_lock:
                processing_status[job_id]['status'] = 'error'
                processing_status[job_id]['error'] = error_msg[:1000]  # Limit error size
                processing_status[job_id]['message'] = user_msg
            
            logger.error(f"Processing failed for job {job_id}: {user_msg}")
        
    except subprocess.TimeoutExpired:
        with processing_status_lock:
            processing_status[job_id]['status'] = 'error'
            processing_status[job_id]['error'] = 'Processing timeout'
            processing_status[job_id]['message'] = 'Processing took too long and was terminated'
        logger.error(f"Processing timeout for job {job_id}")
        
    except Exception as e:
        with processing_status_lock:
            processing_status[job_id]['status'] = 'error'
            processing_status[job_id]['error'] = str(e)[:1000]
            processing_status[job_id]['message'] = f'Processing error: {str(e)[:200]}'
        logger.exception(f"Processing error for job {job_id}")
        
    finally:
        # Remove from active processing
        with active_processing_lock:
            if filename in active_processing and active_processing[filename] == job_id:
                del active_processing[filename]

@app.route('/process/status/<job_id>')
def process_status(job_id):
    """Get processing status with thread safety"""
    with processing_status_lock:
        if job_id in processing_status:
            return jsonify(processing_status[job_id].copy())
    return jsonify({'error': 'Job not found'}), 404

@app.route('/reports')
def reports():
    """Display all generated reports"""
    report_list = []
    reports_dir = app.config['REPORTS_FOLDER']
    
    if os.path.exists(reports_dir):
        # Look for HTML files in subdirectories
        for root, dirs, files in os.walk(reports_dir):
            for filename in files:
                if filename.endswith('.html'):
                    filepath = os.path.join(root, filename)
                    # Get relative path for web access
                    rel_path = os.path.relpath(filepath, reports_dir)
                    report_list.append({
                        'filename': filename,
                        'display_name': f"{os.path.basename(root)} - {filename}",
                        'path': rel_path,
                        'full_path': filepath,
                        'size': os.path.getsize(filepath),
                        'created': datetime.fromtimestamp(os.path.getctime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
                    })
    
    # Sort by creation time, newest first
    report_list.sort(key=lambda x: x['created'], reverse=True)
    
    return render_template('reports.html', reports=report_list)

@app.route('/reports/view/<path:filename>')
def view_report(filename):
    """View a specific report with path traversal protection"""
    # Sanitize path to prevent directory traversal
    filepath = safe_join(app.config['REPORTS_FOLDER'], filename)
    
    if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
        logger.info(f"Serving report: {filename}")
        return send_file(filepath)
    
    logger.warning(f"Report not found or invalid path: {filename}")
    flash('Report not found', 'error')
    return redirect(url_for('reports'))

@app.route('/reports/delete/<path:filename>', methods=['POST'])
def delete_report(filename):
    """Delete a report with path validation"""
    # Sanitize path to prevent directory traversal
    filepath = safe_join(app.config['REPORTS_FOLDER'], filename)
    
    if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
        try:
            os.remove(filepath)
            logger.info(f"Report deleted: {filename}")
            return jsonify({'success': True, 'message': 'Report deleted'})
        except Exception as e:
            logger.error(f"Failed to delete report {filename}: {str(e)}")
            return jsonify({'error': f'Failed to delete: {str(e)}'}), 500
    
    logger.warning(f"Attempt to delete non-existent report: {filename}")
    return jsonify({'error': 'Report not found'}), 404

@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded images with path validation"""
    # Sanitize filename
    filename = secure_filename(filename)
    filepath = safe_join(app.config['UPLOAD_FOLDER'], filename)
    
    if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
        return send_file(filepath)
    
    logger.warning(f"Attempt to access non-existent upload: {filename}")
    return jsonify({'error': 'File not found'}), 404

@app.route('/images/delete/<filename>', methods=['POST'])
def delete_image(filename):
    """Delete an uploaded image with validation"""
    # Sanitize filename
    filename = secure_filename(filename)
    filepath = safe_join(app.config['UPLOAD_FOLDER'], filename)
    
    if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
        try:
            # Check if image is currently being processed
            with active_processing_lock:
                if filename in active_processing:
                    return jsonify({'error': 'Cannot delete image while processing'}), 409
            
            os.remove(filepath)
            logger.info(f"Image deleted: {filename}")
            return jsonify({'success': True, 'message': 'Image deleted'})
        except Exception as e:
            logger.error(f"Failed to delete image {filename}: {str(e)}")
            return jsonify({'error': f'Failed to delete: {str(e)}'}), 500
    
    logger.warning(f"Attempt to delete non-existent image: {filename}")
    return jsonify({'error': 'Image not found'}), 404

@app.route('/batch-process', methods=['POST'])
def batch_process():
    """Process multiple images with validation"""
    data = request.get_json()
    filenames = data.get('filenames', [])
    
    if not filenames:
        return jsonify({'error': 'No filenames provided'}), 400
    
    if len(filenames) > 50:
        return jsonify({'error': 'Too many files. Max 50 at once'}), 400
    
    job_ids = []
    skipped = []
    
    for filename in filenames:
        # Sanitize filename
        filename = secure_filename(filename)
        filepath = safe_join(app.config['UPLOAD_FOLDER'], filename)
        
        if filepath and os.path.exists(filepath):
            # Check if already processing
            with active_processing_lock:
                if filename in active_processing:
                    skipped.append(filename)
                    continue
            
            job_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            with processing_status_lock:
                processing_status[job_id] = {
                    'status': 'queued',
                    'filename': filename,
                    'started': datetime.now().isoformat(),
                    'progress': 0
                }
            
            with active_processing_lock:
                active_processing[filename] = job_id
            
            thread = threading.Thread(target=process_image_background, args=(job_id, filepath, filename))
            thread.daemon = False
            thread.start()
            
            job_ids.append(job_id)
        else:
            skipped.append(filename)
    
    # Clean up old status entries
    cleanup_old_status()
    
    message = f'Started processing {len(job_ids)} images'
    if skipped:
        message += f' (skipped {len(skipped)} invalid or processing files)'
    
    logger.info(f"Batch processing started: {len(job_ids)} jobs")
    
    return jsonify({
        'success': True,
        'job_ids': job_ids,
        'skipped': skipped,
        'message': message
    })

# Background cleanup thread
def periodic_cleanup():
    """Periodically clean up old processing status entries"""
    while True:
        try:
            cleanup_old_status()
            threading.Event().wait(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Cleanup thread error: {str(e)}")
            threading.Event().wait(60)  # Retry after 1 minute

if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=periodic_cleanup)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    
    # Log startup information
    logger.info(f"Starting PAPI Detection Web UI on port {app.config['PORT']}")
    logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"Reports folder: {app.config['REPORTS_FOLDER']}")
    
    app.run(debug=app.config['DEBUG'], port=app.config['PORT'])