"""
Performance monitoring and timing utilities.

Tracks stage timings and calculates effective RPS.
"""
import time
from typing import Dict, Optional
import structlog

logger = structlog.get_logger()


class PerformanceMonitor:
    """
    Monitor and log performance metrics for ETL stages.

    Features:
    - Stage timing
    - Effective RPS calculation
    - Progress checkpoints every N items
    """

    def __init__(self, job_name: str, checkpoint_interval: int = 100):
        """
        Initialize performance monitor.

        Args:
            job_name: Name of the job being monitored
            checkpoint_interval: Log metrics every N items
        """
        self.job_name = job_name
        self.checkpoint_interval = checkpoint_interval
        self.start_time: Optional[float] = None
        self.checkpoint_time: Optional[float] = None
        self.items_processed = 0
        self.checkpoint_items = 0
        self.stage_timings: Dict[str, float] = {}

    def start(self):
        """Start monitoring."""
        self.start_time = time.time()
        self.checkpoint_time = self.start_time

        logger.info(
            "performance_monitor_started",
            job=self.job_name,
            checkpoint_interval=self.checkpoint_interval
        )

    def record_item(self):
        """
        Record completion of one item.

        Logs checkpoint metrics every checkpoint_interval items.
        """
        self.items_processed += 1
        self.checkpoint_items += 1

        if self.checkpoint_items >= self.checkpoint_interval:
            self._log_checkpoint()
            self.checkpoint_items = 0
            self.checkpoint_time = time.time()

    def _log_checkpoint(self):
        """Log checkpoint metrics."""
        if not self.checkpoint_time or not self.start_time:
            return

        current_time = time.time()

        # Checkpoint metrics (last N items)
        checkpoint_duration = current_time - self.checkpoint_time
        checkpoint_rps = self.checkpoint_items / checkpoint_duration if checkpoint_duration > 0 else 0

        # Overall metrics
        total_duration = current_time - self.start_time
        overall_rps = self.items_processed / total_duration if total_duration > 0 else 0

        logger.info(
            "performance_checkpoint",
            job=self.job_name,
            items_processed=self.items_processed,
            checkpoint_items=self.checkpoint_items,
            checkpoint_duration_seconds=round(checkpoint_duration, 2),
            checkpoint_rps=round(checkpoint_rps, 2),
            overall_duration_seconds=round(total_duration, 2),
            overall_rps=round(overall_rps, 2)
        )

    def start_stage(self, stage_name: str):
        """
        Start timing a stage.

        Args:
            stage_name: Name of the stage
        """
        self.stage_timings[stage_name] = time.time()
        logger.debug("stage_started", job=self.job_name, stage=stage_name)

    def end_stage(self, stage_name: str):
        """
        End timing a stage and log duration.

        Args:
            stage_name: Name of the stage
        """
        if stage_name not in self.stage_timings:
            logger.warning("stage_timing_not_started", job=self.job_name, stage=stage_name)
            return

        start_time = self.stage_timings[stage_name]
        duration = time.time() - start_time

        logger.info(
            "stage_completed",
            job=self.job_name,
            stage=stage_name,
            duration_seconds=round(duration, 2)
        )

    def finish(self) -> Dict[str, any]:
        """
        Finish monitoring and return final metrics.

        Returns:
            Dictionary of final metrics
        """
        # Log any remaining items
        if self.checkpoint_items > 0:
            self._log_checkpoint()

        if not self.start_time:
            return {}

        total_duration = time.time() - self.start_time
        overall_rps = self.items_processed / total_duration if total_duration > 0 else 0

        metrics = {
            "items_processed": self.items_processed,
            "total_duration_seconds": round(total_duration, 2),
            "overall_rps": round(overall_rps, 2)
        }

        logger.info(
            "performance_monitor_finished",
            job=self.job_name,
            **metrics
        )

        return metrics
