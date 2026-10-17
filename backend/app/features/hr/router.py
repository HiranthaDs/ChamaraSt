from backend.app.shared.crud_router import collection_router
from backend.app.features.hr.repository import HR_RESOURCES
from backend.app.features.hr.service import HRService
from backend.app.features.hr.models import EmployeeRecord, LeaveRecord

service = HRService()
router = collection_router("/api/hr", "Human resources", HR_RESOURCES,
                           service_provider=service.resource,
                           schemas={"employees": EmployeeRecord, "leaves": LeaveRecord})
