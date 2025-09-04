"""
Pytest configuration and fixtures for ORM tests.
"""

import pytest
import asyncio
from typing import List, Any
from unittest.mock import Mock

from revitpy.orm.validation import WallElement, RoomElement, DoorElement, WindowElement
from revitpy.orm.cache import CacheManager, CacheConfiguration
from revitpy.orm.change_tracker import ChangeTracker


class MockElementProvider:
    """Mock element provider for testing."""
    
    def __init__(self, elements: List[Any] = None):
        self.elements = elements or []
        self._generate_test_elements()
    
    def _generate_test_elements(self):
        """Generate a standard set of test elements."""
        if not self.elements:
            # Create test walls
            self.elements.extend([
                WallElement(id=1, name="Wall 1", height=10, length=20, width=0.5, category="Walls"),
                WallElement(id=2, name="Wall 2", height=8, length=15, width=0.4, category="Walls"),
                WallElement(id=3, name="Wall 3", height=12, length=25, width=0.6, category="Walls"),
            ])
            
            # Create test rooms
            self.elements.extend([
                RoomElement(id=10, number="101", name="Room 101", area=200, perimeter=60, volume=2000),
                RoomElement(id=11, number="102", name="Room 102", area=300, perimeter=70, volume=3000),
                RoomElement(id=12, number="103", name="Room 103", area=150, perimeter=50, volume=1500),
            ])
    
    def get_all_elements(self) -> List[Any]:
        return self.elements.copy()
    
    def get_elements_of_type(self, element_type: Any) -> List[Any]:
        return [elem for elem in self.elements if isinstance(elem, element_type)]
    
    def get_element_by_id(self, element_id: Any) -> Any:
        for elem in self.elements:
            if elem.id == element_id:
                return elem
        return None
    
    async def get_all_elements_async(self) -> List[Any]:
        return self.get_all_elements()
    
    async def get_elements_of_type_async(self, element_type: Any) -> List[Any]:
        return self.get_elements_of_type(element_type)
    
    async def get_element_by_id_async(self, element_id: Any) -> Any:
        return self.get_element_by_id(element_id)


@pytest.fixture
def mock_provider():
    """Fixture providing a mock element provider."""
    return MockElementProvider()


@pytest.fixture
def cache_manager():
    """Fixture providing a cache manager for testing."""
    config = CacheConfiguration(
        max_size=1000,
        enable_statistics=True,
        thread_safe=True
    )
    return CacheManager(config)


@pytest.fixture
def change_tracker():
    """Fixture providing a change tracker for testing."""
    return ChangeTracker(thread_safe=True)


@pytest.fixture
def sample_walls():
    """Fixture providing sample wall elements."""
    return [
        WallElement(id=1, name="Wall 1", height=10, length=20, width=0.5),
        WallElement(id=2, name="Wall 2", height=8, length=15, width=0.4),
        WallElement(id=3, name="Wall 3", height=12, length=25, width=0.6),
    ]


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "benchmark: mark test as a performance benchmark"
    )