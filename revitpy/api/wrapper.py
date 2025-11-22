"""
Main RevitAPI wrapper class providing high-level interface.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from loguru import logger

from .element import Element, ElementSet, IRevitElement
from .exceptions import ConnectionError, ModelError, RevitAPIError
from .query import IElementProvider, Query, QueryBuilder
from .transaction import (
    ITransactionProvider,
    Transaction,
    TransactionGroup,
    TransactionOptions,
)

T = TypeVar("T", bound=Element)


class IRevitApplication(Protocol):
    """Protocol for Revit application interface."""

    @property
    def ActiveDocument(self) -> Any: ...

    def OpenDocumentFile(self, file_path: str) -> Any: ...

    def CreateDocument(self, template_path: str | None = None) -> Any: ...


class IRevitDocument(Protocol):
    """Protocol for Revit document interface."""

    @property
    def Title(self) -> str: ...

    @property
    def PathName(self) -> str: ...

    def GetElements(
        self, filter_criteria: Any | None = None
    ) -> list[IRevitElement]: ...

    def GetElement(self, element_id: Any) -> IRevitElement | None: ...

    def Delete(self, element_ids: list[Any]) -> None: ...

    def Save(self) -> bool: ...

    def Close(self, save_changes: bool = True) -> bool: ...


@dataclass
class DocumentInfo:
    """Information about a Revit document."""

    title: str
    path: str
    is_modified: bool = False
    is_read_only: bool = False
    version: str | None = None

    @property
    def name(self) -> str:
        """Get document name without extension."""
        import os

        return os.path.splitext(self.title)[0]


class RevitDocumentProvider(IElementProvider, ITransactionProvider):
    """
    Provider that bridges RevitPy to the actual Revit document.
    """

    def __init__(self, revit_document: IRevitDocument) -> None:
        self._revit_document = revit_document
        self._element_cache: dict[int, Element] = {}
        self._transaction_stack: list[Any] = []

    @property
    def document(self) -> IRevitDocument:
        """Get the underlying Revit document."""
        return self._revit_document

    def get_all_elements(self) -> list[Element]:
        """Get all elements from the document."""
        try:
            revit_elements = self._revit_document.GetElements()
            return [self._wrap_element(elem) for elem in revit_elements]

        except Exception as e:
            logger.error(f"Failed to get all elements: {e}")
            raise RevitAPIError("Failed to retrieve elements", e)

    def get_elements_of_type(self, element_type: type[Element]) -> list[Element]:
        """Get elements of specific type."""
        # This would use Revit's filtered element collector
        # For now, return all elements and filter by type
        all_elements = self.get_all_elements()
        return [elem for elem in all_elements if isinstance(elem, element_type)]

    def get_element_by_id(self, element_id: Any) -> Element | None:
        """Get element by ID."""
        try:
            # Check cache first
            if isinstance(element_id, int) and element_id in self._element_cache:
                return self._element_cache[element_id]

            revit_element = self._revit_document.GetElement(element_id)
            if revit_element is None:
                return None

            element = self._wrap_element(revit_element)

            # Cache the element
            if isinstance(element_id, int):
                self._element_cache[element_id] = element

            return element

        except Exception as e:
            logger.warning(f"Failed to get element by ID {element_id}: {e}")
            return None

    def delete_elements(self, element_ids: list[Any]) -> None:
        """Delete elements by IDs."""
        try:
            self._revit_document.Delete(element_ids)

            # Remove from cache
            for elem_id in element_ids:
                if isinstance(elem_id, int) and elem_id in self._element_cache:
                    del self._element_cache[elem_id]

            logger.info(f"Deleted {len(element_ids)} elements")

        except Exception as e:
            logger.error(f"Failed to delete elements: {e}")
            raise RevitAPIError("Failed to delete elements", e)

    def refresh_element_cache(self) -> None:
        """Refresh the element cache."""
        self._element_cache.clear()
        logger.debug("Element cache refreshed")

    def _wrap_element(self, revit_element: IRevitElement) -> Element:
        """Wrap a Revit element in our Element class."""
        return Element(revit_element)

    # ITransactionProvider implementation

    def start_transaction(self, name: str) -> Any:
        """Start a new transaction."""
        # This would create a Revit transaction
        # For now, return a mock transaction
        transaction = f"Transaction_{name}_{len(self._transaction_stack)}"
        self._transaction_stack.append(transaction)
        logger.debug(f"Started transaction: {transaction}")
        return transaction

    def commit_transaction(self, transaction: Any) -> bool:
        """Commit a transaction."""
        if transaction not in self._transaction_stack:
            logger.error(f"Transaction not found in stack: {transaction}")
            return False

        self._transaction_stack.remove(transaction)
        logger.debug(f"Committed transaction: {transaction}")
        return True

    def rollback_transaction(self, transaction: Any) -> bool:
        """Rollback a transaction."""
        if transaction not in self._transaction_stack:
            logger.error(f"Transaction not found in stack: {transaction}")
            return False

        self._transaction_stack.remove(transaction)
        logger.debug(f"Rolled back transaction: {transaction}")
        return True

    def is_in_transaction(self) -> bool:
        """Check if currently in a transaction."""
        return len(self._transaction_stack) > 0


class RevitAPI:
    """
    Main RevitPy API class providing high-level interface to Revit.
    """

    def __init__(self, revit_application: IRevitApplication | None = None) -> None:
        self._revit_app = revit_application
        self._active_document: RevitDocumentProvider | None = None
        self._document_cache: dict[str, weakref.ReferenceType] = {}
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to Revit."""
        return self._is_connected and self._revit_app is not None

    @property
    def active_document(self) -> RevitDocumentProvider | None:
        """Get the active document provider."""
        if not self.is_connected:
            return None

        if self._active_document is None:
            try:
                active_doc = self._revit_app.ActiveDocument
                if active_doc is not None:
                    self._active_document = RevitDocumentProvider(active_doc)
            except Exception as e:
                logger.warning(f"Failed to get active document: {e}")

        return self._active_document

    @property
    def elements(self) -> QueryBuilder[Element]:
        """Get query builder for all elements."""
        if not self.active_document:
            raise ConnectionError("No active document")

        return Query.from_provider(self.active_document)

    def connect(self, revit_application: IRevitApplication | None = None) -> None:
        """Connect to Revit application."""
        if revit_application:
            self._revit_app = revit_application

        if not self._revit_app:
            raise ConnectionError("No Revit application provided")

        try:
            # Test connection by accessing a property
            _ = self._revit_app.ActiveDocument
            self._is_connected = True
            logger.info("Connected to Revit application")

        except Exception as e:
            self._is_connected = False
            logger.error(f"Failed to connect to Revit: {e}")
            raise ConnectionError("Failed to connect to Revit application", e)

    def disconnect(self) -> None:
        """Disconnect from Revit application."""
        self._revit_app = None
        self._active_document = None
        self._document_cache.clear()
        self._is_connected = False
        logger.info("Disconnected from Revit")

    def open_document(self, file_path: str) -> RevitDocumentProvider:
        """Open a document."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Revit")

        try:
            revit_doc = self._revit_app.OpenDocumentFile(file_path)
            if revit_doc is None:
                raise ModelError(f"Failed to open document: {file_path}")

            provider = RevitDocumentProvider(revit_doc)

            # Cache the document
            self._document_cache[file_path] = weakref.ref(provider)

            # Set as active document
            self._active_document = provider

            logger.info(f"Opened document: {file_path}")
            return provider

        except Exception as e:
            logger.error(f"Failed to open document {file_path}: {e}")
            raise RevitAPIError(f"Failed to open document: {file_path}", e)

    def create_document(
        self, template_path: str | None = None
    ) -> RevitDocumentProvider:
        """Create a new document."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Revit")

        try:
            revit_doc = self._revit_app.CreateDocument(template_path)
            if revit_doc is None:
                raise ModelError("Failed to create document")

            provider = RevitDocumentProvider(revit_doc)

            # Set as active document
            self._active_document = provider

            logger.info(
                f"Created new document with template: {template_path or 'Default'}"
            )
            return provider

        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise RevitAPIError("Failed to create document", e)

    def get_document_info(
        self, provider: RevitDocumentProvider | None = None
    ) -> DocumentInfo:
        """Get document information."""
        doc_provider = provider or self.active_document
        if not doc_provider:
            raise ConnectionError("No document available")

        doc = doc_provider.document

        return DocumentInfo(
            title=doc.Title,
            path=doc.PathName,
            # These would be populated from actual Revit document properties
            is_modified=False,
            is_read_only=False,
        )

    def save_document(self, provider: RevitDocumentProvider | None = None) -> bool:
        """Save document."""
        doc_provider = provider or self.active_document
        if not doc_provider:
            raise ConnectionError("No document to save")

        try:
            success = doc_provider.document.Save()
            if success:
                logger.info("Document saved successfully")
            else:
                logger.warning("Document save returned false")

            return success

        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            raise RevitAPIError("Failed to save document", e)

    def close_document(
        self, provider: RevitDocumentProvider | None = None, save_changes: bool = True
    ) -> bool:
        """Close document."""
        doc_provider = provider or self.active_document
        if not doc_provider:
            logger.warning("No document to close")
            return True

        try:
            success = doc_provider.document.Close(save_changes)

            if doc_provider == self._active_document:
                self._active_document = None

            # Remove from cache
            for path, weak_ref in list(self._document_cache.items()):
                if weak_ref() == doc_provider:
                    del self._document_cache[path]
                    break

            logger.info(f"Document closed (save_changes: {save_changes})")
            return success

        except Exception as e:
            logger.error(f"Failed to close document: {e}")
            raise RevitAPIError("Failed to close document", e)

    def query(self, element_type: type[T] | None = None) -> QueryBuilder[T]:
        """Create a typed query."""
        if not self.active_document:
            raise ConnectionError("No active document")

        if element_type:
            return Query.of_type(self.active_document, element_type)
        else:
            return Query.from_provider(self.active_document)

    def transaction(self, name: str | None = None, **kwargs) -> Transaction:
        """Create a transaction."""
        if not self.active_document:
            raise ConnectionError("No active document")

        options = TransactionOptions(name=name, **kwargs)
        return Transaction(self.active_document, options)

    def transaction_group(self, name: str | None = None) -> TransactionGroup:
        """Create a transaction group."""
        if not self.active_document:
            raise ConnectionError("No active document")

        return TransactionGroup(self.active_document, name)

    def get_element_by_id(self, element_id: Any) -> Element | None:
        """Get element by ID."""
        if not self.active_document:
            raise ConnectionError("No active document")

        return self.active_document.get_element_by_id(element_id)

    def delete_elements(self, elements: Element | list[Element] | ElementSet) -> None:
        """Delete elements."""
        if not self.active_document:
            raise ConnectionError("No active document")

        # Convert to list of IDs
        if isinstance(elements, Element):
            element_ids = [elements.id.value]
        elif isinstance(elements, ElementSet):
            element_ids = [elem.id.value for elem in elements]
        elif isinstance(elements, list):
            element_ids = [elem.id.value for elem in elements]
        else:
            raise ValueError("Invalid elements parameter")

        self.active_document.delete_elements(element_ids)

    def refresh_cache(self) -> None:
        """Refresh all caches."""
        if self.active_document:
            self.active_document.refresh_element_cache()

        # Clean up weak references
        dead_refs = []
        for path, weak_ref in self._document_cache.items():
            if weak_ref() is None:
                dead_refs.append(path)

        for path in dead_refs:
            del self._document_cache[path]

        logger.info("Refreshed all caches")

    def __enter__(self) -> RevitAPI:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()
