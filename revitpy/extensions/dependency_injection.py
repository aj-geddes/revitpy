"""
Dependency injection container for RevitPy extensions.
"""

import asyncio
import inspect
import threading
from typing import (
    Any, Dict, List, Optional, Type, TypeVar, Generic, Union, Callable,
    Protocol, runtime_checkable, get_type_hints, get_origin, get_args
)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from loguru import logger


T = TypeVar('T')


class ServiceLifetime(Enum):
    """Service lifetime enumeration."""
    
    SINGLETON = "singleton"    # One instance for entire application
    SCOPED = "scoped"         # One instance per scope
    TRANSIENT = "transient"   # New instance every time


@dataclass
class ServiceDescriptor:
    """Describes how to create and manage a service."""
    
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable[..., Any]] = None
    instance: Optional[Any] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    dependencies: List[Type] = field(default_factory=list)
    
    @property
    def is_singleton(self) -> bool:
        return self.lifetime == ServiceLifetime.SINGLETON
    
    @property
    def is_scoped(self) -> bool:
        return self.lifetime == ServiceLifetime.SCOPED
    
    @property
    def is_transient(self) -> bool:
        return self.lifetime == ServiceLifetime.TRANSIENT


@runtime_checkable
class Injectable(Protocol):
    """Protocol for injectable services."""
    
    def __init__(self, *args, **kwargs) -> None: ...


class DIContainer:
    """
    Dependency injection container with support for different service lifetimes.
    """
    
    def __init__(self, parent: Optional['DIContainer'] = None) -> None:
        self.parent = parent
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_services: Dict[Type, Any] = {}
        self._creation_stack: List[Type] = []
        self._lock = threading.RLock()
        self._scope_active = False
    
    def register_singleton(
        self, 
        service_type: Type[T], 
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        instance: Optional[T] = None
    ) -> 'DIContainer':
        """
        Register a singleton service.
        
        Args:
            service_type: The service interface type
            implementation_type: The implementation type
            factory: Factory function to create the service
            instance: Pre-created instance
            
        Returns:
            Self for chaining
        """
        return self._register_service(
            service_type, 
            implementation_type, 
            factory, 
            instance, 
            ServiceLifetime.SINGLETON
        )
    
    def register_scoped(
        self, 
        service_type: Type[T], 
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'DIContainer':
        """
        Register a scoped service.
        
        Args:
            service_type: The service interface type
            implementation_type: The implementation type
            factory: Factory function to create the service
            
        Returns:
            Self for chaining
        """
        return self._register_service(
            service_type, 
            implementation_type, 
            factory, 
            None, 
            ServiceLifetime.SCOPED
        )
    
    def register_transient(
        self, 
        service_type: Type[T], 
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'DIContainer':
        """
        Register a transient service.
        
        Args:
            service_type: The service interface type
            implementation_type: The implementation type
            factory: Factory function to create the service
            
        Returns:
            Self for chaining
        """
        return self._register_service(
            service_type, 
            implementation_type, 
            factory, 
            None, 
            ServiceLifetime.TRANSIENT
        )
    
    def _register_service(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]],
        factory: Optional[Callable[..., T]],
        instance: Optional[T],
        lifetime: ServiceLifetime
    ) -> 'DIContainer':
        """Internal method to register a service."""
        with self._lock:
            # Determine implementation type
            impl_type = implementation_type or service_type
            
            # Analyze dependencies
            dependencies = self._analyze_dependencies(impl_type) if not factory else []
            
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=impl_type,
                factory=factory,
                instance=instance,
                lifetime=lifetime,
                dependencies=dependencies
            )
            
            self._services[service_type] = descriptor
            
            # If singleton with instance, store it
            if lifetime == ServiceLifetime.SINGLETON and instance is not None:
                self._singletons[service_type] = instance
            
            logger.debug(f"Registered {lifetime.value} service: {service_type.__name__}")
            
        return self
    
    def _analyze_dependencies(self, service_type: Type) -> List[Type]:
        """Analyze constructor dependencies for a service type."""
        try:
            # Get constructor signature
            constructor = service_type.__init__
            signature = inspect.signature(constructor)
            
            # Get type hints
            type_hints = get_type_hints(constructor)
            
            dependencies = []
            
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                # Get type annotation
                param_type = type_hints.get(param_name, param.annotation)
                
                if param_type != inspect.Parameter.empty:
                    dependencies.append(param_type)
            
            return dependencies
        
        except Exception as e:
            logger.warning(f"Failed to analyze dependencies for {service_type.__name__}: {e}")
            return []
    
    def get_service(self, service_type: Type[T]) -> T:
        """
        Get a service instance.
        
        Args:
            service_type: The service type to resolve
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered
            RuntimeError: If circular dependency is detected
        """
        with self._lock:
            # Check for circular dependencies
            if service_type in self._creation_stack:
                cycle = " -> ".join([t.__name__ for t in self._creation_stack])
                cycle += f" -> {service_type.__name__}"
                raise RuntimeError(f"Circular dependency detected: {cycle}")
            
            # Try to get from current container
            if service_type in self._services:
                return self._create_service(service_type)
            
            # Try parent container
            if self.parent:
                return self.parent.get_service(service_type)
            
            raise ValueError(f"Service {service_type.__name__} is not registered")
    
    def _create_service(self, service_type: Type[T]) -> T:
        """Create a service instance."""
        descriptor = self._services[service_type]
        
        # Singleton: return existing instance or create once
        if descriptor.is_singleton:
            if service_type in self._singletons:
                return self._singletons[service_type]
            
            instance = self._instantiate_service(descriptor)
            self._singletons[service_type] = instance
            return instance
        
        # Scoped: return existing instance in current scope or create
        elif descriptor.is_scoped:
            if self._scope_active and service_type in self._scoped_services:
                return self._scoped_services[service_type]
            
            instance = self._instantiate_service(descriptor)
            if self._scope_active:
                self._scoped_services[service_type] = instance
            return instance
        
        # Transient: always create new instance
        else:
            return self._instantiate_service(descriptor)
    
    def _instantiate_service(self, descriptor: ServiceDescriptor) -> Any:
        """Instantiate a service using its descriptor."""
        service_type = descriptor.service_type
        
        try:
            self._creation_stack.append(service_type)
            
            # Use provided instance
            if descriptor.instance is not None:
                return descriptor.instance
            
            # Use factory function
            if descriptor.factory is not None:
                # Resolve factory dependencies
                factory_args = self._resolve_function_args(descriptor.factory)
                return descriptor.factory(**factory_args)
            
            # Use implementation type constructor
            if descriptor.implementation_type:
                constructor_args = self._resolve_constructor_args(descriptor.implementation_type)
                return descriptor.implementation_type(**constructor_args)
            
            raise ValueError(f"No way to instantiate service {service_type.__name__}")
        
        finally:
            self._creation_stack.remove(service_type)
    
    def _resolve_constructor_args(self, service_type: Type) -> Dict[str, Any]:
        """Resolve constructor arguments for a service type."""
        try:
            constructor = service_type.__init__
            signature = inspect.signature(constructor)
            type_hints = get_type_hints(constructor)
            
            args = {}
            
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                # Get parameter type
                param_type = type_hints.get(param_name, param.annotation)
                
                if param_type == inspect.Parameter.empty:
                    if param.default == inspect.Parameter.empty:
                        raise ValueError(f"Cannot resolve parameter {param_name} for {service_type.__name__}")
                    continue  # Use default value
                
                # Resolve dependency
                try:
                    args[param_name] = self.get_service(param_type)
                except ValueError:
                    if param.default == inspect.Parameter.empty:
                        raise ValueError(f"Cannot resolve dependency {param_type.__name__} for {service_type.__name__}")
                    # Use default value if available
            
            return args
        
        except Exception as e:
            logger.error(f"Failed to resolve constructor args for {service_type.__name__}: {e}")
            raise
    
    def _resolve_function_args(self, func: Callable) -> Dict[str, Any]:
        """Resolve arguments for a function."""
        try:
            signature = inspect.signature(func)
            type_hints = get_type_hints(func)
            
            args = {}
            
            for param_name, param in signature.parameters.items():
                # Get parameter type
                param_type = type_hints.get(param_name, param.annotation)
                
                if param_type == inspect.Parameter.empty:
                    if param.default == inspect.Parameter.empty:
                        raise ValueError(f"Cannot resolve parameter {param_name} for {func.__name__}")
                    continue  # Use default value
                
                # Resolve dependency
                try:
                    args[param_name] = self.get_service(param_type)
                except ValueError:
                    if param.default == inspect.Parameter.empty:
                        raise ValueError(f"Cannot resolve dependency {param_type.__name__} for {func.__name__}")
            
            return args
        
        except Exception as e:
            logger.error(f"Failed to resolve function args for {func.__name__}: {e}")
            raise
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered."""
        return service_type in self._services or (self.parent and self.parent.is_registered(service_type))
    
    def create_scope(self) -> 'ServiceScope':
        """Create a new service scope."""
        return ServiceScope(self)
    
    @contextmanager
    def scope(self):
        """Context manager for creating a service scope."""
        with self.create_scope():
            yield self
    
    def _enter_scope(self) -> None:
        """Enter a service scope."""
        self._scope_active = True
        self._scoped_services.clear()
    
    def _exit_scope(self) -> None:
        """Exit a service scope."""
        # Dispose scoped services
        for service in self._scoped_services.values():
            if hasattr(service, 'dispose'):
                try:
                    service.dispose()
                except Exception as e:
                    logger.error(f"Error disposing scoped service: {e}")
        
        self._scoped_services.clear()
        self._scope_active = False
    
    def dispose(self) -> None:
        """Dispose the container and all singleton services."""
        with self._lock:
            # Dispose singletons
            for service in self._singletons.values():
                if hasattr(service, 'dispose'):
                    try:
                        service.dispose()
                    except Exception as e:
                        logger.error(f"Error disposing singleton service: {e}")
            
            # Dispose scoped services
            for service in self._scoped_services.values():
                if hasattr(service, 'dispose'):
                    try:
                        service.dispose()
                    except Exception as e:
                        logger.error(f"Error disposing scoped service: {e}")
            
            self._singletons.clear()
            self._scoped_services.clear()
            self._services.clear()
    
    def get_registered_services(self) -> List[Type]:
        """Get list of registered service types."""
        services = list(self._services.keys())
        if self.parent:
            services.extend(self.parent.get_registered_services())
        return services
    
    def create_child_container(self) -> 'DIContainer':
        """Create a child container."""
        return DIContainer(parent=self)


class ServiceScope:
    """Context manager for service scopes."""
    
    def __init__(self, container: DIContainer) -> None:
        self.container = container
    
    def __enter__(self) -> DIContainer:
        self.container._enter_scope()
        return self.container
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.container._exit_scope()


# Decorators for dependency injection

def singleton(service_type: Optional[Type] = None):
    """Decorator to mark a class as a singleton service."""
    def decorator(cls: Type[T]) -> Type[T]:
        cls._di_lifetime = ServiceLifetime.SINGLETON
        cls._di_service_type = service_type or cls
        return cls
    
    if service_type is None:
        # Used as @singleton
        return decorator
    else:
        # Used as @singleton(SomeInterface)
        return decorator


def transient(service_type: Optional[Type] = None):
    """Decorator to mark a class as a transient service."""
    def decorator(cls: Type[T]) -> Type[T]:
        cls._di_lifetime = ServiceLifetime.TRANSIENT
        cls._di_service_type = service_type or cls
        return cls
    
    if service_type is None:
        return decorator
    else:
        return decorator


def scoped(service_type: Optional[Type] = None):
    """Decorator to mark a class as a scoped service."""
    def decorator(cls: Type[T]) -> Type[T]:
        cls._di_lifetime = ServiceLifetime.SCOPED
        cls._di_service_type = service_type or cls
        return cls
    
    if service_type is None:
        return decorator
    else:
        return decorator


def inject(func: Callable) -> Callable:
    """
    Decorator to inject dependencies into a function.
    
    Args:
        func: Function to inject dependencies into
        
    Returns:
        Wrapped function that gets dependencies injected
    """
    def wrapper(*args, **kwargs):
        # Get container from global context or create one
        container = get_current_container()
        if not container:
            raise RuntimeError("No DI container available")
        
        # Resolve function arguments
        injected_kwargs = container._resolve_function_args(func)
        injected_kwargs.update(kwargs)  # Allow override
        
        return func(*args, **injected_kwargs)
    
    return wrapper


# Global container management

_current_container: Optional[DIContainer] = None
_container_lock = threading.Lock()


def set_current_container(container: DIContainer) -> None:
    """Set the current global container."""
    global _current_container
    with _container_lock:
        _current_container = container


def get_current_container() -> Optional[DIContainer]:
    """Get the current global container."""
    global _current_container
    with _container_lock:
        return _current_container


def get_service(service_type: Type[T]) -> T:
    """Get a service from the current container."""
    container = get_current_container()
    if not container:
        raise RuntimeError("No DI container available")
    
    return container.get_service(service_type)


# Extension registration helpers

def register_services_from_module(container: DIContainer, module: Any) -> int:
    """
    Register all decorated services from a module.
    
    Args:
        container: DI container
        module: Module to scan
        
    Returns:
        Number of services registered
    """
    registered_count = 0
    
    for name in dir(module):
        obj = getattr(module, name)
        
        if inspect.isclass(obj) and hasattr(obj, '_di_lifetime'):
            lifetime = obj._di_lifetime
            service_type = obj._di_service_type
            
            if lifetime == ServiceLifetime.SINGLETON:
                container.register_singleton(service_type, obj)
            elif lifetime == ServiceLifetime.SCOPED:
                container.register_scoped(service_type, obj)
            elif lifetime == ServiceLifetime.TRANSIENT:
                container.register_transient(service_type, obj)
            
            registered_count += 1
            logger.debug(f"Auto-registered service: {obj.__name__} as {lifetime.value}")
    
    return registered_count