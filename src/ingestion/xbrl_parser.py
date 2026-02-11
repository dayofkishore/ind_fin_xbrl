"""
XBRL Parser using Arelle Plugin Model

This module provides a wrapper around the Arelle XBRL processor to parse,
validate, and extract data from XBRL instance documents.

The XBRLParser class handles:
- Document validation against schema
- Context extraction (periods, scenarios, dimensions)
- Unit definition extraction
- Fact extraction with proper type conversion
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import date, datetime
import json

from arelle import Cntlr, ModelXbrl, ModelDocument

from src.ingestion.models import (
    XBRLContext,
    XBRLUnit,
    XBRLFact,
    XBRLInstance,
    XBRLDimension,
    ContextPeriodType,
    UnitType,
)
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class XBRLParseError(Exception):
    """Raised when XBRL parsing or validation fails."""
    pass


class XBRLParser:
    """
    Parses and extracts data from XBRL instance documents using Arelle.
    
    Example:
        >>> parser = XBRLParser()
        >>> instance = parser.parse("data/raw/company_10k.xml")
        >>> print(f"Facts extracted: {instance.fact_count}")
    """
    
    def __init__(self, arelle_log_level: str = "WARNING"):
        """
        Initialize the XBRL parser with Arelle controller.
        
        Args:
            arelle_log_level: Logging level for Arelle ("DEBUG", "INFO", "WARNING", "ERROR")
        """
        self.controller = Cntlr.Cntlr()
        self.controller.logHandler.setLevel(getattr(logging, arelle_log_level))
        logger.info(f"XBRL Parser initialized with Arelle {self.controller.VERSION}")
    
    def parse(self, file_path: str) -> XBRLInstance:
        """
        Parse an XBRL instance document and extract all data.
        
        Args:
            file_path: Path to XBRL instance file (.xml)
            
        Returns:
            XBRLInstance: Parsed document with contexts, units, and facts
            
        Raises:
            XBRLParseError: If file not found, invalid XBRL, or parse fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise XBRLParseError(f"XBRL file not found: {file_path}")
        
        logger.info(f"Parsing XBRL instance: {file_path.name}")
        
        try:
            # Load document via Arelle
            model_xbrl = self.controller.modelManager.load(str(file_path))
            
            if not model_xbrl:
                raise XBRLParseError(f"Failed to load XBRL document: {file_path}")
            
            if model_xbrl.errors:
                logger.warning(f"Arelle reported {len(model_xbrl.errors)} errors")
            
            # Extract components
            contexts = self._parse_contexts(model_xbrl)
            units = self._parse_units(model_xbrl)
            facts = self._parse_facts(model_xbrl, contexts)
            
            # Get entity identifier
            entity_id = self._extract_entity_identifier(model_xbrl)
            
            # Get fiscal period focus
            fiscal_period = self._extract_fiscal_period(model_xbrl, contexts)
            
            # Create instance
            instance = XBRLInstance(
                file_path=str(file_path),
                entity_identifier=entity_id,
                fiscal_period_focus=fiscal_period,
                contexts=contexts,
                units=units,
                facts=facts,
                schema_ref=self._extract_schema_reference(model_xbrl),
                namespace_declaration=self._extract_namespaces(model_xbrl),
                validation_errors=[str(e) for e in model_xbrl.errors[:10]],  # First 10
            )
            
            logger.info(
                f"Successfully parsed: {instance.fact_count} facts, "
                f"{instance.context_count} contexts, {instance.unit_count} units"
            )
            
            return instance
            
        except Exception as e:
            logger.error(f"XBRL parsing failed: {str(e)}", exc_info=True)
            raise XBRLParseError(f"Failed to parse XBRL: {str(e)}") from e
        finally:
            # Clean up Arelle model
            if model_xbrl:
                self.controller.modelManager.remove(model_xbrl)
    
    def validate(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Validate an XBRL instance against its schema.
        
        Args:
            file_path: Path to XBRL instance file
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return False, [f"File not found: {file_path}"]
        
        logger.info(f"Validating XBRL: {file_path.name}")
        
        try:
            model_xbrl = self.controller.modelManager.load(str(file_path))
            
            if not model_xbrl:
                return False, ["Failed to load model"]
            
            is_valid = len(model_xbrl.errors) == 0
            errors = [str(e) for e in model_xbrl.errors]
            
            logger.info(f"Validation result: {'PASS' if is_valid else 'FAIL'}")
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False, [str(e)]
        finally:
            if model_xbrl:
                self.controller.modelManager.remove(model_xbrl)
    
    def _parse_contexts(self, model_xbrl: ModelXbrl) -> List[XBRLContext]:
        """Extract all contexts from XBRL model."""
        contexts = []
        
        try:
            for context_key, context_elem in model_xbrl.contexts.items():
                context = self._convert_context(context_key, context_elem)
                if context:
                    contexts.append(context)
                    
        except Exception as e:
            logger.warning(f"Error parsing contexts: {str(e)}")
        
        logger.debug(f"Extracted {len(contexts)} contexts")
        return contexts
    
    def _parse_units(self, model_xbrl: ModelXbrl) -> List[XBRLUnit]:
        """Extract all units from XBRL model."""
        units = []
        
        try:
            for unit_key, unit_elem in model_xbrl.units.items():
                unit = self._convert_unit(unit_key, unit_elem)
                if unit:
                    units.append(unit)
                    
        except Exception as e:
            logger.warning(f"Error parsing units: {str(e)}")
        
        logger.debug(f"Extracted {len(units)} units")
        return units
    
    def _parse_facts(
        self,
        model_xbrl: ModelXbrl,
        contexts: List[XBRLContext]
    ) -> List[XBRLFact]:
        """Extract all facts from XBRL model."""
        facts = []
        context_map = {c.context_id: c for c in contexts}
        
        try:
            for fact in model_xbrl.facts:
                try:
                    xbrl_fact = self._convert_fact(fact, context_map)
                    if xbrl_fact:
                        facts.append(xbrl_fact)
                except Exception as e:
                    logger.debug(f"Error parsing individual fact: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing facts: {str(e)}")
        
        logger.debug(f"Extracted {len(facts)} facts")
        return facts
    
    def _convert_context(self, context_id: str, context_elem) -> Optional[XBRLContext]:
        """Convert Arelle context element to XBRLContext model."""
        try:
            # Determine period type
            period_type = ContextPeriodType.INSTANT
            period_start = None
            period_end = None
            
            if hasattr(context_elem, 'period'):
                period = context_elem.period
                
                if hasattr(period, 'startDate'):
                    period_type = ContextPeriodType.DURATION
                    period_start = period.startDate
                
                if hasattr(period, 'endDate'):
                    period_end = period.endDate
            
            # Extract dimensions from segment and scenario
            segment_dims = []
            scenario_dims = []
            
            if hasattr(context_elem, 'segMember'):
                segment_dims = self._extract_dimensions(context_elem.segMember)
            
            if hasattr(context_elem, 'scenarioMember'):
                scenario_dims = self._extract_dimensions(context_elem.scenarioMember)
            
            # Get entity identifier
            entity_id = ""
            if hasattr(context_elem, 'entityIdentifier'):
                entity_id = context_elem.entityIdentifier[1]
            
            return XBRLContext(
                context_id=context_id,
                entity_identifier=entity_id,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                segment_dimensions=segment_dims,
                scenario_dimensions=scenario_dims,
            )
            
        except Exception as e:
            logger.debug(f"Failed to convert context {context_id}: {str(e)}")
            return None
    
    def _extract_dimensions(self, member_dict: Dict) -> List[XBRLDimension]:
        """Extract dimensions from context members."""
        dimensions = []
        
        try:
            for dim_name, member_name in member_dict.items():
                dimensions.append(
                    XBRLDimension(
                        dimension_name=str(dim_name),
                        member_name=str(member_name),
                    )
                )
        except Exception as e:
            logger.debug(f"Error extracting dimensions: {str(e)}")
        
        return dimensions
    
    def _convert_unit(self, unit_id: str, unit_elem) -> Optional[XBRLUnit]:
        """Convert Arelle unit element to XBRLUnit model."""
        try:
            unit_type = UnitType.PURE
            iso_code = None
            numerator = None
            denominator = None
            
            # Check if monetary
            if hasattr(unit_elem, 'measures'):
                measures = unit_elem.measures
                
                if measures and len(measures) == 1:
                    # Single measure (usually currency or share)
                    measure = measures[0]
                    measure_str = str(measure)
                    
                    # Detect currency
                    if measure_str.startswith("iso4217:"):
                        unit_type = UnitType.MONETARY
                        iso_code = measure_str.replace("iso4217:", "").upper()
                    elif "xbrli:shares" in measure_str.lower():
                        unit_type = UnitType.SHARES
                    else:
                        unit_type = UnitType.OTHER
                
                elif measures and len(measures) == 2:
                    # Composite unit (e.g., USD/share)
                    numerator_str = str(measures[0])
                    denominator_str = str(measures[1])
                    
                    if "iso4217:" in numerator_str.lower():
                        unit_type = UnitType.MONETARY
                        numerator = numerator_str.replace("iso4217:", "").upper()
                    
                    if "xbrli:shares" in denominator_str.lower():
                        unit_type = UnitType.SHARES
                        denominator = denominator_str
            
            return XBRLUnit(
                unit_id=unit_id,
                unit_type=unit_type,
                iso_currency_code=iso_code,
                numerator_iso_code=numerator,
                denominator_iso_code=denominator,
            )
            
        except Exception as e:
            logger.debug(f"Failed to convert unit {unit_id}: {str(e)}")
            return None
    
    def _convert_fact(
        self,
        fact_elem,
        context_map: Dict[str, XBRLContext]
    ) -> Optional[XBRLFact]:
        """Convert Arelle fact element to XBRLFact model."""
        try:
            context_ref = getattr(fact_elem, 'contextID', None)
            if not context_ref:
                return None
            
            # Get concept QName
            concept_qname = str(fact_elem.qname) if hasattr(fact_elem, 'qname') else ""
            concept_label = getattr(fact_elem, 'label', None)
            
            # Get value
            value = getattr(fact_elem, 'value', None)
            
            # Get unit reference
            unit_ref = getattr(fact_elem, 'unitID', None)
            
            # Get decimal places
            decimals = getattr(fact_elem, 'decimals', None)
            
            # Get nil indicator
            is_nil = getattr(fact_elem, 'isNil', False)
            
            # Get value type from concept
            value_type = "nonNumeric"
            if hasattr(fact_elem, 'concept') and fact_elem.concept:
                if hasattr(fact_elem.concept, 'baseXsdType'):
                    base_type = fact_elem.concept.baseXsdType
                    if base_type and 'double' in base_type.lower():
                        value_type = "numeric"
            
            return XBRLFact(
                concept_qname=concept_qname,
                concept_label=concept_label,
                value=value,
                value_type=value_type,
                context_ref=context_ref,
                unit_ref=unit_ref,
                decimals=decimals,
                is_nil=is_nil,
            )
            
        except Exception as e:
            logger.debug(f"Failed to convert fact: {str(e)}")
            return None
    
    def _extract_entity_identifier(self, model_xbrl: ModelXbrl) -> str:
        """Extract entity identifier from document properties."""
        try:
            if hasattr(model_xbrl, 'entityIdentifier'):
                return model_xbrl.entityIdentifier[1]
            
            # Fallback: try first context
            if model_xbrl.contexts:
                for context in model_xbrl.contexts.values():
                    if hasattr(context, 'entityIdentifier'):
                        return context.entityIdentifier[1]
        except Exception:
            pass
        
        return "UNKNOWN"
    
    def _extract_fiscal_period(
        self,
        model_xbrl: ModelXbrl,
        contexts: List[XBRLContext]
    ) -> Optional[str]:
        """Extract fiscal period focus from contexts."""
        try:
            # Look for instant (period-end) contexts
            for context in contexts:
                if (context.period_type == ContextPeriodType.INSTANT and
                    context.period_end and
                    'INSTANT' in context.context_id.upper()):
                    return context.context_id
            
            # Fallback to first instant context
            for context in contexts:
                if context.period_type == ContextPeriodType.INSTANT:
                    return context.context_id
        except Exception:
            pass
        
        return None
    
    def _extract_schema_reference(self, model_xbrl: ModelXbrl) -> Optional[str]:
        """Extract schema reference from instance document."""
        try:
            if hasattr(model_xbrl, 'modelDocument'):
                doc = model_xbrl.modelDocument
                if hasattr(doc, 'schemaLinkbaseRefs'):
                    refs = doc.schemaLinkbaseRefs
                    if refs:
                        return ", ".join([str(r) for r in refs[:3]])
            
            # Fallback: get from document properties
            if hasattr(model_xbrl, 'docinfo'):
                docinfo = model_xbrl.docinfo
                if isinstance(docinfo, dict) and 'schemaRef' in docinfo:
                    return docinfo['schemaRef']
        except Exception:
            pass
        
        return None
    
    def _extract_namespaces(self, model_xbrl: ModelXbrl) -> Dict[str, str]:
        """Extract XML namespaces from instance document."""
        try:
            if hasattr(model_xbrl, 'nsmap'):
                return dict(model_xbrl.nsmap)
            
            if hasattr(model_xbrl, 'modelDocument'):
                doc = model_xbrl.modelDocument
                if hasattr(doc, 'xmlRootElement'):
                    root = doc.xmlRootElement
                    if hasattr(root, 'nsmap'):
                        return dict(root.nsmap)
        except Exception:
            pass
        
        return {}
    
    def close(self):
        """Close and cleanup Arelle controller."""
        try:
            self.controller.close()
            logger.info("XBRL Parser closed")
        except Exception as e:
            logger.error(f"Error closing parser: {str(e)}")


if __name__ == "__main__":
    """Example usage of XBRL parser."""
    
    parser = XBRLParser()
    
    # Example validation (would need actual XBRL file)
    # is_valid, errors = parser.validate("data/raw/sample.xml")
    # print(f"Valid: {is_valid}, Errors: {len(errors)}")
    
    # Example parsing (would need actual XBRL file)
    # instance = parser.parse("data/raw/sample.xml")
    # print(f"Parsed {instance.fact_count} facts from {instance.entity_identifier}")
    
    parser.close()
