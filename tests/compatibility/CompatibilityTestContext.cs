using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Compatibility;
using RevitPy.Compatibility.Abstractions;
using RevitPy.Compatibility.Adapters;
using RevitPy.Compatibility.Features;

namespace RevitPy.Tests.Compatibility
{
    /// <summary>
    /// Test context for compatibility testing providing mocked services and test utilities
    /// </summary>
    public class CompatibilityTestContext
    {
        private readonly ServiceProvider _serviceProvider;
        private readonly Dictionary<RevitVersion, IRevitAPIAbstraction> _apiAdapters;
        private RevitVersionInfo _mockVersionInfo;

        public CompatibilityTestContext()
        {
            _apiAdapters = new Dictionary<RevitVersion, IRevitAPIAbstraction>();
            _serviceProvider = BuildServiceProvider();
        }

        public async Task InitializeAsync()
        {
            await InitializeAPIAdapters();
        }

        public async Task CleanupAsync()
        {
            foreach (var adapter in _apiAdapters.Values)
            {
                if (adapter is IDisposable disposable)
                {
                    disposable.Dispose();
                }
            }

            _serviceProvider?.Dispose();
        }

        public T GetService<T>() => _serviceProvider.GetRequiredService<T>();

        public ILogger<T> GetLogger<T>() => _serviceProvider.GetRequiredService<ILogger<T>>();

        public IRevitAPIAbstraction GetAPIAdapter(RevitVersion version)
        {
            if (_apiAdapters.TryGetValue(version, out var adapter))
            {
                return adapter;
            }

            throw new ArgumentException($"API adapter not available for version {version}");
        }

        public void SetMockVersion(RevitVersionInfo versionInfo)
        {
            _mockVersionInfo = versionInfo;

            // Update the mock version manager
            var versionManager = GetService<IRevitVersionManager>() as MockRevitVersionManager;
            versionManager?.SetMockVersion(versionInfo);
        }

        public object CreateMockElement()
        {
            return new MockElement
            {
                Id = new ElementId(DateTime.UtcNow.Ticks),
                Parameters = new Dictionary<string, object>
                {
                    ["Height"] = 3000.0,
                    ["Width"] = 200.0,
                    ["Area"] = 600000.0,
                    ["Material"] = "Concrete",
                    ["Level"] = "Level 1"
                }
            };
        }

        private ServiceProvider BuildServiceProvider()
        {
            var services = new ServiceCollection();

            // Logging
            services.AddLogging(builder =>
            {
                builder.AddConsole();
                builder.SetMinimumLevel(LogLevel.Debug);
            });

            // Options
            services.Configure<FeatureFlagOptions>(options =>
            {
                options.EnableExperimentalFeatures = true;
                options.DisableDeprecatedFeatures = false;
                options.LogFeatureUsage = true;
            });

            // Core services
            services.AddSingleton<IRevitVersionManager, MockRevitVersionManager>();
            services.AddSingleton<IFeatureFlagManager, FeatureFlagManager>();

            // API adapters
            services.AddTransient<MockRevitAPIAdapter2022>();
            services.AddTransient<MockRevitAPIAdapter2023>();
            services.AddTransient<MockRevitAPIAdapter2024>();
            services.AddTransient<MockRevitAPIAdapter2025>();

            return services.BuildServiceProvider();
        }

        private async Task InitializeAPIAdapters()
        {
            var versions = new[]
            {
                RevitVersion.Revit2022,
                RevitVersion.Revit2023,
                RevitVersion.Revit2024,
                RevitVersion.Revit2025
            };

            foreach (var version in versions)
            {
                var adapter = CreateAPIAdapter(version);
                var context = new APIInitializationContext
                {
                    VersionInfo = new RevitVersionInfo
                    {
                        Version = version,
                        VersionString = version.ToString(),
                        IsValidInstallation = true
                    },
                    Application = new MockApplication(),
                    Document = new MockDocument()
                };

                await adapter.InitializeAsync(context);
                _apiAdapters[version] = adapter;
            }
        }

        private IRevitAPIAbstraction CreateAPIAdapter(RevitVersion version)
        {
            return version switch
            {
                RevitVersion.Revit2022 => _serviceProvider.GetRequiredService<MockRevitAPIAdapter2022>(),
                RevitVersion.Revit2023 => _serviceProvider.GetRequiredService<MockRevitAPIAdapter2023>(),
                RevitVersion.Revit2024 => _serviceProvider.GetRequiredService<MockRevitAPIAdapter2024>(),
                RevitVersion.Revit2025 => _serviceProvider.GetRequiredService<MockRevitAPIAdapter2025>(),
                _ => throw new ArgumentException($"Unsupported version: {version}")
            };
        }
    }

    /// <summary>
    /// Mock Revit version manager for testing
    /// </summary>
    public class MockRevitVersionManager : IRevitVersionManager
    {
        private readonly ILogger<MockRevitVersionManager> _logger;
        private RevitVersionInfo _mockVersion;

        public MockRevitVersionManager(ILogger<MockRevitVersionManager> logger)
        {
            _logger = logger;
            _mockVersion = new RevitVersionInfo
            {
                Version = RevitVersion.Revit2024,
                VersionString = "2024",
                IsValidInstallation = true,
                ProductName = "Autodesk Revit 2024",
                InstallationPath = @"C:\Program Files\Autodesk\Revit 2024"
            };
        }

        public void SetMockVersion(RevitVersionInfo versionInfo)
        {
            _mockVersion = versionInfo;
        }

        public Task<RevitVersionInfo> DetectRevitVersionAsync()
        {
            return Task.FromResult(_mockVersion);
        }

        public IEnumerable<string> GetSupportedFeatures(RevitVersion version)
        {
            return version switch
            {
                RevitVersion.Revit2022 => new[] { "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement" },
                RevitVersion.Revit2023 => new[] { "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement", "ModernTransactions" },
                RevitVersion.Revit2024 => new[] { "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement", "ModernTransactions", "CloudModelSupport" },
                RevitVersion.Revit2025 => new[] { "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement", "ModernTransactions", "CloudModelSupport", "AI_Integration" },
                _ => Array.Empty<string>()
            };
        }

        public bool IsFeatureAvailable(string feature, RevitVersion version)
        {
            var supportedFeatures = GetSupportedFeatures(version);
            return supportedFeatures.Contains(feature);
        }

        public RevitVersion GetMinimumVersionForFeature(string feature)
        {
            return feature switch
            {
                "BasicAPI" or "GeometryAPI" or "ParameterAccess" or "TransactionManagement" => RevitVersion.Revit2022,
                "ModernTransactions" => RevitVersion.Revit2023,
                "CloudModelSupport" => RevitVersion.Revit2024,
                "AI_Integration" => RevitVersion.Revit2025,
                _ => RevitVersion.Unknown
            };
        }

        public async Task<CompatibilityResult> ValidateCompatibilityAsync()
        {
            var result = new CompatibilityResult
            {
                DetectedVersion = _mockVersion,
                IsCompatible = _mockVersion.Version >= RevitVersion.Revit2022 && _mockVersion.Version != RevitVersion.Unknown
            };

            if (_mockVersion.Version == RevitVersion.Unknown)
            {
                result.Issues.Add(new CompatibilityIssue
                {
                    Severity = CompatibilityIssueSeverity.Critical,
                    Feature = "VersionDetection",
                    Message = "Unknown Revit version",
                    Recommendation = "Install a supported Revit version (2022 or later)"
                });
            }

            return result;
        }

        public VersionConfiguration GetVersionConfiguration(RevitVersion version)
        {
            return new VersionConfiguration
            {
                Version = version,
                DotNetVersion = "4.8",
                RequiredAssemblies = new[] { "RevitAPI.dll", "RevitAPIUI.dll" }
            };
        }
    }

    /// <summary>
    /// Base mock API adapter
    /// </summary>
    public abstract class MockRevitAPIAdapter : BaseRevitAPIAdapter
    {
        protected MockRevitAPIAdapter(ILogger logger) : base(logger) { }

        public override IElementManager ElementManager { get; protected set; }
        public override ITransactionManager TransactionManager { get; protected set; }
        public override IParameterManager ParameterManager { get; protected set; }
        public override IGeometryManager GeometryManager { get; protected set; }
        public override ISelectionManager SelectionManager { get; protected set; }
        public override IViewManager ViewManager { get; protected set; }
        public override IFamilyManager FamilyManager { get; protected set; }

        protected override async Task InitializeManagersAsync(APIInitializationContext context)
        {
            ElementManager = new MockElementManager(Logger);
            TransactionManager = new MockTransactionManager(Logger, SupportedVersion);
            ParameterManager = new MockParameterManager(Logger);
            GeometryManager = new MockGeometryManager(Logger);
            SelectionManager = new MockSelectionManager(Logger);
            ViewManager = new MockViewManager(Logger);
            FamilyManager = new MockFamilyManager(Logger);
        }

        protected override async Task InitializeFeatureAdaptersAsync(APIInitializationContext context)
        {
            // Register version-specific feature adapters
            var features = GetSupportedFeatures();
            foreach (var feature in features)
            {
                var adapter = CreateFeatureAdapter(feature);
                if (adapter != null)
                {
                    RegisterFeatureAdapter(feature, adapter);
                }
            }
        }

        protected override async Task ValidateInitializationAsync(APIInitializationContext context)
        {
            // Validation logic
        }

        protected override bool IsFeatureSupportedInVersion(string featureName, RevitVersion version)
        {
            var supportedFeatures = GetSupportedFeatures();
            return supportedFeatures.Contains(featureName);
        }

        protected override T ConvertFromNativeTypeInternal<T>(object nativeObject)
        {
            return (T)nativeObject;
        }

        protected override object ConvertToNativeTypeInternal(object managedObject, Type nativeType)
        {
            return managedObject;
        }

        protected abstract string[] GetSupportedFeatures();
        protected abstract IFeatureAdapter CreateFeatureAdapter(string featureName);
    }

    /// <summary>
    /// Mock API adapters for specific versions
    /// </summary>
    public class MockRevitAPIAdapter2022 : MockRevitAPIAdapter
    {
        public override RevitVersion SupportedVersion => RevitVersion.Revit2022;

        public MockRevitAPIAdapter2022(ILogger<MockRevitAPIAdapter2022> logger) : base(logger) { }

        protected override string[] GetSupportedFeatures()
        {
            return new[] { FeatureFlags.BASIC_API, FeatureFlags.GEOMETRY_API, FeatureFlags.PARAMETER_ACCESS, FeatureFlags.TRANSACTION_MANAGEMENT };
        }

        protected override IFeatureAdapter CreateFeatureAdapter(string featureName)
        {
            return new MockFeatureAdapter(featureName, SupportedVersion, Logger);
        }
    }

    public class MockRevitAPIAdapter2023 : MockRevitAPIAdapter
    {
        public override RevitVersion SupportedVersion => RevitVersion.Revit2023;

        public MockRevitAPIAdapter2023(ILogger<MockRevitAPIAdapter2023> logger) : base(logger) { }

        protected override string[] GetSupportedFeatures()
        {
            return new[] { FeatureFlags.BASIC_API, FeatureFlags.GEOMETRY_API, FeatureFlags.PARAMETER_ACCESS, FeatureFlags.TRANSACTION_MANAGEMENT, FeatureFlags.MODERN_TRANSACTIONS };
        }

        protected override IFeatureAdapter CreateFeatureAdapter(string featureName)
        {
            return new MockFeatureAdapter(featureName, SupportedVersion, Logger);
        }
    }

    public class MockRevitAPIAdapter2024 : MockRevitAPIAdapter
    {
        public override RevitVersion SupportedVersion => RevitVersion.Revit2024;

        public MockRevitAPIAdapter2024(ILogger<MockRevitAPIAdapter2024> logger) : base(logger) { }

        protected override string[] GetSupportedFeatures()
        {
            return new[] { FeatureFlags.BASIC_API, FeatureFlags.GEOMETRY_API, FeatureFlags.PARAMETER_ACCESS, FeatureFlags.TRANSACTION_MANAGEMENT, FeatureFlags.MODERN_TRANSACTIONS, FeatureFlags.CLOUD_MODEL_SUPPORT };
        }

        protected override IFeatureAdapter CreateFeatureAdapter(string featureName)
        {
            return new MockFeatureAdapter(featureName, SupportedVersion, Logger);
        }
    }

    public class MockRevitAPIAdapter2025 : MockRevitAPIAdapter
    {
        public override RevitVersion SupportedVersion => RevitVersion.Revit2025;

        public MockRevitAPIAdapter2025(ILogger<MockRevitAPIAdapter2025> logger) : base(logger) { }

        protected override string[] GetSupportedFeatures()
        {
            return new[] { FeatureFlags.BASIC_API, FeatureFlags.GEOMETRY_API, FeatureFlags.PARAMETER_ACCESS, FeatureFlags.TRANSACTION_MANAGEMENT, FeatureFlags.MODERN_TRANSACTIONS, FeatureFlags.CLOUD_MODEL_SUPPORT, FeatureFlags.AI_INTEGRATION };
        }

        protected override IFeatureAdapter CreateFeatureAdapter(string featureName)
        {
            return new MockFeatureAdapter(featureName, SupportedVersion, Logger);
        }
    }

    /// <summary>
    /// Mock feature adapter
    /// </summary>
    public class MockFeatureAdapter : BaseFeatureAdapter
    {
        private readonly RevitVersion _version;

        public override string FeatureName { get; }
        public override RevitVersion MinimumVersion { get; }
        public override bool IsAvailable => _version >= MinimumVersion;

        public MockFeatureAdapter(string featureName, RevitVersion version, ILogger logger) : base(logger)
        {
            FeatureName = featureName;
            _version = version;
            MinimumVersion = GetMinimumVersionForFeature(featureName);
        }

        public override object GetImplementation(Type interfaceType)
        {
            // Return mock implementation
            return Activator.CreateInstance(interfaceType);
        }

        public override bool SupportsInterface(Type interfaceType)
        {
            return true;
        }

        private RevitVersion GetMinimumVersionForFeature(string featureName)
        {
            return featureName switch
            {
                FeatureFlags.BASIC_API or FeatureFlags.GEOMETRY_API or FeatureFlags.PARAMETER_ACCESS or FeatureFlags.TRANSACTION_MANAGEMENT => RevitVersion.Revit2022,
                FeatureFlags.MODERN_TRANSACTIONS => RevitVersion.Revit2023,
                FeatureFlags.CLOUD_MODEL_SUPPORT => RevitVersion.Revit2024,
                FeatureFlags.AI_INTEGRATION => RevitVersion.Revit2025,
                _ => RevitVersion.Unknown
            };
        }
    }

    // Mock supporting classes
    public class MockElement
    {
        public ElementId Id { get; set; }
        public Dictionary<string, object> Parameters { get; set; } = new();
    }

    public class MockApplication { }
    public class MockDocument { }
}
