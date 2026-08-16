from fastapi import APIRouter, HTTPException

from app.github_actions.schemas import (
    FileWriteRequest,
    GitHubActionResponse,
    RepositoryCapabilityRequest,
    RepositoryCapabilityResponse,
    RepositoryCreateRequest,
)
from app.github_actions.service import (
    GitHubActionError,
    GitHubActionService,
)


router = APIRouter(
    prefix="/github",
    tags=["GitHub Actions"],
)


@router.post(
    "/repository/capabilities",
    response_model=RepositoryCapabilityResponse,
)
async def repository_capabilities(
    request: RepositoryCapabilityRequest,
):
    service = GitHubActionService()

    try:
        capabilities = (
            await service.get_repository_capabilities(
                request.owner,
                request.repo,
            )
        )

        return RepositoryCapabilityResponse(
            capabilities=capabilities
        )

    except GitHubActionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.post(
    "/repository/file",
    response_model=GitHubActionResponse,
)
async def write_repository_file(
    request: FileWriteRequest,
):
    service = GitHubActionService()

    try:
        data = await service.write_file(
            owner=request.owner,
            repo=request.repo,
            path=request.path,
            content=request.content,
            message=request.message,
            branch=request.branch,
            sha=request.sha,
            confirm=request.confirm,
        )

        return GitHubActionResponse(
            success=True,
            action="WRITE_FILE",
            message="Repository file write succeeded.",
            data=data,
        )

    except GitHubActionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.post(
    "/repository/create",
    response_model=GitHubActionResponse,
)
async def create_repository(
    request: RepositoryCreateRequest,
):
    service = GitHubActionService()

    try:
        data = await service.create_repository(
            name=request.name,
            description=request.description,
            private=request.private,
            homepage=request.homepage,
            confirm=request.confirm,
        )

        return GitHubActionResponse(
            success=True,
            action="CREATE_REPOSITORY",
            message="Repository creation succeeded.",
            data=data,
        )

    except GitHubActionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc