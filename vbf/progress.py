"""Progress visualization for VBF modeling tasks.

Provides real-time progress display with multiple output modes:
- Console: Simple terminal output
- Rich: Enhanced terminal with colors and progress bars
- JSON: Machine-readable output for external tools
"""

import asyncio
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from collections import deque
from enum import Enum


class DisplayMode(Enum):
    """Display mode for progress visualization."""
    CONSOLE = "console"        # Simple text output
    RICH = "rich"             # Enhanced with progress bars
    JSON = "json"             # Machine-readable JSON lines
    QUIET = "quiet"           # No output (for programmatic use)


@dataclass
class ProgressStep:
    """Single step progress info."""
    step_id: str
    skill: str
    stage: str
    status: str  # "pending", "running", "success", "failed", "retrying"
    duration: float = 0.0
    error: Optional[str] = None
    attempt: int = 1


@dataclass
class TaskProgress:
    """Complete task progress state."""
    prompt: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    current_stage: str = "reference_analysis"
    steps: Dict[str, ProgressStep] = field(default_factory=dict)
    stage_order: List[str] = field(default_factory=lambda: [
        "reference_analysis", "mood_board", "style_definition",
        "primitive_blocking", "silhouette_validation", "proportion_check",
        "topology_prep", "edge_flow", "boolean_operations",
        "bevel_chamfer", "micro_detailing", "high_poly_finalize",
        "normal_baking", "uv_prep", "material_prep",
        "material_assignment", "lighting_check", "finalize"
    ])
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    llm_calls: int = 0
    memory_mb: float = 0.0

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        start = self.start_time or time.time()
        end = self.end_time or time.time()
        return end - start

    @property
    def percent(self) -> float:
        """Completion percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100

    @property
    def eta(self) -> Optional[float]:
        """Estimated time remaining in seconds."""
        if self.completed_steps == 0 or self.total_steps == 0:
            return None
        avg_time = self.elapsed / self.completed_steps
        remaining = self.total_steps - self.completed_steps
        return avg_time * remaining


class ProgressVisualizer:
    """Real-time progress visualization for VBF tasks.

    Features:
    - Multi-format output (console, rich, JSON)
    - Stage-based progress tracking
    - LLM call statistics
    - Memory monitoring
    - ETA calculation
    """

    def __init__(self, mode: DisplayMode = DisplayMode.CONSOLE, update_interval: float = 0.5):
        self.mode = mode
        self.update_interval = update_interval
        self._progress = TaskProgress()
        self._update_task: Optional[asyncio.Task] = None
        self._running = False
        self._callbacks: List[Callable[[TaskProgress], None]] = []
        self._render_buffer: deque = deque(maxlen=100)

    def register_callback(self, callback: Callable[[TaskProgress], None]) -> None:
        """Register a callback for progress updates."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[TaskProgress], None]) -> None:
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start_task(self, prompt: str, total_steps: int, stages: Optional[List[str]] = None) -> None:
        """Initialize new task progress."""
        self._progress = TaskProgress(
            prompt=prompt,
            total_steps=total_steps,
            start_time=time.time(),
            stage_order=stages or self._progress.stage_order,
        )
        self._running = True

        if self.mode != DisplayMode.QUIET:
            self._update_task = asyncio.create_task(self._update_loop())
            self._render()

    def start_step(self, step_id: str, skill: str, stage: str) -> None:
        """Mark step as started."""
        self._progress.steps[step_id] = ProgressStep(
            step_id=step_id,
            skill=skill,
            stage=stage,
            status="running",
        )
        self._progress.current_stage = stage
        self._notify()

    def complete_step(self, step_id: str, duration: float) -> None:
        """Mark step as completed."""
        if step_id in self._progress.steps:
            step = self._progress.steps[step_id]
            step.status = "success"
            step.duration = duration
            self._progress.completed_steps += 1
        self._notify()

    def fail_step(self, step_id: str, error: str) -> None:
        """Mark step as failed."""
        if step_id in self._progress.steps:
            step = self._progress.steps[step_id]
            step.status = "failed"
            step.error = error
            self._progress.failed_steps += 1
        self._notify()

    def retry_step(self, step_id: str, attempt: int) -> None:
        """Mark step as retrying."""
        if step_id in self._progress.steps:
            step = self._progress.steps[step_id]
            step.status = "retrying"
            step.attempt = attempt
            self._notify()

    def record_llm_call(self) -> None:
        """Record LLM API call."""
        self._progress.llm_calls += 1
        self._notify()

    def update_memory(self, mb: float) -> None:
        """Update memory usage."""
        self._progress.memory_mb = mb
        self._notify()

    def end_task(self) -> None:
        """End task and finalize display."""
        self._progress.end_time = time.time()
        self._running = False

        if self._update_task:
            self._update_task.cancel()
            try:
                asyncio.get_event_loop().run_until_complete(self._update_task)
            except asyncio.CancelledError:
                pass

        self._final_render()
        self._notify()

    def _notify(self) -> None:
        """Notify all callbacks."""
        for callback in self._callbacks:
            try:
                callback(self._progress)
            except Exception:
                pass

    async def _update_loop(self) -> None:
        """Background update loop."""
        while self._running:
            self._render()
            await asyncio.sleep(self.update_interval)

    def _render(self) -> None:
        """Render current progress."""
        if self.mode == DisplayMode.QUIET:
            return

        if self.mode == DisplayMode.JSON:
            self._render_json()
        elif self.mode == DisplayMode.RICH:
            self._render_rich()
        else:
            self._render_console()

    def _render_console(self) -> None:
        """Simple console output."""
        p = self._progress

        # Clear line for simple update
        sys.stdout.write('\r' + ' ' * 80 + '\r')

        # Progress bar
        bar_width = 30
        filled = int((p.percent / 100) * bar_width)
        bar = '=' * filled + '-' * (bar_width - filled)

        # ETA
        eta_str = f"{p.eta:.0f}s" if p.eta else "N/A"

        # Format output
        line = f"[{bar}] {p.percent:5.1f}% | {p.completed_steps}/{p.total_steps} | {p.current_stage} | ETA: {eta_str}"
        sys.stdout.write(line)
        sys.stdout.flush()

    def _render_rich(self) -> None:
        """Rich terminal output with colors."""
        try:
            # Try to use terminal colors
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            RED = '\033[91m'
            BLUE = '\033[94m'
            END = '\033[0m'

            p = self._progress

            # Clear screen area
            for _ in range(10):
                sys.stdout.write('\033[1A\033[2K')

            # Header
            print(f"\n{BLUE}VBF Modeling Task{END}: {p.prompt[:60]}...")
            print(f"Stage: {YELLOW}{p.current_stage}{END}")

            # Progress bar
            bar_width = 40
            filled = int((p.percent / 100) * bar_width)
            bar = GREEN + '=' * filled + END + '-' * (bar_width - filled)
            print(f"Progress: [{bar}] {p.percent:.1f}%")

            # Stats
            print(f"Steps: {GREEN}{p.completed_steps}✓{END} / {p.total_steps}", end="")
            if p.failed_steps > 0:
                print(f" {RED}{p.failed_steps}✗{END}", end="")
            print()

            # Timing
            eta_str = f"{p.eta:.0f}s" if p.eta else "N/A"
            print(f"Time: {p.elapsed:.1f}s elapsed, ~{eta_str} remaining")

            # LLM stats
            print(f"LLM calls: {p.llm_calls} | Memory: {p.memory_mb:.1f}MB")

            # Current steps
            if p.steps:
                print(f"\n{BLUE}Active Steps:{END}")
                for sid, step in list(p.steps.items())[-3:]:
                    status_color = {
                        "running": YELLOW,
                        "success": GREEN,
                        "failed": RED,
                        "retrying": YELLOW,
                    }.get(step.status, "")
                    print(f"  {status_color}[{step.status.upper()}]{END} {step.skill} ({step.stage})")

        except Exception:
            # Fallback to console mode
            self._render_console()

    def _render_json(self) -> None:
        """JSON line output."""
        data = {
            "type": "progress",
            "timestamp": time.time(),
            "data": {
                "prompt": self._progress.prompt,
                "percent": self._progress.percent,
                "completed": self._progress.completed_steps,
                "total": self._progress.total_steps,
                "failed": self._progress.failed_steps,
                "current_stage": self._progress.current_stage,
                "elapsed": self._progress.elapsed,
                "eta": self._progress.eta,
                "llm_calls": self._progress.llm_calls,
                "memory_mb": self._progress.memory_mb,
            }
        }
        print(json.dumps(data))

    def _final_render(self) -> None:
        """Final render when task ends."""
        if self.mode == DisplayMode.QUIET:
            return

        p = self._progress

        if self.mode == DisplayMode.JSON:
            data = {
                "type": "complete",
                "timestamp": time.time(),
                "data": {
                    "prompt": p.prompt,
                    "completed": p.completed_steps,
                    "failed": p.failed_steps,
                    "total": p.total_steps,
                    "elapsed": p.elapsed,
                    "llm_calls": p.llm_calls,
                }
            }
            print(json.dumps(data))
        else:
            # Add newline if in console mode
            print()
            print("=" * 60)
            print(f"Task Complete: {p.completed_steps}/{p.total_steps} steps")
            print(f"Failed: {p.failed_steps}")
            print(f"Total time: {p.elapsed:.2f}s")
            print(f"LLM calls: {p.llm_calls}")
            print("=" * 60)

    def get_progress(self) -> TaskProgress:
        """Get current progress state."""
        return self._progress
