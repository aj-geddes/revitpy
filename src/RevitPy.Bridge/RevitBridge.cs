using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using RevitPy.Core.Exceptions;

namespace RevitPy.Bridge;

/// <summary>
/// High-performance Revit API bridge with comprehensive Python integration
/// </summary>
public class RevitBridge : IRevitBridge
{
    private readonly ILogger<RevitBridge> _logger;
    private readonly IServiceProvider _serviceProvider;
    private readonly ConcurrentDictionary<string, IEventSubscription> _eventSubscriptions;
    private readonly ConcurrentDictionary<Type, object> _typeCache;
    private readonly ConcurrentDictionary<string, MethodInfo> _methodCache;
    private readonly ConcurrentDictionary<string, PropertyInfo> _propertyCache;
    private readonly SemaphoreSlim _initializationSemaphore;
    private bool _initialized;
    private object? _revitApplication;
    private volatile bool _disposed;

    public RevitBridge(
        ILogger<RevitBridge> logger,
        IServiceProvider serviceProvider,
        ITransactionManager transactionManager,
        IRevitTypeConverter typeConverter)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        TransactionManager = transactionManager ?? throw new ArgumentNullException(nameof(transactionManager));
        TypeConverter = typeConverter ?? throw new ArgumentNullException(nameof(typeConverter));

        _eventSubscriptions = new ConcurrentDictionary<string, IEventSubscription>();
        _typeCache = new ConcurrentDictionary<Type, object>();
        _methodCache = new ConcurrentDictionary<string, MethodInfo>();
        _propertyCache = new ConcurrentDictionary<string, PropertyInfo>();
        _initializationSemaphore = new SemaphoreSlim(1, 1);
    }

    /// <inheritdoc/>
    public object? Application => _revitApplication;

    /// <inheritdoc/>
    public object? ActiveDocument
    {
        get
        {
            if (!IsRevitAvailable)
                return null;

            try
            {
                // Get active document from Revit application
                // This would be implemented with actual Revit API calls
                return GetPropertyAsync<object>(_revitApplication!, "ActiveUIDocument.Document").Result;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to get active document");
                return null;
            }
        }
    }

    /// <inheritdoc/>
    public ITransactionManager TransactionManager { get; }

    /// <inheritdoc/>
    public IRevitTypeConverter TypeConverter { get; }

    /// <inheritdoc/>
    public bool IsRevitAvailable => _initialized && _revitApplication != null;

    /// <inheritdoc/>
    public async Task InitializeAsync(object application, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(application);

        await _initializationSemaphore.WaitAsync(cancellationToken);
        try
        {
            if (_initialized)
                return;

            var stopwatch = Stopwatch.StartNew();
            
            _revitApplication = application;
            
            // Initialize type converter with Revit-specific mappings
            await InitializeTypeConverter(cancellationToken);
            
            // Cache frequently used types and methods
            await PreloadTypeCache(cancellationToken);
            
            _initialized = true;
            
            _logger.LogInformation("RevitBridge initialized successfully in {ElapsedMs}ms", 
                stopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to initialize RevitBridge");
            throw new RevitApiException("Failed to initialize RevitBridge", ex);
        }
        finally
        {
            _initializationSemaphore.Release();
        }
    }

    /// <inheritdoc/>
    public async Task<T?> InvokeMethodAsync<T>(
        object target, 
        string methodName, 
        object[]? parameters = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(target);
        ArgumentException.ThrowIfNullOrEmpty(methodName);

        if (!IsRevitAvailable)
            throw new InvalidOperationException("RevitBridge is not initialized");

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var method = GetCachedMethod(target.GetType(), methodName, parameters);
            if (method == null)
            {
                throw new MethodAccessException($"Method '{methodName}' not found on type '{target.GetType().Name}'");
            }

            // Convert parameters from Python to Revit types
            var convertedParameters = ConvertParameters(parameters, method.GetParameters());

            // Invoke method
            var result = method.Invoke(target, convertedParameters);

            // Handle async methods
            if (result is Task task)
            {
                await task;
                
                if (task.GetType().IsGenericType)
                {
                    var resultProperty = task.GetType().GetProperty("Result");
                    result = resultProperty?.GetValue(task);
                }
                else
                {
                    result = null;
                }
            }

            // Convert result to Python-compatible type
            var convertedResult = TypeConverter.ConvertToPython(result);

            _logger.LogDebug("Method '{MethodName}' invoked in {ElapsedMs}ms", 
                methodName, stopwatch.ElapsedMilliseconds);

            return (T?)convertedResult;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to invoke method '{MethodName}' on type '{TypeName}'", 
                methodName, target.GetType().Name);
            throw new RevitApiException($"Method invocation failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<T?> GetPropertyAsync<T>(
        object target, 
        string propertyName,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(target);
        ArgumentException.ThrowIfNullOrEmpty(propertyName);

        if (!IsRevitAvailable)
            throw new InvalidOperationException("RevitBridge is not initialized");

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var property = GetCachedProperty(target.GetType(), propertyName);
            if (property == null)
            {
                throw new PropertyAccessException($"Property '{propertyName}' not found on type '{target.GetType().Name}'");
            }

            if (!property.CanRead)
            {
                throw new PropertyAccessException($"Property '{propertyName}' is not readable");
            }

            var value = property.GetValue(target);
            var convertedValue = TypeConverter.ConvertToPython(value);

            // Log performance for properties that take too long
            if (stopwatch.ElapsedMilliseconds > 1)
            {
                _logger.LogWarning("Property '{PropertyName}' access took {ElapsedMs}ms", 
                    propertyName, stopwatch.ElapsedMilliseconds);
            }

            return (T?)convertedValue;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get property '{PropertyName}' on type '{TypeName}'", 
                propertyName, target.GetType().Name);
            throw new RevitApiException($"Property access failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task SetPropertyAsync(
        object target, 
        string propertyName, 
        object? value,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(target);
        ArgumentException.ThrowIfNullOrEmpty(propertyName);

        if (!IsRevitAvailable)
            throw new InvalidOperationException("RevitBridge is not initialized");

        try
        {
            var property = GetCachedProperty(target.GetType(), propertyName);
            if (property == null)
            {
                throw new PropertyAccessException($"Property '{propertyName}' not found on type '{target.GetType().Name}'");
            }

            if (!property.CanWrite)
            {
                throw new PropertyAccessException($"Property '{propertyName}' is not writable");
            }

            // Convert value from Python to Revit type
            var convertedValue = TypeConverter.ConvertFromPython<object>(value, property.PropertyType);
            
            // Use transaction for property modifications that might affect the model
            if (RequiresTransaction(property))
            {
                await TransactionManager.ExecuteInTransactionAsync(
                    $"Set {target.GetType().Name}.{propertyName}",
                    async () =>
                    {
                        property.SetValue(target, convertedValue);
                        await Task.CompletedTask;
                    },
                    ActiveDocument,
                    cancellationToken);
            }
            else
            {
                property.SetValue(target, convertedValue);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set property '{PropertyName}' on type '{TypeName}'", 
                propertyName, target.GetType().Name);
            throw new RevitApiException($"Property set failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<T?> CreateInstanceAsync<T>(
        string typeName, 
        object[]? parameters = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(typeName);

        if (!IsRevitAvailable)
            throw new InvalidOperationException("RevitBridge is not initialized");

        try
        {
            var type = GetCachedType(typeName);
            if (type == null)
            {
                throw new TypeLoadException($"Type '{typeName}' not found");
            }

            // Convert parameters from Python to appropriate types
            object[] convertedParameters = Array.Empty<object>();
            if (parameters != null && parameters.Length > 0)
            {
                var constructors = type.GetConstructors();
                var matchingConstructor = FindMatchingConstructor(constructors, parameters);
                if (matchingConstructor == null)
                {
                    throw new MethodAccessException($"No matching constructor found for type '{typeName}'");
                }

                convertedParameters = ConvertParameters(parameters, matchingConstructor.GetParameters());
            }

            var instance = Activator.CreateInstance(type, convertedParameters);
            var convertedInstance = TypeConverter.ConvertToPython(instance);

            _logger.LogDebug("Created instance of type '{TypeName}'", typeName);

            return (T?)convertedInstance;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create instance of type '{TypeName}'", typeName);
            throw new RevitApiException($"Instance creation failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<IEventSubscription> RegisterEventHandlerAsync(
        string eventName, 
        Func<object, object[], Task> handler,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(eventName);
        ArgumentNullException.ThrowIfNull(handler);

        if (!IsRevitAvailable)
            throw new InvalidOperationException("RevitBridge is not initialized");

        try
        {
            var subscriptionId = Guid.NewGuid().ToString();
            var subscription = new EventSubscription(subscriptionId, eventName, handler);

            // Register with actual Revit event system
            await RegisterRevitEventHandler(eventName, handler, cancellationToken);

            _eventSubscriptions[subscriptionId] = subscription;

            _logger.LogInformation("Registered event handler for '{EventName}' with subscription {SubscriptionId}", 
                eventName, subscriptionId);

            return subscription;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to register event handler for '{EventName}'", eventName);
            throw new RevitApiException($"Event registration failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public RevitVersionInfo GetVersionInfo()
    {
        if (!IsRevitAvailable)
            throw new InvalidOperationException("RevitBridge is not initialized");

        try
        {
            // Get version information from Revit application
            // This would be implemented with actual Revit API calls
            return new RevitVersionInfo
            {
                Version = GetPropertyAsync<string>(_revitApplication!, "VersionNumber").Result ?? "Unknown",
                BuildNumber = GetPropertyAsync<string>(_revitApplication!, "VersionBuild").Result ?? "Unknown",
                ProductName = GetPropertyAsync<string>(_revitApplication!, "VersionName").Result ?? "Autodesk Revit",
                Language = "English", // Default, could be retrieved from Revit
                AdditionalInfo = new Dictionary<string, string>
                {
                    ["BridgeVersion"] = Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "1.0.0",
                    ["InitializedAt"] = DateTime.UtcNow.ToString("O")
                }
            };
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to get complete version information");
            return new RevitVersionInfo
            {
                Version = "Unknown",
                BuildNumber = "Unknown",
                ProductName = "Autodesk Revit",
                Language = "English",
                AdditionalInfo = new Dictionary<string, string>
                {
                    ["BridgeVersion"] = Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "1.0.0",
                    ["Error"] = ex.Message
                }
            };
        }
    }

    /// <inheritdoc/>
    public bool IsValidRevitObject(object? obj)
    {
        if (obj == null)
            return false;

        try
        {
            var type = obj.GetType();
            
            // Check if it's from a Revit assembly
            var assemblyName = type.Assembly.GetName().Name;
            if (assemblyName?.StartsWith("Revit", StringComparison.OrdinalIgnoreCase) == true)
                return true;

            // Check if it has Revit-specific attributes or interfaces
            // This would be expanded with actual Revit API knowledge
            return type.Namespace?.StartsWith("Autodesk.Revit", StringComparison.OrdinalIgnoreCase) == true;
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Error checking if object is valid Revit object");
            return false;
        }
    }

    /// <inheritdoc/>
    public async Task DisposeAsync(CancellationToken cancellationToken = default)
    {
        if (_disposed)
            return;

        try
        {
            // Unsubscribe from all events
            var unsubscribeTasks = _eventSubscriptions.Values.Select(s => s.UnsubscribeAsync(cancellationToken));
            await Task.WhenAll(unsubscribeTasks);

            _eventSubscriptions.Clear();
            _typeCache.Clear();
            _methodCache.Clear();
            _propertyCache.Clear();

            _initializationSemaphore?.Dispose();

            _disposed = true;

            _logger.LogInformation("RevitBridge disposed successfully");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during RevitBridge disposal");
        }
    }

    private async Task InitializeTypeConverter(CancellationToken cancellationToken)
    {
        // Register common Revit type conversions
        // This would be expanded with actual Revit API type mappings
        
        // Example registrations (would be replaced with actual Revit types):
        // TypeConverter.RegisterBidirectionalConverter<PythonXYZ, Autodesk.Revit.DB.XYZ>(
        //     revitXyz => new PythonXYZ { X = revitXyz.X, Y = revitXyz.Y, Z = revitXyz.Z },
        //     pythonXyz => new Autodesk.Revit.DB.XYZ(pythonXyz.X, pythonXyz.Y, pythonXyz.Z)
        // );

        await Task.CompletedTask;
    }

    private async Task PreloadTypeCache(CancellationToken cancellationToken)
    {
        try
        {
            // Preload commonly used Revit types
            var commonTypes = new[]
            {
                "Autodesk.Revit.ApplicationServices.Application",
                "Autodesk.Revit.DB.Document",
                "Autodesk.Revit.DB.Element",
                "Autodesk.Revit.DB.Transaction",
                "Autodesk.Revit.DB.XYZ",
                "Autodesk.Revit.DB.ElementId"
            };

            foreach (var typeName in commonTypes)
            {
                try
                {
                    var type = Type.GetType(typeName) ?? 
                              AppDomain.CurrentDomain.GetAssemblies()
                                  .SelectMany(a => a.GetTypes())
                                  .FirstOrDefault(t => t.FullName == typeName);

                    if (type != null)
                    {
                        _typeCache[type] = type;
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogDebug(ex, "Could not preload type {TypeName}", typeName);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error preloading type cache");
        }

        await Task.CompletedTask;
    }

    private MethodInfo? GetCachedMethod(Type type, string methodName, object[]? parameters)
    {
        var cacheKey = $"{type.FullName}.{methodName}({string.Join(",", parameters?.Select(p => p?.GetType().Name) ?? Array.Empty<string>())})";
        
        return _methodCache.GetOrAdd(cacheKey, _ =>
        {
            var methods = type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static)
                .Where(m => m.Name == methodName);

            if (parameters == null || parameters.Length == 0)
            {
                return methods.FirstOrDefault(m => m.GetParameters().Length == 0);
            }

            return methods.FirstOrDefault(m => IsMethodMatch(m, parameters));
        });
    }

    private PropertyInfo? GetCachedProperty(Type type, string propertyName)
    {
        var cacheKey = $"{type.FullName}.{propertyName}";
        
        return _propertyCache.GetOrAdd(cacheKey, _ =>
            type.GetProperty(propertyName, BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static));
    }

    private Type? GetCachedType(string typeName)
    {
        return _typeCache.Values.OfType<Type>().FirstOrDefault(t => t.Name == typeName || t.FullName == typeName);
    }

    private object[] ConvertParameters(object[]? parameters, ParameterInfo[] parameterInfos)
    {
        if (parameters == null || parameters.Length == 0)
            return Array.Empty<object>();

        var converted = new object[parameters.Length];
        for (int i = 0; i < parameters.Length && i < parameterInfos.Length; i++)
        {
            converted[i] = TypeConverter.ConvertFromPython<object>(parameters[i], parameterInfos[i].ParameterType);
        }

        return converted;
    }

    private ConstructorInfo? FindMatchingConstructor(ConstructorInfo[] constructors, object[] parameters)
    {
        return constructors.FirstOrDefault(c => IsConstructorMatch(c, parameters));
    }

    private bool IsMethodMatch(MethodInfo method, object[] parameters)
    {
        var paramTypes = method.GetParameters();
        if (paramTypes.Length != parameters.Length)
            return false;

        for (int i = 0; i < parameters.Length; i++)
        {
            if (parameters[i] != null && !TypeConverter.CanConvertFromPython(parameters[i].GetType(), paramTypes[i].ParameterType))
                return false;
        }

        return true;
    }

    private bool IsConstructorMatch(ConstructorInfo constructor, object[] parameters)
    {
        var paramTypes = constructor.GetParameters();
        if (paramTypes.Length != parameters.Length)
            return false;

        for (int i = 0; i < parameters.Length; i++)
        {
            if (parameters[i] != null && !TypeConverter.CanConvertFromPython(parameters[i].GetType(), paramTypes[i].ParameterType))
                return false;
        }

        return true;
    }

    private bool RequiresTransaction(PropertyInfo property)
    {
        // Determine if setting this property requires a transaction
        // This would be based on actual Revit API knowledge
        return property.DeclaringType?.Namespace?.StartsWith("Autodesk.Revit.DB", StringComparison.OrdinalIgnoreCase) == true;
    }

    private async Task RegisterRevitEventHandler(string eventName, Func<object, object[], Task> handler, CancellationToken cancellationToken)
    {
        // This would integrate with the actual Revit event system
        // For now, we just simulate successful registration
        await Task.CompletedTask;
    }
}

/// <summary>
/// Implementation of event subscription
/// </summary>
public class EventSubscription : IEventSubscription
{
    private readonly Func<object, object[], Task> _handler;
    private bool _disposed;

    public EventSubscription(string subscriptionId, string eventName, Func<object, object[], Task> handler)
    {
        SubscriptionId = subscriptionId ?? throw new ArgumentNullException(nameof(subscriptionId));
        EventName = eventName ?? throw new ArgumentNullException(nameof(eventName));
        _handler = handler ?? throw new ArgumentNullException(nameof(handler));
        IsActive = true;
    }

    /// <inheritdoc/>
    public string EventName { get; }

    /// <inheritdoc/>
    public string SubscriptionId { get; }

    /// <inheritdoc/>
    public bool IsActive { get; private set; }

    /// <inheritdoc/>
    public async Task UnsubscribeAsync(CancellationToken cancellationToken = default)
    {
        if (!_disposed && IsActive)
        {
            IsActive = false;
            // Unregister from actual Revit event system
            await Task.CompletedTask;
        }
    }

    /// <inheritdoc/>
    public void Dispose()
    {
        if (!_disposed)
        {
            UnsubscribeAsync().Wait();
            _disposed = true;
        }
    }
}

/// <summary>
/// Exception thrown when property access fails
/// </summary>
public class PropertyAccessException : RevitApiException
{
    public PropertyAccessException(string message) : base(message, "PROPERTY_ACCESS_FAILED") { }
    
    public PropertyAccessException(string message, Exception innerException) : base(message, innerException)
    {
        ErrorCode = "PROPERTY_ACCESS_FAILED";
    }
}

/// <summary>
/// Exception thrown when method access fails
/// </summary>
public class MethodAccessException : RevitApiException
{
    public MethodAccessException(string message) : base(message, "METHOD_ACCESS_FAILED") { }
    
    public MethodAccessException(string message, Exception innerException) : base(message, innerException)
    {
        ErrorCode = "METHOD_ACCESS_FAILED";
    }
}