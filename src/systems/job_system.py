from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import uuid

@dataclass
class Job:
    job_type: str  # "chop", "haul"
    target_pos: Tuple[int, int]
    target_entity_id: Optional[int] = None
    required_skill: Optional[str] = None # e.g., "logging"
    priority: int = 1
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assignee: Optional[int] = None
    required_item: Optional[str] = None # For hauling: "log"

class JobSystem:
    def __init__(self):
        self.jobs: List[Job] = []
    
    def add_job(self, job: Job):
        self.jobs.append(job)
        # Sort by priority (higher first)
        self.jobs.sort(key=lambda j: j.priority, reverse=True)

    def get_available_jobs(self) -> List[Job]:
        return [j for j in self.jobs if j.assignee is None]

    def assign_job(self, job: Job, entity_id: int):
        job.assignee = entity_id

    def complete_job(self, job_id: str):
        self.jobs = [j for j in self.jobs if j.id != job_id]
        
    def get_job_by_id(self, job_id: str) -> Optional[Job]:
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

