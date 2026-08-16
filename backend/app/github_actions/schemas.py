from pydantic import BaseModel, Field


class RepositoryCapabilityRequest(BaseModel):
    owner: str = Field(
        min_length=1,
        max_length=100,
    )

    repo: str = Field(
        min_length=1,
        max_length=100,
    )


class RepositoryCapabilities(BaseModel):
    owner: str
    repo: str

    exists: bool

    authenticated_user: str | None = None

    can_read: bool = False
    can_write: bool = False
    can_maintain: bool = False
    can_admin: bool = False

    action_write_allowed: bool = False

    reason: str


class RepositoryCapabilityResponse(BaseModel):
    capabilities: RepositoryCapabilities


class FileWriteRequest(BaseModel):
    owner: str = Field(
        min_length=1,
        max_length=100,
    )

    repo: str = Field(
        min_length=1,
        max_length=100,
    )

    path: str = Field(
        min_length=1,
        max_length=500,
    )

    content: str

    message: str = Field(
        min_length=1,
        max_length=200,
    )

    branch: str | None = Field(
        default=None,
        max_length=255,
    )

    sha: str | None = Field(
        default=None,
        max_length=100,
    )

    # Explicit user confirmation for a mutation.
    confirm: bool = False


class RepositoryCreateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )

    private: bool = True

    homepage: str | None = Field(
        default=None,
        max_length=1000,
    )

    # Explicit user confirmation for creation.
    confirm: bool = False


class GitHubActionResponse(BaseModel):
    success: bool
    action: str
    message: str
    data: dict | None = None