This directory holds the `Processor` classes for transforming raw EDINET document data into structured formats.

## Purpose
To handle processing of documents from EDINET API, extracting meaningful data from CSV files within ZIP archives.

## Architecture

**Static Method Design**: All processors use static methods without instance variables. This functional approach ensures:
- No persistent state between processing calls
- Clear data flow through explicit parameters
- Better testability and predictability
- Logical alignment with document processing as a transformation operation

## Input Processing Flow

1. **ZIP File Processing**: 
   - File paths for ZIP files (`BaseProcessor.process_zip_file()`)
   - Raw bytes data for ZIP files (`BaseProcessor.process_zip_bytes()`)
   - Directory of ZIP files (`BaseProcessor.process_zip_directory()`)

2. **Data Extraction**:
   - Extract CSV files from ZIP archives
   - Skip auditor reports (jpaud* files)
   - Combine all CSV records into a single list
   - Pass combined data to appropriate processor

3. **Document Type Dispatch**:
   - Map document type codes to specific processor classes
   - Fallback to `GenericReportProcessor` for unsupported types

## Output Structure

Returns `StructuredDocData` (dict) with standardized format:
```python
{
    "doc_id": "string",
    "doc_type_code": "string", 
    "edinet_code": "string",
    "company_name_ja": "string",
    "key_facts": {...},           # Document-specific metrics
    "financial_tables": [...],    # Extracted financial data tables
    "text_blocks": [...]          # Narrative content blocks
}
```

## Processor Classes

### BaseProcessor
- **Abstract base class** providing common functionality
- **Static helper methods**:
  - `get_value_by_id(all_records, element_id, context_filter=None)`: Find specific XBRL element values
  - `get_records_by_id(all_records, element_id)`: Get all records for an element
  - `get_all_text_blocks(all_records)`: Extract text content blocks
  - `_get_common_metadata(all_records, doc_id, doc_type_code)`: Extract standard metadata

### Specialized Processors
- **SemiAnnualReportProcessor** (type 160): Financial metrics, tables, management analysis
- **ExtraordinaryReportProcessor** (type 180): Corporate actions, decisions, M&A events  
- **GenericReportProcessor**: Fallback for unsupported document types

## Implementation Guidelines

### Creating New Processors

1. **Inherit from BaseProcessor**:
   ```python
   class NewReportProcessor(BaseProcessor):
   ```

2. **Implement static process method**:
   ```python
   @staticmethod
   def process(
       all_records: list[dict[str, Any]],
       doc_id: str,
       doc_type_code: str,
   ) -> StructuredDocData | None:
   ```

3. **Use static helper methods**:
   ```python
   # Get common metadata
   structured_data = NewReportProcessor._get_common_metadata(
       all_records, doc_id, doc_type_code
   )
   
   # Extract specific values
   value = NewReportProcessor.get_value_by_id(
       all_records, "xbrl:ElementId", context_filter="Current"
   )
   
   # Get all text blocks
   text_blocks = NewReportProcessor.get_all_text_blocks(all_records)
   ```

4. **Register in BaseProcessor**:
   - Add to `processor_map` in `process_structured_data_from_raw_csv()`
   - Import the new processor class in the method

### Key Principles
- **No instance variables** - Pass all data as parameters
- **Static methods only** - Processors are pure functions
- **Explicit data flow** - All dependencies passed as arguments
- **Consistent output format** - Follow StructuredDocData schema
- **Error handling** - Use ErrorContext for graceful failure handling