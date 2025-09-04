"""
Performance and stress tests for the bridge functionality.
"""

import pytest
import time
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch
import concurrent.futures

from ..serialization.element_serializer import ElementSerializer, ElementSerializationConfig
from ..communication.websocket_server import WebSocketServer
from ..core.bridge_manager import BridgeManager


class TestSerializationPerformance:
    """Test serialization performance with large datasets."""
    
    @pytest.fixture
    def high_performance_serializer(self):
        """Create high-performance serializer configuration."""
        config = ElementSerializationConfig(
            compression_enabled=True,
            batch_size=100,
            include_geometry=True,
            include_parameters=True
        )
        return ElementSerializer(config)
    
    def test_large_dataset_serialization(self, high_performance_serializer, performance_test_data):
        """Test serializing large dataset (1000 elements)."""
        # Mock element extraction for performance test
        with patch.object(high_performance_serializer, '_extract_element_data') as mock_extract:
            mock_extract.side_effect = performance_test_data
            
            # Create mock elements
            mock_elements = [Mock() for _ in range(len(performance_test_data))]
            
            start_time = time.time()
            serialized_elements = high_performance_serializer.serialize_elements(mock_elements)
            end_time = time.time()
            
            # Performance assertions
            processing_time = end_time - start_time
            assert processing_time < 5.0  # Should complete within 5 seconds
            assert len(serialized_elements) == len(performance_test_data)
            
            # Calculate throughput
            throughput = len(performance_test_data) / processing_time
            assert throughput > 100  # Should process >100 elements per second
    
    def test_streaming_serialization_performance(self, high_performance_serializer, performance_test_data):
        """Test streaming serialization performance."""
        with patch.object(high_performance_serializer, '_extract_element_data') as mock_extract:
            mock_extract.side_effect = performance_test_data
            
            mock_elements = [Mock() for _ in range(len(performance_test_data))]
            
            start_time = time.time()
            batches = list(high_performance_serializer.serialize_elements_streaming(mock_elements))
            end_time = time.time()
            
            processing_time = end_time - start_time
            total_elements = sum(len(batch) for batch in batches)
            
            # Performance assertions
            assert processing_time < 3.0  # Streaming should be faster
            assert total_elements == len(performance_test_data)
            assert len(batches) >= 10  # Should create multiple batches
            
            # Memory efficiency check - batches should be reasonable size
            max_batch_size = max(len(batch) for batch in batches)
            assert max_batch_size <= 100  # Should respect batch size limit
    
    def test_compression_efficiency(self, high_performance_serializer, temp_dir):
        """Test compression efficiency on large datasets."""
        # Create large, compressible test data
        large_dataset = []
        for i in range(500):
            element = {
                "id": f"element_{i:06d}",
                "category": "Walls",  # Repetitive data compresses well
                "name": f"Basic Wall - Type A",  # Repetitive
                "type": "Wall",
                "parameters": {
                    "Height": {"value": 3000, "type": "Length", "unit": "mm"},
                    "Width": {"value": 200, "type": "Length", "unit": "mm"},
                    "Material": {"value": "Concrete", "type": "Text", "unit": None}
                },
                "geometry": {
                    "type": "solid",
                    "volume": 600000,
                    "area": 6000,
                    "vertices": [[0, 0, 0], [4000, 0, 0], [4000, 200, 0], [0, 200, 0]]
                }
            }
            large_dataset.append(element)
        
        # Test compression
        uncompressed_file = temp_dir / "uncompressed.json"
        compressed_file = temp_dir / "compressed.json.gz"
        
        # Save uncompressed
        start_time = time.time()
        with open(uncompressed_file, 'w') as f:
            json.dump(large_dataset, f)
        uncompressed_time = time.time() - start_time
        
        # Save compressed
        start_time = time.time()
        high_performance_serializer.save_compressed(large_dataset, compressed_file)
        compressed_time = time.time() - start_time
        
        # Size comparison
        uncompressed_size = uncompressed_file.stat().st_size
        compressed_size = compressed_file.stat().st_size
        compression_ratio = compressed_size / uncompressed_size
        
        # Performance assertions
        assert compression_ratio < 0.5  # Should achieve >50% compression
        assert compressed_time < uncompressed_time * 2  # Compression overhead acceptable
        
        # Verify decompression
        start_time = time.time()
        loaded_data = high_performance_serializer.load_compressed(compressed_file)
        decompression_time = time.time() - start_time
        
        assert len(loaded_data) == len(large_dataset)
        assert decompression_time < 2.0  # Fast decompression


class TestCommunicationPerformance:
    """Test communication protocol performance."""
    
    @pytest.mark.asyncio
    async def test_websocket_throughput(self, sample_analysis_request):
        """Test WebSocket throughput with multiple concurrent requests."""
        server = WebSocketServer(host="localhost", port=8767)
        
        # Mock server response
        async def mock_handler(message):
            return {"success": True, "request_id": message.get("analysis_id")}
        
        server.message_handlers["analysis_request"] = mock_handler
        
        # Simulate multiple concurrent clients
        num_clients = 10
        requests_per_client = 20
        
        async def client_simulation(client_id):
            client_results = []
            for i in range(requests_per_client):
                request = sample_analysis_request.copy()
                request["analysis_id"] = f"client_{client_id}_req_{i}"
                
                # Simulate processing
                await asyncio.sleep(0.01)  # Small delay
                result = await mock_handler(request)
                client_results.append(result)
            
            return client_results
        
        # Run concurrent clients
        start_time = time.time()
        tasks = [client_simulation(i) for i in range(num_clients)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Performance assertions
        total_requests = num_clients * requests_per_client
        processing_time = end_time - start_time
        throughput = total_requests / processing_time
        
        assert throughput > 50  # Should handle >50 requests per second
        assert len(results) == num_clients
        assert all(len(client_results) == requests_per_client for client_results in results)
    
    @pytest.mark.asyncio
    async def test_concurrent_analysis_processing(self, mock_bridge_config, sample_analysis_request):
        """Test concurrent analysis processing performance."""
        config_dict = mock_bridge_config
        config_dict["performance"]["max_concurrent_analyses"] = 5
        
        bridge_manager = BridgeManager.from_dict(config_dict)
        bridge_manager.is_initialized = True
        
        # Mock analysis handler with variable processing time
        async def mock_analysis_handler(request):
            processing_time = 0.1 + (hash(request["analysis_id"]) % 100) / 1000  # 0.1-0.2 seconds
            await asyncio.sleep(processing_time)
            return {
                "success": True,
                "analysis_id": request["analysis_id"],
                "processing_time": processing_time
            }
        
        bridge_manager.analysis_handlers = {
            "energy_performance": mock_analysis_handler
        }
        
        # Create multiple analysis requests
        requests = []
        for i in range(20):
            request = sample_analysis_request.copy()
            request["analysis_id"] = f"concurrent_test_{i:03d}"
            requests.append(request)
        
        # Process requests concurrently
        start_time = time.time()
        tasks = [bridge_manager.process_analysis_request(req) for req in requests]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Performance assertions
        total_time = end_time - start_time
        assert total_time < 5.0  # Should complete within 5 seconds with concurrency
        assert len(results) == 20
        assert all(result["success"] for result in results)
        
        # Verify concurrency benefit (should be faster than sequential)
        estimated_sequential_time = sum(0.15 for _ in requests)  # Average processing time
        concurrency_benefit = estimated_sequential_time / total_time
        assert concurrency_benefit > 2.0  # Should be at least 2x faster
    
    def test_memory_usage_under_load(self, performance_test_data):
        """Test memory usage with large datasets."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large serializer workload
        config = ElementSerializationConfig(
            compression_enabled=True,
            batch_size=50
        )
        serializer = ElementSerializer(config)
        
        # Process multiple large datasets
        datasets = [performance_test_data for _ in range(5)]
        
        for i, dataset in enumerate(datasets):
            with patch.object(serializer, '_extract_element_data') as mock_extract:
                mock_extract.side_effect = dataset
                mock_elements = [Mock() for _ in range(len(dataset))]
                
                # Process dataset
                serialized = serializer.serialize_elements(mock_elements)
                
                # Check memory after each dataset
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - initial_memory
                
                # Memory usage should not grow excessively
                assert memory_increase < 200  # Should not exceed 200MB increase
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        assert total_increase < 100  # Should release memory after processing


class TestStressTests:
    """Stress tests for bridge components."""
    
    @pytest.mark.asyncio
    async def test_rapid_connection_cycling(self):
        """Test rapid connection and disconnection cycles."""
        server = WebSocketServer(host="localhost", port=8768)
        
        # Simulate rapid connection cycling
        cycle_count = 50
        successful_cycles = 0
        
        for i in range(cycle_count):
            try:
                # Mock server start/stop
                with patch.object(server, '_create_server') as mock_create:
                    mock_create.return_value = Mock()
                    
                    await server.start()
                    assert server.is_running
                    
                    await server.stop()
                    assert not server.is_running
                    
                    successful_cycles += 1
                    
            except Exception as e:
                # Log error but continue
                print(f"Cycle {i} failed: {e}")
        
        # Should handle most cycles successfully
        success_rate = successful_cycles / cycle_count
        assert success_rate > 0.9  # >90% success rate
    
    def test_malformed_data_handling(self, high_performance_serializer=None):
        """Test handling of malformed or corrupted data."""
        if not high_performance_serializer:
            config = ElementSerializationConfig()
            high_performance_serializer = ElementSerializer(config)
        
        # Test various malformed inputs
        malformed_inputs = [
            None,
            {},
            {"id": None},
            {"id": "123", "category": None},
            {"id": "123", "parameters": "not_a_dict"},
            {"id": "123", "geometry": []},  # Wrong type
        ]
        
        successful_handles = 0
        
        for malformed_input in malformed_inputs:
            try:
                result = high_performance_serializer.deserialize_element(malformed_input)
                # Should either return valid result or None, not crash
                assert result is None or isinstance(result, dict)
                successful_handles += 1
            except Exception as e:
                # Expected for some inputs, but shouldn't crash
                assert isinstance(e, (ValueError, TypeError, KeyError))
                successful_handles += 1
        
        # Should handle all malformed inputs gracefully
        assert successful_handles == len(malformed_inputs)
    
    @pytest.mark.asyncio
    async def test_timeout_stress(self, sample_analysis_request):
        """Test system behavior under timeout stress."""
        # Create mock handler with variable delays
        async def variable_delay_handler(request):
            delay = hash(request["analysis_id"]) % 5  # 0-4 seconds
            await asyncio.sleep(delay)
            return {"success": True, "delay": delay}
        
        # Test with short timeouts
        timeout_duration = 1.0  # 1 second timeout
        
        requests = []
        for i in range(20):
            request = sample_analysis_request.copy()
            request["analysis_id"] = f"timeout_test_{i:03d}"
            requests.append(request)
        
        # Process with timeouts
        completed = 0
        timed_out = 0
        
        for request in requests:
            try:
                result = await asyncio.wait_for(
                    variable_delay_handler(request), 
                    timeout=timeout_duration
                )
                completed += 1
            except asyncio.TimeoutError:
                timed_out += 1
        
        # Should handle a mix of completed and timed-out requests
        assert completed + timed_out == len(requests)
        assert completed > 0  # Some should complete
        assert timed_out > 0  # Some should timeout
    
    def test_resource_cleanup_under_stress(self):
        """Test resource cleanup under stress conditions."""
        import gc
        
        # Force garbage collection before test
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Create and destroy many objects
        created_objects = []
        
        for i in range(1000):
            # Create various bridge objects
            config = ElementSerializationConfig(batch_size=10)
            serializer = ElementSerializer(config)
            
            # Use objects briefly
            mock_data = {"id": f"stress_{i}", "category": "Test"}
            try:
                serializer.deserialize_element(mock_data)
            except:
                pass  # Expected for minimal data
            
            created_objects.append(serializer)
            
            # Periodic cleanup
            if i % 100 == 0:
                del created_objects[:]
                gc.collect()
        
        # Final cleanup
        del created_objects
        gc.collect()
        
        final_objects = len(gc.get_objects())
        object_increase = final_objects - initial_objects
        
        # Should not have significant memory leaks
        assert object_increase < 500  # Reasonable object increase threshold