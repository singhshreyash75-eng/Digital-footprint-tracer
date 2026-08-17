from fastapi import APIRouter

from app.providers.registry import provider_registry


router = APIRouter(
    prefix="/providers",
    tags=["Providers"],
)


@router.get(
    "",
    summary="List registered providers",
    description=(
        "Returns every provider currently registered in the "
        "Digital Footprint Tracer provider registry."
    ),
)
async def list_providers() -> dict:
    return {
        "success": True,
        "count": len(provider_registry.all()),
        "providers": [
            {
                "name": provider.name,
                "supported_target_types": [
                    target_type.value
                    for target_type in provider.supported_target_types
                ],
            }
            for provider in provider_registry.all()
        ],
    }