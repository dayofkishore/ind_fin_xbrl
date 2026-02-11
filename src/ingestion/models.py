"""
XBRL Domain Models for Phase 1 Ingestion

This module defines Pydantic v2 models for core XBRL entities:
- XBRLContext: Period and scenario information
- XBRLUnit: Measurement units (monetary, shares, pure)
- XBRLDimension: Dimensional information for facts
- XBRLFact: Individual data facts from XBRL instance documents
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional, Dict
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict


class DimensionMemberType(str, Enum):
    """Types of dimension members in XBRL dimensional reporting."""
    EXPLICIT = "explicit"
    TYPED = "typed"


class ContextPeriodType(str, Enum):
    """Period types for XBRL contexts."""
    INSTANT = "instant"
    DURATION = "duration"


class UnitType(str, Enum):
    """Standard XBRL unit measurement types."""
    MONETARY = "monetary"
    SHARES = "shares"
    PURE = "pure"
    PERCENT = "percent"
    OTHER = "other"


class XBRLDimension(BaseModel):
    """
    Represents a dimension in XBRL dimensional reporting.
    
    Dimensions are used to add non-monetary qualitative context to facts
    (e.g., business segments, geographic regions, product lines).
    """
    
    dimension_name: str = Field(
        ...,
        description="QName of the dimension (e.g., 'us-gaap:EntityDomain')"
    )
    member_name: str = Field(
        ...,
        description="QName of the member value (e.g., 'us-gaap:USMember')"
    )
    member_type: DimensionMemberType = Field(
        default=DimensionMemberType.EXPLICIT,
        description="Type of dimension member (explicit or typed)"
    )
    default_member: bool = Field(
        default=False,
        description="Whether this is the default member for the dimension"
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class XBRLContext(BaseModel):
    """
    Represents a context in an XBRL instance document.
    
    Contexts define the period, scenario, and entity information
    for one or more facts.
    """
    
    context_id: str = Field(
        ...,
        description="Unique identifier for this context (e.g., 'FY2024Q4')"
    )
    entity_identifier: str = Field(
        ...,
        description="Entity identifier (typically CIK, LEI, or ticker)"
    )
    entity_scheme: str = Field(
        default="http://www.sec.gov/CIK",
        description="Scheme URI for entity identifier"
    )
    period_type: ContextPeriodType = Field(
        ...,
        description="Whether this is an instant (point-in-time) or duration (period) context"
    )
    period_start: Optional[date] = Field(
        default=None,
        description="Start date for duration periods"
    )
    period_end: Optional[date] = Field(
        default=None,
        description="End date for instant or duration periods"
    )
    segment_dimensions: List[XBRLDimension] = Field(
        default_factory=list,
        description="Dimensional qualifiers for this context (segment)"
    )
    scenario_dimensions: List[XBRLDimension] = Field(
        default_factory=list,
        description="Dimensional qualifiers for scenarios"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when context was parsed"
    )

    @field_validator('period_start', 'period_end')
    @classmethod
    def validate_dates(cls, v: Optional[date]) -> Optional[date]:
        """Ensure dates are valid XBRL date format."""
        if v and isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError as e:
                raise ValueError(f"Invalid date format: {v}") from e
        return v

    model_config = ConfigDict(str_strip_whitespace=True)


class XBRLUnit(BaseModel):
    """
    Represents a unit of measurement in an XBRL instance document.
    
    Units define how numeric facts are measured (currency, shares, percentages, etc.).
    """
    
    unit_id: str = Field(
        ...,
        description="Unique identifier for this unit (e.g., 'USD', 'shares')"
    )
    unit_type: UnitType = Field(
        ...,
        description="Category of measurement unit"
    )
    iso_currency_code: Optional[str] = Field(
        default=None,
        description="ISO 4217 currency code if monetary (e.g., 'USD', 'EUR')"
    )
    numerator_iso_code: Optional[str] = Field(
        default=None,
        description="Numerator for composite units (e.g., 'USD' for USD/share)"
    )
    denominator_iso_code: Optional[str] = Field(
        default=None,
        description="Denominator for composite units (e.g., 'xbrli:shares' for USD/share)"
    )
    display_label: Optional[str] = Field(
        default=None,
        description="Human-readable label for this unit"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when unit was parsed"
    )

    @field_validator('iso_currency_code', 'numerator_iso_code', 'denominator_iso_code')
    @classmethod
    def validate_iso_codes(cls, v: Optional[str]) -> Optional[str]:
        """Ensure ISO codes are uppercase."""
        if v:
            return v.upper()
        return v

    model_config = ConfigDict(str_strip_whitespace=True)


class XBRLFact(BaseModel):
    """
    Represents a single fact in an XBRL instance document.
    
    A fact is a data point with a concept, value, context, and optional unit.
    """
    
    fact_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this fact"
    )
    concept_qname: str = Field(
        ...,
        description="Qualified name of the concept (e.g., 'us-gaap:NetIncomeLoss')"
    )
    concept_label: Optional[str] = Field(
        default=None,
        description="Human-readable label for the concept"
    )
    value: Optional[Any] = Field(
        default=None,
        description="The actual fact value (numeric, text, date, or None for footnotes)"
    )
    value_type: str = Field(
        default="string",
        description="Data type of the value (numeric, nonNumeric, etc.)"
    )
    context_ref: str = Field(
        ...,
        description="Reference to the context providing period/scenario info"
    )
    unit_ref: Optional[str] = Field(
        default=None,
        description="Reference to the unit of measurement (for numeric facts)"
    )
    decimals: Optional[int] = Field(
        default=None,
        description="Decimal places for numeric facts (or 'INF' for unbounded)"
    )
    sign_override: Optional[str] = Field(
        default=None,
        description="Sign override indicator in XBRL (e.g., '-1' for negation)"
    )
    footnote_ids: List[str] = Field(
        default_factory=list,
        description="References to associated footnotes"
    )
    is_nil: bool = Field(
        default=False,
        description="Whether this fact has a nil (missing) value"
    )
    xml_attributes: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional XML attributes from the source document"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when fact was parsed"
    )

    @field_validator('value')
    @classmethod
    def validate_value(cls, v: Optional[Any]) -> Optional[Any]:
        """Ensure value is properly typed (can be extended in subclasses)."""
        if isinstance(v, str):
            return v.strip()
        return v

    model_config = ConfigDict(str_strip_whitespace=True)


class XBRLInstance(BaseModel):
    """
    Represents a parsed XBRL instance document.
    
    This is a container for all contexts, units, and facts from a single
    XBRL submission.
    """
    
    instance_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this instance"
    )
    file_path: str = Field(
        ...,
        description="Full path to the source XBRL instance file"
    )
    entity_identifier: str = Field(
        ...,
        description="Entity identifier from the document"
    )
    fiscal_period_focus: Optional[str] = Field(
        default=None,
        description="Fiscal period focus (e.g., 'FY2024Q4', 'FY2024')"
    )
    contexts: List[XBRLContext] = Field(
        default_factory=list,
        description="All contexts defined in this instance"
    )
    units: List[XBRLUnit] = Field(
        default_factory=list,
        description="All units defined in this instance"
    )
    facts: List[XBRLFact] = Field(
        default_factory=list,
        description="All facts in this instance"
    )
    schema_ref: Optional[str] = Field(
        default=None,
        description="Reference to the schema(s) this instance conforms to"
    )
    namespace_declaration: Dict[str, str] = Field(
        default_factory=dict,
        description="XML namespace declarations from the instance"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="Any validation errors encountered during parsing"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when instance was parsed"
    )

    @property
    def fact_count(self) -> int:
        """Get total number of facts in this instance."""
        return len(self.facts)

    @property
    def context_count(self) -> int:
        """Get total number of contexts in this instance."""
        return len(self.contexts)

    @property
    def unit_count(self) -> int:
        """Get total number of units in this instance."""
        return len(self.units)

    model_config = ConfigDict(str_strip_whitespace=True)


if __name__ == "__main__":
    """Example usage of XBRL data models."""
    
    # Create a context
    context = XBRLContext(
        context_id="FY2024Q4",
        entity_identifier="0001018724",
        period_type=ContextPeriodType.INSTANT,
        period_end=date(2024, 12, 31),
    )
    
    # Create a unit
    unit = XBRLUnit(
        unit_id="USD",
        unit_type=UnitType.MONETARY,
        iso_currency_code="USD",
    )
    
    # Create a fact
    fact = XBRLFact(
        concept_qname="us-gaap:NetIncomeLoss",
        value="1234567890",
        value_type="numeric",
        context_ref="FY2024Q4",
        unit_ref="USD",
        decimals=-6,
    )
    
    # Create an instance
    instance = XBRLInstance(
        file_path="data/raw/my_instance.xml",
        entity_identifier="0001018724",
        fiscal_period_focus="FY2024Q4",
        contexts=[context],
        units=[unit],
        facts=[fact],
    )
    
    print(f"Instance created: {instance.instance_id}")
    print(f"Fact count: {instance.fact_count}")
    print(f"Context count: {instance.context_count}")
    print(f"Unit count: {instance.unit_count}")
