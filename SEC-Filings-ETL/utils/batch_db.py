"""
Batch database operations for improved performance.

Features:
- Batch commits (reduce transaction overhead)
- Upsert operations (INSERT ... ON CONFLICT UPDATE)
- Automatic flushing at batch size
"""
from typing import List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import structlog

from config.settings import settings

logger = structlog.get_logger()


class BatchDBWriter:
    """
    Batch writer for database operations.

    Accumulates records and commits in batches to reduce
    transaction overhead.
    """

    def __init__(self, session: Session, batch_size: int = None, auto_flush: bool = False):
        """
        Initialize batch writer.

        Args:
            session: SQLAlchemy session
            batch_size: Number of items to accumulate before committing (default from settings)
            auto_flush: Disable autoflush for better performance (default: False)
        """
        self.session = session
        self.batch_size = batch_size or settings.batch_size
        self.pending_items: List[Any] = []
        self.total_committed = 0

        # Disable autoflush for performance
        if not auto_flush:
            self.session.autoflush = False

        logger.debug(
            "batch_db_writer_initialized",
            batch_size=self.batch_size,
            auto_flush=auto_flush
        )

    def add(self, item: Any):
        """
        Add an item to the batch.

        Automatically commits when batch size is reached.

        Args:
            item: SQLAlchemy model instance to add
        """
        self.session.add(item)
        self.pending_items.append(item)

        if len(self.pending_items) >= self.batch_size:
            self.flush()

    def flush(self):
        """Flush pending items without committing."""
        if self.pending_items:
            self.session.flush()
            logger.debug("batch_flushed", count=len(self.pending_items))
            self.pending_items.clear()

    def commit(self):
        """Commit the current batch."""
        if self.pending_items or self.session.dirty:
            count = len(self.pending_items)
            self.session.commit()
            self.total_committed += count
            self.pending_items.clear()

            logger.debug(
                "batch_committed",
                batch_count=count,
                total_committed=self.total_committed
            )

    def finish(self):
        """Commit any remaining items and return total count."""
        self.commit()

        logger.info(
            "batch_writer_finished",
            total_committed=self.total_committed
        )

        return self.total_committed


def bulk_upsert(session: Session, model_class, records: List[dict], conflict_columns: List[str]):
    """
    Perform bulk upsert (INSERT ... ON CONFLICT UPDATE) operation.

    Args:
        session: SQLAlchemy session
        model_class: Model class to insert
        records: List of dictionaries with record data
        conflict_columns: Columns that define uniqueness for conflict resolution

    Returns:
        Number of records upserted

    Example:
        bulk_upsert(
            session,
            Artifact,
            [
                {'filing_id': 1, 'filename': 'doc.htm', 'status': 'pending'},
                {'filing_id': 2, 'filename': 'doc.htm', 'status': 'pending'}
            ],
            conflict_columns=['filing_id', 'filename']
        )
    """
    if not records:
        return 0

    # Create insert statement
    stmt = insert(model_class).values(records)

    # Get update columns (all columns except conflict columns)
    update_columns = {
        col.name: col
        for col in stmt.excluded
        if col.name not in conflict_columns and col.name != 'id'
    }

    # Create upsert statement
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=conflict_columns,
        set_=update_columns
    )

    # Execute
    result = session.execute(upsert_stmt)

    logger.info(
        "bulk_upsert_completed",
        model=model_class.__name__,
        records=len(records),
        rows_affected=result.rowcount
    )

    return result.rowcount
