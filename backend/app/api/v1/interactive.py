"""课堂互动内容生成 API。"""

from fastapi import APIRouter, Depends

from app.core.security import require_user
from app.schemas.interactive import InteractiveGenerateRequest, InteractiveGenerateResponse
from app.services.interactive import generate_interactive

router = APIRouter(dependencies=[Depends(require_user)])


@router.post("/generate", response_model=InteractiveGenerateResponse, summary="生成课堂互动内容")
async def generate_interactive_content(request: InteractiveGenerateRequest) -> InteractiveGenerateResponse:
    items, html, warnings = generate_interactive(request)
    return InteractiveGenerateResponse(
        interaction_type=request.interaction_type,
        items=items,
        html=html,
        warnings=warnings,
    )
