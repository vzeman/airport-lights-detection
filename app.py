from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename
import os
import json
import shutil
from datetime import datetime
import subprocess
import threading
import queue
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = 'papi-detector-secret-key-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['REPORTS_FOLDER'] = 'reports'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Ensure required directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORTS_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Processing queue and status tracking
processing_queue = queue.Queue()
processing_status = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    """Home page with upload interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to filename to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': filepath,
            'message': f'File {filename} uploaded successfully'
        }), 200
    
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
    """Process a single image"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        flash('Image not found', 'error')
        return redirect(url_for('gallery'))
    
    # Add to processing queue
    job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    processing_status[job_id] = {
        'status': 'queued',
        'filename': filename,
        'started': datetime.now().isoformat(),
        'progress': 0
    }
    
    # Start processing in background thread
    thread = threading.Thread(target=process_image_background, args=(job_id, filepath, filename))
    thread.daemon = True
    thread.start()
    
    return render_template('process.html', job_id=job_id, filename=filename)

def process_image_background(job_id, filepath, filename):
    """Background processing of image"""
    try:
        processing_status[job_id]['status'] = 'processing'
        processing_status[job_id]['progress'] = 25
        
        # Create reports directory for this job
        reports_dir = app.config['REPORTS_FOLDER']
        os.makedirs(reports_dir, exist_ok=True)
        
        processing_status[job_id]['progress'] = 50
        
        # Run the main processing script with correct arguments
        result = subprocess.run(
            ['python', 'main.py', '--image', filepath, '--output', reports_dir],
            capture_output=True,
            text=True
        )
        
        processing_status[job_id]['progress'] = 75
        
        if result.returncode == 0:
            # Find the generated report (it will be in a subdirectory)
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            
            # Look for HTML reports in subdirectories
            for root, dirs, files in os.walk(reports_dir):
                for file in files:
                    if file.endswith('.html') and base_name in file:
                        # Store the relative path from reports directory
                        rel_path = os.path.relpath(os.path.join(root, file), reports_dir)
                        processing_status[job_id]['report'] = rel_path
                        break
                if 'report' in processing_status[job_id]:
                    break
            
            processing_status[job_id]['status'] = 'completed'
            processing_status[job_id]['progress'] = 100
            processing_status[job_id]['message'] = 'Processing completed successfully'
            processing_status[job_id]['output'] = result.stdout
        else:
            processing_status[job_id]['status'] = 'error'
            processing_status[job_id]['error'] = result.stderr or result.stdout
            processing_status[job_id]['message'] = 'Processing failed'
        
    except Exception as e:
        processing_status[job_id]['status'] = 'error'
        processing_status[job_id]['error'] = str(e)
        processing_status[job_id]['message'] = f'Processing error: {str(e)}'

@app.route('/process/status/<job_id>')
def process_status(job_id):
    """Get processing status"""
    if job_id in processing_status:
        return jsonify(processing_status[job_id])
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
    """View a specific report"""
    filepath = os.path.join(app.config['REPORTS_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    flash('Report not found', 'error')
    return redirect(url_for('reports'))

@app.route('/reports/delete/<path:filename>', methods=['POST'])
def delete_report(filename):
    """Delete a report"""
    filepath = os.path.join(app.config['REPORTS_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'success': True, 'message': 'Report deleted'})
    return jsonify({'error': 'Report not found'}), 404

@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded images"""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/images/delete/<filename>', methods=['POST'])
def delete_image(filename):
    """Delete an uploaded image"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'success': True, 'message': 'Image deleted'})
    return jsonify({'error': 'Image not found'}), 404

@app.route('/batch-process', methods=['POST'])
def batch_process():
    """Process multiple images"""
    data = request.get_json()
    filenames = data.get('filenames', [])
    
    job_ids = []
    for filename in filenames:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            job_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            processing_status[job_id] = {
                'status': 'queued',
                'filename': filename,
                'started': datetime.now().isoformat(),
                'progress': 0
            }
            
            thread = threading.Thread(target=process_image_background, args=(job_id, filepath, filename))
            thread.daemon = True
            thread.start()
            
            job_ids.append(job_id)
    
    return jsonify({
        'success': True,
        'job_ids': job_ids,
        'message': f'Started processing {len(job_ids)} images'
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)