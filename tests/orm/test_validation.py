"""
Unit tests for the ORM validation system.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Any, Dict

from revitpy.orm.validation import (
    BaseElement, WallElement, RoomElement, DoorElement, WindowElement,
    ElementValidator, ValidationLevel, ValidationRule, ConstraintType,
    TypeSafetyMixin, create_wall, create_room, create_door, create_window
)
from revitpy.orm.types import ElementState
from revitpy.orm.exceptions import ValidationError as ORMValidationError
from pydantic import ValidationError


class TestBaseElement:
    """Test BaseElement validation."""
    
    def test_valid_base_element(self):
        """Test creating valid base element."""
        element = BaseElement(
            id=123,
            name="Test Element",
            category="TestCategory"
        )
        
        assert element.id == 123
        assert element.name == "Test Element"
        assert element.category == "TestCategory"
        assert element.state == ElementState.UNCHANGED
        assert element.version == 1
        assert element.is_valid is True
    
    def test_base_element_defaults(self):
        """Test default values for base element."""
        element = BaseElement(id=456)
        
        assert element.id == 456
        assert element.name is None
        assert element.category is None
        assert element.state == ElementState.UNCHANGED
        assert element.version == 1
        assert isinstance(element.created_at, datetime)
        assert isinstance(element.modified_at, datetime)
    
    def test_name_validation(self):
        """Test name field validation."""
        # Empty string should become None
        element = BaseElement(id=1, name="")
        assert element.name is None
        
        # Whitespace-only should become None
        element = BaseElement(id=2, name="   ")
        assert element.name is None
        
        # Valid name should be trimmed
        element = BaseElement(id=3, name="  Valid Name  ")
        assert element.name == "Valid Name"
    
    def test_mark_dirty(self):
        """Test marking element as dirty."""
        element = BaseElement(id=1)
        original_modified = element.modified_at
        original_version = element.version
        
        element.mark_dirty()
        
        assert element.state == ElementState.MODIFIED
        assert element.modified_at > original_modified
        assert element.version == original_version + 1
        assert element.is_dirty() is True
    
    def test_mark_clean(self):
        """Test marking element as clean."""
        element = BaseElement(id=1)
        element.mark_dirty()
        
        element.mark_clean()
        assert element.state == ElementState.UNCHANGED
        assert element.is_dirty() is False


class TestWallElement:
    """Test WallElement validation."""
    
    def test_valid_wall_element(self):
        """Test creating valid wall element."""
        wall = WallElement(
            id=1,
            height=10.0,
            length=20.0,
            width=0.5,
            name="Test Wall"
        )
        
        assert wall.height == 10.0
        assert wall.length == 20.0
        assert wall.width == 0.5
        assert wall.area == 200.0  # Auto-calculated
        assert wall.volume == 100.0  # Auto-calculated
    
    def test_wall_dimension_validation(self):
        """Test wall dimension validation."""
        # Height must be positive
        with pytest.raises(ValidationError):
            WallElement(id=1, height=0, length=10, width=0.5)
        
        with pytest.raises(ValidationError):
            WallElement(id=1, height=-1, length=10, width=0.5)
        
        # Length must be positive
        with pytest.raises(ValidationError):
            WallElement(id=1, height=10, length=0, width=0.5)
        
        # Width must be positive
        with pytest.raises(ValidationError):
            WallElement(id=1, height=10, length=10, width=0)
    
    def test_wall_auto_calculation(self):
        """Test automatic calculation of derived properties."""
        wall = WallElement(id=1, height=8, length=12, width=0.5)
        
        assert wall.area == 96.0  # 8 * 12
        assert wall.volume == 48.0  # 8 * 12 * 0.5
    
    def test_wall_with_provided_area_volume(self):
        """Test wall with explicitly provided area and volume."""
        wall = WallElement(
            id=1,
            height=8,
            length=12, 
            width=0.5,
            area=100.0,  # Override calculated value
            volume=50.0   # Override calculated value
        )
        
        assert wall.area == 100.0
        assert wall.volume == 50.0
    
    def test_wall_structural_properties(self):
        """Test wall structural and finish properties."""
        wall = WallElement(
            id=1,
            height=10,
            length=20,
            width=0.5,
            structural=True,
            fire_rating=2,
            structural_material="Concrete",
            finish_material_interior="Drywall",
            finish_material_exterior="Brick"
        )
        
        assert wall.structural is True
        assert wall.fire_rating == 2
        assert wall.structural_material == "Concrete"


class TestRoomElement:
    """Test RoomElement validation."""
    
    def test_valid_room_element(self):
        """Test creating valid room element."""
        room = RoomElement(
            id=1,
            number="101",
            area=250.0,
            perimeter=60.0,
            volume=2500.0,
            name="Conference Room"
        )
        
        assert room.number == "101"
        assert room.area == 250.0
        assert room.perimeter == 60.0
        assert room.volume == 2500.0
    
    def test_room_number_validation(self):
        """Test room number validation."""
        # Valid room numbers
        room1 = RoomElement(id=1, number="101", area=100, perimeter=40, volume=1000)
        assert room1.number == "101"
        
        room2 = RoomElement(id=2, number="A-101.5", area=100, perimeter=40, volume=1000)
        assert room2.number == "A-101.5"
        
        # Invalid room numbers
        with pytest.raises(ValidationError):
            RoomElement(id=3, number="", area=100, perimeter=40, volume=1000)
        
        with pytest.raises(ValidationError):
            RoomElement(id=4, number="   ", area=100, perimeter=40, volume=1000)
        
        with pytest.raises(ValidationError):
            RoomElement(id=5, number="101@#$", area=100, perimeter=40, volume=1000)
    
    def test_room_area_validation(self):
        """Test room area validation."""
        # Negative area should fail
        with pytest.raises(ValidationError):
            RoomElement(id=1, number="101", area=-10, perimeter=40, volume=1000)
        
        # Zero area is allowed
        room = RoomElement(id=1, number="101", area=0, perimeter=40, volume=1000)
        assert room.area == 0
    
    def test_room_environmental_properties(self):
        """Test room environmental property validation."""
        room = RoomElement(
            id=1,
            number="101",
            area=200,
            perimeter=50,
            volume=2000,
            temperature=72.5,
            humidity=45.0,
            air_flow_required=150.0
        )
        
        assert room.temperature == 72.5
        assert room.humidity == 45.0
        assert room.air_flow_required == 150.0
        
        # Invalid temperature
        with pytest.raises(ValidationError):
            RoomElement(
                id=2, number="102", area=200, perimeter=50, volume=2000,
                temperature=200  # Too hot
            )
        
        # Invalid humidity
        with pytest.raises(ValidationError):
            RoomElement(
                id=3, number="103", area=200, perimeter=50, volume=2000,
                humidity=150  # Over 100%
            )


class TestDoorElement:
    """Test DoorElement validation."""
    
    def test_valid_door_element(self):
        """Test creating valid door element."""
        door = DoorElement(
            id=1,
            width=3.0,
            height=7.0,
            material="Wood",
            fire_rating=0.75,
            hand="Left"
        )
        
        assert door.width == 3.0
        assert door.height == 7.0
        assert door.material == "Wood"
        assert door.fire_rating == 0.75
        assert door.hand == "Left"
    
    def test_door_dimension_validation(self):
        """Test door dimension validation."""
        # Valid dimensions
        door = DoorElement(id=1, width=3.0, height=7.0)
        assert door.width == 3.0
        assert door.height == 7.0
        
        # Invalid dimensions
        with pytest.raises(ValidationError):
            DoorElement(id=2, width=0, height=7.0)
        
        with pytest.raises(ValidationError):
            DoorElement(id=3, width=3.0, height=-1)
    
    def test_door_hand_validation(self):
        """Test door hand validation."""
        # Valid hands
        door_left = DoorElement(id=1, width=3, height=7, hand="Left")
        door_right = DoorElement(id=2, width=3, height=7, hand="Right")
        
        assert door_left.hand == "Left"
        assert door_right.hand == "Right"
        
        # Invalid hand
        with pytest.raises(ValidationError):
            DoorElement(id=3, width=3, height=7, hand="Middle")


class TestWindowElement:
    """Test WindowElement validation."""
    
    def test_valid_window_element(self):
        """Test creating valid window element."""
        window = WindowElement(
            id=1,
            width=4.0,
            height=3.0,
            glass_type="Double Pane",
            u_factor=0.35,
            solar_heat_gain=0.4,
            energy_star_rated=True
        )
        
        assert window.width == 4.0
        assert window.height == 3.0
        assert window.u_factor == 0.35
        assert window.solar_heat_gain == 0.4
        assert window.energy_star_rated is True
    
    def test_window_performance_validation(self):
        """Test window performance property validation."""
        # Valid SHGC
        window = WindowElement(id=1, width=4, height=3, solar_heat_gain=0.5)
        assert window.solar_heat_gain == 0.5
        
        # Invalid SHGC (over 1.0)
        with pytest.raises(ValidationError):
            WindowElement(id=2, width=4, height=3, solar_heat_gain=1.5)
        
        # Invalid SHGC (negative)
        with pytest.raises(ValidationError):
            WindowElement(id=3, width=4, height=3, solar_heat_gain=-0.1)


class TestValidationRule:
    """Test ValidationRule class."""
    
    def test_required_rule(self):
        """Test required validation rule."""
        rule = ValidationRule(
            property_name="name",
            constraint_type=ConstraintType.REQUIRED,
            constraint_value=True,
            error_message="Name is required"
        )
        
        # Valid value
        is_valid, error = rule.validate_value("Test Name")
        assert is_valid is True
        assert error is None
        
        # Invalid values
        is_valid, error = rule.validate_value(None)
        assert is_valid is False
        assert error == "Name is required"
        
        is_valid, error = rule.validate_value("")
        assert is_valid is False
        assert error == "Name is required"
        
        is_valid, error = rule.validate_value("   ")
        assert is_valid is False
        assert error == "Name is required"
    
    def test_min_value_rule(self):
        """Test minimum value validation rule."""
        rule = ValidationRule(
            property_name="height",
            constraint_type=ConstraintType.MIN_VALUE,
            constraint_value=5.0,
            error_message="Height must be at least 5.0"
        )
        
        # Valid value
        is_valid, error = rule.validate_value(10.0)
        assert is_valid is True
        
        # Invalid value
        is_valid, error = rule.validate_value(3.0)
        assert is_valid is False
        assert error == "Height must be at least 5.0"
        
        # None value should pass (optional field)
        is_valid, error = rule.validate_value(None)
        assert is_valid is True
    
    def test_pattern_rule(self):
        """Test pattern validation rule."""
        rule = ValidationRule(
            property_name="room_number",
            constraint_type=ConstraintType.PATTERN,
            constraint_value=r'^\d{3}[A-Z]?$',
            error_message="Room number must be 3 digits optionally followed by a letter"
        )
        
        # Valid patterns
        is_valid, error = rule.validate_value("101")
        assert is_valid is True
        
        is_valid, error = rule.validate_value("205B")
        assert is_valid is True
        
        # Invalid patterns
        is_valid, error = rule.validate_value("1A")
        assert is_valid is False
        
        is_valid, error = rule.validate_value("ABCD")
        assert is_valid is False


class TestElementValidator:
    """Test ElementValidator class."""
    
    def test_validator_creation(self):
        """Test validator creation with different levels."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        assert validator.validation_level == ValidationLevel.STANDARD
        assert len(validator.custom_rules) == 0
        
        # With custom rules
        custom_rule = ValidationRule(
            property_name="test",
            constraint_type=ConstraintType.REQUIRED,
            constraint_value=True,
            error_message="Test required"
        )
        validator = ElementValidator(
            ValidationLevel.STRICT,
            custom_rules=[custom_rule]
        )
        assert len(validator.custom_rules) == 1
    
    def test_validate_valid_element(self):
        """Test validating valid elements."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        wall = WallElement(id=1, height=10, length=20, width=0.5)
        errors = validator.validate_element(wall)
        assert len(errors) == 0
        
        room = RoomElement(id=1, number="101", area=200, perimeter=50, volume=2000)
        errors = validator.validate_element(room)
        assert len(errors) == 0
    
    def test_validate_invalid_element(self):
        """Test validating invalid elements."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        # Create invalid wall (negative height)
        try:
            wall = WallElement(id=1, height=-10, length=20, width=0.5)
            # Should not reach here
            assert False, "Expected validation error"
        except ValidationError:
            pass  # Expected
    
    def test_validate_element_dict(self):
        """Test validating element from dictionary."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        # Valid data
        wall_data = {
            "id": 1,
            "height": 10.0,
            "length": 20.0,
            "width": 0.5,
            "name": "Test Wall"
        }
        errors = validator.validate_element_dict(wall_data, "Wall")
        assert len(errors) == 0
        
        # Invalid data (missing required field)
        invalid_data = {
            "id": 1,
            "height": 10.0,
            # Missing length
            "width": 0.5
        }
        errors = validator.validate_element_dict(invalid_data, "Wall")
        assert len(errors) > 0
        assert "length" in errors
    
    @pytest.mark.asyncio
    async def test_async_validation(self):
        """Test async validation."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        wall = WallElement(id=1, height=10, length=20, width=0.5)
        errors = await validator.validate_element_async(wall)
        assert len(errors) == 0
    
    def test_batch_validation(self):
        """Test batch validation."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        elements = [
            WallElement(id=1, height=10, length=20, width=0.5),
            RoomElement(id=2, number="101", area=200, perimeter=50, volume=2000),
            DoorElement(id=3, width=3, height=7)
        ]
        
        error_list = validator.validate_batch(elements)
        assert len(error_list) == 3
        assert all(len(errors) == 0 for errors in error_list)
    
    @pytest.mark.asyncio
    async def test_async_batch_validation(self):
        """Test async batch validation."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        elements = [
            WallElement(id=1, height=10, length=20, width=0.5),
            RoomElement(id=2, number="101", area=200, perimeter=50, volume=2000)
        ]
        
        error_list = await validator.validate_batch_async(elements)
        assert len(error_list) == 2
        assert all(len(errors) == 0 for errors in error_list)
    
    def test_custom_rules(self):
        """Test custom validation rules."""
        custom_rule = ValidationRule(
            property_name="name",
            constraint_type=ConstraintType.MIN_LENGTH,
            constraint_value=5,
            error_message="Name must be at least 5 characters"
        )
        
        validator = ElementValidator(
            ValidationLevel.STANDARD,
            custom_rules=[custom_rule]
        )
        
        # Element with short name should fail
        element = BaseElement(id=1, name="ABC")
        errors = validator.validate_element(element)
        assert "name" in errors
        assert "must be at least 5 characters" in errors["name"][0]
        
        # Element with long enough name should pass
        element = BaseElement(id=1, name="Valid Name")
        errors = validator.validate_element(element)
        # Should only have the custom rule error for name
        assert len([e for e in errors.get("name", []) if "must be at least 5 characters" in e]) == 0
    
    def test_is_valid_convenience_method(self):
        """Test is_valid convenience method."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        valid_wall = WallElement(id=1, height=10, length=20, width=0.5)
        assert validator.is_valid(valid_wall) is True
    
    def test_assert_valid(self):
        """Test assert_valid method."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        valid_wall = WallElement(id=1, height=10, length=20, width=0.5)
        # Should not raise exception
        validator.assert_valid(valid_wall)
    
    def test_element_registration(self):
        """Test custom element type registration."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        class CustomElement(BaseElement):
            custom_property: str = "default"
        
        validator.register_element_type("Custom", CustomElement)
        assert "Custom" in validator.element_types
        assert validator.element_types["Custom"] == CustomElement
    
    def test_schema_generation(self):
        """Test JSON schema generation."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        schema = validator.get_element_schema("Wall")
        assert schema is not None
        assert "properties" in schema
        assert "height" in schema["properties"]
        assert "length" in schema["properties"]
        assert "width" in schema["properties"]
    
    def test_validation_level_none(self):
        """Test that no validation occurs when level is NONE."""
        validator = ElementValidator(ValidationLevel.NONE)
        
        # Even invalid data should return no errors
        element = BaseElement(id=1)
        errors = validator.validate_element(element)
        assert len(errors) == 0


class TestTypeSafetyMixin:
    """Test TypeSafetyMixin functionality."""
    
    def test_ensure_type_safety_valid(self):
        """Test type safety with valid objects."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        type_safety = TypeSafetyMixin(validator)
        
        wall = WallElement(id=1, height=10, length=20, width=0.5)
        result = type_safety.ensure_type_safety(wall, WallElement)
        assert result is wall
        assert isinstance(result, WallElement)
    
    def test_ensure_type_safety_dict_conversion(self):
        """Test type safety with dictionary conversion."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        type_safety = TypeSafetyMixin(validator)
        
        wall_data = {
            "id": 1,
            "height": 10.0,
            "length": 20.0,
            "width": 0.5
        }
        
        result = type_safety.ensure_type_safety(wall_data, WallElement)
        assert isinstance(result, WallElement)
        assert result.height == 10.0
        assert result.length == 20.0
        assert result.width == 0.5
    
    def test_ensure_type_safety_invalid_type(self):
        """Test type safety with invalid type."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        type_safety = TypeSafetyMixin(validator)
        
        # Try to pass a string when WallElement is expected
        with pytest.raises(ORMValidationError):
            type_safety.ensure_type_safety("not a wall", WallElement)
    
    def test_validate_collection(self):
        """Test collection validation."""
        validator = ElementValidator(ValidationLevel.STANDARD)
        type_safety = TypeSafetyMixin(validator)
        
        elements = [
            WallElement(id=1, height=10, length=20, width=0.5),
            WallElement(id=2, height=8, length=15, width=0.4)
        ]
        
        result = type_safety.validate_collection(elements, WallElement)
        assert len(result) == 2
        assert all(isinstance(elem, WallElement) for elem in result)


class TestFactoryFunctions:
    """Test factory functions for creating elements."""
    
    def test_create_wall(self):
        """Test create_wall factory function."""
        wall = create_wall(
            id=1,
            height=10.0,
            length=20.0,
            width=0.5,
            name="Test Wall"
        )
        
        assert isinstance(wall, WallElement)
        assert wall.id == 1
        assert wall.height == 10.0
        assert wall.length == 20.0
        assert wall.width == 0.5
        assert wall.name == "Test Wall"
    
    def test_create_room(self):
        """Test create_room factory function."""
        room = create_room(
            id=1,
            number="101",
            area=200.0,
            name="Conference Room"
        )
        
        assert isinstance(room, RoomElement)
        assert room.id == 1
        assert room.number == "101"
        assert room.area == 200.0
        assert room.name == "Conference Room"
    
    def test_create_door(self):
        """Test create_door factory function."""
        door = create_door(
            id=1,
            width=3.0,
            height=7.0,
            material="Wood"
        )
        
        assert isinstance(door, DoorElement)
        assert door.id == 1
        assert door.width == 3.0
        assert door.height == 7.0
        assert door.material == "Wood"
    
    def test_create_window(self):
        """Test create_window factory function."""
        window = create_window(
            id=1,
            width=4.0,
            height=3.0,
            glass_type="Double Pane"
        )
        
        assert isinstance(window, WindowElement)
        assert window.id == 1
        assert window.width == 4.0
        assert window.height == 3.0
        assert window.glass_type == "Double Pane"
    
    def test_factory_validation(self):
        """Test that factory functions validate input."""
        # Invalid wall dimensions should raise ValidationError
        with pytest.raises(ValidationError):
            create_wall(id=1, height=-1, length=10, width=0.5)
        
        # Invalid room number should raise ValidationError
        with pytest.raises(ValidationError):
            create_room(id=1, number="", area=100)