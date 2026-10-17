from backend.app.features.production_jobs.repository import WorkflowRepository

class ProposalRepository(WorkflowRepository):
    """Shares the ERP transaction, HR master, audit, and notification infrastructure."""
    def proposal(self, proposal_id):
        return self.one('select * from public.product_proposals where id=%s',(proposal_id,))
    def current_version(self, proposal):
        return self.one('select * from public.product_proposal_versions where proposal_id=%s and version_number=%s',(proposal['id'],proposal['current_version']))
