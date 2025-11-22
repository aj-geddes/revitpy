"""
Comprehensive test suite for the RevitPy-PyRevit interoperability bridge.

This test suite validates all bridge functionality including:
- Core bridge components
- Communication protocols
- Data serialization/deserialization
- PyRevit integration
- RevitPy analysis handlers
- Complete workflow testing
"""

import logging
import os
import sys
from pathlib import Path

# Add bridge module to path for testing
bridge_path = Path(__file__).parent.parent
sys.path.insert(0, str(bridge_path))

# Configure test logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bridge_tests.log")],
)

# Test configuration
TEST_CONFIG = {
    "use_mock_revit": True,  # Use mock objects instead of actual Revit
    "test_data_dir": Path(__file__).parent / "test_data",
    "temp_dir": Path(__file__).parent / "temp",
    "timeout_seconds": 30,
    "max_test_elements": 100,
}

# Create test directories
TEST_CONFIG["test_data_dir"].mkdir(exist_ok=True)
TEST_CONFIG["temp_dir"].mkdir(exist_ok=True)

__all__ = ["TEST_CONFIG"]
