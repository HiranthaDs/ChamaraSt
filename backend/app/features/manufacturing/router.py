from backend.app.shared.crud_router import collection_router
from backend.app.features.manufacturing.repository import MANUFACTURING_RESOURCES
from backend.app.features.manufacturing.service import ManufacturingService
from backend.app.features.manufacturing.models import ManufacturingRecord

service = ManufacturingService()
router = collection_router("/api/manufacturing", "Manufacturing", MANUFACTURING_RESOURCES,
                           "manufacturing", service.resource,
                           {key: ManufacturingRecord for key in MANUFACTURING_RESOURCES})
