"""
Batch generation orchestrator.
Manages generation of multiple posters from the prompt library
with rate limiting, progress tracking, and error recovery.
"""

import asyncio
import uuid
import time
import json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class BatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchItemResult:
    prompt_id: str
    prompt_name: str = ""
    generation_id: Optional[str] = None
    status: str = "pending"  # pending, generating, complete, failed, skipped
    images: list = field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self):
        return {
            "prompt_id": self.prompt_id,
            "prompt_name": self.prompt_name,
            "generation_id": self.generation_id,
            "status": self.status,
            "images": self.images,
            "error": self.error,
        }


@dataclass
class BatchJob:
    batch_id: str
    prompt_ids: list
    status: BatchStatus = BatchStatus.PENDING
    items: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Configuration
    model_id: str = "phoenix"
    size_id: str = "poster_4_5"
    num_images_per_prompt: int = 1
    use_variations: bool = False
    variation_index: Optional[int] = None
    delay_between: float = 3.0

    @property
    def total(self) -> int:
        return len(self.prompt_ids)

    @property
    def completed_count(self) -> int:
        return sum(1 for i in self.items.values() if i.status in ("complete", "skipped"))

    @property
    def failed_count(self) -> int:
        return sum(1 for i in self.items.values() if i.status == "failed")

    @property
    def progress_percent(self) -> float:
        if self.total == 0:
            return 100.0
        done = self.completed_count + self.failed_count
        return round(done / self.total * 100, 1)

    @property
    def current_item(self) -> Optional[str]:
        for pid, item in self.items.items():
            if item.status == "generating":
                return pid
        return None

    def to_dict(self, include_items=False):
        d = {
            "batch_id": self.batch_id,
            "status": self.status.value,
            "total": self.total,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "progress_percent": self.progress_percent,
            "current_item": self.current_item,
            "model_id": self.model_id,
            "size_id": self.size_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
        if include_items:
            d["items"] = {pid: item.to_dict() for pid, item in self.items.items()}
        return d


class BatchManager:
    """Manages batch generation jobs."""

    def __init__(self, notifier=None):
        self._jobs: dict = {}
        self._tasks: dict = {}
        self._notifier = notifier

    def create_batch(
        self,
        prompt_ids: list,
        model_id: str = "phoenix",
        size_id: str = "poster_4_5",
        num_images_per_prompt: int = 1,
        use_variations: bool = False,
        variation_index: Optional[int] = None,
        delay_between: float = 3.0,
    ) -> BatchJob:
        batch_id = str(uuid.uuid4())[:8]
        job = BatchJob(
            batch_id=batch_id,
            prompt_ids=prompt_ids,
            model_id=model_id,
            size_id=size_id,
            num_images_per_prompt=num_images_per_prompt,
            use_variations=use_variations,
            variation_index=variation_index,
            delay_between=delay_between,
        )
        for pid in prompt_ids:
            job.items[pid] = BatchItemResult(prompt_id=pid)
        self._jobs[batch_id] = job
        return job

    async def run_batch(self, batch_id: str, leonardo, db, prompt_lib, models, sizes):
        """Execute the batch generation as a background task."""
        job = self._jobs.get(batch_id)
        if not job:
            return

        job.status = BatchStatus.RUNNING
        job.started_at = time.time()

        # Resolve model UUID
        model_config = models.get(job.model_id, models.get("phoenix"))
        model_uuid = model_config["id"]

        # Resolve size dimensions (cap to Leonardo max of 1536)
        size_config = sizes.get(job.size_id, sizes.get("poster_4_5"))
        width = min(size_config["width"], 1536)
        height = min(size_config["height"], 1536)

        for prompt_id in job.prompt_ids:
            if job.status == BatchStatus.CANCELLED:
                break

            item = job.items[prompt_id]
            item.status = "generating"
            item.started_at = time.time()

            try:
                # Get prompt from library
                lib_prompt = prompt_lib.get_prompt(prompt_id)
                if not lib_prompt:
                    item.status = "skipped"
                    item.error = "Prompt not found in library"
                    continue

                item.prompt_name = lib_prompt["name"]

                # Choose prompt text (main or variation)
                prompt_text = lib_prompt["prompt"]
                if job.use_variations and job.variation_index is not None:
                    variations = lib_prompt.get("variations", [])
                    if 0 <= job.variation_index < len(variations):
                        prompt_text = variations[job.variation_index]

                neg_prompt = lib_prompt.get("negative_prompt", "")

                # Add composition suffix for crop safety
                from sizes import COMPOSITION_SUFFIX
                generation_prompt = prompt_text + COMPOSITION_SUFFIX

                # Start generation
                result = await leonardo.create_generation(
                    prompt=generation_prompt,
                    model_id=model_uuid,
                    num_images=job.num_images_per_prompt,
                    negative_prompt=neg_prompt,
                    width=width,
                    height=height,
                )

                gen_id = result["generation_id"]
                item.generation_id = gen_id

                # Save to DB
                await db.save_generation(
                    generation_id=gen_id,
                    prompt=prompt_text,
                    negative_prompt=neg_prompt,
                    model_id=model_uuid,
                    model_name=model_config.get("name", job.model_id),
                    style=lib_prompt.get("category", ""),
                    preset=prompt_id,
                    width=width,
                    height=height,
                    num_images=job.num_images_per_prompt,
                )

                # Poll for completion
                gen_result = await leonardo.wait_for_generation(
                    gen_id,
                    poll_interval=3.0,
                    timeout=120.0,
                )

                if gen_result["status"] == "COMPLETE":
                    item.status = "complete"
                    item.images = gen_result.get("images", [])

                    # Save images to DB
                    if item.images:
                        await db.save_generated_images(gen_id, item.images)

                    # Update generation status
                    await db.update_generation_status(
                        gen_id, "COMPLETE",
                        api_credit_cost=gen_result.get("api_credit_cost", 0),
                    )
                else:
                    item.status = "failed"
                    item.error = f"Generation status: {gen_result['status']}"
                    await db.update_generation_status(
                        gen_id, gen_result["status"],
                        error_message=item.error,
                    )

                item.completed_at = time.time()

            except Exception as e:
                item.status = "failed"
                item.error = str(e)
                item.completed_at = time.time()

            # Rate limiting
            if job.status == BatchStatus.RUNNING:
                await asyncio.sleep(job.delay_between)

        # Mark batch complete
        if job.status != BatchStatus.CANCELLED:
            job.status = BatchStatus.COMPLETED
        job.completed_at = time.time()

        # Notify batch completion
        if self._notifier:
            completed_count = sum(1 for i in job.items.values() if i.status == "complete")
            failed_count = sum(1 for i in job.items.values() if i.status == "failed")
            try:
                await self._notifier.notify_batch_completed(
                    batch_id=batch_id,
                    total=len(job.items),
                    completed=completed_count,
                    failed=failed_count,
                )
            except Exception:
                pass  # Don't fail batch for notification issues

    def start_batch(self, batch_id: str, leonardo, db, prompt_lib, models, sizes):
        """Launch batch as asyncio background task."""
        task = asyncio.create_task(
            self.run_batch(batch_id, leonardo, db, prompt_lib, models, sizes)
        )
        self._tasks[batch_id] = task
        return task

    def get_batch(self, batch_id: str) -> Optional[BatchJob]:
        return self._jobs.get(batch_id)

    def cancel_batch(self, batch_id: str) -> bool:
        job = self._jobs.get(batch_id)
        if job and job.status == BatchStatus.RUNNING:
            job.status = BatchStatus.CANCELLED
            return True
        return False

    def list_batches(self) -> list:
        return [
            j.to_dict()
            for j in sorted(self._jobs.values(), key=lambda x: x.created_at, reverse=True)
        ]
