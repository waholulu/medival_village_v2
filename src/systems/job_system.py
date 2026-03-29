from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import uuid
import heapq

@dataclass
class Job:
    job_type: str  # "chop", "haul", "plant", "harvest", "trap", "fish", "tend_fire", "haul_to_blueprint", "build"
    target_pos: Tuple[int, int]
    target_entity_id: Optional[int] = None
    required_skill: Optional[str] = None  # e.g., "logging"
    priority: int = 1
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assignee: Optional[int] = None
    required_item: Optional[str] = None  # For hauling: "log"
    metadata: Optional[Dict] = None # For extra data like "material_type"

class JobSystem:
    def __init__(self):
        # Primary storage: dict for O(1) lookup by id
        self._jobs_by_id: Dict[str, Job] = {}
        # Secondary index: jobs indexed by target_entity_id for fast existence checks
        self._jobs_by_target: Dict[int, List[str]] = {}
    
    @property
    def jobs(self) -> List[Job]:
        """Compatibility property: return all jobs as a list (sorted by priority desc)."""
        result = list(self._jobs_by_id.values())
        result.sort(key=lambda j: j.priority, reverse=True)
        return result
    
    def add_job(self, job: Job):
        """Add a job to the system."""
        self._jobs_by_id[job.id] = job
        # Update target entity index
        if job.target_entity_id is not None:
            if job.target_entity_id not in self._jobs_by_target:
                self._jobs_by_target[job.target_entity_id] = []
            self._jobs_by_target[job.target_entity_id].append(job.id)

    def get_available_jobs(self) -> List[Job]:
        """Get all unassigned jobs, sorted by priority (highest first)."""
        result = [j for j in self._jobs_by_id.values() if j.assignee is None]
        result.sort(key=lambda j: j.priority, reverse=True)
        return result

    def assign_job(self, job: Job, entity_id: int):
        """Assign a job to an entity."""
        job.assignee = entity_id

    def complete_job(self, job_id: str):
        """Remove a completed job from the system."""
        job = self._jobs_by_id.pop(job_id, None)
        if job:
            # Track job completion in diagnostic logger
            from src.utils.diagnostic_logger import DiagnosticLogger
            diag = DiagnosticLogger.get_instance()
            if diag:
                diag.record_job_completed()

            if job.target_entity_id is not None:
                # Clean up target entity index
                target_jobs = self._jobs_by_target.get(job.target_entity_id, [])
                if job_id in target_jobs:
                    target_jobs.remove(job_id)
                if not target_jobs:
                    self._jobs_by_target.pop(job.target_entity_id, None)

    def release_job(self, job_id: str):
        """Release a job back to the available pool (unassign without removing).
        Used when a villager is interrupted and can't continue the job right now."""
        job = self._jobs_by_id.get(job_id)
        if job:
            job.assignee = None
        
    def get_job_by_id(self, job_id: str) -> Optional[Job]:
        """O(1) job lookup by id."""
        return self._jobs_by_id.get(job_id)
    
    def has_job_for_entity(self, target_entity_id: int, job_type: Optional[str] = None) -> bool:
        """Check if a job already exists for a given target entity. O(1) average case."""
        job_ids = self._jobs_by_target.get(target_entity_id, [])
        if not job_ids:
            return False
        if job_type is None:
            return True
        return any(
            self._jobs_by_id[jid].job_type == job_type 
            for jid in job_ids 
            if jid in self._jobs_by_id
        )

    def has_job_for_entity_with_metadata(self, target_entity_id: int, job_type: str, metadata_key: str, metadata_value: any) -> bool:
        """Check if a job exists for a target entity with specific metadata. O(1) average case."""
        job_ids = self._jobs_by_target.get(target_entity_id, [])
        if not job_ids:
            return False
        
        for jid in job_ids:
            job = self._jobs_by_id.get(jid)
            if job and job.job_type == job_type and job.metadata and job.metadata.get(metadata_key) == metadata_value:
                return True
        return False

