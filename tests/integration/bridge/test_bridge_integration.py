"""Integration tests for Python-C# bridge communication.

This module tests the complete integration between the Python framework
and the C# bridge, including type conversion, transaction management,
and error handling across the language boundary.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from revitpy.api.exceptions import RevitAPIException, RevitConnectionError
from revitpy.api.wrapper import RevitAPIWrapper
from revitpy.orm.models import Door, Wall, Window
from revitpy.orm.session import RevitSession


class TestPythonCSharpBridge:
    """Test integration between Python and C# components."""

    @pytest.fixture
    def mock_bridge_connector(self):
        """Mock the C# bridge connector."""
        with patch("revitpy.api.wrapper.BridgeConnector") as mock_connector:
            mock_bridge = MagicMock()
            mock_bridge.IsConnected = True
            mock_bridge.Version = "2024.1.0"
            mock_bridge.CallAsync = AsyncMock()
            mock_bridge.Subscribe = MagicMock()
            mock_bridge.Unsubscribe = MagicMock()
            mock_bridge.Disconnect = MagicMock()

            mock_connector.return_value.connect.return_value = mock_bridge
            yield mock_bridge

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_bridge_lifecycle(self, mock_bridge_connector):
        """Test complete bridge lifecycle from connection to disconnection."""
        # Test connection
        wrapper = RevitAPIWrapper()
        connected = await wrapper.connect()

        assert connected is True
        assert wrapper.is_connected is True

        # Test API call
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {
                "Id": 12345,
                "Name": "Test Wall",
                "Category": "Walls",
                "Parameters": {"Height": 3000.0, "Width": 200.0},
            }
        )

        result = await wrapper.call_api("GetElement", {"elementId": 12345})

        assert result["Id"] == 12345
        assert result["Name"] == "Test Wall"

        # Test disconnection
        await wrapper.disconnect()
        assert wrapper.is_connected is False
        mock_bridge_connector.Disconnect.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_type_conversion_roundtrip(self, mock_bridge_connector):
        """Test type conversion between Python and C#."""
        wrapper = RevitAPIWrapper()
        await wrapper.connect()

        # Test various data types
        test_data = {
            "integer": 42,
            "float": 3.14159,
            "string": "Hello RevitPy",
            "boolean": True,
            "array": [1, 2, 3, 4, 5],
            "nested_object": {
                "id": 123,
                "properties": {"height": 3000.0, "materials": ["Concrete", "Steel"]},
            },
            "null_value": None,
        }

        # Mock C# bridge to return the same data (simulating roundtrip)
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {"converted_data": test_data, "conversion_success": True}
        )

        result = await wrapper.call_api("TestTypeConversion", test_data)

        # Verify type conversion preserved data integrity
        converted_data = result["converted_data"]
        assert converted_data["integer"] == 42
        assert abs(converted_data["float"] - 3.14159) < 0.00001
        assert converted_data["string"] == "Hello RevitPy"
        assert converted_data["boolean"] is True
        assert converted_data["array"] == [1, 2, 3, 4, 5]
        assert converted_data["nested_object"]["id"] == 123
        assert converted_data["null_value"] is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transaction_management_integration(self, mock_bridge_connector):
        """Test transaction management across the bridge."""
        wrapper = RevitAPIWrapper()
        await wrapper.connect()

        # Mock successful transaction
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {
                "transaction_id": "tx_12345",
                "status": "started",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        )

        # Start transaction
        tx_result = await wrapper.call_api(
            "StartTransaction", {"name": "Test Transaction"}
        )
        assert tx_result["status"] == "started"

        # Perform operations within transaction
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {"element_id": 67890, "success": True, "transaction_id": "tx_12345"}
        )

        create_result = await wrapper.call_api(
            "CreateElement",
            {
                "elementType": "Wall",
                "parameters": {"Height": 3000.0},
                "transaction_id": "tx_12345",
            },
        )
        assert create_result["success"] is True

        # Commit transaction
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {"transaction_id": "tx_12345", "status": "committed", "changes_count": 1}
        )

        commit_result = await wrapper.call_api(
            "CommitTransaction", {"transaction_id": "tx_12345"}
        )
        assert commit_result["status"] == "committed"
        assert commit_result["changes_count"] == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transaction_rollback_integration(self, mock_bridge_connector):
        """Test transaction rollback across the bridge."""
        wrapper = RevitAPIWrapper()
        await wrapper.connect()

        # Start transaction
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {"transaction_id": "tx_rollback", "status": "started"}
        )

        await wrapper.call_api("StartTransaction", {"name": "Rollback Test"})

        # Simulate error during operation
        mock_bridge_connector.CallAsync.side_effect = Exception("Simulated error")

        with pytest.raises(RevitAPIException):
            await wrapper.call_api(
                "CreateElement",
                {"elementType": "InvalidType", "transaction_id": "tx_rollback"},
            )

        # Transaction should be automatically rolled back
        mock_bridge_connector.CallAsync.side_effect = None
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {"transaction_id": "tx_rollback", "status": "rolled_back"}
        )

        rollback_result = await wrapper.call_api(
            "RollbackTransaction", {"transaction_id": "tx_rollback"}
        )
        assert rollback_result["status"] == "rolled_back"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_event_system_integration(self, mock_bridge_connector):
        """Test event system integration across the bridge."""
        wrapper = RevitAPIWrapper()
        await wrapper.connect()

        # Track received events
        received_events = []

        def event_handler(event_data):
            received_events.append(event_data)

        # Subscribe to events
        wrapper.subscribe("ElementChanged", event_handler)
        mock_bridge_connector.Subscribe.assert_called_once_with("ElementChanged")

        # Simulate event from C# bridge
        event_data = {
            "event_type": "ElementChanged",
            "element_id": 12345,
            "change_type": "modified",
            "timestamp": "2024-01-01T12:00:00Z",
        }

        wrapper._handle_event("ElementChanged", event_data)

        # Verify event was handled
        assert len(received_events) == 1
        assert received_events[0]["element_id"] == 12345
        assert received_events[0]["change_type"] == "modified"

        # Unsubscribe
        wrapper.unsubscribe("ElementChanged")
        mock_bridge_connector.Unsubscribe.assert_called_once_with("ElementChanged")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_propagation_across_bridge(self, mock_bridge_connector):
        """Test error propagation from C# to Python."""
        wrapper = RevitAPIWrapper()
        await wrapper.connect()

        # Test various error types
        error_scenarios = [
            {
                "exception": "ElementNotFoundException",
                "message": "Element with ID 99999 not found",
                "error_code": "ELEMENT_NOT_FOUND",
            },
            {
                "exception": "InvalidOperationException",
                "message": "Cannot modify element in read-only transaction",
                "error_code": "INVALID_OPERATION",
            },
            {
                "exception": "ArgumentException",
                "message": "Invalid parameter value for Height: -100",
                "error_code": "INVALID_ARGUMENT",
            },
        ]

        for scenario in error_scenarios:
            mock_bridge_connector.CallAsync.side_effect = Exception(
                f"{scenario['exception']}: {scenario['message']}"
            )

            with pytest.raises(RevitAPIException) as exc_info:
                await wrapper.call_api("TestErrorScenario", scenario)

            assert scenario["message"] in str(exc_info.value)

        # Reset mock
        mock_bridge_connector.CallAsync.side_effect = None


class TestORMBridgeIntegration:
    """Test ORM integration with C# bridge."""

    @pytest.fixture
    def mock_session(self, mock_bridge_connector):
        """Create mock RevitSession with bridge integration."""
        session = MagicMock(spec=RevitSession)
        wrapper = RevitAPIWrapper()
        wrapper._bridge = mock_bridge_connector
        wrapper._connected = True
        session.api_wrapper = wrapper
        return session

    @pytest.fixture
    def mock_bridge_connector(self):
        """Mock bridge connector for ORM tests."""
        mock_bridge = MagicMock()
        mock_bridge.CallAsync = AsyncMock()
        return mock_bridge

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_orm_element_crud_operations(
        self, mock_session, mock_bridge_connector
    ):
        """Test CRUD operations through ORM with bridge integration."""
        # Test Create
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {
                "Id": 12345,
                "Name": "New Wall",
                "Category": "Walls",
                "Parameters": {"Height": 3000.0, "Width": 200.0},
            }
        )

        # Create wall through ORM
        wall_data = {
            "elementType": "Wall",
            "wallType": "Basic Wall",
            "parameters": {"Height": 3000.0, "Width": 200.0},
        }

        result = await mock_session.api_wrapper.call_api("CreateElement", wall_data)
        wall = Wall.from_data(result, session=mock_session)

        assert isinstance(wall, Wall)
        assert wall.id == 12345
        assert wall.height == 3000.0

        # Test Read
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            {
                "Id": 12345,
                "Name": "New Wall",
                "Category": "Walls",
                "Parameters": {"Height": 3000.0, "Width": 200.0},
            }
        )

        await wall.refresh()
        assert wall.name == "New Wall"

        # Test Update
        wall.height = 3500.0
        mock_bridge_connector.CallAsync.return_value = json.dumps({"success": True})
        await wall.save()

        # Verify update call was made
        update_call = None
        for call in mock_bridge_connector.CallAsync.call_args_list:
            if call[0][0] == "UpdateElement":
                update_call = call
                break

        assert update_call is not None
        update_params = json.loads(update_call[0][1])
        assert update_params["elementId"] == 12345
        assert update_params["parameters"]["Height"] == 3500.0

        # Test Delete
        mock_bridge_connector.CallAsync.return_value = json.dumps({"success": True})
        await wall.delete()

        assert wall._deleted is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_orm_relationships_integration(
        self, mock_session, mock_bridge_connector
    ):
        """Test ORM relationships through bridge."""
        # Create wall
        wall_data = {
            "Id": 12345,
            "Name": "Host Wall",
            "Category": "Walls",
            "Parameters": {"Height": 3000.0},
        }
        wall = Wall.from_data(wall_data, session=mock_session)

        # Mock hosted elements query
        mock_bridge_connector.CallAsync.return_value = json.dumps(
            [
                {
                    "Id": 67890,
                    "Name": "Door 1",
                    "Category": "Doors",
                    "Parameters": {"Height": 2100.0, "HostId": 12345},
                },
                {
                    "Id": 67891,
                    "Name": "Window 1",
                    "Category": "Windows",
                    "Parameters": {"Height": 1200.0, "HostId": 12345},
                },
            ]
        )

        # Get hosted elements
        hosted_elements = await wall.get_hosted_elements()

        assert len(hosted_elements) == 2
        assert isinstance(hosted_elements[0], Door)
        assert isinstance(hosted_elements[1], Window)
        assert hosted_elements[0].name == "Door 1"
        assert hosted_elements[1].name == "Window 1"

        # Verify API call was made correctly
        mock_bridge_connector.CallAsync.assert_called_with(
            "GetHostedElements",
            json.dumps({"hostId": 12345}),
            30.0,  # Default timeout
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_orm_query_integration(self, mock_session, mock_bridge_connector):
        """Test ORM queries through bridge integration."""
        from revitpy.orm.query import QueryBuilder

        # Mock query results
        mock_elements = [
            {
                "Id": i,
                "Name": f"Wall {i}",
                "Category": "Walls",
                "Parameters": {"Height": 3000.0 + (i * 100)},
            }
            for i in range(1, 6)  # 5 walls
        ]

        mock_bridge_connector.CallAsync.return_value = json.dumps(mock_elements)

        # Build and execute query
        query = (
            QueryBuilder(session=mock_session)
            .filter_by_category("Walls")
            .filter_by_parameter("Height", ">", 2500.0)
            .of_type(Wall)
            .limit(10)
        )

        results = await query.all()

        # Verify results
        assert len(results) == 5
        assert all(isinstance(wall, Wall) for wall in results)
        assert all(wall.category == "Walls" for wall in results)

        # Verify query parameters sent to bridge
        query_call = mock_bridge_connector.CallAsync.call_args
        assert query_call[0][0] == "QueryElements"

        query_params = json.loads(query_call[0][1])
        assert len(query_params["filters"]) == 2
        assert query_params["element_type"] == "Wall"
        assert query_params["limit"] == 10


class TestConcurrentBridgeOperations:
    """Test concurrent operations across the bridge."""

    @pytest.fixture
    def mock_bridge_connector(self):
        """Mock bridge connector for concurrent testing."""
        mock_bridge = MagicMock()
        mock_bridge.CallAsync = AsyncMock()
        return mock_bridge

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_api_calls_thread_safety(self, mock_bridge_connector):
        """Test thread safety of concurrent API calls."""
        wrapper = RevitAPIWrapper()
        wrapper._bridge = mock_bridge_connector
        wrapper._connected = True

        # Mock responses with call-specific data
        async def mock_call_async(method, params, timeout=None):
            # Parse parameters to return call-specific response
            param_dict = json.loads(params) if isinstance(params, str) else params
            call_id = param_dict.get("callId", 0)

            return json.dumps(
                {
                    "callId": call_id,
                    "method": method,
                    "result": f"Response for call {call_id}",
                    "timestamp": time.time(),
                }
            )

        mock_bridge_connector.CallAsync.side_effect = mock_call_async

        # Make 20 concurrent API calls
        tasks = []
        for i in range(20):
            task = wrapper.call_api("TestMethod", {"callId": i})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all calls completed successfully
        assert len(results) == 20

        # Verify each call got the correct response
        for i, result in enumerate(results):
            assert result["callId"] == i
            assert result["method"] == "TestMethod"
            assert f"call {i}" in result["result"]

        # Verify thread safety - all calls should have been made
        assert mock_bridge_connector.CallAsync.call_count == 20

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_transactions(self, mock_bridge_connector):
        """Test concurrent transaction handling."""
        wrapper = RevitAPIWrapper()
        wrapper._bridge = mock_bridge_connector
        wrapper._connected = True

        # Mock transaction responses
        transaction_counter = 0

        async def mock_transaction_call(method, params, timeout=None):
            nonlocal transaction_counter

            if method == "StartTransaction":
                transaction_counter += 1
                return json.dumps(
                    {"transaction_id": f"tx_{transaction_counter}", "status": "started"}
                )
            elif method == "CommitTransaction":
                param_dict = json.loads(params)
                return json.dumps(
                    {
                        "transaction_id": param_dict["transaction_id"],
                        "status": "committed",
                    }
                )
            else:
                return json.dumps({"success": True})

        mock_bridge_connector.CallAsync.side_effect = mock_transaction_call

        # Run multiple transactions concurrently
        async def transaction_workflow(tx_id):
            # Start transaction
            tx_result = await wrapper.call_api(
                "StartTransaction", {"name": f"TX_{tx_id}"}
            )
            tx_id_actual = tx_result["transaction_id"]

            # Do some work
            await wrapper.call_api(
                "CreateElement", {"elementType": "Wall", "transaction_id": tx_id_actual}
            )

            # Commit transaction
            commit_result = await wrapper.call_api(
                "CommitTransaction", {"transaction_id": tx_id_actual}
            )

            return commit_result

        # Run 5 concurrent transactions
        tasks = [transaction_workflow(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Verify all transactions completed
        assert len(results) == 5
        assert all(result["status"] == "committed" for result in results)

        # Verify unique transaction IDs
        tx_ids = [result["transaction_id"] for result in results]
        assert len(set(tx_ids)) == 5  # All unique

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_high_load_bridge_performance(
        self, mock_bridge_connector, performance_monitor
    ):
        """Test bridge performance under high load."""
        wrapper = RevitAPIWrapper()
        wrapper._bridge = mock_bridge_connector
        wrapper._connected = True

        # Mock fast responses
        mock_bridge_connector.CallAsync.return_value = json.dumps({"result": "success"})

        with performance_monitor.measure():
            # Make 1000 API calls as quickly as possible
            tasks = []
            for i in range(1000):
                task = wrapper.call_api("PerformanceTest", {"iteration": i})
                tasks.append(task)

            results = await asyncio.gather(*tasks)

        metrics = performance_monitor.last_metrics

        # Performance assertions
        assert len(results) == 1000
        assert metrics["execution_time"] < 10.0  # Less than 10 seconds

        # Calculate throughput
        throughput = 1000 / metrics["execution_time"]
        assert throughput > 100  # More than 100 calls per second


class TestBridgeErrorRecovery:
    """Test error recovery and resilience across the bridge."""

    @pytest.fixture
    def mock_bridge_connector(self):
        """Mock bridge connector for error testing."""
        mock_bridge = MagicMock()
        mock_bridge.CallAsync = AsyncMock()
        return mock_bridge

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connection_recovery(self, mock_bridge_connector):
        """Test automatic connection recovery after bridge failure."""
        wrapper = RevitAPIWrapper(config={"auto_reconnect": True, "retry_count": 3})

        # Mock initial connection success
        with patch("revitpy.api.wrapper.BridgeConnector") as mock_connector:
            mock_connector.return_value.connect.return_value = mock_bridge_connector
            mock_bridge_connector.IsConnected = True

            await wrapper.connect()
            assert wrapper.is_connected

            # Simulate connection loss
            mock_bridge_connector.IsConnected = False
            mock_bridge_connector.CallAsync.side_effect = ConnectionError(
                "Bridge disconnected"
            )

            # First call should fail and trigger reconnection attempt
            with pytest.raises(RevitConnectionError):
                await wrapper.call_api("TestMethod", {})

            # Mock successful reconnection
            mock_bridge_connector.IsConnected = True
            mock_bridge_connector.CallAsync.side_effect = None
            mock_bridge_connector.CallAsync.return_value = json.dumps(
                {"result": "success"}
            )

            # Retry should succeed after reconnection
            result = await wrapper.call_api("TestMethod", {})
            assert result["result"] == "success"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, mock_bridge_connector):
        """Test handling of partial failures in batch operations."""
        wrapper = RevitAPIWrapper()
        wrapper._bridge = mock_bridge_connector
        wrapper._connected = True

        # Mock responses with some failures
        call_count = 0

        async def mock_call_with_failures(method, params, timeout=None):
            nonlocal call_count
            call_count += 1

            # Fail every 3rd call
            if call_count % 3 == 0:
                raise Exception(f"Simulated failure for call {call_count}")

            return json.dumps({"call_number": call_count, "result": "success"})

        mock_bridge_connector.CallAsync.side_effect = mock_call_with_failures

        # Make batch calls
        calls = [{"method": "TestMethod", "params": {"id": i}} for i in range(10)]

        results = await wrapper.batch_call(calls, fail_fast=False)

        # Verify mixed results (successes and failures)
        assert len(results) == 10

        success_count = sum(
            1 for result in results if not isinstance(result, Exception)
        )
        failure_count = sum(1 for result in results if isinstance(result, Exception))

        assert success_count == 7  # 7 successful calls
        assert failure_count == 3  # 3 failed calls (every 3rd)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_and_retry_logic(self, mock_bridge_connector):
        """Test timeout and retry logic across the bridge."""
        wrapper = RevitAPIWrapper(config={"retry_count": 3, "timeout": 1.0})
        wrapper._bridge = mock_bridge_connector
        wrapper._connected = True

        call_attempts = 0

        async def mock_call_with_retries(method, params, timeout=None):
            nonlocal call_attempts
            call_attempts += 1

            # Succeed on 3rd attempt
            if call_attempts < 3:
                raise TimeoutError("Simulated timeout")

            return json.dumps(
                {"attempt": call_attempts, "result": "success after retries"}
            )

        mock_bridge_connector.CallAsync.side_effect = mock_call_with_retries

        # Call should eventually succeed after retries
        result = await wrapper.call_api("RetryTest", {})

        assert result["attempt"] == 3
        assert result["result"] == "success after retries"
        assert call_attempts == 3


@pytest.mark.integration
@pytest.mark.slow
class TestBridgeMemoryManagement:
    """Test memory management across the bridge."""

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_large_operations(self, memory_leak_detector):
        """Test memory cleanup after large bridge operations."""
        memory_leak_detector.start()

        # Mock large data operations
        with patch("revitpy.api.wrapper.BridgeConnector") as mock_connector:
            mock_bridge = MagicMock()
            mock_bridge.IsConnected = True

            # Mock large response data (10MB per call)
            large_data = "x" * (10 * 1024 * 1024)
            mock_bridge.CallAsync = AsyncMock(
                return_value=json.dumps(
                    {"large_data": large_data, "size": len(large_data)}
                )
            )

            mock_connector.return_value.connect.return_value = mock_bridge

            wrapper = RevitAPIWrapper()
            await wrapper.connect()

            # Perform multiple large operations
            for i in range(10):
                result = await wrapper.call_api("GetLargeDataSet", {"iteration": i})
                assert result["size"] == len(large_data)

                # Force garbage collection between operations
                import gc

                gc.collect()

        # Check for memory leaks
        memory_stats = memory_leak_detector.check()

        # Memory should not grow significantly (less than 50MB total)
        assert memory_stats["memory_increase_mb"] < 50
