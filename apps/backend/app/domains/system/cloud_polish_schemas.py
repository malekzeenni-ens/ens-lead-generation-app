from pydantic import BaseModel, ConfigDict, Field, SecretStr


class CloudPolishConfigurationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr = Field(min_length=10, max_length=300)


class CloudPolishStatusRead(BaseModel):
    configured: bool
    enabled: bool
    model: str
