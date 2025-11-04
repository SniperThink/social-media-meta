# app/routes/content.py
from fastapi import APIRouter, HTTPException
from app.models import schemas
from app.services import generator_service
from pydantic import BaseModel
from app.models import schemas

router = APIRouter(
    prefix="/api/content",
    tags=["Content Generation"]
)

@router.post("/generate", response_model=schemas.GenerateResponse)
async def generate_content(req: schemas.GenerateRequest):
    """
    Receives a prompt, post type, and number of media, returns generated content.
    """
    if req.post_type == 'static':
            data = generator_service.generate_static_post(req.prompt, req.num_media)
    elif req.post_type.startswith('carousel_'):
            # Extract number from carousel_N format
            try:
                num_slides = int(req.post_type.split('_')[1])
                data = generator_service.generate_carousel_post(req.prompt, num_slides)
            except (IndexError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid carousel post type format")
    elif req.post_type == 'video':
            data = generator_service.generate_video_post(req.prompt, req.num_media)
    else:
            raise HTTPException(status_code=400, detail="Invalid post type")
    return data


@router.post('/regenerate', response_model=schemas.RegenerateResponse)
async def regenerate(req: schemas.RegenerateRequest):
        """Regenerate a single media item or caption."""
        result = generator_service.regenerate_item(prompt=req.prompt, post_type=req.post_type, index=req.index, media=req.media, regen_target=req.regen_target, captions=req.captions)
        # Map result to the response model keys
        resp = schemas.RegenerateResponse(
                media_url=result.get('media_url'),
                caption=result.get('caption'),
                captions=result.get('captions')
        )
        return resp

@router.post('/update_caption', response_model=schemas.UpdateCaptionResponse)
async def update_caption(req: schemas.UpdateCaptionRequest):
    """Update a specific caption in the list."""
    # For now, just return success since captions are stored in frontend session
    # In a real app, you'd update a database or session store
    return schemas.UpdateCaptionResponse(success=True, message="Caption updated successfully")
