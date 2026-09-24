using System;
using System.Collections.Concurrent;
using System.Threading;
using Autodesk.Revit.UI;
using Python.Runtime;

namespace RevitPy.Addin;

/// <summary>
/// Marshals Python callables from background threads onto Revit's main API thread via an
/// <see cref="ExternalEvent"/>. Exposed to Python as <c>builtins.__revitpy_dispatcher__</c>
/// and used by <c>revitpy.revit.host.call_on_revit_thread</c>.
/// </summary>
/// <remarks>
/// Python callers poll <see cref="DispatchRequest.IsCompleted"/> while sleeping instead of
/// blocking on a wait handle: pythonnet does not release the GIL during .NET calls, so a
/// blocking wait would hold the GIL that <see cref="Execute"/> needs on the main thread and
/// deadlock Revit.
/// </remarks>
public sealed class RevitDispatcher : IExternalEventHandler
{
    private readonly ConcurrentQueue<DispatchRequest> _queue = new ConcurrentQueue<DispatchRequest>();
    private ExternalEvent? _event;

    public int PendingCount => _queue.Count;

    /// <summary>Creates the external event. Must run on Revit's main thread.</summary>
    public void Register()
    {
        _event ??= ExternalEvent.Create(this);
    }

    /// <summary>Queues <paramref name="callable"/>(uiapp) for execution on the main thread.</summary>
    public DispatchRequest Post(PyObject callable)
    {
        if (_event == null)
        {
            throw new InvalidOperationException("RevitDispatcher has not been registered.");
        }

        var request = new DispatchRequest(callable);
        _queue.Enqueue(request);
        _event.Raise();
        return request;
    }

    public void Execute(UIApplication app)
    {
        while (_queue.TryDequeue(out var request))
        {
            try
            {
                using (Py.GIL())
                {
                    request.Complete(request.Callable.Invoke(app.ToPython()));
                }
            }
            catch (PythonException ex)
            {
                request.Fail(ex.Format());
            }
            catch (Exception ex)
            {
                request.Fail(ex.ToString());
            }
        }
    }

    public string GetName() => "RevitPy dispatcher";
}

/// <summary>A callable queued on <see cref="RevitDispatcher"/> and its outcome.</summary>
public sealed class DispatchRequest
{
    private bool _isCompleted;
    private bool _succeeded;
    private PyObject? _result;
    private string? _error;

    internal DispatchRequest(PyObject callable)
    {
        Callable = callable;
    }

    public PyObject Callable { get; }

    public bool IsCompleted => Volatile.Read(ref _isCompleted);

    public bool Succeeded => Volatile.Read(ref _succeeded);

    public PyObject? Result => Volatile.Read(ref _result);

    public string? Error => Volatile.Read(ref _error);

    internal void Complete(PyObject result)
    {
        Volatile.Write(ref _result, result);
        Volatile.Write(ref _succeeded, true);
        Volatile.Write(ref _isCompleted, true);
    }

    internal void Fail(string error)
    {
        Volatile.Write(ref _error, error);
        Volatile.Write(ref _succeeded, false);
        Volatile.Write(ref _isCompleted, true);
    }
}
