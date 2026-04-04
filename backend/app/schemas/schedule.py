from pydantic import BaseModel, field_validator


SUPPORTED_TIMEZONES = [
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Singapore",
    "Asia/Seoul",
    "Asia/Hong_Kong",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "UTC",
]


class ScheduleConfigResponse(BaseModel):
    schedule_hour: int
    schedule_minute: int
    timezone: str
    is_active: bool

    model_config = {"from_attributes": True}


class ScheduleConfigUpsert(BaseModel):
    schedule_hour: int
    schedule_minute: int
    timezone: str
    is_active: bool = True

    @field_validator("schedule_hour")
    @classmethod
    def valid_hour(cls, v: int) -> int:
        if not (0 <= v <= 23):
            raise ValueError("Hour must be 0-23")
        return v

    @field_validator("schedule_minute")
    @classmethod
    def valid_minute(cls, v: int) -> int:
        if v not in (0, 30):
            raise ValueError("Minute must be 0 or 30")
        return v

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, v: str) -> str:
        if v not in SUPPORTED_TIMEZONES:
            raise ValueError(f"Unsupported timezone: {v}")
        return v
