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
        "Returns all registered providers, supported target "
        "types, identifiers, and provider-specific capabilities."
    ),
)
async def list_providers() -> dict:
    providers = []

    for provider in provider_registry.all():
        providers.append(
            {
                "name": provider.name,
                "supported_target_types": [
                    target_type.value
                    for target_type
                    in provider.supported_target_types
                ],
                "supported_identifiers": (
                    provider.get_supported_identifiers()
                ),
                "capabilities": (
                    provider.get_capabilities()
                ),
            }
        )

    return {
        "success": True,
        "count": len(providers),
        "providers": providers,
    }