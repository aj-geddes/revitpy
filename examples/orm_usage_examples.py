"""
RevitPy ORM Usage Examples

This module demonstrates how to use the RevitPy ORM layer for common
Revit development tasks with high performance and type safety.
"""

import asyncio
from typing import List
from datetime import datetime

# Import ORM components
from revitpy.orm import (
    RevitContext, AsyncRevitContext, QueryBuilder, ElementSet,
    WallElement, RoomElement, DoorElement, WindowElement,
    create_wall, create_room, create_door, create_window,
    ElementValidator, ValidationLevel, CachePolicy
)
from revitpy.orm.types import BatchOperationType
from revitpy.orm.exceptions import ValidationError, QueryError


class RevitORMExamples:
    """Collection of ORM usage examples."""
    
    def __init__(self, provider):
        """Initialize with element provider."""
        self.provider = provider
    
    def basic_querying_example(self):
        """Demonstrate basic LINQ-style querying."""
        print("=== Basic Querying Example ===")
        
        with RevitContext(self.provider) as ctx:
            # Simple queries
            all_walls = ctx.all(WallElement).to_list()
            print(f"Total walls: {len(all_walls)}")
            
            # Filtered queries
            tall_walls = ctx.where(WallElement, lambda w: w.height > 10).to_list()
            print(f"Tall walls (>10 ft): {len(tall_walls)}")
            
            # Ordered queries
            walls_by_height = (ctx.all(WallElement)
                              .order_by(lambda w: w.height)
                              .to_list())
            
            print("Walls ordered by height:")
            for wall in walls_by_height[:5]:  # First 5
                print(f"  {wall.name}: {wall.height} ft")
            
            # Aggregations
            wall_count = ctx.count(WallElement)
            avg_height = ctx.all(WallElement).average(lambda w: w.height)
            max_wall = ctx.all(WallElement).max(lambda w: w.height)
            
            print(f"Statistics - Count: {wall_count}, Avg Height: {avg_height:.2f}, Max: {max_wall.height}")
    
    def complex_querying_example(self):
        """Demonstrate complex multi-step queries."""
        print("\n=== Complex Querying Example ===")
        
        with RevitContext(self.provider) as ctx:
            # Complex query with multiple conditions
            structural_exterior_walls = (
                ctx.all(WallElement)
                .where(lambda w: w.structural == True)
                .where(lambda w: w.width > 0.5)  # Thick walls
                .where(lambda w: w.height > 8)   # Tall walls
                .order_by(lambda w: w.length)    # Order by length
                .take(10)                        # Top 10
                .to_list()
            )
            
            print(f"Structural exterior walls: {len(structural_exterior_walls)}")
            
            # Projection queries (select specific properties)
            wall_summaries = (
                ctx.all(WallElement)
                .where(lambda w: w.fire_rating > 0)
                .select(lambda w: {
                    "name": w.name,
                    "area": w.area,
                    "fire_rating": w.fire_rating,
                    "volume": w.volume
                })
                .order_by(lambda summary: summary["area"])
                .to_list()
            )
            
            print(f"Fire-rated wall summaries: {len(wall_summaries)}")
            for summary in wall_summaries[:3]:
                print(f"  {summary['name']}: {summary['area']:.1f} sq ft, {summary['fire_rating']}hr rating")
    
    def validation_example(self):
        """Demonstrate type safety and validation."""
        print("\n=== Validation Example ===")
        
        # Create validator
        validator = ElementValidator(ValidationLevel.STRICT)
        
        try:
            # Valid wall creation
            wall = create_wall(
                id=1001,
                height=10.0,
                length=20.0,
                width=0.5,
                name="Example Wall",
                structural=True,
                fire_rating=2
            )
            
            print(f"Created valid wall: {wall.name}")
            
            # Validate the wall
            errors = validator.validate_element(wall)
            if not errors:
                print("Wall validation passed!")
            
        except ValidationError as e:
            print(f"Validation error: {e.validation_errors}")
        
        try:
            # Invalid wall creation (negative height)
            invalid_wall = create_wall(
                id=1002,
                height=-5.0,  # Invalid!
                length=20.0,
                width=0.5
            )
        except ValidationError as e:
            print(f"Caught expected validation error: {list(e.validation_errors.keys())}")
        
        # Room validation
        try:
            room = create_room(
                id=2001,
                number="101A",
                area=250.0,
                name="Conference Room",
                department="Engineering",
                occupancy=12
            )
            print(f"Created valid room: {room.name} ({room.area} sq ft)")
            
        except ValidationError as e:
            print(f"Room validation error: {e.validation_errors}")
    
    def change_tracking_example(self):
        """Demonstrate change tracking and batch updates."""
        print("\n=== Change Tracking Example ===")
        
        with RevitContext(self.provider) as ctx:
            # Get some walls to modify
            walls = ctx.all(WallElement).take(5).to_list()
            
            print(f"Modifying {len(walls)} walls...")
            
            # Modify properties (changes are tracked automatically)
            for i, wall in enumerate(walls):
                wall.fire_rating = i + 1
                wall.structural = (i % 2 == 0)
                wall.mark_dirty()  # Explicitly mark as changed
            
            # Check tracked changes
            print(f"Tracked changes: {ctx.change_count}")
            
            # Batch update using ElementSet
            wall_set = ElementSet(walls, WallElement)
            batch_updates = {
                "finish_material_interior": "Drywall",
                "finish_material_exterior": "Brick"
            }
            
            updated_count = wall_set.batch_update(batch_updates)
            print(f"Batch updated {updated_count} properties")
            
            # Save all changes
            try:
                saved_changes = ctx.save_changes()
                print(f"Successfully saved {saved_changes} changes")
            except Exception as e:
                print(f"Error saving changes: {e}")
                ctx.reject_changes()  # Rollback changes
    
    def caching_example(self):
        """Demonstrate intelligent caching."""
        print("\n=== Caching Example ===")
        
        # Configure context with caching
        from revitpy.orm import ContextConfiguration
        config = ContextConfiguration(
            cache_policy=CachePolicy.MEMORY,
            cache_max_size=5000,
            performance_monitoring=True
        )
        
        with RevitContext(self.provider, config=config) as ctx:
            # First query (cache miss)
            print("First query (cache miss)...")
            start_time = datetime.now()
            large_rooms = ctx.where(RoomElement, lambda r: r.area > 200).to_list()
            first_duration = (datetime.now() - start_time).total_seconds() * 1000
            
            print(f"Found {len(large_rooms)} large rooms in {first_duration:.2f}ms")
            
            # Second identical query (cache hit)
            print("Second identical query (potential cache hit)...")
            start_time = datetime.now()
            large_rooms_cached = ctx.where(RoomElement, lambda r: r.area > 200).to_list()
            second_duration = (datetime.now() - start_time).total_seconds() * 1000
            
            print(f"Found {len(large_rooms_cached)} large rooms in {second_duration:.2f}ms")
            
            # Show cache statistics
            if ctx.cache_statistics:
                stats = ctx.cache_statistics
                print(f"Cache statistics: {stats.hit_rate:.1f}% hit rate, {stats.hits} hits, {stats.misses} misses")
    
    def relationship_example(self):
        """Demonstrate relationship navigation."""
        print("\n=== Relationship Example ===")
        
        with RevitContext(self.provider) as ctx:
            # This example assumes relationships are configured
            # In a real implementation, you'd set up relationships between
            # walls and rooms, doors and rooms, etc.
            
            try:
                # Get a room
                room = ctx.first(RoomElement)
                print(f"Working with room: {room.name}")
                
                # Navigate to related walls (if relationship configured)
                # room_walls = room.walls
                # print(f"Room has {len(room_walls)} walls")
                
                # Navigate from wall to room
                wall = ctx.first(WallElement)
                print(f"Working with wall: {wall.name}")
                
                # wall_room = wall.room
                # print(f"Wall is in room: {wall_room.name if wall_room else 'None'}")
                
                print("(Relationship navigation requires relationship configuration)")
                
            except QueryError as e:
                print(f"Query error: {e}")
    
    async def async_example(self):
        """Demonstrate async operations."""
        print("\n=== Async Example ===")
        
        async with AsyncRevitContext(self.provider) as ctx:
            # Async queries
            print("Performing async queries...")
            
            walls = await ctx.get_all_async(WallElement)
            print(f"Retrieved {len(walls)} walls asynchronously")
            
            # Async aggregations
            room_count = await ctx.all(RoomElement).count_async()
            first_room = await ctx.all(RoomElement).first_async()
            
            print(f"Room count: {room_count}")
            print(f"First room: {first_room.name if first_room else 'None'}")
            
            # Async streaming for large datasets
            print("Streaming walls asynchronously...")
            wall_count = 0
            async for wall in ctx.all(WallElement).as_streaming(batch_size=10):
                wall_count += 1
                if wall_count <= 5:  # Show first few
                    print(f"  Processing wall: {wall.name}")
            
            print(f"Processed {wall_count} walls via streaming")
            
            # Async transactions
            async with ctx.transaction() as trans:
                wall = await ctx.get_by_id_async(1)
                if wall:
                    wall.name = f"Modified Wall {datetime.now().strftime('%H:%M:%S')}"
                    wall.mark_dirty()
                    
                changes = await ctx.save_changes_async()
                print(f"Saved {changes} changes in async transaction")
    
    def performance_example(self):
        """Demonstrate performance optimization techniques."""
        print("\n=== Performance Example ===")
        
        with RevitContext(self.provider) as ctx:
            # Lazy evaluation
            print("Using lazy evaluation...")
            query = ctx.all(WallElement).where(lambda w: w.height > 8)
            print("Query created (not executed yet)")
            
            # Force execution
            start_time = datetime.now()
            results = query.to_list()
            duration = (datetime.now() - start_time).total_seconds() * 1000
            print(f"Executed query: {len(results)} results in {duration:.2f}ms")
            
            # Batch operations
            print("Performing batch operations...")
            if results:
                element_set = ElementSet(results, WallElement)
                
                # Batch update
                start_time = datetime.now()
                updates = {"structural": True}
                updated = element_set.batch_update(updates, batch_size=50)
                duration = (datetime.now() - start_time).total_seconds() * 1000
                
                print(f"Batch updated {updated} properties in {duration:.2f}ms")
                throughput = updated / (duration / 1000) if duration > 0 else 0
                print(f"Throughput: {throughput:.0f} updates/second")
            
            # Memory-efficient iteration
            print("Using memory-efficient iteration...")
            processed = 0
            for wall in ctx.all(WallElement).as_lazy():
                processed += 1
                if processed >= 10:  # Process only first 10
                    break
            
            print(f"Processed {processed} walls with minimal memory usage")
    
    def error_handling_example(self):
        """Demonstrate comprehensive error handling."""
        print("\n=== Error Handling Example ===")
        
        with RevitContext(self.provider) as ctx:
            # Query errors
            try:
                # This should fail - looking for single element that doesn't exist
                nonexistent = ctx.single(WallElement, lambda w: w.name == "NonExistent Wall")
            except QueryError as e:
                print(f"Caught query error: {e}")
                print(f"Operation: {e.query_operation}")
            
            # Validation errors
            try:
                invalid_data = {
                    "id": "invalid_id",  # Should be int/string
                    "height": -5.0,      # Should be positive
                    "length": 0,         # Should be positive
                    "width": "invalid"   # Should be numeric
                }
                validator = ElementValidator()
                errors = validator.validate_element_dict(invalid_data, "Wall")
                if errors:
                    print(f"Validation errors found: {list(errors.keys())}")
                    
            except Exception as e:
                print(f"Validation exception: {e}")
            
            # Cache errors (simulated)
            try:
                # Attempt to access cache statistics when caching is disabled
                stats = ctx.cache_statistics
                if stats is None:
                    print("Cache statistics not available (caching may be disabled)")
            except Exception as e:
                print(f"Cache error: {e}")


def create_sample_provider():
    """Create a sample element provider for demonstration."""
    from tests.orm.conftest import MockElementProvider
    
    # Create sample elements
    elements = []
    
    # Add walls
    for i in range(20):
        wall = create_wall(
            id=i + 1,
            height=8 + (i % 8),
            length=10 + (i % 15),
            width=0.3 + (i % 3) * 0.1,
            name=f"Wall {i+1:02d}",
            structural=(i % 3 == 0),
            fire_rating=(i % 4)
        )
        elements.append(wall)
    
    # Add rooms
    for i in range(10):
        room = create_room(
            id=100 + i,
            number=f"{101 + i}",
            area=150 + i * 25,
            name=f"Room {101 + i}",
            department=f"Department {i % 3}",
            occupancy=2 + i % 15
        )
        elements.append(room)
    
    # Add doors
    for i in range(8):
        door = create_door(
            id=200 + i,
            width=2.5 + (i % 3) * 0.25,
            height=6.5 + (i % 2) * 0.5,
            name=f"Door {i+1:02d}",
            material="Wood" if i % 2 == 0 else "Steel",
            fire_rating=(i % 4) * 0.75
        )
        elements.append(door)
    
    # Add windows
    for i in range(6):
        window = create_window(
            id=300 + i,
            width=3.0 + (i % 4) * 0.5,
            height=2.5 + (i % 3) * 0.5,
            name=f"Window {i+1:02d}",
            glass_type="Double Pane" if i % 2 == 0 else "Triple Pane",
            energy_star_rated=(i % 3 == 0)
        )
        elements.append(window)
    
    return MockElementProvider(elements)


async def main():
    """Main function to run all examples."""
    print("RevitPy ORM Usage Examples")
    print("=" * 50)
    
    # Create sample provider
    provider = create_sample_provider()
    
    # Create examples instance
    examples = RevitORMExamples(provider)
    
    # Run synchronous examples
    examples.basic_querying_example()
    examples.complex_querying_example()
    examples.validation_example()
    examples.change_tracking_example()
    examples.caching_example()
    examples.relationship_example()
    examples.performance_example()
    examples.error_handling_example()
    
    # Run async examples
    await examples.async_example()
    
    print("\n" + "=" * 50)
    print("All examples completed successfully!")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())