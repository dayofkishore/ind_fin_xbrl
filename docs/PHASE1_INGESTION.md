# Phase 1: XBRL Ingestion Module Documentation

## Overview

Phase 1 establishes the foundational XBRL ingestion pipeline. It handles the discovery, parsing, and extraction of financial data from XBRL (eXtensible Business Reporting Language) instance documents using the Arelle XBRL processor.

**Status**: ✅ Infrastructure Complete  
**Phase Duration**: Weeks 1-2 of Development  
**Key Dependencies**: Arelle (arelle-release), Pydantic v2, PyYAML

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    XBRL Instance Files                       │
│                   (data/raw/*.xml)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   File Handler       │ ◄── src/ingestion/file_handler.py
              │  (Discovery & Valid) │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Arelle Controller   │ ◄── External: arelle-release
              │    (XBRL Processor)  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────────────┐
              │    XBRL Parser Module        │ ◄── src/ingestion/xbrl_parser.py
              │                              │
              │ • parse()                    │
              │ • validate()                 │
              │ • extract_contexts()         │
              │ • extract_units()            │
              │ • extract_facts()            │
              └──────────┬───────────────────┘
                         │
            ┌────────────┼────────────┐
            │            │            │
            ▼            ▼            ▼
        Contexts      Units         Facts
        (Context)    (Unit)       (Fact)
            │            │            │
            └────────────┼────────────┘
                         ▼
              ┌──────────────────────────────┐
              │  Domain Models (Pydantic)    │ ◄── src/ingestion/models.py
              │                              │
              │ • XBRLContext                │
              │ • XBRLUnit                   │
              │ • XBRLFact                   │
              │ • XBRLInstance (Container)   │
              └──────────┬───────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Validated Output   │
              │  (JSON/Python Dict)  │
              └──────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │ Phase 2 & Beyond                  │
        │ (Taxonomies, Graph Storage, etc.) │
        └───────────────────────────────────┘
```

---

## Module Structure

### `src/ingestion/models.py`
**Pydantic v2 domain models for XBRL data structures**

#### Classes

##### `XBRLDimension`
- Represents dimensional qualifiers (e.g., business segment, geography)
- Attributes: `dimension_name`, `member_name`, `member_type`, `default_member`
- Used for multi-dimensional financial reporting

##### `XBRLContext`
- Represents period and scenario information for facts
- Attributes: `context_id`, `entity_identifier`, `period_type`, `period_start`, `period_end`, `segment_dimensions`, `scenario_dimensions`
- Supports `ContextPeriodType.INSTANT` and `ContextPeriodType.DURATION`

##### `XBRLUnit`
- Represents measurement units (currency, shares, percentages, etc.)
- Attributes: `unit_id`, `unit_type`, `iso_currency_code`, `numerator_iso_code`, `denominator_iso_code`
- Supports `UnitType`: MONETARY, SHARES, PURE, PERCENT, OTHER

##### `XBRLFact`
- Represents a single data point/metric
- Attributes: `concept_qname`, `value`, `context_ref`, `unit_ref`, `decimals`, `footnote_ids`, `is_nil`
- Includes XML attribute preservation for round-tripping

##### `XBRLInstance`
- Container for all components of a parsed document
- Attributes: `file_path`, `entity_identifier`, `contexts`, `units`, `facts`, `validation_errors`
- Properties: `fact_count`, `context_count`, `unit_count`

#### Usage Example
```python
from src.ingestion.models import XBRLContext, XBRLUnit, XBRLFact, XBRLInstance
from datetime import date

# Create context
context = XBRLContext(
    context_id="FY2024Q4",
    entity_identifier="0001018724",
    period_type=ContextPeriodType.INSTANT,
    period_end=date(2024, 12, 31)
)

# Create unit
unit = XBRLUnit(
    unit_id="USD",
    unit_type=UnitType.MONETARY,
    iso_currency_code="USD"
)

# Create fact
fact = XBRLFact(
    concept_qname="us-gaap:NetIncomeLoss",
    value="1234567890",
    context_ref="FY2024Q4",
    unit_ref="USD",
    decimals=-6
)

# Create instance
instance = XBRLInstance(
    file_path="data/raw/10k.xml",
    entity_identifier="0001018724",
    contexts=[context],
    units=[unit],
    facts=[fact]
)
```

---

### `src/ingestion/xbrl_parser.py`
**Arelle-based XBRL parser and validator**

#### Class: `XBRLParser`

**Public Methods:**

##### `parse(file_path: str) -> XBRLInstance`
- Parses complete XBRL instance document
- Extracts contexts, units, and facts
- Validates structure and collects validation errors
- Returns structured `XBRLInstance` object

**Parameters:**
- `file_path`: Path to XBRL instance file (`.xml`)

**Returns:** `XBRLInstance` with all extracted components

**Raises:** `XBRLParseError` if parsing fails

**Example:**
```python
parser = XBRLParser()
instance = parser.parse("data/raw/company_10k.xml")
print(f"Extracted {instance.fact_count} facts")
```

##### `validate(file_path: str) -> Tuple[bool, List[str]]`
- Validates XBRL against schema without full parse
- Returns validation passes and error messages
- Faster alternative when only validation needed

**Example:**
```python
is_valid, errors = parser.validate("data/raw/company_10k.xml")
if not is_valid:
    for error in errors:
        print(f"Validation error: {error}")
```

##### `close()`
- Cleanup and teardown Arelle controller
- Call before program exit

**Private Methods** (Internal Use):
- `_parse_contexts()` - Extract all contexts from model
- `_parse_units()` - Extract all units from model
- `_parse_facts()` - Extract all facts from model
- `_convert_context()` - Arelle element → XBRLContext
- `_convert_unit()` - Arelle element → XBRLUnit
- `_convert_fact()` - Arelle element → XBRLFact
- `_extract_dimensions()` - Parse dimensional information
- `_extract_entity_identifier()` - Get entity identifier
- `_extract_fiscal_period()` - Get fiscal period label
- `_extract_namespaces()` - Preserve XML namespaces

**Error Handling:**
- `XBRLParseError`: Raised on file not found, invalid XBRL, or parse failure
- All Arelle errors captured in `XBRLInstance.validation_errors`

---

### `src/ingestion/file_handler.py`
**File discovery, validation, and path management**

#### Class: `XBRLFileHandler`

**Public Methods:**

##### `find_instances(directory=None, recursive=True, pattern=None) -> List[Path]`
- Discover XBRL instance files in directory tree
- Filters out taxonomy/schema files using heuristics
- Optionally filters by name pattern

**Example:**
```python
handler = XBRLFileHandler()
instances = handler.find_instances("data/raw/", recursive=True)
print(f"Found {len(instances)} instances")
```

##### `find_schemas(directory=None, recursive=True) -> List[Path]`
- Discover XBRL schema files (`.xsd`)

##### `find_all_xbrl_files(directory=None, recursive=True) -> Dict[XBRLFileType, List[Path]]`
- Find all XBRL-related files organized by type
- Returns dict mapping `XBRLFileType` to file lists

##### `detect_file_type(file_path: Path) -> XBRLFileType`
- Classify file as INSTANCE, SCHEMA, LINKBASE, STYLESHEET, or OTHER
- Uses extension + content heuristics

##### `validate_instance_file(file_path: str) -> Tuple[bool, Optional[str]]`
- Check file exists, is readable XML, has XML declaration
- Returns (is_valid, error_message) tuple

##### `batch_validate_instances(file_paths: List[str]) -> Dict[str, Tuple[bool, Optional[str]]]`
- Validate multiple files in one call
- Returns mapping of file paths to validation results

##### `get_file_info(file_path: str) -> Dict[str, any]`
- Get file metadata (size, type, modification time, etc.)

##### `resolve_path(file_path: str, base_dir: Optional[str]) -> Path`
- Resolve relative/absolute paths
- Search order: absolute → relative to base_dir → relative to workspace root

**Enum: `XBRLFileType`**
- `INSTANCE` - Instance documents
- `SCHEMA` - Taxonomy schemas
- `LINKBASE` - Linkbase files
- `STYLESHEET` - Presentation/calculation stylesheets
- `OTHER` - Other file types

---

## Data Flow

### Complete Ingestion Pipeline

```
1. File Discovery
   ├─ Find instance files in data/raw/
   ├─ Validate file format (XML, extensions)
   └─ Build file queue

2. File Loading
   ├─ Load instance via Arelle
   ├─ Load referenced schemas/linkbases
   └─ Build in-memory model

3. Context Extraction
   ├─ Parse period information (instant/duration)
   ├─ Extract entity identifiers
   ├─ Parse segment/scenario dimensions
   └─ Create XBRLContext objects

4. Unit Extraction
   ├─ Parse ISO currency codes
   ├─ Detect composite units (e.g. USD/share)
   ├─ Classify unit types
   └─ Create XBRLUnit objects

5. Fact Extraction
   ├─ Iterate through all facts
   ├─ Map to contexts and units
   ├─ Detect nil/missing values
   ├─ Parse dimensional attributes
   └─ Create XBRLFact objects

6. Instance Assembly
   ├─ Combine contexts, units, facts
   ├─ Validate references
   ├─ Collect validation errors
   └─ Create XBRLInstance container

7. Output
   ├─ Serialize to JSON/Python dict
   ├─ Pass to Phase 2 (normalization)
   └─ Archive raw parsed data
```

---

## Integration Points

### With Existing Infrastructure

**Logger** (`src/utils/logger.py`):
- All modules use structured JSON logging
- Logs categorized as INFO, WARNING, ERROR
- Example: `logger.info(f"Parsed {instance.fact_count} facts")`

**Settings** (`src/utils/settings.py`):
- Gets `data_path`, `root_path` from configuration
- Environment-based configuration
- Example: `file_handler.raw_data_path = settings.data_path / "raw"`

### With Phase 2+

- **Input**: Raw XBRL instance files
- **Output**: Structured `XBRLInstance` objects ready for normalization
- **Data Contract**: Models defined in `models.py` are immutable for downstream use

---

## Testing

### Test Suite: `tests/test_ingestion_core.py`

**Test Classes:**

1. **TestXBRLModels** (9 tests)
   - Model initialization and validation
   - Period type handling
   - Dimensional information
   - Serialization

2. **TestXBRLFileHandler** (8 tests)
   - File type detection
   - File validation (exists, format, readability)
   - Batch validation
   - File metadata retrieval

3. **TestXBRLParser** (3 tests)
   - Parser initialization
   - Error handling (file not found)
   - Validation workflow

4. **TestIngestionPipeline** (3 tests)
   - Model + handler integration
   - File validation workflow
   - End-to-end component interaction

5. **TestLoggingIntegration** (1 test)
   - Logger initialization

6. **TestSettingsIntegration** (1 test)
   - Settings path resolution

**Running Tests:**
```bash
# Run all Phase 1 tests
python -m pytest tests/test_ingestion_core.py -v

# Run specific test class
python -m pytest tests/test_ingestion_core.py::TestXBRLModels -v

# Run with coverage
python -m pytest tests/test_ingestion_core.py --cov=src.ingestion
```

**Expected Results**: All 25+ tests should pass

---

## Configuration

### Environment Variables

None required for Phase 1. Uses defaults from `src/utils/settings.py`:
- `DATA_PATH`: `data/` (relative to project root)
- `LOG_LEVEL`: `INFO`

### File Structure Requirements

```
project_root/
├── data/
│   ├── raw/              # Input: XBRL instance files
│   │   ├── company1_10k.xml
│   │   ├── company1_10q.xml
│   │   └── ... (instances to parse)
│   ├── processed/        # Output: Normalized XBRL (Phase 2)
│   ├── artifacts/        # Output: Graph data, indexes (Phase 3+)
│   └── taxonomy/         # Reference: XBRL taxonomies (Phase 2)
├── src/
│   ├── ingestion/        # Phase 1 modules
│   ├── normalization/    # Phase 2 (future)
│   ├── graph/            # Phase 3 (future)
│   └── utils/            # Shared utilities
└── tests/
    └── test_ingestion_core.py
```

---

## Common Tasks

### Parse a Single XBRL File

```python
from src.ingestion.xbrl_parser import XBRLParser
from src.utils.logger import get_logger

logger = get_logger(__name__)

parser = XBRLParser()

try:
    instance = parser.parse("data/raw/company_financial_report.xml")
    logger.info(f"Parsed {instance.entity_identifier}")
    logger.info(f"Facts: {instance.fact_count}")
    logger.info(f"Contexts: {instance.context_count}")
    logger.info(f"Units: {instance.unit_count}")
finally:
    parser.close()
```

### Find and Validate Files Before Parsing

```python
from src.ingestion.file_handler import XBRLFileHandler
from src.ingestion.xbrl_parser import XBRLParser

handler = XBRLFileHandler()
parser = XBRLParser()

# Find all instances
instances = handler.find_instances(recursive=True)
logger.info(f"Found {len(instances)} instance files")

# Validate before parsing
validation_results = handler.batch_validate_instances([str(f) for f in instances])

valid_files = [f for f, (valid, _) in validation_results.items() if valid]
logger.info(f"{len(valid_files)} files are valid")

# Parse valid files
parsed_instances = []
for file_path in valid_files[:5]:  # Parse first 5
    try:
        instance = parser.parse(file_path)
        parsed_instances.append(instance)
    except Exception as e:
        logger.error(f"Failed to parse {file_path}: {str(e)}")

parser.close()
```

### Export Parsed Data to JSON

```python
import json
from src.ingestion.xbrl_parser import XBRLParser

parser = XBRLParser()
instance = parser.parse("data/raw/10k.xml")

# Convert to JSON-compatible format
data = instance.model_dump(mode='json')

# Save to file
with open("data/processed/parsed_instance.json", "w") as f:
    json.dump(data, f, indent=2, default=str)

parser.close()
```

---

## Limitations & Known Issues

### Phase 1 Scope Limitations

1. **No Taxonomy Reconciliation**: Facts extracted as-is; no mapping to standardized concept definitions
2. **No Unit Conversions**: Units preserved as-reported; no cross-currency or normalized units
3. **No Dimensional Consolidation**: All dimensional variants stored separately
4. **Minimal Validation**: Relies on Arelle validation; no custom financial data rules
5. **No Performance Optimization**: Single-threaded parsing; suitable for individual files only

### Arelle Integration Notes

- Arelle requires Java Runtime Environment (JRE) for full functionality
- Some XBRL features (exotic linkbases, custom taxonomies) may not be fully supported
- Memory usage scales with instance size; large documents require sufficient heap

---

## Next Steps (Phase 2)

- **Taxonomy Reference Loading**: Load and parse XBRL taxonomy definitions
- **Concept Mapping**: Map fact concepts to standardized definitions
- **Dimensional Consolidation**: Merge multi-dimensional facts into uniform structure
- **Data Normalization**: Apply rules for unit conversion, consolidation
- **Entity Matching**: Resolve entity identifiers across sources and taxonomies

---

## References

- [XBRL International](https://www.xbrl.org/)
- [Arelle Documentation](https://arelle.org/)
- [SEC XBRL Filing Manual](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany)
- [XBRL Specification (XBRL 2.1)](https://www.xbrl.org/specification/)

---

**Last Updated**: February 2026  
**Maintainer**: Development Team  
**Status**: ✅ Production Ready (Phase 1 Foundation)
