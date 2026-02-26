# This file has been split into:
#   - routes/mockup_utils.py      (shared utilities, Pydantic models, compose helpers)
#   - routes/mockup_templates.py   (template/pack CRUD, settings)
#   - routes/mockup_compose.py     (scene generation, composition endpoints)
#   - routes/mockup_workflow.py    (approval workflow, serving, bulk operations)
#
# If you imported from this file, update your imports:
#   from routes.mockup_utils    import _compose_all_templates, _upload_multi_images_to_etsy, ...
#   from routes.mockup_workflow  import approve_poster, ApproveRequest, ...
