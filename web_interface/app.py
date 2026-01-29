import sys
import os

# Add project root to Python path if not already there
# This allows imports to work when running from any directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, request, jsonify, render_template
from config.settings import SettingsManager
from config.validation import DEFAULT_SETTINGS
from monitoring.metrics import SystemMetrics
from monitoring.system_utils import format_uptime
from config.station_id_maps import station_id_maps
from config.constants import API_KEY_MIN_LENGTH, WEB_SERVER_PORT
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Changed from INFO to WARNING to reduce noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app with templates in the same directory
app = Flask(__name__, template_folder='templates')

# Reduce Flask's own logging noise
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('flask').setLevel(logging.ERROR)

settings_manager = SettingsManager()
metrics = SystemMetrics(is_writer=False)  # Website reads from shared metrics file

@app.route('/health')
def health_check():
    """Health check endpoint."""
    try:
        health_status = metrics.get_health_status()
        status_code = 200 if health_status['healthy'] else 503
        return jsonify(health_status), status_code
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'healthy': False,
            'error': str(e)
        }), 500

@app.route('/metrics')
def get_metrics():
    """Get system metrics."""
    try:
        return jsonify({
            'health': metrics.get_health_status(),
            'performance': metrics.get_performance_metrics()
        })
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return jsonify({'error': str(e)}), 500

# Station tracking endpoints removed for stable version

@app.route('/system_status')
def get_system_status():
    """Get system status for web interface display."""
    try:
        health_status = metrics.get_health_status()
        performance_metrics = metrics.get_performance_metrics()
        
        # Format uptimes for display using shared utility
        session_uptime_str = format_uptime(health_status.get('session_uptime_seconds', 0))
        total_uptime_str = format_uptime(health_status.get('total_uptime_seconds', 0))
        
        # Determine overall system health
        overall_healthy = health_status.get('healthy', False)
        
        # Check individual component health
        api_healthy = health_status.get('api_healthy', False)
        led_healthy = health_status.get('led_healthy', False)
        
        # Create detailed status
        system_status = {
            'overall_healthy': overall_healthy,
            'session_uptime': session_uptime_str,
            'total_uptime': total_uptime_str,
            'session_start_time': health_status.get('session_start_time', 'Unknown'),
            'first_start_time': health_status.get('first_start_time', 'Unknown'),
            'active_vehicles': health_status.get('active_vehicles', 0),
            'display_mode': health_status.get('display_mode', 'Unknown'),
            'last_led_update': health_status.get('last_led_update', 'Unknown'),
            'last_api_success': health_status.get('last_api_success', 'Unknown'),
            'memory_usage': health_status.get('memory_usage'),
            'cpu_temperature': health_status.get('cpu_temperature'),
            'components': {
                'api': {
                    'healthy': api_healthy,
                    'status': 'Healthy' if api_healthy else 'Unhealthy',
                    'details': 'MBTA API connection working' if api_healthy else 'MBTA API connection issues'
                },
                'led': {
                    'healthy': led_healthy,
                    'status': 'Healthy' if led_healthy else 'Unhealthy',
                    'details': 'LED display working' if led_healthy else 'LED display issues'
                }
            },
            'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify(system_status)
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return jsonify({
            'overall_healthy': False,
            'error': str(e),
            'components': {
                'api': {'healthy': False, 'status': 'Error', 'details': 'Unable to check status'},
                'led': {'healthy': False, 'status': 'Error', 'details': 'Unable to check status'}
            }
        }), 500

@app.route('/')
def index():
    try:
        # Force reload to ensure we get the most current settings
        # This prevents issues with cached environment variables
        settings = settings_manager.force_reload()
            
        # If settings is empty, try to load defaults or show error
        if not settings:
            logger.warning("No settings found, attempting to load defaults")
            settings = settings_manager.get_default_settings()
            if not settings:
                logger.error("No default settings available")
                settings = {}
        
        # Convert settings keys to uppercase to match the template expectations
        template_settings = {k.upper(): v for k, v in settings.items()}
        
        # Mask the API key if it exists
        if 'MBTA_API_KEY' in template_settings:
            template_settings['MBTA_API_KEY'] = '********' if template_settings['MBTA_API_KEY'] else ''
            
        # Update the template settings to include the rainbow mode and display mode
        template_settings['RAINBOW_MODE'] = settings.get('rainbow_mode', 'off')
        template_settings['DISPLAY_MODE'] = settings.get('display_mode', 'vehicles')
        template_settings['SHOW_DEBUGGER_OPTIONS'] = settings.get('show_debugger_options', False)
        
        return render_template('index.html', settings=template_settings)
    except Exception as e:
        logger.error(f"Error loading settings for index page: {e}", exc_info=True)
        # Create a minimal default settings dict from DEFAULT_SETTINGS (converted to uppercase keys)
        default_settings = {k.upper(): v for k, v in DEFAULT_SETTINGS.items()}
        # Add any additional template-specific defaults
        default_settings['RAINBOW_MODE'] = 'off'
        return render_template('index.html', settings=default_settings)

@app.route('/save_settings', methods=['POST'])
def save_settings_route():
    try:
        settings = request.json
        # Convert settings keys to lowercase for storage
        storage_settings = {k.lower(): v for k, v in settings.items()}
        
        # Handle API key preservation - only update if a valid new key is provided
        api_key = storage_settings.get('mbta_api_key', '')
        should_preserve_existing = (
            api_key == '********' or  # Masked key from frontend
            api_key == '' or          # Empty string
            api_key is None or        # None value
            api_key == 'None' or      # String 'None'
            (isinstance(api_key, str) and len(api_key.strip()) < API_KEY_MIN_LENGTH)  # Too short to be valid
        )
        
        if should_preserve_existing:
            # Get current settings to preserve existing API key
            current_settings = settings_manager.check_and_reload()
            if current_settings is None:
                current_settings = settings_manager.load_settings()
            
            if current_settings and current_settings.get('mbta_api_key'):
                storage_settings['mbta_api_key'] = current_settings['mbta_api_key']
            else:
                # No existing key, set to None
                storage_settings['mbta_api_key'] = None
        
        # Save all settings to the configuration file
        settings_manager.save_settings(storage_settings)
        
        # Force reload to ensure the new settings are immediately available
        # This prevents caching issues with python-decouple
        settings_manager.force_reload()
        
        return jsonify(message='Settings saved!')
    except Exception as e:
        logger.error(f"Error saving settings: {e}", exc_info=True)
        return jsonify(message=f'Error saving settings: {str(e)}'), 500

@app.route('/get_settings', methods=['GET'])
def get_settings():
    try:
        # Force reload to ensure we get the most current settings
        # This prevents issues with cached environment variables
        settings = settings_manager.force_reload()
            
        # Convert settings keys to uppercase for consistency with frontend
        response_settings = {k.upper(): v for k, v in settings.items()}
        
        # Mask the API key if it exists
        if 'MBTA_API_KEY' in response_settings:
            response_settings['MBTA_API_KEY'] = '********' if response_settings['MBTA_API_KEY'] else ''
            
        return jsonify(response_settings)
    except Exception as e:
        logger.error(f"Error loading settings: {e}", exc_info=True)
        return jsonify(message=f'Error loading settings: {str(e)}'), 500

if __name__ == '__main__':
    # Reduce Flask output noise
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT, debug=False, use_reloader=False)