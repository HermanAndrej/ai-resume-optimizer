from pydantic import BaseModel, Field, field_validator


class PersonalInfo(BaseModel):
    """Top-level fields on the profile row (excluding summary)."""

    full_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=50)
    location: str = Field(default="", max_length=200)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return v
        # Lightweight check — we don't want to reject unusual but valid addresses.
        if "@" not in v or "." not in v.split("@", 1)[1]:
            raise ValueError("Must be a valid email address")
        return v


class ProfileLink(BaseModel):
    id: int | None = None
    label: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=500)
