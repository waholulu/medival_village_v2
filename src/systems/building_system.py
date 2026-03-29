from src.core.ecs import System, EntityManager
from src.components.building_components import BlueprintComponent, BuildingComponent
from src.components.data_components import PositionComponent, ItemComponent
from src.world.grid import Grid
from src.systems.job_system import JobSystem, Job
from src.core.config_manager import ConfigManager
from src.utils.logger import Logger, LogCategory

class BuildingSystem(System):
    def __init__(self, entity_manager: EntityManager, job_system: JobSystem, grid: Grid, config_manager: ConfigManager):
        self.entity_manager = entity_manager
        self.job_system = job_system
        self.grid = grid
        self.config_manager = config_manager
        
    def update(self, dt: float):
        # Scan blueprints and generate jobs if needed
        for entity_id, blueprint, pos in self.entity_manager.get_entities_with(BlueprintComponent, PositionComponent):
            # Check what materials are still needed
            needs_materials = False
            for mat_type, count_needed in blueprint.required_materials.items():
                current = blueprint.current_materials.get(mat_type, 0)
                if current < count_needed:
                    needs_materials = True
                    # Check if there's already a job for this material to this blueprint
                    if not self._has_hauling_job_for(entity_id, mat_type):
                        # Calculate how many more we need
                        amount_needed = count_needed - current
                        
                        # Note: The AI system will find the items in the stockpile when claiming the job
                        self.job_system.add_job(Job(
                            job_type="haul_to_blueprint",
                            target_pos=(pos.x, pos.y),
                            target_entity_id=entity_id,
                            priority=15, # High priority to finish construction
                            required_skill="farming", # General labor for now or a new 'building' skill
                            metadata={"material_type": mat_type, "amount_needed": amount_needed}
                        ))
            
            # If all materials are present, generate a build job
            if not needs_materials and blueprint.work_completed < blueprint.work_required:
                if not self._has_build_job_for(entity_id):
                    self.job_system.add_job(Job(
                        job_type="build",
                        target_pos=(pos.x, pos.y),
                        target_entity_id=entity_id,
                        priority=10,
                        required_skill="logging", # Use logging for woodworking/building for now
                    ))
            
            # If work is complete, transform to finished building
            if not needs_materials and blueprint.work_completed >= blueprint.work_required:
                Logger.gameplay(f"Finished building {blueprint.building_type} at ({pos.x}, {pos.y})")
                
                # Remove Blueprint component, add Building component
                self.entity_manager.remove_component(entity_id, BlueprintComponent)
                self.entity_manager.add_component(entity_id, BuildingComponent(building_type=blueprint.building_type))
                
                # We could also mark the grid here (e.g., unwalkable or set a zone)
    
    def _has_hauling_job_for(self, blueprint_id: int, material_type: str) -> bool:
        """Check if there is already an active job to haul this given material to the blueprint."""
        return self.job_system.has_job_for_entity_with_metadata(
            blueprint_id, "haul_to_blueprint", "material_type", material_type
        )
        
    def _has_build_job_for(self, blueprint_id: int) -> bool:
        """Check if there is already an active build job for the blueprint."""
        return self.job_system.has_job_for_entity(blueprint_id, "build")
