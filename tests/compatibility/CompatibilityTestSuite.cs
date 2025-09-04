using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using RevitPy.Compatibility;
using RevitPy.Compatibility.Features;

namespace RevitPy.Tests.Compatibility
{
    /// <summary>
    /// Comprehensive compatibility test suite for RevitPy across different Revit versions
    /// </summary>
    [TestClass]
    public class CompatibilityTestSuite
    {
        private IRevitVersionManager _versionManager;
        private IFeatureFlagManager _featureFlagManager;
        private ILogger<CompatibilityTestSuite> _logger;
        private CompatibilityTestContext _testContext;
        
        [TestInitialize]
        public async Task Initialize()
        {
            _testContext = new CompatibilityTestContext();
            _logger = _testContext.GetLogger<CompatibilityTestSuite>();
            _versionManager = _testContext.GetService<IRevitVersionManager>();
            _featureFlagManager = _testContext.GetService<IFeatureFlagManager>();
            
            await _testContext.InitializeAsync();
        }
        
        [TestCleanup]
        public async Task Cleanup()
        {
            await _testContext.CleanupAsync();
        }
        
        #region Version Detection Tests
        
        [TestMethod]
        [TestCategory("VersionDetection")]
        public async Task DetectRevitVersion_ShouldReturnValidVersion()
        {
            // Act
            var versionInfo = await _versionManager.DetectRevitVersionAsync();
            
            // Assert
            Assert.IsNotNull(versionInfo);
            Assert.AreNotEqual(RevitVersion.Unknown, versionInfo.Version);
            Assert.IsFalse(string.IsNullOrEmpty(versionInfo.VersionString));
            Assert.IsTrue(versionInfo.IsValidInstallation);
            
            _logger.LogInformation("Detected Revit version: {Version}", versionInfo.Version);
        }
        
        [TestMethod]
        [TestCategory("VersionDetection")]
        [DataRow(RevitVersion.Revit2022)]
        [DataRow(RevitVersion.Revit2023)]
        [DataRow(RevitVersion.Revit2024)]
        [DataRow(RevitVersion.Revit2025)]
        public async Task ValidateCompatibility_ForSupportedVersions_ShouldSucceed(RevitVersion version)
        {
            // Arrange
            var mockVersionInfo = CreateMockVersionInfo(version);
            _testContext.SetMockVersion(mockVersionInfo);
            
            // Act
            var result = await _versionManager.ValidateCompatibilityAsync();
            
            // Assert
            Assert.IsNotNull(result);
            Assert.IsTrue(result.IsCompatible, $"Version {version} should be compatible");
            Assert.AreEqual(version, result.DetectedVersion.Version);
            
            _logger.LogInformation("Compatibility validation passed for {Version}", version);
        }
        
        [TestMethod]
        [TestCategory("VersionDetection")]
        [DataRow(RevitVersion.Unknown)]
        public async Task ValidateCompatibility_ForUnsupportedVersions_ShouldFail(RevitVersion version)
        {
            // Arrange
            var mockVersionInfo = CreateMockVersionInfo(version);
            _testContext.SetMockVersion(mockVersionInfo);
            
            // Act
            var result = await _versionManager.ValidateCompatibilityAsync();
            
            // Assert
            Assert.IsNotNull(result);
            Assert.IsFalse(result.IsCompatible, $"Version {version} should not be compatible");
            Assert.IsTrue(result.Issues.Any(i => i.Severity >= CompatibilityIssueSeverity.Critical));
        }
        
        #endregion
        
        #region Feature Flag Tests
        
        [TestMethod]
        [TestCategory("FeatureFlags")]
        [DataRow(FeatureFlags.BASIC_API, RevitVersion.Revit2022, true)]
        [DataRow(FeatureFlags.MODERN_TRANSACTIONS, RevitVersion.Revit2022, false)]
        [DataRow(FeatureFlags.MODERN_TRANSACTIONS, RevitVersion.Revit2023, true)]
        [DataRow(FeatureFlags.CLOUD_MODEL_SUPPORT, RevitVersion.Revit2023, false)]
        [DataRow(FeatureFlags.CLOUD_MODEL_SUPPORT, RevitVersion.Revit2024, true)]
        [DataRow(FeatureFlags.AI_INTEGRATION, RevitVersion.Revit2024, false)]
        [DataRow(FeatureFlags.AI_INTEGRATION, RevitVersion.Revit2025, true)]
        public void IsFeatureEnabled_ShouldReturnCorrectAvailability(string featureName, RevitVersion version, bool expectedEnabled)
        {
            // Act
            var isEnabled = _featureFlagManager.IsFeatureEnabled(featureName, version);
            
            // Assert
            Assert.AreEqual(expectedEnabled, isEnabled, 
                $"Feature {featureName} should be {(expectedEnabled ? "enabled" : "disabled")} in version {version}");
        }
        
        [TestMethod]
        [TestCategory("FeatureFlags")]
        public void GetCompatibilityMatrix_ShouldGenerateCompleteMatrix()
        {
            // Act
            var matrix = _featureFlagManager.GetCompatibilityMatrix();
            
            // Assert
            Assert.IsNotNull(matrix);
            Assert.IsTrue(matrix.Features.Count > 0);
            
            // Verify core features are present for all supported versions
            var coreFeatures = new[] { FeatureFlags.BASIC_API, FeatureFlags.GEOMETRY_API, FeatureFlags.PARAMETER_ACCESS };
            var supportedVersions = new[] { RevitVersion.Revit2022, RevitVersion.Revit2023, RevitVersion.Revit2024, RevitVersion.Revit2025 };
            
            foreach (var feature in coreFeatures)
            {
                Assert.IsTrue(matrix.Features.ContainsKey(feature), $"Core feature {feature} should be in matrix");
                
                foreach (var version in supportedVersions)
                {
                    var availability = matrix.GetFeatureAvailability(feature, version);
                    Assert.AreEqual(FeatureAvailability.Available, availability, 
                        $"Core feature {feature} should be available in {version}");
                }
            }
            
            _logger.LogInformation("Generated compatibility matrix with {FeatureCount} features", matrix.Features.Count);
        }
        
        [TestMethod]
        [TestCategory("FeatureFlags")]
        public async Task ValidateFeatureDependencies_ShouldDetectMissingDependencies()
        {
            // Arrange
            const string featureWithDependencies = FeatureFlags.ORM_SUPPORT;
            const RevitVersion testVersion = RevitVersion.Revit2023;
            
            // Act
            var result = await _featureFlagManager.ValidateFeatureDependenciesAsync(featureWithDependencies, testVersion);
            
            // Assert
            Assert.IsNotNull(result);
            Assert.AreEqual(featureWithDependencies, result.FeatureName);
            Assert.AreEqual(testVersion, result.Version);
            
            // ORM support depends on BasicAPI and ParameterAccess
            var config = _featureFlagManager.GetFeatureConfiguration(featureWithDependencies, testVersion);
            foreach (var dependency in config.Dependencies)
            {
                var dependencyEnabled = _featureFlagManager.IsFeatureEnabled(dependency, testVersion);
                if (!dependencyEnabled)
                {
                    Assert.IsTrue(result.MissingDependencies.Contains(dependency), 
                        $"Missing dependency {dependency} should be detected");
                }
            }
        }
        
        #endregion
        
        #region API Compatibility Tests
        
        [TestMethod]
        [TestCategory("APICompatibility")]
        [DataRow(RevitVersion.Revit2022)]
        [DataRow(RevitVersion.Revit2023)]
        [DataRow(RevitVersion.Revit2024)]
        [DataRow(RevitVersion.Revit2025)]
        public async Task ElementCreation_ShouldWorkAcrossVersions(RevitVersion version)
        {
            // Arrange
            var testAdapter = _testContext.GetAPIAdapter(version);
            var creationParams = new ElementCreationParameters
            {
                ElementType = typeof(MockWall),
                Parameters = new Dictionary<string, object>
                {
                    ["Height"] = 3000.0,
                    ["Width"] = 200.0
                }
            };
            
            // Act & Assert
            await testAdapter.TransactionManager.ExecuteInTransactionAsync("CreateElement", async () =>
            {
                var element = await testAdapter.ElementManager.CreateElementAsync<MockWall>(creationParams);
                Assert.IsNotNull(element);
            });
        }
        
        [TestMethod]
        [TestCategory("APICompatibility")]
        [DataRow(RevitVersion.Revit2022)]
        [DataRow(RevitVersion.Revit2023)]
        [DataRow(RevitVersion.Revit2024)]
        [DataRow(RevitVersion.Revit2025)]
        public async Task ParameterAccess_ShouldWorkAcrossVersions(RevitVersion version)
        {
            // Arrange
            var testAdapter = _testContext.GetAPIAdapter(version);
            var mockElement = _testContext.CreateMockElement();
            
            // Act
            var parameterValue = await testAdapter.ParameterManager.GetParameterValueAsync<double>(mockElement, "Height");
            
            // Assert
            Assert.IsTrue(parameterValue > 0);
            
            // Test parameter setting
            await testAdapter.TransactionManager.ExecuteInTransactionAsync("SetParameter", async () =>
            {
                var success = await testAdapter.ParameterManager.SetParameterValueAsync(mockElement, "Height", 4000.0);
                Assert.IsTrue(success);
            });
        }
        
        [TestMethod]
        [TestCategory("APICompatibility")]
        [DataRow(RevitVersion.Revit2023)] // Modern transactions available from 2023
        [DataRow(RevitVersion.Revit2024)]
        [DataRow(RevitVersion.Revit2025)]
        public async Task ModernTransactions_ShouldWorkInSupportedVersions(RevitVersion version)
        {
            // Arrange
            var testAdapter = _testContext.GetAPIAdapter(version);
            
            // Skip if modern transactions not supported
            if (!testAdapter.SupportsFeature(FeatureFlags.MODERN_TRANSACTIONS))
            {
                Assert.Inconclusive($"Modern transactions not supported in {version}");
                return;
            }
            
            // Act & Assert
            var result = await testAdapter.TransactionManager.ExecuteInTransactionAsync("ModernTransaction", async () =>
            {
                // Simulate some work
                await Task.Delay(10);
                return "Success";
            });
            
            Assert.IsTrue(result.Success);
            Assert.AreEqual("Success", result.Result);
        }
        
        #endregion
        
        #region Performance Tests
        
        [TestMethod]
        [TestCategory("Performance")]
        [DataRow(RevitVersion.Revit2022)]
        [DataRow(RevitVersion.Revit2023)]
        [DataRow(RevitVersion.Revit2024)]
        [DataRow(RevitVersion.Revit2025)]
        public async Task ElementQuery_PerformanceConsistencyAcrossVersions(RevitVersion version)
        {
            // Arrange
            var testAdapter = _testContext.GetAPIAdapter(version);
            var filter = new ElementFilter { ElementType = typeof(MockWall) };
            var iterations = 100;
            var times = new List<TimeSpan>();
            
            // Act
            for (int i = 0; i < iterations; i++)
            {
                var startTime = DateTime.UtcNow;
                var elements = await testAdapter.ElementManager.GetElementsAsync<MockWall>(filter);
                var endTime = DateTime.UtcNow;
                
                times.Add(endTime - startTime);
            }
            
            // Assert
            var averageTime = TimeSpan.FromTicks((long)times.Average(t => t.Ticks));
            var maxTime = times.Max();
            
            Assert.IsTrue(averageTime.TotalMilliseconds < 100, 
                $"Average query time ({averageTime.TotalMilliseconds:F2}ms) should be under 100ms for {version}");
            Assert.IsTrue(maxTime.TotalMilliseconds < 500, 
                $"Maximum query time ({maxTime.TotalMilliseconds:F2}ms) should be under 500ms for {version}");
            
            _logger.LogInformation("Version {Version}: Avg={AvgMs:F2}ms, Max={MaxMs:F2}ms", 
                version, averageTime.TotalMilliseconds, maxTime.TotalMilliseconds);
        }
        
        [TestMethod]
        [TestCategory("Performance")]
        public async Task ComparePerformanceAcrossVersions()
        {
            // Arrange
            var versions = new[] { RevitVersion.Revit2022, RevitVersion.Revit2023, RevitVersion.Revit2024, RevitVersion.Revit2025 };
            var performanceResults = new Dictionary<RevitVersion, PerformanceMetrics>();
            
            // Act
            foreach (var version in versions)
            {
                var metrics = await MeasureVersionPerformance(version);
                performanceResults[version] = metrics;
            }
            
            // Assert
            var baselineVersion = RevitVersion.Revit2022;
            var baseline = performanceResults[baselineVersion];
            
            foreach (var version in versions.Skip(1))
            {
                var current = performanceResults[version];
                
                // Performance should not degrade more than 20% compared to baseline
                var degradationRatio = current.AverageExecutionTime.TotalMilliseconds / baseline.AverageExecutionTime.TotalMilliseconds;
                Assert.IsTrue(degradationRatio < 1.2, 
                    $"Performance degradation in {version} ({degradationRatio:P}) should be less than 20%");
                
                _logger.LogInformation("Version {Version}: {Ratio:P} of baseline performance", version, degradationRatio);
            }
        }
        
        #endregion
        
        #region Error Handling Tests
        
        [TestMethod]
        [TestCategory("ErrorHandling")]
        [DataRow(RevitVersion.Revit2022)]
        [DataRow(RevitVersion.Revit2023)]
        [DataRow(RevitVersion.Revit2024)]
        [DataRow(RevitVersion.Revit2025)]
        public async Task GracefulDegradation_UnsupportedFeatures(RevitVersion version)
        {
            // Arrange
            var testAdapter = _testContext.GetAPIAdapter(version);
            
            // Act & Assert
            if (!testAdapter.SupportsFeature(FeatureFlags.CLOUD_MODEL_SUPPORT))
            {
                // Should gracefully handle unsupported feature
                var featureAdapter = testAdapter.GetFeatureAdapter(FeatureFlags.CLOUD_MODEL_SUPPORT);
                
                if (featureAdapter != null)
                {
                    await Assert.ThrowsExceptionAsync<NotSupportedException>(async () =>
                    {
                        await featureAdapter.ExecuteAsync(async () => "This should fail");
                    });
                }
            }
        }
        
        [TestMethod]
        [TestCategory("ErrorHandling")]
        public async Task FallbackMechanisms_ShouldWorkCorrectly()
        {
            // Arrange
            var testAdapter = _testContext.GetAPIAdapter(RevitVersion.Revit2022);
            var primaryActionCalled = false;
            var fallbackActionCalled = false;
            
            // Act
            var result = await testAdapter.ExecuteWithFallbackAsync(
                primaryAction: async () =>
                {
                    primaryActionCalled = true;
                    throw new NotSupportedException("Primary action failed");
                },
                fallbackAction: async () =>
                {
                    fallbackActionCalled = true;
                    return "Fallback successful";
                }
            );
            
            // Assert
            Assert.IsTrue(primaryActionCalled);
            Assert.IsTrue(fallbackActionCalled);
            Assert.AreEqual("Fallback successful", result);
        }
        
        #endregion
        
        #region Integration Tests
        
        [TestMethod]
        [TestCategory("Integration")]
        public async Task EndToEndWorkflow_ShouldWorkAcrossVersions()
        {
            // Test a complete workflow across all supported versions
            var versions = new[] { RevitVersion.Revit2022, RevitVersion.Revit2023, RevitVersion.Revit2024, RevitVersion.Revit2025 };
            
            foreach (var version in versions)
            {
                await TestCompleteWorkflow(version);
            }
        }
        
        private async Task TestCompleteWorkflow(RevitVersion version)
        {
            var testAdapter = _testContext.GetAPIAdapter(version);
            
            await testAdapter.TransactionManager.ExecuteInTransactionAsync($"CompleteWorkflow_{version}", async () =>
            {
                // 1. Create element
                var element = await testAdapter.ElementManager.CreateElementAsync<MockWall>(new ElementCreationParameters
                {
                    ElementType = typeof(MockWall)
                });
                
                // 2. Set parameters
                await testAdapter.ParameterManager.SetParameterValueAsync(element, "Height", 3000.0);
                
                // 3. Query elements
                var elements = await testAdapter.ElementManager.GetElementsAsync<MockWall>(new ElementFilter());
                
                // 4. Verify results
                Assert.IsNotNull(element);
                Assert.IsTrue(elements.Any());
                
                var height = await testAdapter.ParameterManager.GetParameterValueAsync<double>(element, "Height");
                Assert.AreEqual(3000.0, height, 0.1);
            });
            
            _logger.LogInformation("Complete workflow test passed for {Version}", version);
        }
        
        #endregion
        
        #region Helper Methods
        
        private RevitVersionInfo CreateMockVersionInfo(RevitVersion version)
        {
            return new RevitVersionInfo
            {
                Version = version,
                VersionString = version.ToString(),
                ProductName = $"Autodesk Revit {version}",
                InstallationPath = @"C:\Program Files\Autodesk\Revit " + ((int)version).ToString(),
                IsValidInstallation = version != RevitVersion.Unknown,
                BuildNumber = "20.0.0.0",
                ReleaseDate = DateTime.Now.AddYears(-1)
            };
        }
        
        private async Task<PerformanceMetrics> MeasureVersionPerformance(RevitVersion version)
        {
            var testAdapter = _testContext.GetAPIAdapter(version);
            var iterations = 50;
            var times = new List<TimeSpan>();
            
            for (int i = 0; i < iterations; i++)
            {
                var startTime = DateTime.UtcNow;
                
                // Simulate typical operations
                await testAdapter.TransactionManager.ExecuteInTransactionAsync("PerfTest", async () =>
                {
                    var element = await testAdapter.ElementManager.CreateElementAsync<MockWall>(
                        new ElementCreationParameters { ElementType = typeof(MockWall) });
                    
                    await testAdapter.ParameterManager.SetParameterValueAsync(element, "Height", 3000.0);
                    
                    var elements = await testAdapter.ElementManager.GetElementsAsync<MockWall>(
                        new ElementFilter { ElementType = typeof(MockWall) });
                });
                
                var endTime = DateTime.UtcNow;
                times.Add(endTime - startTime);
            }
            
            return new PerformanceMetrics
            {
                Version = version,
                AverageExecutionTime = TimeSpan.FromTicks((long)times.Average(t => t.Ticks)),
                MinExecutionTime = times.Min(),
                MaxExecutionTime = times.Max(),
                IterationCount = iterations
            };
        }
        
        #endregion
    }
    
    /// <summary>
    /// Performance metrics for version comparison
    /// </summary>
    public class PerformanceMetrics
    {
        public RevitVersion Version { get; set; }
        public TimeSpan AverageExecutionTime { get; set; }
        public TimeSpan MinExecutionTime { get; set; }
        public TimeSpan MaxExecutionTime { get; set; }
        public int IterationCount { get; set; }
    }
    
    /// <summary>
    /// Mock wall element for testing
    /// </summary>
    public class MockWall
    {
        public ElementId Id { get; set; } = new ElementId(12345);
        public Dictionary<string, object> Parameters { get; set; } = new Dictionary<string, object>
        {
            ["Height"] = 3000.0,
            ["Width"] = 200.0,
            ["Length"] = 5000.0
        };
    }
}