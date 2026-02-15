"""
Minimal Byte Replacement Image Rewriter

SAFETY GUARANTEES:
- No full-document serialization (no str(soup), prettify(), tostring())
- Only replaces exact bytes of image attribute values
- Preserves encoding, entities, iXBRL, whitespace, case
- Idempotent: second run produces zero diff

Approach:
1. Read file as bytes
2. Use regex to locate and replace ONLY attribute values (src="...", srcset="...")
3. Write atomically via temp file
4. Never decode/encode the entire document
"""

import re
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import urljoin, urlparse
import structlog

logger = structlog.get_logger()


class MinimalImageRewriter:
    """
    Rewrites image references using minimal byte replacement.

    Only touches the attribute value bytes, nothing else.
    """

    # Regex patterns for finding image attributes (on bytes)
    # Matches: src="..." or src='...' (capturing the value)
    IMG_SRC_PATTERN = rb'(<img[^>]*\s+src\s*=\s*["\'])([^"\']+)(["\'])'
    IMG_SRCSET_PATTERN = rb'(<img[^>]*\s+srcset\s*=\s*["\'])([^"\']+)(["\'])'
    SOURCE_SRCSET_PATTERN = rb'(<source[^>]*\s+srcset\s*=\s*["\'])([^"\']+)(["\'])'

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            'files_processed': 0,
            'images_rewritten': 0,
            'size_delta': 0,  # Total size change across all files
        }

    def build_image_mapping(
        self,
        html_path: Path,
        document_url: Optional[str] = None
    ) -> Dict[bytes, bytes]:
        """
        Build mapping from old image references to new local paths.

        Scans the same directory for images matching the pattern:
        HTML: JSM_2025_FY_27-02-2025.html
        Images: JSM_2025_FY_27-02-2025_image-001.jpg

        Args:
            html_path: Path to HTML file
            document_url: Optional URL for resolving relative refs

        Returns:
            Dict mapping old references (as bytes) to new local paths (as bytes)
        """
        html_dir = html_path.parent
        html_stem = html_path.stem

        mapping = {}

        # Find all images in the same directory
        for img_file in html_dir.iterdir():
            if not img_file.is_file():
                continue

            # Check if it's an image
            if img_file.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.gif', '.svg'}:
                continue

            # Check if it's related to this HTML file
            if not img_file.stem.startswith(html_stem):
                continue

            # New local reference (relative path)
            new_ref = f"./{img_file.name}"

            # Try to infer what the original reference might have been
            # Pattern: JSM_2025_FY_27-02-2025_image-001.jpg → sequence number 001
            match = re.search(r'_image-(\d+)', img_file.stem)
            if match:
                seq = int(match.group(1))

                # Common original reference patterns
                possible_old_refs = [
                    # SEC pattern: img{accession_number}_{seq}.jpg
                    f"img{html_stem.split('_')[-1]}_{seq - 1}.{img_file.suffix[1:]}",
                    # Simple pattern: image{seq}.jpg
                    f"image{seq:03d}.{img_file.suffix[1:]}",
                    # Another pattern: g{seq}.jpg
                    f"g{seq}.{img_file.suffix[1:]}",
                ]

                for old_ref in possible_old_refs:
                    mapping[old_ref.encode('utf-8')] = new_ref.encode('utf-8')

        logger.info(
            "image_mapping_built",
            html_file=html_path.name,
            mapping_size=len(mapping)
        )

        return mapping

    def detect_original_references(self, content_bytes: bytes) -> List[bytes]:
        """
        Detect all image references in the HTML.

        Returns list of unique image references found.
        """
        refs = set()

        # Find all img src
        for match in re.finditer(self.IMG_SRC_PATTERN, content_bytes, re.IGNORECASE):
            refs.add(match.group(2))

        # Find all img srcset
        for match in re.finditer(self.IMG_SRCSET_PATTERN, content_bytes, re.IGNORECASE):
            # srcset can have multiple refs like "img1.jpg 1x, img2.jpg 2x"
            srcset_value = match.group(2)
            for part in srcset_value.split(b','):
                ref = part.strip().split()[0] if b' ' in part else part.strip()
                refs.add(ref)

        # Find all source srcset
        for match in re.finditer(self.SOURCE_SRCSET_PATTERN, content_bytes, re.IGNORECASE):
            srcset_value = match.group(2)
            for part in srcset_value.split(b','):
                ref = part.strip().split()[0] if b' ' in part else part.strip()
                refs.add(ref)

        return list(refs)

    def enhance_mapping_with_detected_refs(
        self,
        content_bytes: bytes,
        base_mapping: Dict[bytes, bytes],
        html_path: Path
    ) -> Dict[bytes, bytes]:
        """
        Enhance mapping by detecting actual references in the HTML.

        This finds references like "img127516550_0.jpg" and maps them
        to the corresponding local image based on sequence number.

        HTML refs are typically 0-indexed: img{accession}_0.jpg, img{accession}_1.jpg
        Local files are 1-indexed: {basename}_image-001.jpg, {basename}_image-002.jpg
        """
        detected_refs = self.detect_original_references(content_bytes)

        # Get local images for this HTML file
        html_dir = html_path.parent
        html_stem = html_path.stem

        local_images = []
        for img_file in sorted(html_dir.iterdir()):
            if not img_file.is_file():
                continue
            if img_file.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.gif', '.svg'}:
                continue
            if img_file.stem.startswith(html_stem):
                local_images.append(img_file)

        # Sort by sequence number to ensure correct ordering
        def extract_seq(p: Path) -> int:
            match = re.search(r'_image-(\d+)', p.stem)
            return int(match.group(1)) if match else 999999

        local_images.sort(key=extract_seq)

        logger.debug(
            "found_local_images",
            file=html_path.name,
            count=len(local_images),
            images=[img.name for img in local_images[:3]]
        )

        # Build enhanced mapping
        mapping = dict(base_mapping)

        for ref in detected_refs:
            if ref in mapping:
                continue  # Already mapped

            if ref.startswith(b'data:') or ref.startswith(b'http'):
                continue  # Skip data URIs and absolute URLs for now

            # Try to extract sequence number from reference
            # Pattern: img{number}_{seq}.jpg where seq is 0-indexed
            ref_str = ref.decode('utf-8', errors='ignore')
            seq_match = re.search(r'_(\d+)\.', ref_str)

            if seq_match:
                seq = int(seq_match.group(1))
                # HTML refs are 0-indexed, local files are 1-indexed
                # img127516550_0.jpg → JSM_2025_FY_27-02-2025_image-001.jpg
                if seq < len(local_images):
                    new_ref = f"./{local_images[seq].name}"
                    mapping[ref] = new_ref.encode('utf-8')
                    logger.debug(
                        "mapped_detected_ref",
                        old_ref=ref_str,
                        new_ref=new_ref,
                        html_index=seq,
                        local_index=seq + 1
                    )

        logger.info(
            "mapping_enhanced",
            file=html_path.name,
            total_mappings=len(mapping),
            detected_refs=len(detected_refs)
        )

        return mapping

    def replace_image_references(
        self,
        content_bytes: bytes,
        mapping: Dict[bytes, bytes]
    ) -> Tuple[bytes, int]:
        """
        Replace image references using minimal byte replacement.

        Args:
            content_bytes: Original HTML as bytes
            mapping: Dict mapping old refs (bytes) to new refs (bytes)

        Returns:
            Tuple of (modified_bytes, num_replacements)
        """
        result = content_bytes
        num_replacements = 0

        # Replace img src attributes
        def replace_src(match):
            nonlocal num_replacements
            prefix = match.group(1)  # <img...src="
            old_value = match.group(2)  # the actual src value
            suffix = match.group(3)  # closing quote

            # Extract just the filename if it's a path
            if b'/' in old_value:
                old_filename = old_value.split(b'/')[-1]
            else:
                old_filename = old_value

            # Check if we have a mapping for this
            new_value = mapping.get(old_value) or mapping.get(old_filename)

            if new_value and new_value != old_value:
                num_replacements += 1
                logger.debug(
                    "replacing_img_src",
                    old=old_value[:100].decode('utf-8', errors='ignore'),
                    new=new_value.decode('utf-8')
                )
                return prefix + new_value + suffix

            return match.group(0)  # No change

        # Replace all img src
        result = re.sub(
            self.IMG_SRC_PATTERN,
            replace_src,
            result,
            flags=re.IGNORECASE
        )

        # Replace img srcset (similar approach)
        def replace_srcset(match):
            nonlocal num_replacements
            prefix = match.group(1)
            old_value = match.group(2)
            suffix = match.group(3)

            # srcset can have multiple refs: "img1.jpg 1x, img2.jpg 2x"
            # We need to replace each ref individually
            parts = old_value.split(b',')
            new_parts = []
            modified = False

            for part in parts:
                part = part.strip()
                if b' ' in part:
                    ref, descriptor = part.split(None, 1)
                else:
                    ref, descriptor = part, b''

                # Extract filename
                if b'/' in ref:
                    ref_filename = ref.split(b'/')[-1]
                else:
                    ref_filename = ref

                new_ref = mapping.get(ref) or mapping.get(ref_filename)

                if new_ref and new_ref != ref:
                    modified = True
                    num_replacements += 1
                    if descriptor:
                        new_parts.append(new_ref + b' ' + descriptor)
                    else:
                        new_parts.append(new_ref)
                else:
                    new_parts.append(part)

            if modified:
                return prefix + b', '.join(new_parts) + suffix

            return match.group(0)

        result = re.sub(
            self.IMG_SRCSET_PATTERN,
            replace_srcset,
            result,
            flags=re.IGNORECASE
        )

        # Replace source srcset (same as img srcset)
        result = re.sub(
            self.SOURCE_SRCSET_PATTERN,
            replace_srcset,
            result,
            flags=re.IGNORECASE
        )

        return result, num_replacements

    def rewrite_file(self, html_path: Path) -> Dict:
        """
        Rewrite a single HTML file using minimal byte replacement.

        Args:
            html_path: Path to HTML file

        Returns:
            Dict with results: {
                'path': str,
                'rewritten': bool,
                'num_replacements': int,
                'bytes_changed': int,
                'error': str (optional)
            }
        """
        result = {
            'path': str(html_path),
            'rewritten': False,
            'num_replacements': 0,
            'bytes_changed': 0,
        }

        try:
            # Read original file as bytes
            original_bytes = html_path.read_bytes()
            original_size = len(original_bytes)

            # Build image mapping
            mapping = self.build_image_mapping(html_path)

            if not mapping:
                logger.info("no_images_found", file=html_path.name)
                return result

            # Enhance mapping by detecting actual references in HTML
            mapping = self.enhance_mapping_with_detected_refs(original_bytes, mapping, html_path)

            # Replace image references
            modified_bytes, num_replacements = self.replace_image_references(
                original_bytes,
                mapping
            )

            if num_replacements == 0:
                logger.info("no_replacements_needed", file=html_path.name)
                return result

            # Calculate actual bytes changed (size difference)
            # Note: Simple byte-by-byte comparison is misleading because when
            # we replace "abc" with "abcdef", all subsequent bytes shift.
            # Size difference is a better metric for minimal replacement.
            bytes_changed = abs(len(modified_bytes) - len(original_bytes))

            result['num_replacements'] = num_replacements
            result['bytes_changed'] = bytes_changed
            result['rewritten'] = True

            if not self.dry_run:
                # Write atomically via temp file
                with tempfile.NamedTemporaryFile(
                    mode='wb',
                    dir=html_path.parent,
                    delete=False
                ) as tmp:
                    tmp.write(modified_bytes)
                    tmp_path = Path(tmp.name)

                # Backup original (if not already backed up)
                backup_path = html_path.with_suffix(html_path.suffix + '.bak')
                if not backup_path.exists():
                    html_path.rename(backup_path)
                    logger.info("backup_created", backup=backup_path.name)
                else:
                    html_path.unlink()

                # Move temp to final location
                tmp_path.rename(html_path)

                logger.info(
                    "file_rewritten",
                    file=html_path.name,
                    replacements=num_replacements,
                    bytes_changed=bytes_changed,
                    size_before=original_size,
                    size_after=len(modified_bytes)
                )
            else:
                logger.info(
                    "dry_run_would_rewrite",
                    file=html_path.name,
                    replacements=num_replacements,
                    bytes_changed=bytes_changed
                )

            self.stats['files_processed'] += 1
            self.stats['images_rewritten'] += num_replacements
            self.stats['size_delta'] += bytes_changed

        except Exception as e:
            result['error'] = str(e)
            logger.error(
                "rewrite_failed",
                file=html_path.name,
                error=str(e),
                exc_info=True
            )

        return result

    def validate_idempotent(self, html_path: Path) -> bool:
        """
        Validate that rewriting is idempotent.

        Runs rewrite twice and checks that second run produces no changes.
        """
        # First run
        result1 = self.rewrite_file(html_path)

        if not result1['rewritten']:
            return True  # Nothing to rewrite

        # Second run (on same file)
        result2 = self.rewrite_file(html_path)

        if result2['num_replacements'] > 0:
            logger.error(
                "not_idempotent",
                file=html_path.name,
                first_run=result1['num_replacements'],
                second_run=result2['num_replacements']
            )
            return False

        logger.info("idempotent_validated", file=html_path.name)
        return True
