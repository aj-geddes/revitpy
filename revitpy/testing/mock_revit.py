"""
Mock Revit environment for testing without actual Revit installation.
"""

from typing import Any, Dict, List, Optional, Set, Union, Callable
from dataclasses import dataclass, field
from uuid import uuid4
import json
from pathlib import Path
from loguru import logger


@dataclass
class MockParameter:
    """Mock Revit parameter."""
    
    name: str
    value: Any = None
    type_name: str = "String"
    storage_type: str = "String"
    is_read_only: bool = False
    
    def AsString(self) -> str:
        return str(self.value) if self.value is not None else ""
    
    def AsDouble(self) -> float:
        try:
            return float(self.value) if self.value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def AsInteger(self) -> int:
        try:
            return int(self.value) if self.value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def AsValueString(self) -> str:
        return self.AsString()


class MockElementId:
    """Mock Revit element ID."""
    
    def __init__(self, value: int) -> None:
        self.IntegerValue = value
    
    def __str__(self) -> str:
        return str(self.IntegerValue)
    
    def __eq__(self, other) -> bool:
        if isinstance(other, MockElementId):
            return self.IntegerValue == other.IntegerValue
        return False
    
    def __hash__(self) -> int:
        return hash(self.IntegerValue)


class MockElement:
    """Mock Revit element."""
    
    def __init__(
        self,
        element_id: int = None,
        name: str = "MockElement",
        category: str = "Generic",
        element_type: str = "Element"
    ) -> None:
        self.Id = MockElementId(element_id or self._generate_id())
        self.Name = name
        self.Category = category
        self.ElementType = element_type
        self._parameters: Dict[str, MockParameter] = {}
        self._properties: Dict[str, Any] = {}
        
        # Add default parameters
        self._add_default_parameters()
    
    def _generate_id(self) -> int:
        """Generate unique element ID."""
        return int(str(uuid4().int)[:8])
    
    def _add_default_parameters(self) -> None:
        """Add default parameters."""
        self._parameters["Name"] = MockParameter("Name", self.Name)
        self._parameters["Category"] = MockParameter("Category", self.Category)
        self._parameters["Type"] = MockParameter("Type", self.ElementType)
        self._parameters["Comments"] = MockParameter("Comments", "")
        self._parameters["Mark"] = MockParameter("Mark", "")
    
    def GetParameterValue(self, parameter_name: str) -> Any:
        """Get parameter value."""
        if parameter_name in self._parameters:
            return self._parameters[parameter_name]
        raise KeyError(f"Parameter '{parameter_name}' not found")
    
    def SetParameterValue(self, parameter_name: str, value: Any) -> None:
        """Set parameter value."""
        if parameter_name in self._parameters:
            param = self._parameters[parameter_name]
            if param.is_read_only:
                raise ValueError(f"Parameter '{parameter_name}' is read-only")
            param.value = value
        else:
            # Create new parameter
            self._parameters[parameter_name] = MockParameter(parameter_name, value)
    
    def GetParameter(self, parameter_name: str) -> Optional[MockParameter]:
        """Get parameter object."""
        return self._parameters.get(parameter_name)
    
    def SetParameter(self, parameter_name: str, parameter: MockParameter) -> None:
        """Set parameter object."""
        self._parameters[parameter_name] = parameter
    
    def GetAllParameters(self) -> Dict[str, MockParameter]:
        """Get all parameters."""
        return self._parameters.copy()
    
    def HasParameter(self, parameter_name: str) -> bool:
        """Check if parameter exists."""
        return parameter_name in self._parameters
    
    def GetProperty(self, property_name: str) -> Any:
        """Get element property."""
        return self._properties.get(property_name)
    
    def SetProperty(self, property_name: str, value: Any) -> None:
        """Set element property."""
        self._properties[property_name] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert element to dictionary."""
        return {
            'id': self.Id.IntegerValue,
            'name': self.Name,
            'category': self.Category,
            'element_type': self.ElementType,
            'parameters': {
                name: {'value': param.value, 'type': param.type_name}
                for name, param in self._parameters.items()
            },
            'properties': self._properties.copy()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MockElement':
        """Create element from dictionary."""
        element = cls(
            element_id=data['id'],
            name=data['name'],
            category=data['category'],
            element_type=data['element_type']
        )
        
        # Set parameters
        for name, param_data in data.get('parameters', {}).items():
            element.SetParameterValue(name, param_data['value'])
            if 'type' in param_data:
                element._parameters[name].type_name = param_data['type']
        
        # Set properties
        for name, value in data.get('properties', {}).items():
            element.SetProperty(name, value)
        
        return element
    
    def __str__(self) -> str:
        return f"MockElement({self.Id.IntegerValue}): {self.Name}"
    
    def __repr__(self) -> str:
        return f"<MockElement id={self.Id.IntegerValue} name='{self.Name}' type='{self.ElementType}'>"


class MockTransaction:
    """Mock Revit transaction."""
    
    def __init__(self, name: str = "MockTransaction") -> None:
        self.name = name
        self.is_started = False
        self.is_committed = False
        self.is_rolled_back = False
    
    def Start(self) -> bool:
        """Start transaction."""
        self.is_started = True
        return True
    
    def Commit(self) -> bool:
        """Commit transaction."""
        if not self.is_started:
            return False
        self.is_committed = True
        return True
    
    def RollBack(self) -> bool:
        """Rollback transaction."""
        if not self.is_started:
            return False
        self.is_rolled_back = True
        return True


class MockDocument:
    """Mock Revit document."""
    
    def __init__(
        self,
        title: str = "MockDocument.rvt",
        path: str = "",
        is_family_document: bool = False
    ) -> None:
        self.Title = title
        self.PathName = path
        self.IsFamilyDocument = is_family_document
        self._elements: Dict[int, MockElement] = {}
        self._element_counter = 1000
        self._is_modified = False
        self._transactions: List[MockTransaction] = []
    
    def GetElements(self, filter_criteria=None) -> List[MockElement]:
        """Get all elements or filtered elements."""
        elements = list(self._elements.values())
        
        if filter_criteria and callable(filter_criteria):
            elements = [elem for elem in elements if filter_criteria(elem)]
        
        return elements
    
    def GetElement(self, element_id: Union[int, MockElementId]) -> Optional[MockElement]:
        """Get element by ID."""
        if isinstance(element_id, MockElementId):
            element_id = element_id.IntegerValue
        
        return self._elements.get(element_id)
    
    def AddElement(self, element: MockElement) -> MockElement:
        """Add element to document."""
        self._elements[element.Id.IntegerValue] = element
        self._is_modified = True
        return element
    
    def CreateElement(
        self,
        name: str = "NewElement",
        category: str = "Generic",
        element_type: str = "Element"
    ) -> MockElement:
        """Create new element."""
        self._element_counter += 1
        element = MockElement(
            element_id=self._element_counter,
            name=name,
            category=category,
            element_type=element_type
        )
        
        return self.AddElement(element)
    
    def Delete(self, element_ids: List[Union[int, MockElementId]]) -> None:
        """Delete elements by IDs."""
        for element_id in element_ids:
            if isinstance(element_id, MockElementId):
                element_id = element_id.IntegerValue
            
            if element_id in self._elements:
                del self._elements[element_id]
                self._is_modified = True
    
    def Save(self) -> bool:
        """Save document."""
        if not self.PathName:
            return False
        
        self._is_modified = False
        return True
    
    def Close(self, save_changes: bool = True) -> bool:
        """Close document."""
        if save_changes and self._is_modified:
            return self.Save()
        return True
    
    def StartTransaction(self, name: str = "Transaction") -> MockTransaction:
        """Start a new transaction."""
        transaction = MockTransaction(name)
        transaction.Start()
        self._transactions.append(transaction)
        return transaction
    
    def IsModified(self) -> bool:
        """Check if document is modified."""
        return self._is_modified
    
    def GetElementCount(self) -> int:
        """Get number of elements."""
        return len(self._elements)
    
    def GetElementsByCategory(self, category: str) -> List[MockElement]:
        """Get elements by category."""
        return [elem for elem in self._elements.values() if elem.Category == category]
    
    def GetElementsByType(self, element_type: str) -> List[MockElement]:
        """Get elements by type."""
        return [elem for elem in self._elements.values() if elem.ElementType == element_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary."""
        return {
            'title': self.Title,
            'path': self.PathName,
            'is_family_document': self.IsFamilyDocument,
            'is_modified': self._is_modified,
            'elements': [elem.to_dict() for elem in self._elements.values()]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MockDocument':
        """Create document from dictionary."""
        doc = cls(
            title=data['title'],
            path=data['path'],
            is_family_document=data.get('is_family_document', False)
        )
        
        doc._is_modified = data.get('is_modified', False)
        
        # Add elements
        for elem_data in data.get('elements', []):
            element = MockElement.from_dict(elem_data)
            doc._elements[element.Id.IntegerValue] = element
        
        return doc


class MockApplication:
    """Mock Revit application."""
    
    def __init__(self) -> None:
        self._documents: List[MockDocument] = []
        self._active_document: Optional[MockDocument] = None
    
    @property
    def ActiveDocument(self) -> Optional[MockDocument]:
        """Get active document."""
        return self._active_document
    
    def OpenDocumentFile(self, file_path: str) -> MockDocument:
        """Open document file."""
        doc = MockDocument(title=Path(file_path).name, path=file_path)
        self._documents.append(doc)
        self._active_document = doc
        return doc
    
    def CreateDocument(self, template_path: Optional[str] = None) -> MockDocument:
        """Create new document."""
        doc = MockDocument(title="Untitled.rvt")
        self._documents.append(doc)
        self._active_document = doc
        return doc
    
    def GetOpenDocuments(self) -> List[MockDocument]:
        """Get all open documents."""
        return self._documents.copy()
    
    def CloseDocument(self, document: MockDocument) -> bool:
        """Close document."""
        if document in self._documents:
            self._documents.remove(document)
            
            if self._active_document == document:
                self._active_document = self._documents[0] if self._documents else None
            
            return True
        return False


class MockRevit:
    """
    Mock Revit environment for testing RevitPy without actual Revit installation.
    """
    
    def __init__(self) -> None:
        self.application = MockApplication()
        self._fixtures: Dict[str, Any] = {}
        self._event_handlers: List[Callable] = []
    
    @property
    def active_document(self) -> Optional[MockDocument]:
        """Get active document."""
        return self.application.ActiveDocument
    
    def create_document(self, title: str = "TestDocument.rvt") -> MockDocument:
        """Create a test document."""
        doc = MockDocument(title=title)
        self.application._documents.append(doc)
        self.application._active_document = doc
        return doc
    
    def create_element(
        self,
        name: str = "TestElement",
        category: str = "Generic",
        element_type: str = "Element",
        parameters: Optional[Dict[str, Any]] = None
    ) -> MockElement:
        """Create a test element."""
        element = MockElement(name=name, category=category, element_type=element_type)
        
        if parameters:
            for param_name, value in parameters.items():
                element.SetParameterValue(param_name, value)
        
        # Add to active document if available
        if self.active_document:
            self.active_document.AddElement(element)
        
        return element
    
    def create_elements(
        self,
        count: int,
        name_prefix: str = "Element",
        category: str = "Generic",
        element_type: str = "Element"
    ) -> List[MockElement]:
        """Create multiple test elements."""
        elements = []
        
        for i in range(count):
            element = self.create_element(
                name=f"{name_prefix}_{i+1}",
                category=category,
                element_type=element_type
            )
            elements.append(element)
        
        return elements
    
    def load_fixture(self, fixture_name: str, fixture_data: Any) -> None:
        """Load test fixture."""
        self._fixtures[fixture_name] = fixture_data
        logger.debug(f"Loaded fixture: {fixture_name}")
    
    def get_fixture(self, fixture_name: str) -> Any:
        """Get test fixture."""
        return self._fixtures.get(fixture_name)
    
    def save_state(self, file_path: str) -> None:
        """Save mock Revit state to file."""
        state = {
            'documents': [doc.to_dict() for doc in self.application._documents],
            'active_document_title': self.active_document.Title if self.active_document else None,
            'fixtures': self._fixtures
        }
        
        with open(file_path, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info(f"Saved mock Revit state to {file_path}")
    
    def load_state(self, file_path: str) -> None:
        """Load mock Revit state from file."""
        with open(file_path, 'r') as f:
            state = json.load(f)
        
        # Clear current state
        self.application._documents.clear()
        self.application._active_document = None
        
        # Load documents
        for doc_data in state.get('documents', []):
            doc = MockDocument.from_dict(doc_data)
            self.application._documents.append(doc)
        
        # Set active document
        active_title = state.get('active_document_title')
        if active_title:
            for doc in self.application._documents:
                if doc.Title == active_title:
                    self.application._active_document = doc
                    break
        
        # Load fixtures
        self._fixtures = state.get('fixtures', {})
        
        logger.info(f"Loaded mock Revit state from {file_path}")
    
    def reset(self) -> None:
        """Reset mock Revit to initial state."""
        self.application._documents.clear()
        self.application._active_document = None
        self._fixtures.clear()
        self._event_handlers.clear()
        
        logger.debug("Reset mock Revit environment")
    
    def add_event_handler(self, handler: Callable) -> None:
        """Add event handler for testing."""
        self._event_handlers.append(handler)
    
    def trigger_event(self, event_type: str, event_data: Any) -> None:
        """Trigger event for testing."""
        for handler in self._event_handlers:
            try:
                handler(event_type, event_data)
            except Exception as e:
                logger.error(f"Event handler failed: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get mock Revit statistics."""
        total_elements = sum(doc.GetElementCount() for doc in self.application._documents)
        
        return {
            'documents': len(self.application._documents),
            'total_elements': total_elements,
            'fixtures': len(self._fixtures),
            'event_handlers': len(self._event_handlers),
            'has_active_document': self.active_document is not None
        }