// Global app utilities
document.addEventListener('DOMContentLoaded', function() {
    console.log('PAPI Light Detection System initialized');
    
    // Add active state to current nav item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
    
    // Auto-hide alerts after 5 seconds
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            alert.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Helper function to format file sizes
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Helper function to show notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.innerHTML = `
        ${message}
        <button class="alert-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    const mainContent = document.querySelector('.main-content');
    mainContent.insertBefore(notification, mainContent.firstChild);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Helper function for API calls
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'API call failed');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        showNotification(`Error: ${error.message}`, 'error');
        throw error;
    }
}

// Add loading state to buttons
function setButtonLoading(button, loading = true) {
    if (loading) {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = 'Loading...';
    } else {
        button.disabled = false;
        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
        }
    }
}

// Image preview functionality
function previewImage(file) {
    if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.createElement('img');
            preview.src = e.target.result;
            preview.style.maxWidth = '200px';
            preview.style.maxHeight = '200px';
            preview.style.marginTop = '10px';
            
            // Add preview to upload area if exists
            const uploadArea = document.getElementById('uploadArea');
            if (uploadArea) {
                const existingPreview = uploadArea.querySelector('img');
                if (existingPreview) {
                    existingPreview.remove();
                }
                uploadArea.appendChild(preview);
            }
        };
        reader.readAsDataURL(file);
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + U: Go to upload page
    if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
        e.preventDefault();
        window.location.href = '/';
    }
    
    // Ctrl/Cmd + G: Go to gallery
    if ((e.ctrlKey || e.metaKey) && e.key === 'g') {
        e.preventDefault();
        window.location.href = '/gallery';
    }
    
    // Ctrl/Cmd + R: Go to reports
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        window.location.href = '/reports';
    }
});

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateY(0);
            opacity: 1;
        }
        to {
            transform: translateY(-20px);
            opacity: 0;
        }
    }
    
    .nav-link.active {
        color: #667eea;
        font-weight: 600;
    }
`;
document.head.appendChild(style);