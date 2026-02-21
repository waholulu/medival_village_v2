"""
ECS系统单元测试
测试Entity创建、销毁、Component添加移除、查询功能
"""
import tests  # 确保 tests/__init__.py 中的 sys.path 设置生效

from tests.test_framework import TestBase
from src.core.ecs import EntityManager
from src.components.data_components import PositionComponent, MovementComponent, ActionComponent


class TestECS(TestBase):
    """ECS系统测试"""
    
    def setup(self):
        self.entity_manager = EntityManager()
    
    def test_create_entity(self):
        """测试实体创建"""
        entity = self.entity_manager.create_entity()
        self.assert_is_not_none(entity, "Entity should be created")
        self.assert_true(self.entity_manager.has_entity(entity), "Entity should exist")
    
    def test_destroy_entity(self):
        """测试实体销毁"""
        entity = self.entity_manager.create_entity()
        self.entity_manager.destroy_entity(entity)
        self.assert_false(self.entity_manager.has_entity(entity), "Entity should be destroyed")
    
    def test_add_component(self):
        """测试添加组件"""
        entity = self.entity_manager.create_entity()
        pos = PositionComponent(x=10, y=20)
        self.entity_manager.add_component(entity, pos)
        
        retrieved = self.entity_manager.get_component(entity, PositionComponent)
        self.assert_is_not_none(retrieved, "Component should be added")
        self.assert_equal(retrieved.x, 10, "Component x should be 10")
        self.assert_equal(retrieved.y, 20, "Component y should be 20")
    
    def test_remove_component(self):
        """测试移除组件"""
        entity = self.entity_manager.create_entity()
        pos = PositionComponent(x=10, y=20)
        self.entity_manager.add_component(entity, pos)
        
        self.entity_manager.remove_component(entity, PositionComponent)
        retrieved = self.entity_manager.get_component(entity, PositionComponent)
        self.assert_is_none(retrieved, "Component should be removed")
    
    def test_has_component(self):
        """测试检查组件是否存在"""
        entity = self.entity_manager.create_entity()
        self.assert_false(
            self.entity_manager.has_component(entity, PositionComponent),
            "Entity should not have PositionComponent initially"
        )
        
        pos = PositionComponent(x=10, y=20)
        self.entity_manager.add_component(entity, pos)
        self.assert_true(
            self.entity_manager.has_component(entity, PositionComponent),
            "Entity should have PositionComponent after adding"
        )
    
    def test_get_entities_with(self):
        """测试查询具有特定组件的实体"""
        # 创建多个实体
        entity1 = self.entity_manager.create_entity()
        entity2 = self.entity_manager.create_entity()
        entity3 = self.entity_manager.create_entity()
        
        # 只给entity1和entity2添加PositionComponent
        self.entity_manager.add_component(entity1, PositionComponent(x=1, y=1))
        self.entity_manager.add_component(entity2, PositionComponent(x=2, y=2))
        
        # 查询所有有PositionComponent的实体
        entities_with_pos = list(self.entity_manager.get_entities_with(PositionComponent))
        self.assert_equal(len(entities_with_pos), 2, "Should find 2 entities with PositionComponent")
    
    def test_get_entities_with_multiple_components(self):
        """测试查询具有多个组件的实体"""
        entity1 = self.entity_manager.create_entity()
        entity2 = self.entity_manager.create_entity()
        
        # entity1有Position和Movement
        self.entity_manager.add_component(entity1, PositionComponent(x=1, y=1))
        self.entity_manager.add_component(entity1, MovementComponent())
        
        # entity2只有Position
        self.entity_manager.add_component(entity2, PositionComponent(x=2, y=2))
        
        # 查询同时有Position和Movement的实体
        entities = list(self.entity_manager.get_entities_with(PositionComponent, MovementComponent))
        self.assert_equal(len(entities), 1, "Should find 1 entity with both components")
        self.assert_equal(entities[0][0], entity1, "Should be entity1")
    
    def test_component_isolation(self):
        """测试组件隔离 - 不同实体的组件应该独立"""
        entity1 = self.entity_manager.create_entity()
        entity2 = self.entity_manager.create_entity()
        
        pos1 = PositionComponent(x=10, y=20)
        pos2 = PositionComponent(x=30, y=40)
        
        self.entity_manager.add_component(entity1, pos1)
        self.entity_manager.add_component(entity2, pos2)
        
        retrieved1 = self.entity_manager.get_component(entity1, PositionComponent)
        retrieved2 = self.entity_manager.get_component(entity2, PositionComponent)
        
        self.assert_equal(retrieved1.x, 10, "Entity1 x should be 10")
        self.assert_equal(retrieved1.y, 20, "Entity1 y should be 20")
        self.assert_equal(retrieved2.x, 30, "Entity2 x should be 30")
        self.assert_equal(retrieved2.y, 40, "Entity2 y should be 40")
    
    def test_destroy_entity_removes_components(self):
        """测试销毁实体时移除所有组件"""
        entity = self.entity_manager.create_entity()
        self.entity_manager.add_component(entity, PositionComponent(x=10, y=20))
        self.entity_manager.add_component(entity, MovementComponent())
        self.entity_manager.add_component(entity, ActionComponent())
        
        self.entity_manager.destroy_entity(entity)
        
        # 所有组件应该都被移除
        self.assert_is_none(
            self.entity_manager.get_component(entity, PositionComponent),
            "PositionComponent should be removed"
        )
        self.assert_is_none(
            self.entity_manager.get_component(entity, MovementComponent),
            "MovementComponent should be removed"
        )
        self.assert_is_none(
            self.entity_manager.get_component(entity, ActionComponent),
            "ActionComponent should be removed"
        )

    def test_entity_ids_are_unique(self):
        """测试实体ID应唯一"""
        ids = set()
        for _ in range(100):
            entity = self.entity_manager.create_entity()
            self.assert_false(entity in ids, f"Entity ID {entity} should be unique")
            ids.add(entity)

    def test_get_component_nonexistent_entity(self):
        """查询不存在实体的组件应返回None"""
        result = self.entity_manager.get_component(99999, PositionComponent)
        self.assert_is_none(result, "Should return None for nonexistent entity")

    def test_get_entities_with_no_matching(self):
        """没有匹配组件时应返回空"""
        entity = self.entity_manager.create_entity()
        self.entity_manager.add_component(entity, MovementComponent())
        results = list(self.entity_manager.get_entities_with(PositionComponent, ActionComponent))
        self.assert_equal(len(results), 0, "No entity has both Position and Action")

    def test_destroy_already_destroyed_entity(self):
        """销毁已销毁的实体不应崩溃"""
        entity = self.entity_manager.create_entity()
        self.entity_manager.destroy_entity(entity)
        self.entity_manager.destroy_entity(entity)
        self.assert_false(self.entity_manager.has_entity(entity), "Entity should remain destroyed")

