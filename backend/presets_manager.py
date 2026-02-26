"""
Custom preset manager.
Loads/saves JSON preset files from saved_presets/ directory.
Handles generation of single or all prompts from a preset.
"""

import json
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

PRESETS_DIR = Path(__file__).parent / "saved_presets"

# Shorthand model names -> Leonardo UUIDs
MODEL_IDS = {
    "seedream": "e71a1c2f-4f80-4800-934f-2c68979d8cc8",
    "kino": "aa77f04e-3eec-4034-9c07-d0f619684628",
    "lightning": "b24e16ff-06e3-43eb-8d33-4416c2d75876",
    "anime": "e71a1c2f-4f80-4800-934f-2c68979d8cc8",
    "diffusion": "ac614f96-1082-45bf-be9d-757f2d31c174",
}


class PresetsManager:
    def __init__(self):
        self._presets: Dict[str, dict] = {}
        self._running_jobs: Dict[str, dict] = {}
        PRESETS_DIR.mkdir(exist_ok=True)
        self._load_all()

    def _load_all(self):
        self._presets.clear()
        for f in PRESETS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                preset_id = f.stem
                data["_id"] = preset_id
                data["_file"] = str(f)
                self._presets[preset_id] = data
            except Exception as e:
                logger.warning("Failed to load %s: %s", f.name, e)

    def list_presets(self) -> List[dict]:
        result = []
        for pid, p in self._presets.items():
            result.append({
                "id": pid,
                "name": p.get("name", pid),
                "model": p.get("model", ""),
                "prompt_count": len(p.get("prompts", [])),
                "settings": p.get("settings", {}),
                "generated_count": sum(
                    1 for pr in p.get("prompts", []) if pr.get("generation_id")
                ),
            })
        return result

    def get_preset(self, preset_id: str) -> Optional[dict]:
        return self._presets.get(preset_id)

    def save_preset(self, data: dict) -> str:
        name = data.get("name", "untitled")
        base_id = name.lower().replace(" ", "-")
        base_id = "".join(c for c in base_id if c.isalnum() or c == "-")
        base_id = base_id.strip("-") or "preset"

        preset_id = base_id
        counter = 2
        while preset_id in self._presets:
            preset_id = f"{base_id}-{counter}"
            counter += 1

        for prompt in data.get("prompts", []):
            if "generation_id" not in prompt:
                prompt["generation_id"] = None
            if "images" not in prompt:
                prompt["images"] = []

        filepath = PRESETS_DIR / f"{preset_id}.json"
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        data["_id"] = preset_id
        data["_file"] = str(filepath)
        self._presets[preset_id] = data
        return preset_id

    def delete_preset(self, preset_id: str) -> bool:
        preset = self._presets.pop(preset_id, None)
        if not preset:
            return False
        filepath = Path(preset.get("_file", ""))
        if filepath.exists():
            filepath.unlink()
        return True

    def _resolve_model_id(self, model_name: str) -> str:
        if model_name in MODEL_IDS:
            return MODEL_IDS[model_name]
        from config import MODELS
        for key, val in MODELS.items():
            if key == model_name:
                return val["id"]
        return MODELS.get("phoenix", {}).get(
            "id", "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"
        )

    def _save_to_disk(self, preset_id: str):
        preset = self._presets.get(preset_id)
        if not preset:
            return
        filepath = Path(preset.get("_file", ""))
        save_data = {k: v for k, v in preset.items() if not k.startswith("_")}
        filepath.write_text(json.dumps(save_data, indent=2, ensure_ascii=False))

    async def generate_single(self, preset_id: str, prompt_id: str, leonardo, db) -> dict:
        preset = self._presets.get(preset_id)
        if not preset:
            raise ValueError(f"Preset not found: {preset_id}")

        prompt_data = None
        for p in preset.get("prompts", []):
            if p.get("id") == prompt_id:
                prompt_data = p
                break
        if not prompt_data:
            raise ValueError(f"Prompt not found: {prompt_id}")

        suffix = preset.get("suffix", "")
        neg_prompt = preset.get("negative_prompt", "")
        model_name = preset.get("model", "phoenix")
        settings = preset.get("settings", {})

        model_uuid = self._resolve_model_id(model_name)
        width = min(settings.get("width", 1200), 1536)
        height = min(settings.get("height", 1500), 1536)
        width = width // 8 * 8
        height = height // 8 * 8
        num_images = min(settings.get("num_images", 4), 4)

        full_prompt = prompt_data["prompt"] + suffix

        result = await leonardo.create_generation(
            prompt=full_prompt,
            model_id=model_uuid,
            num_images=num_images,
            negative_prompt=neg_prompt,
            width=width,
            height=height,
        )

        gen_id = result["generation_id"]

        await db.save_generation(
            generation_id=gen_id,
            prompt=full_prompt,
            negative_prompt=neg_prompt,
            model_id=model_uuid,
            model_name=model_name,
            style=f"custom:{preset_id}",
            preset=prompt_id,
            width=width,
            height=height,
            num_images=num_images,
        )

        gen_result = await leonardo.wait_for_generation(
            gen_id, poll_interval=3.0, timeout=120.0
        )

        images = gen_result.get("images", [])

        if gen_result["status"] == "COMPLETE":
            if images:
                await db.save_generated_images(gen_id, images)
            await db.update_generation_status(
                gen_id, "COMPLETE",
                api_credit_cost=gen_result.get("api_credit_cost", 0),
            )
            prompt_data["generation_id"] = gen_id
            prompt_data["images"] = images
            self._save_to_disk(preset_id)
        else:
            await db.update_generation_status(
                gen_id, gen_result["status"],
                error_message=f"Generation {gen_result['status']}",
            )

        return {
            "generation_id": gen_id,
            "prompt_id": prompt_id,
            "status": gen_result["status"],
            "images": images,
        }

    async def generate_all(self, preset_id: str) -> str:
        preset = self._presets.get(preset_id)
        if not preset:
            raise ValueError(f"Preset not found: {preset_id}")

        # Check for existing running job on this preset
        for jid, job in self._running_jobs.items():
            if job["preset_id"] == preset_id and job["status"] == "running":
                raise ValueError(f"Batch already running for this preset (job {jid})")

        job_id = str(uuid.uuid4())[:8]
        prompts = preset.get("prompts", [])

        job = {
            "job_id": job_id,
            "preset_id": preset_id,
            "status": "running",
            "total": len(prompts),
            "completed": 0,
            "failed": 0,
            "current_prompt_id": None,
            "items": {
                p["id"]: {
                    "prompt_id": p["id"],
                    "prompt_name": p.get("name", p["id"]),
                    "status": "skipped" if p.get("generation_id") else "pending",
                    "generation_id": p.get("generation_id"),
                    "images": p.get("images", []),
                    "error": None,
                }
                for p in prompts
            },
        }

        # Count already-generated as completed
        job["completed"] = sum(1 for it in job["items"].values() if it["status"] == "skipped")

        self._running_jobs[job_id] = job
        return job_id

    async def run_generate_all(self, job_id: str, leonardo, db):
        job = self._running_jobs.get(job_id)
        if not job:
            return

        preset_id = job["preset_id"]
        preset = self._presets.get(preset_id)
        if not preset:
            job["status"] = "failed"
            return

        prompts = preset.get("prompts", [])
        pending = [p for p in prompts if not p.get("generation_id")]

        for i, prompt_data in enumerate(pending):
            pid = prompt_data["id"]
            item = job["items"][pid]

            job["current_prompt_id"] = pid
            item["status"] = "generating"

            try:
                result = await self.generate_single(preset_id, pid, leonardo, db)
                item["generation_id"] = result["generation_id"]
                item["images"] = result.get("images", [])
                if result["status"] == "COMPLETE":
                    item["status"] = "complete"
                    job["completed"] += 1
                else:
                    item["status"] = "failed"
                    item["error"] = f"Status: {result['status']}"
                    job["failed"] += 1
            except Exception as e:
                item["status"] = "failed"
                item["error"] = str(e)
                job["failed"] += 1

            # Rate limiting delay between generations
            if i < len(pending) - 1:
                await asyncio.sleep(3.0)

        job["status"] = "completed"
        job["current_prompt_id"] = None

    def get_job(self, job_id: str) -> Optional[dict]:
        return self._running_jobs.get(job_id)
