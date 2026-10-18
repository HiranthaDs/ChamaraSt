from backend.app.shared.crud_router import collection_router
from backend.app.features.finance.repository import FINANCE_RESOURCES
from backend.app.features.finance.service import FinanceService
from backend.app.features.finance.models import ExpenseRecord, InvoiceRecord

service = FinanceService()
router = collection_router("/api/finance", "Finance", FINANCE_RESOURCES,
                           service_provider=service.resource,
                           schemas={"invoices": InvoiceRecord, "expenses": ExpenseRecord})
