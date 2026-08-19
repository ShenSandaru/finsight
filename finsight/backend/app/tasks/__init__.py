"""Export task definitions."""

from app.tasks.definitions import health_check_task, failing_test_task, process_document

__all__ = ["health_check_task", "failing_test_task", "process_document"]
