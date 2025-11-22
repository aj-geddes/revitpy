using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace RevitPy.Compatibility.Abstractions
{
    /// <summary>
    /// Version-agnostic Revit API abstraction interface
    /// Provides consistent API surface across different Revit versions
    /// </summary>
    public interface IRevitAPIAbstraction
    {
        /// <summary>
        /// Gets the supported Revit version for this abstraction
        /// </summary>
        RevitVersion SupportedVersion { get; }

        /// <summary>
        /// Initializes the API abstraction
        /// </summary>
        /// <param name="context">Initialization context</param>
        Task InitializeAsync(APIInitializationContext context);

        // Element Management
        IElementManager ElementManager { get; }
        ITransactionManager TransactionManager { get; }
        IParameterManager ParameterManager { get; }
        IGeometryManager GeometryManager { get; }
        ISelectionManager SelectionManager { get; }
        IViewManager ViewManager { get; }
        IFamilyManager FamilyManager { get; }

        // Version-specific feature checks
        bool SupportsFeature(string featureName);
        IFeatureAdapter GetFeatureAdapter(string featureName);

        // Error handling and recovery
        Task<T> ExecuteWithFallbackAsync<T>(Func<Task<T>> primaryAction, Func<Task<T>> fallbackAction);
        void HandleVersionSpecificException(Exception exception);
    }

    /// <summary>
    /// Element management abstraction
    /// </summary>
    public interface IElementManager
    {
        Task<TElement> CreateElementAsync<TElement>(ElementCreationParameters parameters)
            where TElement : class;

        Task<TElement> GetElementAsync<TElement>(ElementId elementId)
            where TElement : class;

        Task<IEnumerable<TElement>> GetElementsAsync<TElement>(ElementFilter filter)
            where TElement : class;

        Task<bool> DeleteElementAsync(ElementId elementId);

        Task<TElement> ModifyElementAsync<TElement>(TElement element, Action<TElement> modification)
            where TElement : class;

        Task<IEnumerable<TElement>> GetElementsByTypeAsync<TElement>(Type elementType)
            where TElement : class;
    }

    /// <summary>
    /// Transaction management abstraction
    /// </summary>
    public interface ITransactionManager
    {
        Task<TransactionResult> ExecuteInTransactionAsync(string transactionName, Func<Task> action);
        Task<TransactionResult<T>> ExecuteInTransactionAsync<T>(string transactionName, Func<Task<T>> action);

        Task<ITransaction> BeginTransactionAsync(string transactionName);
        Task CommitTransactionAsync(ITransaction transaction);
        Task RollbackTransactionAsync(ITransaction transaction);

        bool IsInTransaction { get; }
        bool SupportsNestedTransactions { get; }
    }

    /// <summary>
    /// Parameter management abstraction
    /// </summary>
    public interface IParameterManager
    {
        Task<T> GetParameterValueAsync<T>(object element, string parameterName);
        Task<bool> SetParameterValueAsync<T>(object element, string parameterName, T value);

        Task<IEnumerable<ParameterInfo>> GetParametersAsync(object element);
        Task<ParameterInfo> GetParameterInfoAsync(object element, string parameterName);

        Task<bool> CreateParameterAsync(object element, ParameterDefinition definition);
        Task<bool> DeleteParameterAsync(object element, string parameterName);

        bool SupportsParameterType(Type parameterType);
        object ConvertParameterValue(object value, Type targetType);
    }

    /// <summary>
    /// Geometry management abstraction
    /// </summary>
    public interface IGeometryManager
    {
        Task<GeometryElement> GetGeometryAsync(object element);
        Task<BoundingBox> GetBoundingBoxAsync(object element);

        Task<Point3D> TransformPointAsync(Point3D point, Transform transform);
        Task<Curve> CreateLineAsync(Point3D start, Point3D end);
        Task<Surface> CreateSurfaceAsync(GeometryCreationParameters parameters);

        bool SupportsGeometryType(Type geometryType);
        Task<T> ConvertGeometryAsync<T>(object geometry) where T : class;
    }

    /// <summary>
    /// Selection management abstraction
    /// </summary>
    public interface ISelectionManager
    {
        Task<IEnumerable<ElementId>> GetSelectedElementsAsync();
        Task SetSelectedElementsAsync(IEnumerable<ElementId> elementIds);

        Task<ElementId> PickElementAsync(string prompt, ElementFilter filter = null);
        Task<IEnumerable<ElementId>> PickElementsAsync(string prompt, ElementFilter filter = null);

        Task<Point3D> PickPointAsync(string prompt);
        Task<IEnumerable<Point3D>> PickPointsAsync(string prompt);

        bool SupportsMultiSelect { get; }
        bool SupportsFilteredSelection { get; }
    }

    /// <summary>
    /// View management abstraction
    /// </summary>
    public interface IViewManager
    {
        Task<View> GetActiveViewAsync();
        Task SetActiveViewAsync(View view);

        Task<IEnumerable<View>> GetViewsAsync(ViewType viewType = ViewType.All);
        Task<View> CreateViewAsync(ViewCreationParameters parameters);

        Task<bool> SetViewParameterAsync(View view, string parameterName, object value);
        Task<T> GetViewParameterAsync<T>(View view, string parameterName);

        bool SupportsViewType(ViewType viewType);
    }

    /// <summary>
    /// Family management abstraction
    /// </summary>
    public interface IFamilyManager
    {
        Task<Family> LoadFamilyAsync(string familyPath);
        Task<bool> ReloadFamilyAsync(Family family);

        Task<IEnumerable<FamilySymbol>> GetFamilySymbolsAsync(Family family);
        Task<FamilyInstance> CreateFamilyInstanceAsync(FamilySymbol symbol, Point3D location);

        Task<bool> EditFamilyAsync(Family family, Func<FamilyDocument, Task> editAction);

        bool SupportsFamilyType(Type familyType);
    }

    /// <summary>
    /// Feature adapter for version-specific implementations
    /// </summary>
    public interface IFeatureAdapter
    {
        string FeatureName { get; }
        RevitVersion MinimumVersion { get; }
        bool IsAvailable { get; }

        Task<T> ExecuteAsync<T>(Func<Task<T>> action);
        Task ExecuteAsync(Func<Task> action);

        object GetImplementation(Type interfaceType);
        bool SupportsInterface(Type interfaceType);
    }

    // Supporting Types
    public class APIInitializationContext
    {
        public RevitVersionInfo VersionInfo { get; set; }
        public object Application { get; set; }
        public object Document { get; set; }
        public Dictionary<string, object> Properties { get; set; } = new();
    }

    public class ElementCreationParameters
    {
        public Type ElementType { get; set; }
        public Dictionary<string, object> Parameters { get; set; } = new();
        public object Location { get; set; }
        public object Level { get; set; }
    }

    public class ElementFilter
    {
        public Type ElementType { get; set; }
        public Dictionary<string, object> Criteria { get; set; } = new();
        public string Category { get; set; }
        public Func<object, bool> CustomFilter { get; set; }
    }

    public interface ITransaction : IDisposable
    {
        string Name { get; }
        TransactionStatus Status { get; }
        Task CommitAsync();
        Task RollbackAsync();
    }

    public enum TransactionStatus
    {
        Started,
        Committed,
        RolledBack,
        Error
    }

    public class TransactionResult
    {
        public bool Success { get; set; }
        public string ErrorMessage { get; set; }
        public Exception Exception { get; set; }
    }

    public class TransactionResult<T> : TransactionResult
    {
        public T Result { get; set; }
    }

    public class ParameterInfo
    {
        public string Name { get; set; }
        public Type ValueType { get; set; }
        public object Value { get; set; }
        public bool IsReadOnly { get; set; }
        public string Unit { get; set; }
        public string Group { get; set; }
    }

    public class ParameterDefinition
    {
        public string Name { get; set; }
        public Type ValueType { get; set; }
        public string Group { get; set; }
        public bool IsInstance { get; set; }
        public object DefaultValue { get; set; }
    }

    public class GeometryElement
    {
        public object NativeGeometry { get; set; }
        public BoundingBox BoundingBox { get; set; }
        public IEnumerable<object> Faces { get; set; }
        public IEnumerable<object> Edges { get; set; }
    }

    public class BoundingBox
    {
        public Point3D Min { get; set; }
        public Point3D Max { get; set; }
        public Point3D Center => new Point3D(
            (Min.X + Max.X) / 2,
            (Min.Y + Max.Y) / 2,
            (Min.Z + Max.Z) / 2
        );
    }

    public class Point3D
    {
        public double X { get; set; }
        public double Y { get; set; }
        public double Z { get; set; }

        public Point3D() { }
        public Point3D(double x, double y, double z)
        {
            X = x; Y = y; Z = z;
        }
    }

    public class Transform
    {
        public double[,] Matrix { get; set; } = new double[4, 4];
        public Point3D Origin { get; set; } = new Point3D();
    }

    public abstract class Curve
    {
        public abstract Point3D StartPoint { get; }
        public abstract Point3D EndPoint { get; }
        public abstract double Length { get; }
    }

    public abstract class Surface
    {
        public abstract BoundingBox BoundingBox { get; }
        public abstract double Area { get; }
    }

    public class GeometryCreationParameters
    {
        public Type GeometryType { get; set; }
        public Dictionary<string, object> Parameters { get; set; } = new();
    }

    public class View
    {
        public object NativeView { get; set; }
        public string Name { get; set; }
        public ViewType ViewType { get; set; }
        public ElementId Id { get; set; }
    }

    public enum ViewType
    {
        All,
        FloorPlan,
        CeilingPlan,
        Elevation,
        Section,
        ThreeD,
        Schedule,
        DrawingSheet
    }

    public class ViewCreationParameters
    {
        public ViewType ViewType { get; set; }
        public string Name { get; set; }
        public object ViewTemplate { get; set; }
        public object Level { get; set; }
        public Dictionary<string, object> Properties { get; set; } = new();
    }

    public class Family
    {
        public object NativeFamily { get; set; }
        public string Name { get; set; }
        public string Category { get; set; }
        public ElementId Id { get; set; }
    }

    public class FamilySymbol
    {
        public object NativeSymbol { get; set; }
        public string Name { get; set; }
        public Family Family { get; set; }
        public ElementId Id { get; set; }
    }

    public class FamilyInstance
    {
        public object NativeInstance { get; set; }
        public FamilySymbol Symbol { get; set; }
        public Point3D Location { get; set; }
        public ElementId Id { get; set; }
    }

    public class FamilyDocument
    {
        public object NativeDocument { get; set; }
        public Family Family { get; set; }
    }

    public class ElementId
    {
        public long Id { get; set; }
        public ElementId(long id) { Id = id; }
        public static implicit operator ElementId(long id) => new ElementId(id);
        public static implicit operator long(ElementId elementId) => elementId.Id;

        public override bool Equals(object obj)
        {
            return obj is ElementId other && Id == other.Id;
        }

        public override int GetHashCode()
        {
            return Id.GetHashCode();
        }
    }
}
