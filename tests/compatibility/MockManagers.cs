using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using RevitPy.Compatibility.Abstractions;

namespace RevitPy.Tests.Compatibility
{
    /// <summary>
    /// Mock element manager for testing
    /// </summary>
    public class MockElementManager : IElementManager
    {
        private readonly ILogger _logger;
        private readonly Dictionary<ElementId, object> _elements;
        private long _nextElementId = 1000;

        public MockElementManager(ILogger logger)
        {
            _logger = logger;
            _elements = new Dictionary<ElementId, object>();

            // Pre-populate with some test elements
            PopulateTestElements();
        }

        public async Task<TElement> CreateElementAsync<TElement>(ElementCreationParameters parameters) where TElement : class
        {
            await Task.Delay(1); // Simulate async operation

            var elementId = new ElementId(_nextElementId++);
            var element = CreateMockElement<TElement>(elementId, parameters);

            _elements[elementId] = element;

            _logger.LogDebug("Created element {ElementId} of type {ElementType}", elementId.Id, typeof(TElement).Name);
            return element;
        }

        public async Task<TElement> GetElementAsync<TElement>(ElementId elementId) where TElement : class
        {
            await Task.Delay(1); // Simulate async operation

            if (_elements.TryGetValue(elementId, out var element) && element is TElement typedElement)
            {
                return typedElement;
            }

            return null;
        }

        public async Task<IEnumerable<TElement>> GetElementsAsync<TElement>(ElementFilter filter) where TElement : class
        {
            await Task.Delay(10); // Simulate query time

            var results = _elements.Values
                .OfType<TElement>()
                .Where(e => MatchesFilter(e, filter))
                .ToList();

            _logger.LogDebug("Found {Count} elements of type {ElementType}", results.Count, typeof(TElement).Name);
            return results;
        }

        public async Task<bool> DeleteElementAsync(ElementId elementId)
        {
            await Task.Delay(1); // Simulate async operation

            var removed = _elements.Remove(elementId);
            _logger.LogDebug("Deleted element {ElementId}: {Success}", elementId.Id, removed);
            return removed;
        }

        public async Task<TElement> ModifyElementAsync<TElement>(TElement element, Action<TElement> modification) where TElement : class
        {
            await Task.Delay(1); // Simulate async operation

            modification(element);
            _logger.LogDebug("Modified element of type {ElementType}", typeof(TElement).Name);
            return element;
        }

        public async Task<IEnumerable<TElement>> GetElementsByTypeAsync<TElement>(Type elementType) where TElement : class
        {
            await Task.Delay(5); // Simulate query time

            var results = _elements.Values
                .Where(e => elementType.IsAssignableFrom(e.GetType()))
                .OfType<TElement>()
                .ToList();

            return results;
        }

        private TElement CreateMockElement<TElement>(ElementId elementId, ElementCreationParameters parameters) where TElement : class
        {
            var element = Activator.CreateInstance<TElement>();

            // Set common properties if available
            if (element is MockWall wall)
            {
                wall.Id = elementId;
                if (parameters.Parameters.TryGetValue("Height", out var height))
                    wall.Parameters["Height"] = height;
                if (parameters.Parameters.TryGetValue("Width", out var width))
                    wall.Parameters["Width"] = width;
            }
            else if (element is MockElement mockElement)
            {
                mockElement.Id = elementId;
                foreach (var param in parameters.Parameters)
                {
                    mockElement.Parameters[param.Key] = param.Value;
                }
            }

            return element;
        }

        private bool MatchesFilter<TElement>(TElement element, ElementFilter filter) where TElement : class
        {
            if (filter == null)
                return true;

            if (filter.ElementType != null && !filter.ElementType.IsAssignableFrom(element.GetType()))
                return false;

            if (filter.CustomFilter != null && !filter.CustomFilter(element))
                return false;

            return true;
        }

        private void PopulateTestElements()
        {
            // Create some test walls
            for (int i = 0; i < 10; i++)
            {
                var wall = new MockWall
                {
                    Id = new ElementId(_nextElementId++),
                    Parameters = new Dictionary<string, object>
                    {
                        ["Height"] = 3000.0 + (i * 100),
                        ["Width"] = 200.0,
                        ["Length"] = 5000.0 + (i * 500),
                        ["Material"] = i % 2 == 0 ? "Concrete" : "Brick"
                    }
                };
                _elements[wall.Id] = wall;
            }
        }
    }

    /// <summary>
    /// Mock transaction manager for testing
    /// </summary>
    public class MockTransactionManager : ITransactionManager
    {
        private readonly ILogger _logger;
        private readonly RevitVersion _version;
        private readonly List<MockTransaction> _activeTransactions;

        public bool IsInTransaction => _activeTransactions.Any();
        public bool SupportsNestedTransactions => _version >= RevitVersion.Revit2023;

        public MockTransactionManager(ILogger logger, RevitVersion version)
        {
            _logger = logger;
            _version = version;
            _activeTransactions = new List<MockTransaction>();
        }

        public async Task<TransactionResult> ExecuteInTransactionAsync(string transactionName, Func<Task> action)
        {
            try
            {
                using var transaction = await BeginTransactionAsync(transactionName) as MockTransaction;

                await action();
                await CommitTransactionAsync(transaction);

                return new TransactionResult { Success = true };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Transaction {TransactionName} failed", transactionName);
                return new TransactionResult
                {
                    Success = false,
                    ErrorMessage = ex.Message,
                    Exception = ex
                };
            }
        }

        public async Task<TransactionResult<T>> ExecuteInTransactionAsync<T>(string transactionName, Func<Task<T>> action)
        {
            try
            {
                using var transaction = await BeginTransactionAsync(transactionName) as MockTransaction;

                var result = await action();
                await CommitTransactionAsync(transaction);

                return new TransactionResult<T>
                {
                    Success = true,
                    Result = result
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Transaction {TransactionName} failed", transactionName);
                return new TransactionResult<T>
                {
                    Success = false,
                    ErrorMessage = ex.Message,
                    Exception = ex
                };
            }
        }

        public async Task<ITransaction> BeginTransactionAsync(string transactionName)
        {
            await Task.Delay(1); // Simulate transaction start time

            if (!SupportsNestedTransactions && IsInTransaction)
            {
                throw new InvalidOperationException("Nested transactions not supported in this version");
            }

            var transaction = new MockTransaction(transactionName);
            _activeTransactions.Add(transaction);

            _logger.LogDebug("Started transaction: {TransactionName}", transactionName);
            return transaction;
        }

        public async Task CommitTransactionAsync(ITransaction transaction)
        {
            await Task.Delay(1); // Simulate commit time

            if (transaction is MockTransaction mockTransaction)
            {
                mockTransaction.Status = TransactionStatus.Committed;
                _activeTransactions.Remove(mockTransaction);
                _logger.LogDebug("Committed transaction: {TransactionName}", transaction.Name);
            }
        }

        public async Task RollbackTransactionAsync(ITransaction transaction)
        {
            await Task.Delay(1); // Simulate rollback time

            if (transaction is MockTransaction mockTransaction)
            {
                mockTransaction.Status = TransactionStatus.RolledBack;
                _activeTransactions.Remove(mockTransaction);
                _logger.LogDebug("Rolled back transaction: {TransactionName}", transaction.Name);
            }
        }
    }

    /// <summary>
    /// Mock transaction implementation
    /// </summary>
    public class MockTransaction : ITransaction
    {
        public string Name { get; }
        public TransactionStatus Status { get; set; }

        public MockTransaction(string name)
        {
            Name = name;
            Status = TransactionStatus.Started;
        }

        public async Task CommitAsync()
        {
            Status = TransactionStatus.Committed;
        }

        public async Task RollbackAsync()
        {
            Status = TransactionStatus.RolledBack;
        }

        public void Dispose()
        {
            if (Status == TransactionStatus.Started)
            {
                RollbackAsync().Wait();
            }
        }
    }

    /// <summary>
    /// Mock parameter manager for testing
    /// </summary>
    public class MockParameterManager : IParameterManager
    {
        private readonly ILogger _logger;

        public MockParameterManager(ILogger logger)
        {
            _logger = logger;
        }

        public async Task<T> GetParameterValueAsync<T>(object element, string parameterName)
        {
            await Task.Delay(1); // Simulate parameter access time

            var parameters = GetElementParameters(element);
            if (parameters.TryGetValue(parameterName, out var value))
            {
                return (T)Convert.ChangeType(value, typeof(T));
            }

            return default(T);
        }

        public async Task<bool> SetParameterValueAsync<T>(object element, string parameterName, T value)
        {
            await Task.Delay(1); // Simulate parameter write time

            var parameters = GetElementParameters(element);
            parameters[parameterName] = value;

            _logger.LogDebug("Set parameter {ParameterName} = {Value}", parameterName, value);
            return true;
        }

        public async Task<IEnumerable<ParameterInfo>> GetParametersAsync(object element)
        {
            await Task.Delay(5); // Simulate parameter enumeration time

            var parameters = GetElementParameters(element);
            return parameters.Select(kvp => new ParameterInfo
            {
                Name = kvp.Key,
                Value = kvp.Value,
                ValueType = kvp.Value?.GetType() ?? typeof(object),
                IsReadOnly = false
            }).ToList();
        }

        public async Task<ParameterInfo> GetParameterInfoAsync(object element, string parameterName)
        {
            await Task.Delay(1); // Simulate parameter info retrieval

            var parameters = GetElementParameters(element);
            if (parameters.TryGetValue(parameterName, out var value))
            {
                return new ParameterInfo
                {
                    Name = parameterName,
                    Value = value,
                    ValueType = value?.GetType() ?? typeof(object),
                    IsReadOnly = false
                };
            }

            return null;
        }

        public async Task<bool> CreateParameterAsync(object element, ParameterDefinition definition)
        {
            await Task.Delay(2); // Simulate parameter creation time

            var parameters = GetElementParameters(element);
            parameters[definition.Name] = definition.DefaultValue;

            _logger.LogDebug("Created parameter {ParameterName}", definition.Name);
            return true;
        }

        public async Task<bool> DeleteParameterAsync(object element, string parameterName)
        {
            await Task.Delay(1); // Simulate parameter deletion time

            var parameters = GetElementParameters(element);
            var removed = parameters.Remove(parameterName);

            _logger.LogDebug("Deleted parameter {ParameterName}: {Success}", parameterName, removed);
            return removed;
        }

        public bool SupportsParameterType(Type parameterType)
        {
            var supportedTypes = new[]
            {
                typeof(string), typeof(double), typeof(int), typeof(bool),
                typeof(DateTime), typeof(ElementId)
            };

            return supportedTypes.Contains(parameterType);
        }

        public object ConvertParameterValue(object value, Type targetType)
        {
            return Convert.ChangeType(value, targetType);
        }

        private Dictionary<string, object> GetElementParameters(object element)
        {
            return element switch
            {
                MockWall wall => wall.Parameters,
                MockElement mockElement => mockElement.Parameters,
                _ => new Dictionary<string, object>()
            };
        }
    }

    /// <summary>
    /// Mock geometry manager for testing
    /// </summary>
    public class MockGeometryManager : IGeometryManager
    {
        private readonly ILogger _logger;

        public MockGeometryManager(ILogger logger)
        {
            _logger = logger;
        }

        public async Task<GeometryElement> GetGeometryAsync(object element)
        {
            await Task.Delay(5); // Simulate geometry extraction time

            return new GeometryElement
            {
                NativeGeometry = element,
                BoundingBox = new BoundingBox
                {
                    Min = new Point3D(0, 0, 0),
                    Max = new Point3D(1000, 1000, 3000)
                }
            };
        }

        public async Task<BoundingBox> GetBoundingBoxAsync(object element)
        {
            await Task.Delay(2); // Simulate bounding box calculation

            return new BoundingBox
            {
                Min = new Point3D(0, 0, 0),
                Max = new Point3D(1000, 1000, 3000)
            };
        }

        public async Task<Point3D> TransformPointAsync(Point3D point, Transform transform)
        {
            await Task.Delay(1); // Simulate transformation

            // Simple mock transformation (just add origin)
            return new Point3D(
                point.X + transform.Origin.X,
                point.Y + transform.Origin.Y,
                point.Z + transform.Origin.Z
            );
        }

        public async Task<Curve> CreateLineAsync(Point3D start, Point3D end)
        {
            await Task.Delay(1); // Simulate line creation

            return new MockLine(start, end);
        }

        public async Task<Surface> CreateSurfaceAsync(GeometryCreationParameters parameters)
        {
            await Task.Delay(3); // Simulate surface creation

            return new MockSurface();
        }

        public bool SupportsGeometryType(Type geometryType)
        {
            var supportedTypes = new[] { typeof(Point3D), typeof(Curve), typeof(Surface) };
            return supportedTypes.Any(t => t.IsAssignableFrom(geometryType));
        }

        public async Task<T> ConvertGeometryAsync<T>(object geometry) where T : class
        {
            await Task.Delay(1); // Simulate conversion

            return geometry as T;
        }
    }

    /// <summary>
    /// Mock selection manager for testing
    /// </summary>
    public class MockSelectionManager : ISelectionManager
    {
        private readonly ILogger _logger;
        private readonly HashSet<ElementId> _selectedElements;

        public bool SupportsMultiSelect => true;
        public bool SupportsFilteredSelection => true;

        public MockSelectionManager(ILogger logger)
        {
            _logger = logger;
            _selectedElements = new HashSet<ElementId>();
        }

        public async Task<IEnumerable<ElementId>> GetSelectedElementsAsync()
        {
            await Task.Delay(1); // Simulate selection retrieval
            return _selectedElements.ToList();
        }

        public async Task SetSelectedElementsAsync(IEnumerable<ElementId> elementIds)
        {
            await Task.Delay(1); // Simulate selection setting

            _selectedElements.Clear();
            foreach (var id in elementIds)
            {
                _selectedElements.Add(id);
            }

            _logger.LogDebug("Selected {Count} elements", _selectedElements.Count);
        }

        public async Task<ElementId> PickElementAsync(string prompt, ElementFilter filter = null)
        {
            await Task.Delay(100); // Simulate user interaction time

            // Return a mock element ID
            return new ElementId(DateTime.UtcNow.Ticks);
        }

        public async Task<IEnumerable<ElementId>> PickElementsAsync(string prompt, ElementFilter filter = null)
        {
            await Task.Delay(200); // Simulate user interaction time

            // Return mock element IDs
            return new[]
            {
                new ElementId(DateTime.UtcNow.Ticks),
                new ElementId(DateTime.UtcNow.Ticks + 1),
                new ElementId(DateTime.UtcNow.Ticks + 2)
            };
        }

        public async Task<Point3D> PickPointAsync(string prompt)
        {
            await Task.Delay(150); // Simulate user interaction time

            return new Point3D(1000, 2000, 0);
        }

        public async Task<IEnumerable<Point3D>> PickPointsAsync(string prompt)
        {
            await Task.Delay(300); // Simulate user interaction time

            return new[]
            {
                new Point3D(0, 0, 0),
                new Point3D(1000, 0, 0),
                new Point3D(1000, 1000, 0)
            };
        }
    }

    /// <summary>
    /// Mock view manager for testing
    /// </summary>
    public class MockViewManager : IViewManager
    {
        private readonly ILogger _logger;
        private View _activeView;

        public MockViewManager(ILogger logger)
        {
            _logger = logger;
            _activeView = new View
            {
                Name = "3D View",
                ViewType = ViewType.ThreeD,
                Id = new ElementId(1)
            };
        }

        public async Task<View> GetActiveViewAsync()
        {
            await Task.Delay(1);
            return _activeView;
        }

        public async Task SetActiveViewAsync(View view)
        {
            await Task.Delay(5); // Simulate view switching time
            _activeView = view;
            _logger.LogDebug("Set active view to {ViewName}", view.Name);
        }

        public async Task<IEnumerable<View>> GetViewsAsync(ViewType viewType = ViewType.All)
        {
            await Task.Delay(10); // Simulate view enumeration

            var views = new List<View>
            {
                new View { Name = "Floor Plan - Level 1", ViewType = ViewType.FloorPlan, Id = new ElementId(10) },
                new View { Name = "Floor Plan - Level 2", ViewType = ViewType.FloorPlan, Id = new ElementId(11) },
                new View { Name = "3D View", ViewType = ViewType.ThreeD, Id = new ElementId(12) },
                new View { Name = "Elevation - South", ViewType = ViewType.Elevation, Id = new ElementId(13) }
            };

            return viewType == ViewType.All ? views : views.Where(v => v.ViewType == viewType);
        }

        public async Task<View> CreateViewAsync(ViewCreationParameters parameters)
        {
            await Task.Delay(20); // Simulate view creation time

            var view = new View
            {
                Name = parameters.Name,
                ViewType = parameters.ViewType,
                Id = new ElementId(DateTime.UtcNow.Ticks)
            };

            _logger.LogDebug("Created view {ViewName} of type {ViewType}", view.Name, view.ViewType);
            return view;
        }

        public async Task<bool> SetViewParameterAsync(View view, string parameterName, object value)
        {
            await Task.Delay(1);
            _logger.LogDebug("Set view parameter {ParameterName} = {Value} for view {ViewName}",
                parameterName, value, view.Name);
            return true;
        }

        public async Task<T> GetViewParameterAsync<T>(View view, string parameterName)
        {
            await Task.Delay(1);
            return default(T);
        }

        public bool SupportsViewType(ViewType viewType)
        {
            return Enum.IsDefined(typeof(ViewType), viewType) && viewType != ViewType.All;
        }
    }

    /// <summary>
    /// Mock family manager for testing
    /// </summary>
    public class MockFamilyManager : IFamilyManager
    {
        private readonly ILogger _logger;

        public MockFamilyManager(ILogger logger)
        {
            _logger = logger;
        }

        public async Task<Family> LoadFamilyAsync(string familyPath)
        {
            await Task.Delay(50); // Simulate family loading time

            var family = new Family
            {
                Name = System.IO.Path.GetFileNameWithoutExtension(familyPath),
                Category = "Walls",
                Id = new ElementId(DateTime.UtcNow.Ticks)
            };

            _logger.LogDebug("Loaded family {FamilyName} from {FamilyPath}", family.Name, familyPath);
            return family;
        }

        public async Task<bool> ReloadFamilyAsync(Family family)
        {
            await Task.Delay(30); // Simulate family reloading time
            _logger.LogDebug("Reloaded family {FamilyName}", family.Name);
            return true;
        }

        public async Task<IEnumerable<FamilySymbol>> GetFamilySymbolsAsync(Family family)
        {
            await Task.Delay(10); // Simulate symbol enumeration

            return new[]
            {
                new FamilySymbol { Name = "Type 1", Family = family, Id = new ElementId(family.Id.Id + 1) },
                new FamilySymbol { Name = "Type 2", Family = family, Id = new ElementId(family.Id.Id + 2) }
            };
        }

        public async Task<FamilyInstance> CreateFamilyInstanceAsync(FamilySymbol symbol, Point3D location)
        {
            await Task.Delay(15); // Simulate instance creation time

            var instance = new FamilyInstance
            {
                Symbol = symbol,
                Location = location,
                Id = new ElementId(DateTime.UtcNow.Ticks)
            };

            _logger.LogDebug("Created family instance of {SymbolName} at ({X}, {Y}, {Z})",
                symbol.Name, location.X, location.Y, location.Z);
            return instance;
        }

        public async Task<bool> EditFamilyAsync(Family family, Func<FamilyDocument, Task> editAction)
        {
            await Task.Delay(100); // Simulate family editing time

            var familyDoc = new FamilyDocument { Family = family };
            await editAction(familyDoc);

            _logger.LogDebug("Edited family {FamilyName}", family.Name);
            return true;
        }

        public bool SupportsFamilyType(Type familyType)
        {
            return true; // Mock supports all family types
        }
    }

    // Mock geometry classes
    public class MockLine : Curve
    {
        public override Point3D StartPoint { get; }
        public override Point3D EndPoint { get; }
        public override double Length { get; }

        public MockLine(Point3D start, Point3D end)
        {
            StartPoint = start;
            EndPoint = end;
            Length = Math.Sqrt(
                Math.Pow(end.X - start.X, 2) +
                Math.Pow(end.Y - start.Y, 2) +
                Math.Pow(end.Z - start.Z, 2)
            );
        }
    }

    public class MockSurface : Surface
    {
        public override BoundingBox BoundingBox => new BoundingBox
        {
            Min = new Point3D(0, 0, 0),
            Max = new Point3D(1000, 1000, 0)
        };

        public override double Area => 1000000; // 1M square units
    }
}
