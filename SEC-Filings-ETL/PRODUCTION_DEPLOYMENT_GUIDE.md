# Production Deployment Guide - Minimal Byte Replacement Image Rewriter

## Quick Start

### Verify Setup
```bash
# Check storage configuration
python -c "from config.settings import settings; print('Storage:', settings.storage_root)"

# Check dataset size
find /Users/hao/Desktop/FINAI/sec_filings_data -name "*.html" ! -name "*.bak" | wc -l
```

### Test Mode (Dry Run)
```bash
# Preview changes without modifying files
python scripts/test_jsm_image_rewrite.py --exchange NASDAQ --sample 10 --dry-run
```

### Production Commands

#### 1. Single Company
```bash
# Test specific company (e.g., AAPL)
python scripts/test_jsm_image_rewrite.py --ticker AAPL

# Specific file
python scripts/test_jsm_image_rewrite.py --file /path/to/file.html
```

#### 2. Sample Testing
```bash
# Random sample of 50 NASDAQ files
python scripts/test_jsm_image_rewrite.py --exchange NASDAQ --sample 50

# Random sample of 100 NYSE files
python scripts/test_jsm_image_rewrite.py --exchange NYSE --sample 100
```

#### 3. Full Deployment
```bash
# All NASDAQ companies (26,734 files)
python scripts/test_jsm_image_rewrite.py --exchange NASDAQ

# All NYSE companies
python scripts/test_jsm_image_rewrite.py --exchange NYSE

# All exchanges (entire dataset)
python scripts/test_jsm_image_rewrite.py
```

## Pre-Deployment Checklist

- [ ] Verify storage root is accessible
- [ ] Check sufficient disk space (minimal impact, ~150 KB total)
- [ ] Ensure database is not locked
- [ ] Review test results from sample run
- [ ] Verify backup strategy (.bak files created automatically)

## Safety Features

### 1. Automatic Backups
Original files backed up as `.html.bak` before first modification.

### 2. Idempotent Operation
Safe to run multiple times - second run will detect no changes needed.

### 3. Atomic Writes
Files written atomically via temp files (no partial writes).

### 4. Validation Built-In
Each file automatically validated for:
- Encoding preservation
- Entity preservation
- iXBRL structure preservation

## Expected Results

### Sample Output
```
================================================================================
Image Rewrite Test - Minimal Byte Replacement
================================================================================
Found 100 HTML file(s)

Processing: IRON_2025_FY_27-02-2025.html
   Encoding: ASCII ✅
   Images: 35
   Size: +745 bytes
   Status: ✅ PASS

...

Summary
================================================================================
Files processed: 100
Images rewritten: 28
Total size delta: +595 bytes

✅ All files processed successfully
   Original files backed up with .bak extension
```

## Monitoring

### Key Metrics to Watch
1. **Files processed**: Should match expected count
2. **Images rewritten**: Typically 5-10% of files
3. **Size delta**: ~20 bytes per image (predictable)
4. **Errors**: Should be 0

### Success Indicators
- ✅ Encoding preserved (ASCII/UTF-8)
- ✅ Entities preserved (&#160;, &amp;, etc.)
- ✅ iXBRL preserved
- ✅ Size delta is minimal and predictable
- ✅ Second run shows 0 replacements (idempotent)

### Warning Signs
- ⚠️ Unexpected size increase (>50 bytes/image)
- ⚠️ Encoding changes detected
- ⚠️ Entity transformation detected
- ⚠️ Errors in processing

## Rollback Procedure

If issues detected:

```bash
# Restore original files from backups
cd /Users/hao/Desktop/FINAI/sec_filings_data
find . -name "*.html.bak" -exec sh -c 'cp "$1" "${1%.bak}"' _ {} \;

# Verify restoration
python scripts/test_jsm_image_rewrite.py --exchange NASDAQ --sample 10 --dry-run
```

## Performance Expectations

### Processing Speed
- **Small files** (<1 MB): ~50-100ms
- **Medium files** (1-5 MB): ~100-200ms
- **Large files** (>5 MB): ~200-500ms

### Dataset Estimates
- **100 files**: ~10-15 seconds
- **1,000 files**: ~2-3 minutes
- **10,000 files**: ~20-30 minutes
- **26,734 files (NASDAQ)**: ~45-60 minutes

## Troubleshooting

### Issue: "No HTML files found"
**Solution**: Check storage root path and exchange name
```bash
ls -la /Users/hao/Desktop/FINAI/sec_filings_data/NASDAQ
```

### Issue: "Permission denied"
**Solution**: Check file permissions
```bash
chmod u+w /path/to/file.html
```

### Issue: "File not found" for specific file
**Solution**: Use relative path from storage root or full path
```bash
# Use full path
python scripts/test_jsm_image_rewrite.py \
    --file /Users/hao/Desktop/FINAI/sec_filings_data/NASDAQ/AAPL/2025/AAPL_2025_FY_31-10-2025.html

# Or use --ticker and filename
python scripts/test_jsm_image_rewrite.py \
    --ticker AAPL \
    --file AAPL_2025_FY_31-10-2025.html
```

### Issue: Images not being mapped
**Solution**: Verify images exist with correct naming pattern
```bash
ls -la /path/to/company/2025/*image*.jpg
```

Expected pattern: `{TICKER}_{YEAR}_{TYPE}_{DATE}_image-001.jpg`

## Integration with Pipeline

### Standalone Usage (Current)
```python
from utils.minimal_image_rewrite import MinimalImageRewriter

rewriter = MinimalImageRewriter()
result = rewriter.rewrite_file(html_path)

if result['rewritten']:
    print(f"Rewrote {result['num_replacements']} images")
```

### Pipeline Integration (Future)
Add to filing download pipeline after HTML and images are downloaded:
```python
# After downloading HTML + images
html_path = download_filing(...)
image_paths = download_images(...)

# Rewrite image references
rewriter = MinimalImageRewriter()
rewriter.rewrite_file(html_path)
```

## Recommended Deployment Strategy

### Phase 1: Extended Validation (1-2 hours)
```bash
# Test 500 random NASDAQ files
python scripts/test_jsm_image_rewrite.py --exchange NASDAQ --sample 500

# Review results, verify all green
# Check backup files created
# Verify idempotency (run again, expect 0 changes)
```

### Phase 2: Full NASDAQ (1 hour)
```bash
# Process all NASDAQ
python scripts/test_jsm_image_rewrite.py --exchange NASDAQ

# Verify summary
# Spot-check 10 random files manually
```

### Phase 3: NYSE (1-2 hours)
```bash
# Process all NYSE
python scripts/test_jsm_image_rewrite.py --exchange NYSE

# Verify summary
```

### Phase 4: Other Exchanges (if any)
```bash
# Process remaining exchanges
python scripts/test_jsm_image_rewrite.py
```

## Validation Commands

### Verify Encoding Preserved
```bash
# Check first file in dataset
head -1 /Users/hao/Desktop/FINAI/sec_filings_data/NASDAQ/AAPL/2025/AAPL_2025_FY_31-10-2025.html

# Should show: <?xml version='1.0' encoding='ASCII'?>
```

### Verify Image References Rewritten
```bash
# Check for old pattern (should not exist after rewrite)
grep -n 'img[0-9]*_[0-9]*.jpg' /path/to/file.html

# Check for new pattern (should exist after rewrite)
grep -n './.*_image-[0-9]*.jpg' /path/to/file.html
```

### Verify Idempotency
```bash
# Run twice on same file
python scripts/test_jsm_image_rewrite.py --file /path/to/file.html
python scripts/test_jsm_image_rewrite.py --file /path/to/file.html

# Second run should show: "Replacements: 0"
```

## Support

### Log Files
Structured logs via structlog - all operations logged with context.

### Reporting Issues
When reporting issues, include:
1. Command run
2. File path
3. Error message
4. File size and encoding (first line of file)
5. Number of images expected

### Contact
See main repository documentation for support channels.

---

**Last Updated**: 2025-11-05
**Version**: 1.0
**Status**: Production Ready
