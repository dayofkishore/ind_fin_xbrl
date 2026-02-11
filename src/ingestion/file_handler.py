"""
File Handling Utilities for XBRL Processing

This module provides utilities for:
- Locating XBRL instance and taxonomy files
- Validating file paths and formats
- Detecting document types (XBRL instance vs schema/taxonomy)
- Batch file discovery with filtering
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from enum import Enum

from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class XBRLFileType(str, Enum):
    """Types of XBRL-related files."""
    INSTANCE = "instance"  # XBRL instance document (.xml)
    SCHEMA = "schema"      # XBRL taxonomy schema (.xsd)
    LINKBASE = "linkbase"  # Linkbase (.xml or .xsd)
    STYLESHEET = "stylesheet"  # Presentation/calculation stylesheet
    OTHER = "other"        # Other files


class FileNotFoundError(Exception):
    """Raised when expected file cannot be found."""
    pass


class InvalidFileError(Exception):
    """Raised when file format or content is invalid."""
    pass


class XBRLFileHandler:
    """
    Handles XBRL file discovery, validation, and path resolution.
    
    Example:
        >>> handler = XBRLFileHandler()
        >>> instances = handler.find_instances("data/raw/")
        >>> print(f"Found {len(instances)} XBRL instance files")
    """
    
    # Standard XBRL file patterns
    INSTANCE_EXTENSIONS = {'.xml'}
    SCHEMA_EXTENSIONS = {'.xsd'}
    LINKBASE_EXTENSIONS = {'.xml', '.xsd'}
    
    # Common XBRL directory names
    TAXONOMY_DIRS = {
        'taxonomy', 'schemas', 'linkbases', 'gl', 'us-gaap-std',
        'ifrs-gl', 'esef', 'wg', 'dqc_rules'
    }
    
    # Filename patterns indicating file type
    INSTANCE_INDICATORS = {
        '_', '-instance', '_10k', '_10q', '_8k', '_sc13',
        'exhibit', 'balance', 'income'
    }
    
    SCHEMA_INDICATORS = {
        '_del.xsd', '_pre.xsd', '_cal.xsd', '_def.xsd', '_lab.xsd',
        '_ref.xsd', '-schema.xsd', '.xsd'
    }
    
    def __init__(self):
        """Initialize file handler."""
        self.raw_data_path = settings.data_path / "raw"
        self.processed_data_path = settings.data_path / "processed"
        self.artifact_path = settings.data_path / "artifacts"
        logger.info(f"File handler initialized with root: {settings.data_path}")
    
    def find_instances(
        self,
        directory: Optional[str] = None,
        recursive: bool = True,
        pattern: Optional[str] = None
    ) -> List[Path]:
        """
        Find all XBRL instance files in a directory.
        
        Args:
            directory: Directory to search (defaults to data/raw/)
            recursive: Whether to search subdirectories
            pattern: Optional glob pattern to match filenames
            
        Returns:
            List of Path objects for instance files
        """
        search_dir = Path(directory or self.raw_data_path)
        
        if not search_dir.exists():
            logger.warning(f"Search directory does not exist: {search_dir}")
            return []
        
        logger.debug(f"Searching for instances in {search_dir} (recursive={recursive})")
        
        instances = []
        glob_pattern = f"**/*.xml" if recursive else "*.xml"
        
        for file_path in search_dir.glob(glob_pattern):
            # Filter out taxonomy/schema files
            if self._is_instance_file(file_path):
                instances.append(file_path)
                logger.debug(f"Found instance: {file_path.name}")
        
        if pattern:
            instances = [f for f in instances if pattern.lower() in f.name.lower()]
        
        logger.info(f"Found {len(instances)} instance file(s)")
        return instances
    
    def find_schemas(
        self,
        directory: Optional[str] = None,
        recursive: bool = True
    ) -> List[Path]:
        """
        Find all XBRL schema files in a directory.
        
        Args:
            directory: Directory to search (defaults to data/raw/)
            recursive: Whether to search subdirectories
            
        Returns:
            List of Path objects for schema files
        """
        search_dir = Path(directory or self.raw_data_path)
        
        if not search_dir.exists():
            logger.warning(f"Search directory does not exist: {search_dir}")
            return []
        
        logger.debug(f"Searching for schemas in {search_dir} (recursive={recursive})")
        
        schemas = []
        glob_pattern = f"**/*.xsd" if recursive else "*.xsd"
        
        for file_path in search_dir.glob(glob_pattern):
            schemas.append(file_path)
            logger.debug(f"Found schema: {file_path.name}")
        
        logger.info(f"Found {len(schemas)} schema file(s)")
        return schemas
    
    def find_all_xbrl_files(
        self,
        directory: Optional[str] = None,
        recursive: bool = True
    ) -> Dict[XBRLFileType, List[Path]]:
        """
        Find all XBRL-related files in a directory, organized by type.
        
        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
            
        Returns:
            Dictionary mapping file types to lists of paths
        """
        search_dir = Path(directory or self.raw_data_path)
        
        result = {
            XBRLFileType.INSTANCE: [],
            XBRLFileType.SCHEMA: [],
            XBRLFileType.LINKBASE: [],
            XBRLFileType.STYLESHEET: [],
            XBRLFileType.OTHER: [],
        }
        
        if not search_dir.exists():
            return result
        
        glob_pattern = f"**/*" if recursive else "*"
        
        for file_path in search_dir.glob(glob_pattern):
            if not file_path.is_file():
                continue
            
            if file_path.suffix not in {'.xml', '.xsd', '.css'}:
                continue
            
            file_type = self.detect_file_type(file_path)
            result[file_type].append(file_path)
        
        return result
    
    def detect_file_type(self, file_path: Path) -> XBRLFileType:
        """
        Detect the type of XBRL file.
        
        Args:
            file_path: Path to file to analyze
            
        Returns:
            XBRLFileType enum value
        """
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        
        name_lower = file_path.name.lower()
        suffix = file_path.suffix.lower()
        
        # Check by extension first
        if suffix == '.xsd':
            return XBRLFileType.SCHEMA
        
        if suffix == '.css':
            return XBRLFileType.STYLESHEET
        
        if suffix != '.xml':
            return XBRLFileType.OTHER
        
        # For .xml files, check content hints
        if 'linkbase' in name_lower or '-' in name_lower:
            if any(indicator in name_lower for indicator in
                   {'_del', '_pre', '_cal', '_def', '_lab', '_ref'}):
                return XBRLFileType.LINKBASE
        
        if self._is_instance_file(file_path):
            return XBRLFileType.INSTANCE
        
        # Default for .xml
        return XBRLFileType.OTHER
    
    def _is_instance_file(self, file_path: Path) -> bool:
        """
        Determine if a file is likely an XBRL instance document.
        
        Uses heuristics since full validation requires XML parsing.
        """
        name_lower = file_path.name.lower()
        
        # Check positive indicators
        for indicator in self.INSTANCE_INDICATORS:
            if indicator.lower() in name_lower:
                return True
        
        # Exclude known schema/taxonomy patterns
        for indicator in self.SCHEMA_INDICATORS:
            if indicator.lower() in name_lower:
                return False
        
        # Exclude taxonomy directories
        for part in file_path.parts:
            if part.lower() in self.TAXONOMY_DIRS:
                return False
        
        # Default: if it's an .xml file and not excluded, treat as instance
        return file_path.suffix.lower() == '.xml'
    
    def validate_instance_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that a file exists and appears to be a valid XBRL instance.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(file_path)
        
        if not path.exists():
            error = f"File not found: {file_path}"
            logger.warning(error)
            return False, error
        
        if not path.is_file():
            error = f"Path is not a file: {file_path}"
            logger.warning(error)
            return False, error
        
        if path.suffix.lower() != '.xml':
            error = f"File is not an XML file: {file_path}"
            logger.warning(error)
            return False, error
        
        try:
            # Basic XML validation - check if file is readable
            with open(path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if not first_line.startswith('<?xml'):
                    logger.warning(f"File does not appear to be XML: {file_path}")
                    # Not necessarily invalid - some files omit declaration
        except Exception as e:
            error = f"Cannot read file: {str(e)}"
            logger.warning(error)
            return False, error
        
        logger.debug(f"File validation passed: {file_path}")
        return True, None
    
    def resolve_path(self, file_path: str, base_dir: Optional[str] = None) -> Path:
        """
        Resolve a file path, handling relative and absolute paths.
        
        Args:
            file_path: Path to resolve (relative or absolute)
            base_dir: Base directory for relative paths (defaults to data/raw/)
            
        Returns:
            Resolved absolute Path object
            
        Raises:
            FileNotFoundError: If path cannot be resolved
        """
        path = Path(file_path)
        
        # If already absolute, return as-is
        if path.is_absolute():
            if path.exists():
                return path
            raise FileNotFoundError(f"Absolute path does not exist: {file_path}")
        
        # Try relative to base directory
        base = Path(base_dir or self.raw_data_path)
        resolved = base / path
        
        if resolved.exists():
            logger.debug(f"Resolved path: {resolved}")
            return resolved
        
        # Try relative to workspace root
        workspace_path = settings.root_path / path
        if workspace_path.exists():
            logger.debug(f"Resolved path: {workspace_path}")
            return workspace_path
        
        raise FileNotFoundError(
            f"Cannot resolve path: {file_path} "
            f"(tried {base} and {settings.root_path})"
        )
    
    def get_file_info(self, file_path: str) -> Dict[str, any]:
        """
        Get metadata about a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file metadata
        """
        path = Path(file_path)
        
        if not path.exists():
            return {"exists": False}
        
        try:
            stat_info = path.stat()
            return {
                "exists": True,
                "path": str(path.absolute()),
                "name": path.name,
                "size_bytes": stat_info.st_size,
                "file_type": self.detect_file_type(path).value,
                "extension": path.suffix,
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "modified": stat_info.st_mtime,
            }
        except Exception as e:
            logger.error(f"Error getting file info: {str(e)}")
            return {"exists": True, "error": str(e)}
    
    def batch_validate_instances(self, file_paths: List[str]) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Validate multiple instance files at once.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            Dictionary mapping file paths to (is_valid, error) tuples
        """
        results = {}
        for file_path in file_paths:
            is_valid, error = self.validate_instance_file(file_path)
            results[file_path] = (is_valid, error)
        
        valid_count = sum(1 for valid, _ in results.values() if valid)
        logger.info(f"Batch validation: {valid_count}/{len(file_paths)} files valid")
        
        return results


if __name__ == "__main__":
    """Example usage of file handler."""
    
    handler = XBRLFileHandler()
    
    # Find all instances
    instances = handler.find_instances(recursive=True)
    print(f"Found {len(instances)} instances")
    
    # Find all schemas
    schemas = handler.find_schemas(recursive=True)
    print(f"Found {len(schemas)} schemas")
    
    # Find all XBRL files by type
    all_files = handler.find_all_xbrl_files(recursive=True)
    for file_type, paths in all_files.items():
        if paths:
            print(f"{file_type.value}: {len(paths)} files")
    
    # Validate a specific file
    # valid, error = handler.validate_instance_file("data/raw/test.xml")
    # print(f"Validation result: {valid}, Error: {error}")
