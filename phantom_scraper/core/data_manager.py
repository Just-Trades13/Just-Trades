import json
import csv
import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import sqlite3
import logging

class DataManager:
    def __init__(self, db_path: str = "phantom_scraper.db"):
        self.db_path = db_path
        self.output_dir = "output"
        self.logger = logging.getLogger(__name__)
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                task_type TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Create results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (task_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def save_data(self, task_id: str, data: Any, task_type: str, config: Optional[Dict] = None):
        """Save scraped data to database and files"""
        try:
            # Save to database
            self._save_to_database(task_id, data, task_type, config)
            
            # Save to files
            self._save_to_files(task_id, data, task_type)
            
            self.logger.info(f"Data saved successfully for task {task_id}")
            
        except Exception as e:
            self.logger.error(f"Error saving data for task {task_id}: {e}")
            raise
            
    def _save_to_database(self, task_id: str, data: Any, task_type: str, config: Optional[Dict] = None):
        """Save data to SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert or update task
            cursor.execute('''
                INSERT OR REPLACE INTO tasks (task_id, task_type, config, status)
                VALUES (?, ?, ?, ?)
            ''', (task_id, task_type, json.dumps(config or {}), 'completed'))
            
            # Insert results
            cursor.execute('''
                INSERT INTO results (task_id, data)
                VALUES (?, ?)
            ''', (task_id, json.dumps(data)))
            
            conn.commit()
            
        finally:
            conn.close()
            
    def _save_to_files(self, task_id: str, data: Any, task_type: str):
        """Save data to various file formats"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create task-specific directory
        task_dir = os.path.join(self.output_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # Save as JSON
        json_path = os.path.join(task_dir, f"{task_type}_{timestamp}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
        # Save as CSV if data is a list of dictionaries
        if isinstance(data, list) and data and isinstance(data[0], dict):
            csv_path = os.path.join(task_dir, f"{task_type}_{timestamp}.csv")
            df = pd.DataFrame(data)
            df.to_csv(csv_path, index=False, encoding='utf-8')
            
        # Save as Excel if data is a list of dictionaries
        if isinstance(data, list) and data and isinstance(data[0], dict):
            excel_path = os.path.join(task_dir, f"{task_type}_{timestamp}.xlsx")
            df = pd.DataFrame(data)
            df.to_excel(excel_path, index=False)
            
        self.logger.info(f"Files saved to {task_dir}")
        
    def get_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve data for a specific task"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get task info
            cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
            task = cursor.fetchone()
            
            if not task:
                return None
                
            # Get results
            cursor.execute('SELECT data FROM results WHERE task_id = ? ORDER BY created_at DESC', (task_id,))
            results = cursor.fetchall()
            
            if not results:
                return None
                
            return {
                "task_id": task[1],
                "task_type": task[2],
                "config": json.loads(task[3]),
                "status": task[5],
                "created_at": task[4],
                "data": [json.loads(result[0]) for result in results]
            }
            
        finally:
            conn.close()
            
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT t.task_id, t.task_type, t.config, t.status, t.created_at,
                       COUNT(r.id) as result_count
                FROM tasks t
                LEFT JOIN results r ON t.task_id = r.task_id
                GROUP BY t.task_id
                ORDER BY t.created_at DESC
            ''')
            
            tasks = []
            for row in cursor.fetchall():
                tasks.append({
                    "task_id": row[0],
                    "task_type": row[1],
                    "config": json.loads(row[2]),
                    "status": row[3],
                    "created_at": row[4],
                    "result_count": row[5]
                })
                
            return tasks
            
        finally:
            conn.close()
            
    def export_data(self, task_id: str, format: str = "csv") -> str:
        """Export data in specified format"""
        data = self.get_data(task_id)
        if not data:
            raise ValueError(f"No data found for task {task_id}")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task_id}_{timestamp}.{format}"
        filepath = os.path.join(self.output_dir, filename)
        
        if format == "csv":
            df = pd.DataFrame(data["data"])
            df.to_csv(filepath, index=False, encoding='utf-8')
        elif format == "excel":
            df = pd.DataFrame(data["data"])
            df.to_excel(filepath, index=False)
        elif format == "json":
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")
            
        return filepath
        
    def delete_task(self, task_id: str):
        """Delete a task and its data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Delete results
            cursor.execute('DELETE FROM results WHERE task_id = ?', (task_id,))
            
            # Delete task
            cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
            
            conn.commit()
            
            # Delete files
            task_dir = os.path.join(self.output_dir, task_id)
            if os.path.exists(task_dir):
                import shutil
                shutil.rmtree(task_dir)
                
        finally:
            conn.close()
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get scraping statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Total tasks
            cursor.execute('SELECT COUNT(*) FROM tasks')
            total_tasks = cursor.fetchone()[0]
            
            # Completed tasks
            cursor.execute('SELECT COUNT(*) FROM tasks WHERE status = "completed"')
            completed_tasks = cursor.fetchone()[0]
            
            # Total results
            cursor.execute('SELECT COUNT(*) FROM results')
            total_results = cursor.fetchone()[0]
            
            # Tasks by type
            cursor.execute('SELECT task_type, COUNT(*) FROM tasks GROUP BY task_type')
            tasks_by_type = dict(cursor.fetchall())
            
            return {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "total_results": total_results,
                "tasks_by_type": tasks_by_type,
                "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            }
            
        finally:
            conn.close()
