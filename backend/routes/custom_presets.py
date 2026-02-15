import asyncio
import json
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from deps import presets_manager, leonardo
import database as db

router = APIRouter(tags=["custom-presets"])


@router.get("/custom-presets")
async def list_custom_presets():
    return {"presets": presets_manager.list_presets()}


@router.get("/custom-presets/{preset_id}")
async def get_custom_preset(preset_id: str):
    preset = presets_manager.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    # Return without internal fields
    return {k: v for k, v in preset.items() if not k.startswith("_")}


@router.post("/custom-presets/upload")
async def upload_custom_preset(file: UploadFile = File(...)):
    try:
        content = await file.read()
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    _validate_preset(data)
    preset_id = presets_manager.save_preset(data)
    return {"preset_id": preset_id, "name": data.get("name", preset_id)}


class PresetJsonBody(BaseModel):
    name: str
    model: str = "phoenix"
    suffix: str = ""
    negative_prompt: str = ""
    settings: dict = {}
    prompts: list = []


@router.post("/custom-presets/upload-json")
async def upload_custom_preset_json(body: PresetJsonBody):
    data = body.model_dump()
    _validate_preset(data)
    preset_id = presets_manager.save_preset(data)
    return {"preset_id": preset_id, "name": data.get("name", preset_id)}


@router.delete("/custom-presets/{preset_id}")
async def delete_custom_preset(preset_id: str):
    ok = presets_manager.delete_preset(preset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"ok": True}


@router.post("/custom-presets/{preset_id}/generate/{prompt_id}")
async def generate_single_preset_prompt(preset_id: str, prompt_id: str):
    try:
        result = await presets_manager.generate_single(preset_id, prompt_id, leonardo, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom-presets/{preset_id}/generate-all")
async def generate_all_preset_prompts(preset_id: str):
    try:
        job_id = await presets_manager.generate_all(preset_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Run in background
    asyncio.create_task(presets_manager.run_generate_all(job_id, leonardo, db))
    return {"job_id": job_id}


@router.get("/custom-presets/jobs/{job_id}")
async def get_preset_job_status(job_id: str):
    job = presets_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _validate_preset(data: dict):
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="Preset must have a 'name'")
    prompts = data.get("prompts")
    if not prompts or not isinstance(prompts, list):
        raise HTTPException(status_code=400, detail="Preset must have non-empty 'prompts' array")
    for i, p in enumerate(prompts):
        if not p.get("id"):
            raise HTTPException(status_code=400, detail=f"Prompt #{i} missing 'id'")
        if not p.get("prompt"):
            raise HTTPException(status_code=400, detail=f"Prompt #{i} missing 'prompt'")
