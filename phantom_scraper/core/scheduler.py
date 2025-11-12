import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from celery import Celery
from celery.schedules import crontab
import redis
from core.scraper import PhantomScraper
from core.data_manager import DataManager

# Initialize Celery
celery_app = Celery('phantom_scraper')
celery_app.config_from_object('config.Config')

# Initialize Redis
redis_client = redis.from_url('redis://localhost:6379/0')

class TaskScheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.data_manager = DataManager()
        
    def create_scraping_task(self, task_config: Dict[str, Any]) -> str:
        """Create a new scraping task"""
        task_id = f"scrape_{int(time.time())}"
        
        # Store task configuration in Redis
        redis_client.setex(
            f"task:{task_id}", 
            3600,  # 1 hour expiry
            json.dumps(task_config)
        )
        
        # Queue the task
        scrape_task.delay(task_id, task_config)
        
        return task_id
        
    def schedule_recurring_task(self, task_config: Dict[str, Any], schedule: str) -> str:
        """Schedule a recurring task"""
        task_id = f"recurring_{int(time.time())}"
        
        # Parse schedule (e.g., "daily", "hourly", "weekly")
        if schedule == "daily":
            crontab_schedule = crontab(hour=9, minute=0)  # 9 AM daily
        elif schedule == "hourly":
            crontab_schedule = crontab(minute=0)
        elif schedule == "weekly":
            crontab_schedule = crontab(day_of_week=1, hour=9, minute=0)  # Monday 9 AM
        else:
            raise ValueError(f"Unsupported schedule: {schedule}")
            
        # Add to Celery beat schedule
        celery_app.conf.beat_schedule[f"recurring_{task_id}"] = {
            'task': 'core.scheduler.scrape_task',
            'schedule': crontab_schedule,
            'args': (task_id, task_config)
        }
        
        return task_id
        
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task"""
        # Check if task exists in Redis
        task_data = redis_client.get(f"task:{task_id}")
        if not task_data:
            return {"status": "not_found"}
            
        task_config = json.loads(task_data)
        
        # Check Celery task status
        celery_task = celery_app.AsyncResult(task_id)
        
        return {
            "status": celery_task.status,
            "result": celery_task.result if celery_task.successful() else None,
            "error": str(celery_task.result) if celery_task.failed() else None,
            "config": task_config
        }
        
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks"""
        tasks = []
        for key in redis_client.scan_iter(match="task:*"):
            task_id = key.decode('utf-8').replace("task:", "")
            task_data = redis_client.get(key)
            if task_data:
                task_config = json.loads(task_data)
                tasks.append({
                    "task_id": task_id,
                    "config": task_config,
                    "status": self.get_task_status(task_id)["status"]
                })
        return tasks

@celery_app.task(bind=True)
def scrape_task(self, task_id: str, task_config: Dict[str, Any]):
    """Celery task for scraping"""
    scraper = PhantomScraper(headless=True)
    data_manager = DataManager()
    
    try:
        # Update task status
        redis_client.setex(
            f"task_status:{task_id}",
            3600,
            json.dumps({"status": "running", "started_at": datetime.now().isoformat()})
        )
        
        # Execute scraping based on task type
        if task_config["type"] == "linkedin_profiles":
            results = scraper.scrape_linkedin_profiles(
                task_config["search_url"],
                task_config.get("max_profiles", 50)
            )
        elif task_config["type"] == "google_maps":
            results = scraper.scrape_google_maps(
                task_config["search_query"],
                task_config.get("max_results", 50)
            )
        elif task_config["type"] == "website_data":
            results = scraper.scrape_website_data(
                task_config["url"],
                task_config["selectors"]
            )
        else:
            raise ValueError(f"Unknown task type: {task_config['type']}")
            
        # Save results
        data_manager.save_data(task_id, results, task_config["type"])
        
        # Update task status
        redis_client.setex(
            f"task_status:{task_id}",
            3600,
            json.dumps({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "results_count": len(results) if isinstance(results, list) else 1
            })
        )
        
        return {"status": "success", "results_count": len(results) if isinstance(results, list) else 1}
        
    except Exception as e:
        # Update task status with error
        redis_client.setex(
            f"task_status:{task_id}",
            3600,
            json.dumps({
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            })
        )
        raise e
        
    finally:
        scraper.stop()

# Example task configurations
LINKEDIN_TASK_CONFIG = {
    "type": "linkedin_profiles",
    "search_url": "https://www.linkedin.com/search/results/people/?keywords=software%20engineer",
    "max_profiles": 100,
    "description": "Scrape LinkedIn profiles for software engineers"
}

GOOGLE_MAPS_TASK_CONFIG = {
    "type": "google_maps",
    "search_query": "restaurants near me",
    "max_results": 50,
    "description": "Scrape restaurant listings from Google Maps"
}

WEBSITE_TASK_CONFIG = {
    "type": "website_data",
    "url": "https://example.com",
    "selectors": {
        "title": "h1",
        "description": ".description",
        "links": "a"
    },
    "description": "Scrape data from example.com"
}
