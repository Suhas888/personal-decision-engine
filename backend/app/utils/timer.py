import time
import logging
from contextlib import contextmanager

logger = logging.getLogger("pde.timer")

class ServerTimer:
    def __init__(self, request_name: str):
        self.request_name = request_name
        self.stages = {}
        self.start_time = time.perf_counter()
        
    @contextmanager
    def stage(self, stage_name: str):
        stage_start = time.perf_counter()
        yield
        stage_end = time.perf_counter()
        self.stages[stage_name] = self.stages.get(stage_name, 0) + (stage_end - stage_start)

    def log_total(self):
        end_time = time.perf_counter()
        total = end_time - self.start_time
        
        # Build the log string
        parts = [f"request={self.request_name}"]
        for name, duration in self.stages.items():
            if duration < 0.01:
                parts.append(f"{name}={duration*1000:.1f}ms")
            else:
                parts.append(f"{name}={duration:.3f}s")
        parts.append(f"total={total:.3f}s")
        
        logger.info(" ".join(parts))
        print(f"[TIMER] " + " ".join(parts))
        return {
            "request": self.request_name,
            "total_ms": round(total * 1000, 2),
            "stages_ms": {k: round(v * 1000, 2) for k, v in self.stages.items()}
        }
