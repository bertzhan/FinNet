# Quarantine System Fixes

## Issues Fixed

### 1. QuarantineRecord Model Mismatch
**Problem:**
- The `QuarantineRecord` model only had basic fields (`id`, `document_id`, `reason`, `details`, `quarantined_at`, `released_at`, `released_by`)
- Code was trying to use expanded fields (`source_type`, `doc_type`, `original_path`, `quarantine_path`, `failure_stage`, `failure_reason`, `failure_details`, `status`, etc.)
- This caused: `'source_type' is an invalid keyword argument for QuarantineRecord`

**Solution:**
- Updated `QuarantineRecord` model in `src/storage/metadata/models.py` to include all required fields
- Modified `document_id` to be nullable (supports cases where document isn't in database yet)
- Added proper indexes for efficient querying
- Removed deprecated fields that don't exist in database

**Updated Fields:**
```python
class QuarantineRecord(Base):
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # References (nullable to support pre-database-insert failures)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=True)

    # Source information
    source_type = Column(String(50), nullable=False)  # a_share/hk_stock/us_stock
    doc_type = Column(String(50), nullable=False)

    # Path information
    original_path = Column(String(500), nullable=False)
    quarantine_path = Column(String(500), nullable=False)

    # Failure information
    failure_stage = Column(String(50), nullable=False)  # ingestion_failed/validation_failed/content_failed
    failure_reason = Column(String(500), nullable=False)
    failure_details = Column(Text)

    # Status and resolution
    status = Column(String(50), default='pending')  # pending/processing/resolved/discarded
    handler = Column(String(100))
    resolution = Column(Text)

    # Timestamps
    quarantine_time = Column(DateTime, nullable=False, default=func.now())
    resolution_time = Column(DateTime)

    # Metadata
    extra_metadata = Column(JSON)
```

### 2. MinIO Metadata Encoding Error
**Problem:**
- MinIO S3 metadata only supports US-ASCII characters
- Error messages in Chinese (e.g., "缺少数据库ID") were being added to MinIO metadata
- This caused: `unsupported metadata value 缺少数据库ID; only US-ASCII encoded characters are supported`

**Solution:**
- Modified `quarantine_manager.py` to only include ASCII-safe values in MinIO metadata
- Chinese error messages are now stored in the PostgreSQL database instead
- MinIO metadata now only contains: `original_path`, `failure_stage`, `quarantine_time`, `document_id` (if exists)

**Changes in `src/storage/metadata/quarantine_manager.py`:**
```python
# Before (caused encoding error)
metadata={
    "original_path": original_path,
    "failure_stage": failure_stage,
    "failure_reason": failure_reason,  # Contains Chinese!
    "quarantine_time": datetime.now().isoformat()
}

# After (ASCII-safe)
metadata = {
    "original_path": original_path,
    "failure_stage": failure_stage,
    "quarantine_time": datetime.now().isoformat()
}
if document_id:
    metadata["document_id"] = str(document_id)
```

## Database Migration

### SQL Script
Created `scripts/update_quarantine_table.sql` to add new columns and indexes.

### Python Script
Created `scripts/update_quarantine_table.py` to execute the migration.

**How to run:**
```bash
python scripts/update_quarantine_table.py
```

## Verification

### Test Results
```bash
# Database record created successfully
✅ Latest quarantine record found:
   - id: 1
   - document_id: None
   - source_type: a_share
   - doc_type: ipo_prospectus
   - failure_reason: 缺少数据库ID  # Chinese stored in DB (OK)
   - failure_details: 文档记录未成功创建到数据库
   - status: pending
   - quarantine_time: 2026-01-16 10:46:44.852744

# MinIO metadata contains only ASCII
✅ Object metadata:
   - x-amz-meta-failure_stage: validation_failed
   - x-amz-meta-original_path: bronze/a_share/ipo_prospectus/300552/300552.pdf
   - x-amz-meta-quarantine_time: 2026-01-16T18:46:44.737201
   # No Chinese characters! ✅
```

## Files Modified

1. **Model Definition:**
   - `src/storage/metadata/models.py` - Updated `QuarantineRecord` class

2. **Quarantine Logic:**
   - `src/storage/metadata/quarantine_manager.py` - Fixed MinIO metadata encoding

3. **Migration Scripts:**
   - `scripts/update_quarantine_table.sql` - Database schema changes
   - `scripts/update_quarantine_table.py` - Migration execution script

## Next Steps

The quarantine system should now work correctly:
1. ✅ Database schema matches code expectations
2. ✅ MinIO metadata uses ASCII-only values
3. ✅ Chinese error messages stored in PostgreSQL
4. ✅ Supports documents without database IDs (validation failures)

You can now run the IPO crawl job again without encountering these errors.
