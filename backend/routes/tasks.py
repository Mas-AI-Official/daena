"""
Tasks API Routes
Provides endpoints for task management
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
import uuid
import time
import random

from backend.database import get_db, Task

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "pending"
    department_id: Optional[str] = None
    agent_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None  # Alias for agent_id
    priority: str = "medium"
    owner_type: str = "agent"  # agent, department, system
    owner_id: Optional[str] = None
    progress: float = 0.0
    payload_json: Optional[Dict[str, Any]] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    progress: Optional[float] = None
    payload_json: Optional[Dict[str, Any]] = None
    result_json: Optional[Dict[str, Any]] = None

class TaskAssignment(BaseModel):
    agent_id: str

@router.post("/")
async def create_task(task_data: TaskCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Create a new task"""
    try:
        # Generate unique task_id
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        # Use assigned_agent_id if provided, otherwise use agent_id
        assigned_agent_id = task_data.assigned_agent_id or task_data.agent_id
        
        task = Task(
            task_id=task_id,
            title=task_data.title,
            description=task_data.description,
            status=task_data.status,
            department_id=task_data.department_id,
            assigned_agent_id=assigned_agent_id,
            priority=task_data.priority,
            owner_type=task_data.owner_type,
            owner_id=task_data.owner_id or assigned_agent_id,
            progress=task_data.progress,
            payload_json=task_data.payload_json or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        return {
            "success": True,
            "task_id": task.task_id,
            "task": {
                "id": str(task.id),
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "department_id": task.department_id,
                "assigned_agent_id": task.assigned_agent_id,
                "progress": task.progress,
                "created_at": task.created_at.isoformat() if task.created_at else None
            }
        }
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_tasks(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List all tasks with optional filtering"""
    try:
        # Note: Task model doesn't have is_active, so we filter by status != "deleted" if needed
        query = db.query(Task).filter(Task.status != "deleted")
        
        if status:
            query = query.filter(Task.status == status)
        
        if priority:
            query = query.filter(Task.priority == priority)
        
        total = query.count()
        tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()
        
        task_list = []
        for task in tasks:
            task_list.append({
                "task_id": task.task_id,
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority or "medium",
                "department_id": task.department_id,
                "assigned_agent_id": task.assigned_agent_id,
                "owner_type": task.owner_type,
                "owner_id": task.owner_id,
                "progress": task.progress or 0.0,
                "payload_json": task.payload_json or {},
                "result_json": task.result_json or {},
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            })
        
        return {
            "success": True,
            "tasks": task_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}")
async def get_task(task_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific task by ID (can be task_id string or numeric id)"""
    try:
        # Try to find by task_id first (string), then by numeric id
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            # Try numeric ID
            try:
                numeric_id = int(task_id)
                task = db.query(Task).filter(Task.id == numeric_id).first()
            except ValueError:
                pass
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "success": True,
            "task": {
                "id": str(task.id),
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority or "medium",
                "department_id": task.department_id,
                "assigned_agent_id": task.assigned_agent_id,
                "owner_type": task.owner_type,
                "owner_id": task.owner_id,
                "progress": task.progress or 0.0,
                "payload_json": task.payload_json or {},
                "result_json": task.result_json or {},
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update a task"""
    try:
        # Try to find by task_id first (string), then by numeric id
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            try:
                numeric_id = int(task_id)
                task = db.query(Task).filter(Task.id == numeric_id).first()
            except ValueError:
                pass
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task_data.title is not None:
            task.title = task_data.title
        if task_data.description is not None:
            task.description = task_data.description
        if task_data.status is not None:
            task.status = task_data.status
        if task_data.priority is not None:
            task.priority = task_data.priority
        if task_data.progress is not None:
            task.progress = task_data.progress
        if task_data.payload_json is not None:
            task.payload_json = task_data.payload_json
        if task_data.result_json is not None:
            task.result_json = task_data.result_json
        
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        
        return {
            "success": True,
            "task": {
                "id": str(task.id),
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority or "medium",
                "progress": task.progress or 0.0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete a task (set status to 'deleted')"""
    try:
        # Try to find by task_id first (string), then by numeric id
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            try:
                numeric_id = int(task_id)
                task = db.query(Task).filter(Task.id == numeric_id).first()
            except ValueError:
                pass
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Set status to deleted instead of is_active (which doesn't exist in Task model)
        task.status = "deleted"
        task.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Task deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/overview")
async def get_task_stats_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get task statistics overview"""
    try:
        query = db.query(Task).filter(Task.status != "deleted")
        total_tasks = query.count()
        pending_tasks = query.filter(Task.status == "pending").count()
        running_tasks = query.filter(Task.status == "running").count()
        completed_tasks = query.filter(Task.status == "completed").count()
        failed_tasks = query.filter(Task.status == "failed").count()
        
        # Priority distribution
        priority_counts = {}
        for priority in ["low", "medium", "high", "urgent"]:
            priority_counts[priority] = query.filter(Task.priority == priority).count()
        
        # Department distribution
        department_counts = {}
        dept_tasks = query.filter(Task.department_id.isnot(None)).all()
        for task in dept_tasks:
            dept = task.department_id
            department_counts[dept] = department_counts.get(dept, 0) + 1
        
        # Calculate success rate
        total_completed = completed_tasks + failed_tasks
        success_rate = completed_tasks / total_completed if total_completed > 0 else 0
        
        return {
            "success": True,
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "running_tasks": running_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": success_rate,
            "priority_distribution": priority_counts,
            "department_distribution": department_counts
        }
    except Exception as e:
        logger.error(f"Failed to get task stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/performance")
async def get_task_performance(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get task performance metrics"""
    try:
        completed_tasks = db.query(Task).filter(
            Task.status == "completed",
            Task.status != "deleted"
        ).all()
        
        if not completed_tasks:
            return {
                "success": True,
                "message": "No completed tasks found",
                "total_completed_tasks": 0
            }
        
        # Calculate average completion time from result_json if available
        completion_times = []
        for task in completed_tasks:
            if task.result_json and isinstance(task.result_json, dict):
                exec_time = task.result_json.get("execution_time", "")
                if exec_time and exec_time.endswith("s"):
                    try:
                        seconds = float(exec_time[:-1])
                        completion_times.append(seconds)
                    except ValueError:
                        pass
        
        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
        
        # Calculate tasks by priority
        priority_performance = {}
        for priority in ["low", "medium", "high", "urgent"]:
            priority_tasks = [t for t in completed_tasks if t.priority == priority]
            if priority_tasks:
                priority_times = []
                for task in priority_tasks:
                    if task.result_json and isinstance(task.result_json, dict):
                        exec_time = task.result_json.get("execution_time", "")
                        if exec_time and exec_time.endswith("s"):
                            try:
                                seconds = float(exec_time[:-1])
                                priority_times.append(seconds)
                            except ValueError:
                                pass
                
                priority_performance[priority] = {
                    "count": len(priority_tasks),
                    "avg_completion_time": sum(priority_times) / len(priority_times) if priority_times else 0
                }
        
        # Recent completions (last 24 hours)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_completions = len([
            t for t in completed_tasks 
            if t.updated_at and t.updated_at >= recent_cutoff
        ])
        
        return {
            "success": True,
            "total_completed_tasks": len(completed_tasks),
            "average_completion_time_seconds": avg_completion_time,
            "priority_performance": priority_performance,
            "recent_completions": recent_completions
        }
    except Exception as e:
        logger.error(f"Failed to get task performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/department/{department_id}")
async def get_department_tasks(department_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get all tasks for a specific department"""
    try:
        tasks = db.query(Task).filter(
            Task.department_id == department_id,
            Task.status != "deleted"
        ).order_by(Task.created_at.desc()).all()
        
        task_list = []
        for task in tasks:
            task_list.append({
                "task_id": task.task_id,
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority or "medium",
                "assigned_agent_id": task.assigned_agent_id,
                "progress": task.progress or 0.0,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            })
        
        return {
            "success": True,
            "tasks": task_list,
            "department_id": department_id,
            "total": len(task_list)
        }
    except Exception as e:
        logger.error(f"Failed to get department tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{task_id}/assign")
async def assign_task(
    task_id: str,
    assignment: TaskAssignment,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Assign a task to an agent"""
    try:
        # Try to find by task_id first (string), then by numeric id
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            try:
                numeric_id = int(task_id)
                task = db.query(Task).filter(Task.id == numeric_id).first()
            except ValueError:
                pass
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task.assigned_agent_id = assignment.agent_id
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        
        return {
            "success": True,
            "message": f"Task assigned to agent {assignment.agent_id}",
            "task": {
                "task_id": task.task_id,
                "assigned_agent_id": task.assigned_agent_id
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{task_id}/start")
async def start_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Start a task execution"""
    try:
        # Try to find by task_id first (string), then by numeric id
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            try:
                numeric_id = int(task_id)
                task = db.query(Task).filter(Task.id == numeric_id).first()
            except ValueError:
                pass
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.status != "pending":
            raise HTTPException(status_code=400, detail="Task is not in pending status")
        
        task.status = "running"
        task.progress = 0.0
        task.updated_at = datetime.utcnow()
        db.commit()
        
        # Simulate task execution in background
        def simulate_task_execution():
            # Get a new session for background task
            from backend.database import SessionLocal
            bg_db = SessionLocal()
            try:
                bg_task = bg_db.query(Task).filter(Task.task_id == task_id).first()
                if not bg_task:
                    return
                
                # Simulate execution
                time.sleep(random.uniform(5, 15))
                
                # Randomly determine success or failure (90% success rate)
                if random.random() > 0.1:
                    bg_task.status = "completed"
                    bg_task.progress = 100.0
                    bg_task.result_json = {
                        "execution_time": f"{random.randint(5, 15)}s",
                        "data_processed": random.randint(100, 1000),
                        "success": True
                    }
                else:
                    bg_task.status = "failed"
                    bg_task.result_json = {
                        "error": "Task execution failed due to system error"
                    }
                
                bg_task.updated_at = datetime.utcnow()
                bg_db.commit()
            finally:
                bg_db.close()
        
        background_tasks.add_task(simulate_task_execution)
        
        return {
            "success": True,
            "message": "Task started successfully",
            "task_id": task.task_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Cancel a task"""
    try:
        # Try to find by task_id first (string), then by numeric id
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            try:
                numeric_id = int(task_id)
                task = db.query(Task).filter(Task.id == numeric_id).first()
            except ValueError:
                pass
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.status in ["completed", "failed", "cancelled", "deleted"]:
            raise HTTPException(status_code=400, detail="Task cannot be cancelled")
        
        task.status = "cancelled"
        task.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Task cancelled successfully",
            "task_id": task.task_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agent/{agent_id}")
async def get_agent_tasks(agent_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get all tasks assigned to a specific agent"""
    try:
        tasks = db.query(Task).filter(
            Task.assigned_agent_id == agent_id,
            Task.status != "deleted"
        ).order_by(Task.created_at.desc()).all()
        
        task_list = []
        for task in tasks:
            task_list.append({
                "task_id": task.task_id,
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority or "medium",
                "department_id": task.department_id,
                "progress": task.progress or 0.0,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            })
        
        return {
            "success": True,
            "tasks": task_list,
            "agent_id": agent_id,
            "total": len(task_list)
        }
    except Exception as e:
        logger.error(f"Failed to get agent tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
