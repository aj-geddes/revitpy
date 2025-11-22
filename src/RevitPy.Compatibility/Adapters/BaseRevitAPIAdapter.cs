using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using RevitPy.Compatibility.Abstractions;

namespace RevitPy.Compatibility.Adapters
{
    /// <summary>
    /// Base implementation for Revit API adapters providing common functionality
    /// </summary>
    public abstract class BaseRevitAPIAdapter : IRevitAPIAbstraction
    {
        protected readonly ILogger Logger;
        protected readonly Dictionary<string, IFeatureAdapter> FeatureAdapters;
        protected APIInitializationContext InitializationContext;

        public abstract RevitVersion SupportedVersion { get; }

        public abstract IElementManager ElementManager { get; protected set; }
        public abstract ITransactionManager TransactionManager { get; protected set; }
        public abstract IParameterManager ParameterManager { get; protected set; }
        public abstract IGeometryManager GeometryManager { get; protected set; }
        public abstract ISelectionManager SelectionManager { get; protected set; }
        public abstract IViewManager ViewManager { get; protected set; }
        public abstract IFamilyManager FamilyManager { get; protected set; }

        protected BaseRevitAPIAdapter(ILogger logger)
        {
            Logger = logger;
            FeatureAdapters = new Dictionary<string, IFeatureAdapter>();
        }

        public virtual async Task InitializeAsync(APIInitializationContext context)
        {
            Logger.LogInformation("Initializing Revit API adapter for version {Version}", SupportedVersion);

            InitializationContext = context;

            try
            {
                await InitializeManagersAsync(context);
                await InitializeFeatureAdaptersAsync(context);
                await ValidateInitializationAsync(context);

                Logger.LogInformation("Successfully initialized Revit API adapter for version {Version}", SupportedVersion);
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Failed to initialize Revit API adapter for version {Version}", SupportedVersion);
                throw;
            }
        }

        public virtual bool SupportsFeature(string featureName)
        {
            if (FeatureAdapters.TryGetValue(featureName, out var adapter))
            {
                return adapter.IsAvailable;
            }

            // Check version-specific feature support
            return IsFeatureSupportedInVersion(featureName, SupportedVersion);
        }

        public virtual IFeatureAdapter GetFeatureAdapter(string featureName)
        {
            if (FeatureAdapters.TryGetValue(featureName, out var adapter))
            {
                return adapter;
            }

            Logger.LogWarning("Feature adapter not found for feature: {FeatureName}", featureName);
            return null;
        }

        public virtual async Task<T> ExecuteWithFallbackAsync<T>(Func<Task<T>> primaryAction, Func<Task<T>> fallbackAction)
        {
            try
            {
                Logger.LogDebug("Executing primary action");
                return await primaryAction();
            }
            catch (Exception ex)
            {
                Logger.LogWarning(ex, "Primary action failed, trying fallback");

                try
                {
                    return await fallbackAction();
                }
                catch (Exception fallbackEx)
                {
                    Logger.LogError(fallbackEx, "Fallback action also failed");
                    throw new AggregateException("Both primary and fallback actions failed", ex, fallbackEx);
                }
            }
        }

        public virtual void HandleVersionSpecificException(Exception exception)
        {
            Logger.LogError(exception, "Version-specific exception occurred in {Version}", SupportedVersion);

            // Handle common version-specific exceptions
            switch (exception)
            {
                case NotSupportedException notSupported:
                    Logger.LogWarning("Feature not supported in {Version}: {Message}", SupportedVersion, notSupported.Message);
                    break;

                case System.IO.FileNotFoundException fileNotFound:
                    Logger.LogError("Required assembly not found for {Version}: {FileName}", SupportedVersion, fileNotFound.FileName);
                    break;

                case MissingMethodException missingMethod:
                    Logger.LogWarning("Method not available in {Version}: {Message}", SupportedVersion, missingMethod.Message);
                    break;

                default:
                    Logger.LogError("Unhandled version-specific exception in {Version}: {Exception}", SupportedVersion, exception);
                    break;
            }
        }

        protected abstract Task InitializeManagersAsync(APIInitializationContext context);
        protected abstract Task InitializeFeatureAdaptersAsync(APIInitializationContext context);
        protected abstract Task ValidateInitializationAsync(APIInitializationContext context);
        protected abstract bool IsFeatureSupportedInVersion(string featureName, RevitVersion version);

        protected virtual void RegisterFeatureAdapter(string featureName, IFeatureAdapter adapter)
        {
            FeatureAdapters[featureName] = adapter;
            Logger.LogDebug("Registered feature adapter for {FeatureName} in version {Version}", featureName, SupportedVersion);
        }

        protected virtual async Task<T> ExecuteWithVersionHandlingAsync<T>(Func<Task<T>> action, string operationName)
        {
            try
            {
                Logger.LogDebug("Executing {OperationName} for version {Version}", operationName, SupportedVersion);
                return await action();
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Failed to execute {OperationName} for version {Version}", operationName, SupportedVersion);
                HandleVersionSpecificException(ex);
                throw;
            }
        }

        protected virtual async Task ExecuteWithVersionHandlingAsync(Func<Task> action, string operationName)
        {
            try
            {
                Logger.LogDebug("Executing {OperationName} for version {Version}", operationName, SupportedVersion);
                await action();
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Failed to execute {OperationName} for version {Version}", operationName, SupportedVersion);
                HandleVersionSpecificException(ex);
                throw;
            }
        }

        protected virtual T ConvertFromNativeType<T>(object nativeObject)
        {
            if (nativeObject == null)
                return default(T);

            if (nativeObject is T directCast)
                return directCast;

            // Attempt version-specific conversion
            return ConvertFromNativeTypeInternal<T>(nativeObject);
        }

        protected virtual object ConvertToNativeType(object managedObject, Type nativeType)
        {
            if (managedObject == null)
                return null;

            if (nativeType.IsAssignableFrom(managedObject.GetType()))
                return managedObject;

            // Attempt version-specific conversion
            return ConvertToNativeTypeInternal(managedObject, nativeType);
        }

        protected abstract T ConvertFromNativeTypeInternal<T>(object nativeObject);
        protected abstract object ConvertToNativeTypeInternal(object managedObject, Type nativeType);

        protected virtual void ValidateVersionCompatibility(string operationName)
        {
            if (InitializationContext?.VersionInfo == null)
            {
                throw new InvalidOperationException($"API adapter not properly initialized for operation: {operationName}");
            }

            if (InitializationContext.VersionInfo.Version != SupportedVersion)
            {
                throw new InvalidOperationException($"Version mismatch for operation {operationName}: Expected {SupportedVersion}, got {InitializationContext.VersionInfo.Version}");
            }
        }
    }

    /// <summary>
    /// Base feature adapter implementation
    /// </summary>
    public abstract class BaseFeatureAdapter : IFeatureAdapter
    {
        protected readonly ILogger Logger;

        public abstract string FeatureName { get; }
        public abstract RevitVersion MinimumVersion { get; }
        public abstract bool IsAvailable { get; }

        protected BaseFeatureAdapter(ILogger logger)
        {
            Logger = logger;
        }

        public virtual async Task<T> ExecuteAsync<T>(Func<Task<T>> action)
        {
            if (!IsAvailable)
            {
                throw new NotSupportedException($"Feature {FeatureName} is not available");
            }

            try
            {
                Logger.LogDebug("Executing feature action for {FeatureName}", FeatureName);
                return await action();
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Failed to execute feature action for {FeatureName}", FeatureName);
                throw;
            }
        }

        public virtual async Task ExecuteAsync(Func<Task> action)
        {
            if (!IsAvailable)
            {
                throw new NotSupportedException($"Feature {FeatureName} is not available");
            }

            try
            {
                Logger.LogDebug("Executing feature action for {FeatureName}", FeatureName);
                await action();
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Failed to execute feature action for {FeatureName}", FeatureName);
                throw;
            }
        }

        public abstract object GetImplementation(Type interfaceType);
        public abstract bool SupportsInterface(Type interfaceType);
    }
}
