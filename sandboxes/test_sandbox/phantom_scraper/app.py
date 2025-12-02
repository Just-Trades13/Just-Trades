from flask import Flask, render_template, request, jsonify, send_file
import json
import os
from core.scheduler import TaskScheduler
from core.data_manager import DataManager
from core.scraper import PhantomScraper
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Initialize components
scheduler = TaskScheduler()
data_manager = DataManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    """Main dashboard"""
    stats = data_manager.get_statistics()
    tasks = data_manager.list_tasks()
    return render_template('index.html', stats=stats, tasks=tasks)

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks"""
    tasks = data_manager.list_tasks()
    return jsonify(tasks)

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new scraping task"""
    try:
        task_config = request.json
        
        # Validate required fields
        required_fields = ['type', 'name', 'description']
        for field in required_fields:
            if field not in task_config:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create task based on type
        if task_config['type'] == 'linkedin_profiles':
            if 'search_url' not in task_config:
                return jsonify({'error': 'search_url is required for LinkedIn tasks'}), 400
                
            task_id = scheduler.create_scraping_task({
                'type': 'linkedin_profiles',
                'search_url': task_config['search_url'],
                'max_profiles': task_config.get('max_profiles', 50),
                'name': task_config['name'],
                'description': task_config['description']
            })
            
        elif task_config['type'] == 'google_maps':
            if 'search_query' not in task_config:
                return jsonify({'error': 'search_query is required for Google Maps tasks'}), 400
                
            task_id = scheduler.create_scraping_task({
                'type': 'google_maps',
                'search_query': task_config['search_query'],
                'max_results': task_config.get('max_results', 50),
                'name': task_config['name'],
                'description': task_config['description']
            })
            
        elif task_config['type'] == 'website_data':
            if 'url' not in task_config or 'selectors' not in task_config:
                return jsonify({'error': 'url and selectors are required for website tasks'}), 400
                
            task_id = scheduler.create_scraping_task({
                'type': 'website_data',
                'url': task_config['url'],
                'selectors': task_config['selectors'],
                'name': task_config['name'],
                'description': task_config['description']
            })
            
        else:
            return jsonify({'error': 'Invalid task type'}), 400
            
        return jsonify({'task_id': task_id, 'status': 'created'})
        
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """Get specific task details"""
    task_data = data_manager.get_data(task_id)
    if not task_data:
        return jsonify({'error': 'Task not found'}), 404
        
    return jsonify(task_data)

@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Get task status"""
    status = scheduler.get_task_status(task_id)
    return jsonify(status)

@app.route('/api/tasks/<task_id>/export', methods=['GET'])
def export_task_data(task_id):
    """Export task data"""
    try:
        format_type = request.args.get('format', 'csv')
        filepath = data_manager.export_data(task_id, format_type)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    try:
        data_manager.delete_task(task_id)
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/schedule', methods=['POST'])
def schedule_recurring_task():
    """Schedule a recurring task"""
    try:
        task_config = request.json
        schedule = task_config.get('schedule', 'daily')
        
        task_id = scheduler.schedule_recurring_task(task_config, schedule)
        return jsonify({'task_id': task_id, 'status': 'scheduled'})
        
    except Exception as e:
        logger.error(f"Error scheduling task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-scraper', methods=['POST'])
def test_scraper():
    """Test scraper with a single URL"""
    try:
        test_config = request.json
        scraper = PhantomScraper(headless=True)
        
        if test_config['type'] == 'website_data':
            results = scraper.scrape_website_data(
                test_config['url'],
                test_config['selectors']
            )
        else:
            return jsonify({'error': 'Only website_data type supported for testing'}), 400
            
        scraper.stop()
        return jsonify({'results': results})
        
    except Exception as e:
        logger.error(f"Error testing scraper: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get scraping statistics"""
    stats = data_manager.get_statistics()
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
