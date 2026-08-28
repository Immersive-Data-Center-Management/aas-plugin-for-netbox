"""
Pytest configuration and fixtures for unit tests.

This file is automatically discovered by pytest and provides shared fixtures
and configuration for all tests in this directory.
"""
import sys
import pytest
from unittest.mock import MagicMock

# Create mock dcim module and Device model for patching
# This allows @patch('dcim.models.Device') to work without requiring NetBox
mock_dcim = MagicMock()
mock_dcim_models = MagicMock()
mock_dcim.models = mock_dcim_models

# Add the mock to sys.modules so patches can find it
sys.modules['dcim'] = mock_dcim
sys.modules['dcim.models'] = mock_dcim_models
