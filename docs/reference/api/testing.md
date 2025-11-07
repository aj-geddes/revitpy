---
layout: api
title: Testing Framework API
description: Comprehensive testing tools with mock objects and fixtures
---

# Testing Framework API

RevitPy's Testing Framework provides comprehensive tools for testing Revit applications with mock objects, fixtures, and assertions.

## Overview

The Testing Framework includes:

- **Mock Revit environment**: Test without running Revit
- **Test fixtures**: Reusable test components
- **Assertions**: Specialized assertions for Revit elements
- **Test runners**: Execute and organize tests
- **Snapshot testing**: Compare element states
- **Async test support**: Test async operations

## Core Classes

### MockRevit

Complete mock Revit environment for testing.

::: revitpy.testing.MockRevit
    options:
      members:
        - create_document
        - create_element
        - create_application
        - get_active_document
        - set_active_document

### MockDocument

Mock Revit document.

::: revitpy.testing.MockDocument
    options:
      members:
        - create_element
        - get_element
        - delete_element
        - get_elements
        - start_transaction
        - save

### MockElement

Mock Revit element with configurable properties.

::: revitpy.testing.MockElement
    options:
      members:
        - Id
        - Name
        - Category
        - get_parameter
        - set_parameter
        - delete

### RevitTestCase

Base class for Revit test cases.

::: revitpy.testing.RevitTestCase
    options:
      members:
        - setUp
        - tearDown
        - create_mock_context
        - create_mock_element
        - assert_element_exists
        - assert_parameter_value

### AsyncRevitTestCase

Test case for async operations.

::: revitpy.testing.AsyncRevitTestCase
    options:
      members:
        - setUp
        - tearDown
        - run_async
        - assert_async_completes

## Basic Testing

### Simple Test Case

```python
import unittest
from revitpy.testing import RevitTestCase, MockRevit, MockElement

class TestWallOperations(RevitTestCase):
    """Test wall operations."""

    def setUp(self):
        """Set up test environment."""
        self.mock_revit = MockRevit()
        self.doc = self.mock_revit.create_document()

    def test_create_wall(self):
        """Test wall creation."""
        # Create mock wall
        wall = self.doc.create_element(
            category='Walls',
            properties={'Name': 'Test Wall', 'Height': 10.0}
        )

        # Assertions
        self.assertIsNotNone(wall)
        self.assertEqual(wall.Name, 'Test Wall')
        self.assertEqual(wall.Height, 10.0)

    def test_update_wall_parameter(self):
        """Test updating wall parameter."""
        wall = self.doc.create_element(
            category='Walls',
            properties={'Name': 'Wall 1', 'Height': 8.0}
        )

        # Update parameter
        wall.set_parameter('Height', 12.0)

        # Assert
        self.assertEqual(wall.get_parameter('Height').AsDouble(), 12.0)

    def tearDown(self):
        """Clean up after test."""
        self.mock_revit.cleanup()

if __name__ == '__main__':
    unittest.main()
```

### Testing with Mock Context

```python
from revitpy.testing import create_mock_context

class TestElementQueries(RevitTestCase):
    """Test element querying."""

    def test_query_walls(self):
        """Test querying walls."""
        with create_mock_context() as context:
            # Add test data
            context.add_element(MockElement('Wall', Height=8.0, Name='Wall-1'))
            context.add_element(MockElement('Wall', Height=12.0, Name='Wall-2'))
            context.add_element(MockElement('Wall', Height=15.0, Name='Wall-3'))

            # Query walls
            tall_walls = (context.elements
                         .of_category('Walls')
                         .where(lambda w: w.Height > 10.0)
                         .to_list())

            # Assertions
            self.assertEqual(len(tall_walls), 2)
            self.assertTrue(all(w.Height > 10.0 for w in tall_walls))

    def test_query_with_ordering(self):
        """Test query with ordering."""
        with create_mock_context() as context:
            # Add test data
            context.add_element(MockElement('Wall', Height=15.0, Name='C'))
            context.add_element(MockElement('Wall', Height=8.0, Name='A'))
            context.add_element(MockElement('Wall', Height=12.0, Name='B'))

            # Query with ordering
            walls = (context.elements
                    .of_category('Walls')
                    .order_by(lambda w: w.Name)
                    .to_list())

            # Assert correct order
            self.assertEqual(walls[0].Name, 'A')
            self.assertEqual(walls[1].Name, 'B')
            self.assertEqual(walls[2].Name, 'C')
```

## Test Fixtures

### Element Fixtures

```python
from revitpy.testing import ElementFixture, DocumentFixture

class WallFixture(ElementFixture):
    """Fixture for wall elements."""

    def create_default_wall(self):
        """Create a default wall for testing."""
        return self.create_element(
            category='Walls',
            properties={
                'Name': 'Standard Wall',
                'Height': 10.0,
                'Width': 0.5,
                'Length': 20.0
            }
        )

    def create_exterior_wall(self):
        """Create an exterior wall."""
        return self.create_element(
            category='Walls',
            properties={
                'Name': 'Exterior Wall',
                'Height': 12.0,
                'Width': 0.75,
                'Function': 1  # Exterior
            }
        )

class TestWithFixtures(RevitTestCase):
    """Test using fixtures."""

    def setUp(self):
        """Set up fixtures."""
        self.wall_fixture = WallFixture()

    def test_with_default_wall(self):
        """Test with default wall fixture."""
        wall = self.wall_fixture.create_default_wall()

        self.assertEqual(wall.Name, 'Standard Wall')
        self.assertEqual(wall.Height, 10.0)

    def test_with_exterior_wall(self):
        """Test with exterior wall fixture."""
        wall = self.wall_fixture.create_exterior_wall()

        self.assertEqual(wall.get_parameter('Function').AsInteger(), 1)
```

### Document Fixtures

```python
class DocumentFixture:
    """Fixture for complete document setup."""

    def create_test_document(self):
        """Create a complete test document."""
        mock_revit = MockRevit()
        doc = mock_revit.create_document()

        # Add walls
        for i in range(10):
            doc.create_element(
                category='Walls',
                properties={'Name': f'Wall-{i+1}', 'Height': 10.0 + i}
            )

        # Add doors
        for i in range(5):
            doc.create_element(
                category='Doors',
                properties={'Name': f'Door-{i+1}', 'Height': 7.0, 'Width': 3.0}
            )

        # Add rooms
        for i in range(8):
            doc.create_element(
                category='Rooms',
                properties={'Name': f'Room-{i+1}', 'Area': 100.0 + i * 10}
            )

        return doc

class TestWithDocumentFixture(RevitTestCase):
    """Test with complete document fixture."""

    def setUp(self):
        """Set up document fixture."""
        fixture = DocumentFixture()
        self.doc = fixture.create_test_document()

    def test_element_counts(self):
        """Test element counts in document."""
        walls = self.doc.get_elements('Walls')
        doors = self.doc.get_elements('Doors')
        rooms = self.doc.get_elements('Rooms')

        self.assertEqual(len(walls), 10)
        self.assertEqual(len(doors), 5)
        self.assertEqual(len(rooms), 8)
```

## Specialized Assertions

### Element Assertions

```python
from revitpy.testing import RevitAssertions

class TestWithAssertions(RevitTestCase):
    """Test using specialized assertions."""

    def test_element_exists(self):
        """Test element existence assertion."""
        with create_mock_context() as context:
            wall = context.create_element('Wall', Name='Test Wall')

            # Assert element exists
            self.assert_element_exists(context, wall.Id)

    def test_parameter_value(self):
        """Test parameter value assertion."""
        wall = MockElement('Wall', Height=10.0)

        # Assert parameter value
        self.assert_parameter_value(wall, 'Height', 10.0)

    def test_parameter_in_range(self):
        """Test parameter in range."""
        wall = MockElement('Wall', Height=10.0)

        # Assert parameter in range
        self.assert_parameter_in_range(wall, 'Height', 8.0, 12.0)

    def test_element_category(self):
        """Test element category assertion."""
        wall = MockElement('Wall')

        # Assert category
        self.assert_element_category(wall, 'Walls')

    def test_element_has_parameter(self):
        """Test element has parameter."""
        wall = MockElement('Wall', Height=10.0)

        # Assert has parameter
        self.assert_element_has_parameter(wall, 'Height')
```

### Geometry Assertions

```python
from revitpy.testing import GeometryAssertions

class TestGeometry(RevitTestCase, GeometryAssertions):
    """Test geometry operations."""

    def test_bounding_box(self):
        """Test bounding box assertion."""
        element = MockElement('Wall', Width=1.0, Height=10.0, Length=20.0)

        # Assert bounding box dimensions
        self.assert_bounding_box_dimensions(
            element,
            expected_width=1.0,
            expected_height=10.0,
            expected_length=20.0,
            tolerance=0.01
        )

    def test_point_location(self):
        """Test point location."""
        element = MockElement('Wall')
        point = (10.0, 20.0, 0.0)

        # Assert point location
        self.assert_point_equals(
            element.get_location(),
            point,
            tolerance=0.01
        )

    def test_volume(self):
        """Test element volume."""
        element = MockElement('Wall', Volume=200.0)

        # Assert volume
        self.assert_volume_equals(element, 200.0, tolerance=1.0)
```

## Snapshot Testing

### Element Snapshots

```python
from revitpy.testing import SnapshotTester, ElementSnapshot

class TestWithSnapshots(RevitTestCase):
    """Test using snapshot testing."""

    def setUp(self):
        """Set up snapshot tester."""
        self.snapshot_tester = SnapshotTester(snapshot_dir='./test_snapshots')

    def test_element_snapshot(self):
        """Test element state snapshot."""
        wall = MockElement(
            'Wall',
            Name='Test Wall',
            Height=10.0,
            Width=0.5,
            Comments='Original'
        )

        # Create snapshot
        snapshot = ElementSnapshot.create(wall)
        self.snapshot_tester.save_snapshot('wall_original', snapshot)

        # Modify element
        wall.set_parameter('Comments', 'Modified')

        # Compare with snapshot
        current = ElementSnapshot.create(wall)
        diff = self.snapshot_tester.compare_snapshot('wall_original', current)

        # Assert changes
        self.assertEqual(len(diff.changed_parameters), 1)
        self.assertIn('Comments', diff.changed_parameters)
```

### Geometry Snapshots

```python
from revitpy.testing import GeometrySnapshot

class TestGeometrySnapshots(RevitTestCase):
    """Test geometry snapshots."""

    def test_geometry_snapshot(self):
        """Test geometry state snapshot."""
        element = MockElement('Wall')

        # Create geometry snapshot
        snapshot = GeometrySnapshot.create(element)

        # Save snapshot
        snapshot.save('wall_geometry.json')

        # Later: load and compare
        loaded_snapshot = GeometrySnapshot.load('wall_geometry.json')
        current = GeometrySnapshot.create(element)

        # Compare geometry
        is_equal = loaded_snapshot.equals(current, tolerance=0.01)
        self.assertTrue(is_equal)
```

## Async Testing

### Async Test Cases

```python
from revitpy.testing import AsyncRevitTestCase
from revitpy.async_support import AsyncRevit, async_transaction

class TestAsyncOperations(AsyncRevitTestCase):
    """Test async operations."""

    async def test_async_element_query(self):
        """Test async element query."""
        async_revit = AsyncRevit()

        # Mock async elements
        await self.add_mock_elements_async([
            MockElement('Wall', Height=8.0),
            MockElement('Wall', Height=12.0),
            MockElement('Wall', Height=15.0)
        ])

        # Query asynchronously
        walls = await async_revit.get_elements_async('Walls')

        # Assertions
        self.assertEqual(len(walls), 3)

    async def test_async_transaction(self):
        """Test async transaction."""
        async_revit = AsyncRevit()

        wall = await self.create_mock_element_async('Wall', Height=10.0)

        async with async_transaction(async_revit, "Test Update") as txn:
            await async_revit.set_parameter_async(wall, 'Height', 12.0)
            await txn.commit()

        # Verify
        updated_wall = await async_revit.get_element_by_id_async(wall.Id)
        self.assertEqual(updated_wall.Height, 12.0)

    async def test_async_error_handling(self):
        """Test async error handling."""
        async_revit = AsyncRevit()

        with self.assertRaises(Exception):
            await async_revit.get_element_by_id_async(invalid_id)
```

### Testing Async Context Managers

```python
class TestAsyncContextManagers(AsyncRevitTestCase):
    """Test async context managers."""

    async def test_async_element_scope(self):
        """Test async element scope."""
        from revitpy.async_support import async_element_scope

        async_revit = AsyncRevit()

        async with async_element_scope(async_revit, element_id=123) as element:
            self.assertIsNotNone(element)
            await async_revit.set_parameter_async(element, 'Comments', 'Test')

        # Element automatically cleaned up
```

## Test Runners

### Custom Test Runner

```python
from revitpy.testing import RevitTestRunner

class CustomTestRunner(RevitTestRunner):
    """Custom test runner with additional features."""

    def run_tests(self, test_suite):
        """Run tests with custom behavior."""
        # Set up test environment
        self.setup_test_environment()

        # Run tests
        result = super().run_tests(test_suite)

        # Generate custom report
        self.generate_custom_report(result)

        # Clean up
        self.cleanup_test_environment()

        return result

    def setup_test_environment(self):
        """Set up test environment."""
        print("Setting up test environment...")
        # Custom setup logic

    def generate_custom_report(self, result):
        """Generate custom test report."""
        print("\nCustom Test Report:")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")

# Use custom runner
runner = CustomTestRunner()
suite = unittest.TestLoader().loadTestsFromTestCase(TestWallOperations)
runner.run_tests(suite)
```

### Test Suite Organization

```python
from revitpy.testing import RevitTestSuite

def create_test_suite():
    """Create organized test suite."""
    suite = RevitTestSuite()

    # Add test groups
    suite.add_test_group('core', [
        TestElementOperations,
        TestTransactionManagement,
        TestQueryOperations
    ])

    suite.add_test_group('orm', [
        TestOrmQueries,
        TestRelationships,
        TestChangeTracking
    ])

    suite.add_test_group('async', [
        TestAsyncOperations,
        TestTaskQueue,
        TestCancellation
    ])

    return suite

# Run specific test group
suite = create_test_suite()
suite.run_group('core')

# Run all tests
suite.run_all()
```

## Mocking Strategies

### Partial Mocking

```python
from revitpy.testing import PartialMock

class TestWithPartialMock(RevitTestCase):
    """Test with partial mocking."""

    def test_partial_mock(self):
        """Test with partially mocked element."""
        # Create element with some real behavior, some mocked
        element = PartialMock(
            real_class=Wall,
            mock_methods=['get_geometry'],  # Mock only these methods
            properties={'Height': 10.0, 'Name': 'Test Wall'}
        )

        # Real behavior
        name = element.Name  # Uses real property

        # Mocked behavior
        geometry = element.get_geometry()  # Uses mock
```

### Spy Objects

```python
from revitpy.testing import SpyElement

class TestWithSpies(RevitTestCase):
    """Test with spy objects."""

    def test_method_calls(self):
        """Test method call tracking."""
        element = SpyElement('Wall')

        # Use element
        element.get_parameter('Height')
        element.set_parameter('Height', 12.0)
        element.get_parameter('Width')

        # Verify method calls
        self.assert_method_called(element, 'get_parameter')
        self.assert_method_called_with(element, 'set_parameter', 'Height', 12.0)
        self.assertEqual(element.get_call_count('get_parameter'), 2)
```

## Performance Testing

### Performance Test Cases

```python
from revitpy.testing import PerformanceTestCase

class TestPerformance(PerformanceTestCase):
    """Test performance characteristics."""

    def test_query_performance(self):
        """Test query performance."""
        with create_mock_context() as context:
            # Add test data
            for i in range(1000):
                context.add_element(MockElement('Wall', Height=10.0))

            # Measure query performance
            with self.measure_time() as timer:
                walls = context.elements.of_category('Walls').to_list()

            # Assert performance
            self.assertLess(timer.elapsed, 1.0, "Query took too long")

    def test_batch_update_performance(self):
        """Test batch update performance."""
        with create_mock_context() as context:
            walls = [MockElement('Wall') for _ in range(100)]

            with self.measure_time() as timer:
                with context.transaction("Batch Update") as txn:
                    for wall in walls:
                        wall.set_parameter('Comments', 'Updated')
                    txn.commit()

            # Assert performance
            time_per_element = timer.elapsed / len(walls)
            self.assertLess(time_per_element, 0.01, "Update too slow per element")
```

## Integration Testing

### Full Integration Tests

```python
class IntegrationTestCase(RevitTestCase):
    """Integration tests with full mock environment."""

    def setUp(self):
        """Set up complete integration test environment."""
        self.mock_revit = MockRevit()
        self.doc = self.mock_revit.create_document()
        self.app = self.mock_revit.create_application()

        # Set up full environment
        self.setup_complete_document()

    def setup_complete_document(self):
        """Set up complete document with all element types."""
        # Add levels
        self.level1 = self.doc.create_element('Level', Name='Level 1', Elevation=0.0)
        self.level2 = self.doc.create_element('Level', Name='Level 2', Elevation=12.0)

        # Add walls
        for i in range(20):
            self.doc.create_element(
                'Wall',
                Name=f'Wall-{i+1}',
                Level=self.level1,
                Height=10.0
            )

        # Add other elements...

    def test_complete_workflow(self):
        """Test complete workflow."""
        # Query elements
        walls = self.doc.get_elements('Walls')
        self.assertEqual(len(walls), 20)

        # Modify elements
        with self.doc.start_transaction("Update") as txn:
            for wall in walls:
                wall.set_parameter('Comments', 'Updated')
            txn.commit()

        # Verify modifications
        for wall in walls:
            self.assertEqual(wall.get_parameter('Comments').AsString(), 'Updated')
```

## Best Practices

1. **Use appropriate mocks**: Mock only what you need
2. **Test behavior, not implementation**: Focus on what code does, not how
3. **Keep tests isolated**: Each test should be independent
4. **Use fixtures**: Reuse common test setups
5. **Test edge cases**: Include boundary and error conditions
6. **Use descriptive test names**: Test names should describe what they test
7. **Mock external dependencies**: Isolate tests from external systems

## Next Steps

- **[Testing Guide](../../guides/testing.md)**: Comprehensive testing guide
- **[Test Examples](../../examples/testing/)**: Example test cases
- **[CI/CD Integration](../../guides/ci-cd.md)**: Integrate tests into CI/CD
