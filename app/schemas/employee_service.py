from pydantic import BaseModel, ConfigDict, Field


class EmployeeServiceCreate(BaseModel):
    employee_id: int = Field(gt=0)
    service_id: int = Field(gt=0)


class EmployeeServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    service_id: int
