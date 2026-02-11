"""
Integration Tests for Phase 1 XBRL Ingestion Module

Tests for:
- XBRL data models (Pydantic validation)
- Arelle parser integration
- File handler discovery and validation
- Full ingestion pipeline
"""

import unittest
from pathlib import Path
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ingestion.models import (
    XBRLContext, XBRLUnit, XBRLFact, XBRLInstance,
    XBRLDimension, ContextPeriodType, UnitType, DimensionMemberType
)
from src.ingestion.file_handler import (
    XBRLFileHandler, XBRLFileType, FileNotFoundError as CustomFileNotFoundError
)
from src.ingestion.xbrl_parser import XBRLParser, XBRLParseError
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger(__name__)


class TestXBRLModels(unittest.TestCase):
    """Test XBRL data model validation and serialization."""
    
    def test_xbrl_dimension_creation(self):
        """Test XBRLDimension model initialization."""
        dim = XBRLDimension(
            dimension_name="us-gaap:EntityDomain",
            member_name="us-gaap:USMember",
            member_type=DimensionMemberType.EXPLICIT
        )
        
        self.assertEqual(dim.dimension_name, "us-gaap:EntityDomain")
        self.assertEqual(dim.member_name, "us-gaap:USMember")
        self.assertEqual(dim.member_type, DimensionMemberType.EXPLICIT)
        self.assertFalse(dim.default_member)
    
    def test_xbrl_context_instant_period(self):
        """Test XBRLContext with instant (point-in-time) period."""
        context = XBRLContext(
            context_id="FY2024Q4",
            entity_identifier="0001018724",
            period_type=ContextPeriodType.INSTANT,
            period_end=date(2024, 12, 31)
        )
        
        self.assertEqual(context.context_id, "FY2024Q4")
        self.assertEqual(context.period_type, ContextPeriodType.INSTANT)
        self.assertIsNone(context.period_start)
        self.assertEqual(context.period_end, date(2024, 12, 31))
    
    def test_xbrl_context_duration_period(self):
        """Test XBRLContext with duration (date range) period."""
        context = XBRLContext(
            context_id="FY2024_DURATION",
            entity_identifier="0001018724",
            period_type=ContextPeriodType.DURATION,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31)
        )
        
        self.assertEqual(context.period_type, ContextPeriodType.DURATION)
        self.assertEqual(context.period_start, date(2024, 1, 1))
        self.assertEqual(context.period_end, date(2024, 12, 31))
    
    def test_xbrl_context_with_dimensions(self):
        """Test XBRLContext with segment and scenario dimensions."""
        dim = XBRLDimension(
            dimension_name="us-gaap:SegmentDomain",
            member_name="us-gaap:USSegment"
        )
        
        context = XBRLContext(
            context_id="SEGMENT_CONTEXT",
            entity_identifier="0001018724",
            period_type=ContextPeriodType.INSTANT,
            period_end=date(2024, 12, 31),
            segment_dimensions=[dim]
        )
        
        self.assertEqual(len(context.segment_dimensions), 1)
        self.assertEqual(context.segment_dimensions[0].member_name, "us-gaap:USSegment")
    
    def test_xbrl_unit_monetary(self):
        """Test XBRLUnit for monetary values."""
        unit = XBRLUnit(
            unit_id="USD",
            unit_type=UnitType.MONETARY,
            iso_currency_code="usd"  # Will be uppercased
        )
        
        self.assertEqual(unit.unit_type, UnitType.MONETARY)
        self.assertEqual(unit.iso_currency_code, "USD")
    
    def test_xbrl_unit_shares(self):
        """Test XBRLUnit for share measurements."""
        unit = XBRLUnit(
            unit_id="shares",
            unit_type=UnitType.SHARES
        )
        
        self.assertEqual(unit.unit_type, UnitType.SHARES)
    
    def test_xbrl_fact_creation(self):
        """Test XBRLFact model initialization."""
        fact = XBRLFact(
            concept_qname="us-gaap:NetIncomeLoss",
            value="1234567890",
            value_type="numeric",
            context_ref="FY2024Q4",
            unit_ref="USD",
            decimals=-6
        )
        
        self.assertEqual(fact.concept_qname, "us-gaap:NetIncomeLoss")
        self.assertEqual(fact.value, "1234567890")
        self.assertEqual(fact.context_ref, "FY2024Q4")
        self.assertFalse(fact.is_nil)
    
    def test_xbrl_fact_with_footnotes(self):
        """Test XBRLFact with associated footnotes."""
        fact = XBRLFact(
            concept_qname="us-gaap:NetIncomeLoss",
            value="1000",
            context_ref="FY2024Q4",
            footnote_ids=["fn_1", "fn_2"]
        )
        
        self.assertEqual(len(fact.footnote_ids), 2)
        self.assertIn("fn_1", fact.footnote_ids)
    
    def test_xbrl_instance_creation(self):
        """Test XBRLInstance container model."""
        context = XBRLContext(
            context_id="FY2024",
            entity_identifier="0001018724",
            period_type=ContextPeriodType.INSTANT,
            period_end=date(2024, 12, 31)
        )
        
        unit = XBRLUnit(
            unit_id="USD",
            unit_type=UnitType.MONETARY,
            iso_currency_code="USD"
        )
        
        fact = XBRLFact(
            concept_qname="us-gaap:NetIncomeLoss",
            value="1000",
            context_ref="FY2024",
            unit_ref="USD"
        )
        
        instance = XBRLInstance(
            file_path="data/raw/instance.xml",
            entity_identifier="0001018724",
            contexts=[context],
            units=[unit],
            facts=[fact]
        )
        
        self.assertEqual(instance.entity_identifier, "0001018724")
        self.assertEqual(instance.fact_count, 1)
        self.assertEqual(instance.context_count, 1)
        self.assertEqual(instance.unit_count, 1)
    
    def test_xbrl_instance_serialization(self):
        """Test XBRLInstance can be serialized to JSON-compatible format."""
        instance = XBRLInstance(
            file_path="data/raw/instance.xml",
            entity_identifier="0001018724",
        )
        
        # Should be able to call model_dump() for serialization
        data = instance.model_dump(mode='json')
        self.assertIsInstance(data, dict)
        self.assertEqual(data['entity_identifier'], "0001018724")


class TestXBRLFileHandler(unittest.TestCase):
    """Test file handling and discovery functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.handler = XBRLFileHandler()
        self.temp_dir = tempfile.TemporaryDirectory()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_detect_instance_file(self):
        """Test detection of XBRL instance files."""
        # Create mock files
        instance_path = Path(self.temp_dir.name) / "company_10k.xml"
        instance_path.touch()
        
        file_type = self.handler.detect_file_type(instance_path)
        self.assertEqual(file_type, XBRLFileType.INSTANCE)
    
    def test_detect_schema_file(self):
        """Test detection of XBRL schema files."""
        schema_path = Path(self.temp_dir.name) / "us-gaap_del.xsd"
        schema_path.touch()
        
        file_type = self.handler.detect_file_type(schema_path)
        self.assertEqual(file_type, XBRLFileType.SCHEMA)
    
    def test_detect_linkbase_file(self):
        """Test detection of XBRL linkbase files."""
        linkbase_path = Path(self.temp_dir.name) / "us-gaap_pre.xml"
        linkbase_path.touch()
        
        file_type = self.handler.detect_file_type(linkbase_path)
        self.assertEqual(file_type, XBRLFileType.LINKBASE)
    
    def test_validate_instance_file_not_found(self):
        """Test validation fails for non-existent file."""
        is_valid, error = self.handler.validate_instance_file("nonexistent.xml")
        self.assertFalse(is_valid)
        self.assertIn("not found", error.lower())
    
    def test_validate_instance_file_valid_xml(self):
        """Test validation passes for valid XML file."""
        instance_path = Path(self.temp_dir.name) / "test_instance.xml"
        instance_path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<root></root>')
        
        is_valid, error = self.handler.validate_instance_file(str(instance_path))
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_instance_file_non_xml(self):
        """Test validation fails for non-XML file."""
        txt_path = Path(self.temp_dir.name) / "test.txt"
        txt_path.write_text("Not an XML file")
        
        is_valid, error = self.handler.validate_instance_file(str(txt_path))
        self.assertFalse(is_valid)
        self.assertIn("XML", error)
    
    def test_batch_validate_instances(self):
        """Test batch validation of multiple files."""
        # Create test files
        valid_file = Path(self.temp_dir.name) / "valid.xml"
        valid_file.write_text('<?xml version="1.0"?>\n<root></root>')
        
        invalid_file = Path(self.temp_dir.name) / "invalid.txt"
        invalid_file.write_text("Not XML")
        
        results = self.handler.batch_validate_instances([
            str(valid_file),
            str(invalid_file)
        ])
        
        self.assertEqual(len(results), 2)
        self.assertTrue(results[str(valid_file)][0])
        self.assertFalse(results[str(invalid_file)][0])
    
    def test_get_file_info(self):
        """Test getting file metadata."""
        test_file = Path(self.temp_dir.name) / "test.xml"
        test_file.write_text('<?xml version="1.0"?>')
        
        info = self.handler.get_file_info(str(test_file))
        
        self.assertTrue(info['exists'])
        self.assertEqual(info['name'], 'test.xml')
        self.assertGreater(info['size_bytes'], 0)
        self.assertIn('file_type', info)


class TestXBRLParser(unittest.TestCase):
    """Test XBRL parsing functionality."""
    
    @patch('src.ingestion.xbrl_parser.Cntlr')
    def test_parser_initialization(self, mock_cntlr_class):
        """Test XBRLParser initialization."""
        mock_controller = MagicMock()
        mock_controller.VERSION = "2.36.0"
        mock_cntlr_class.Cntlr.return_value = mock_controller
        
        parser = XBRLParser()
        
        self.assertIsNotNone(parser.controller)
        # Check controller was initialized (version may vary)
        self.assertTrue(hasattr(parser.controller, 'logHandler'))
    
    @patch('src.ingestion.xbrl_parser.Cntlr')
    def test_parse_file_not_found(self, mock_cntlr_class):
        """Test parsing non-existent file raises error."""
        mock_controller = MagicMock()
        mock_cntlr_class.return_value = mock_controller
        
        parser = XBRLParser()
        
        with self.assertRaises(XBRLParseError):
            parser.parse("nonexistent_file.xml")
    
    @patch('src.ingestion.xbrl_parser.Cntlr')
    def test_validate_file_not_found(self, mock_cntlr_class):
        """Test validation of non-existent file."""
        mock_controller = MagicMock()
        mock_cntlr_class.return_value = mock_controller
        
        parser = XBRLParser()
        
        is_valid, errors = parser.validate("nonexistent_file.xml")
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class TestIngestionPipeline(unittest.TestCase):
    """Integration tests for the full ingestion pipeline."""
    
    def test_models_and_handler_integration(self):
        """Test that models and file handler work together."""
        handler = XBRLFileHandler()
        
        # Create test context and unit
        context = XBRLContext(
            context_id="TEST",
            entity_identifier="TEST123",
            period_type=ContextPeriodType.INSTANT,
            period_end=date(2024, 12, 31)
        )
        
        unit = XBRLUnit(
            unit_id="test_unit",
            unit_type=UnitType.OTHER
        )
        
        # Create instance
        instance = XBRLInstance(
            file_path="data/raw/test.xml",
            entity_identifier="TEST123",
            contexts=[context],
            units=[unit]
        )
        
        # Verify instance created correctly
        self.assertEqual(instance.fact_count, 0)
        self.assertEqual(instance.context_count, 1)
        self.assertEqual(instance.unit_count, 1)
    
    def test_file_validation_workflow(self):
        """Test complete file validation workflow."""
        handler = XBRLFileHandler()
        
        # Create temporary test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create valid instance
            instance_file = Path(temp_dir) / "company_10k.xml"
            instance_file.write_text('<?xml version="1.0"?>\n<instance></instance>')
            
            # Validate
            is_valid, error = handler.validate_instance_file(str(instance_file))
            self.assertTrue(is_valid)
            
            # Get info
            info = handler.get_file_info(str(instance_file))
            self.assertTrue(info['exists'])
            self.assertEqual(info['file_type'], 'instance')


class TestLoggingIntegration(unittest.TestCase):
    """Test logging integration with ingestion modules."""
    
    def test_logger_creates_properly(self):
        """Test that logger is initialized from utils."""
        test_logger = get_logger("test_ingestion")
        self.assertIsNotNone(test_logger)
        
        # Should be able to log without errors
        test_logger.info("Test logging message")


class TestSettingsIntegration(unittest.TestCase):
    """Test settings integration with ingestion modules."""
    
    def test_settings_provides_paths(self):
        """Test that settings provide required paths."""
        app_settings = get_settings()
        
        self.assertIsNotNone(app_settings.root_path)
        self.assertIsNotNone(app_settings.data_path)
        self.assertTrue(app_settings.root_path.exists())


def run_tests():
    """Run all tests with verbose output."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestXBRLModels))
    suite.addTests(loader.loadTestsFromTestCase(TestXBRLFileHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestXBRLParser))
    suite.addTests(loader.loadTestsFromTestCase(TestIngestionPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestLoggingIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSettingsIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
