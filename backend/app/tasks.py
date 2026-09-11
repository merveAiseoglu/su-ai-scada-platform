import asyncio
import logging
from typing import Set

# A global set to store strong references to background tasks.
# This prevents Python's garbage collector from destroying the tasks
# before they finish, which can happen if no strong reference is kept.
_background_tasks: Set[asyncio.Task] = set()

logger = logging.getLogger(__name__)


def _handle_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Background task failed with exception: {e}", exc_info=True)
    finally:
        _background_tasks.discard(task)


def fire_and_forget(coro) -> asyncio.Task:
    """
    Schedules a coroutine to run in the background.
    Maintains a strong reference to the task to prevent premature garbage collection.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_handle_task_result)
    return task
