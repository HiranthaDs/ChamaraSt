from fastapi import APIRouter, Depends
from backend.app.db.postgres import get_connection
from backend.app.features.production_jobs.router import actor_context, attachment_response
from backend.app.features.production_jobs.models import Note, DocumentInput
from backend.app.features.production_jobs.service import JobService
from .models import ProposalInput, ProposalEdit, ProposalStatusAction, ReviewInput, EstimateInput, PrototypeInput, PrototypeTest, ConversionInput
from .repository import ProposalRepository
from .service import ProposalService

router=APIRouter(prefix='/api/product-proposals',tags=['Product development'])
def service(actor=Depends(actor_context)):
    with get_connection() as db: yield ProposalService(ProposalRepository(db),actor)

@router.get('')
def proposals(svc=Depends(service)): return svc.list()
@router.post('',status_code=201)
def create(body:ProposalInput,svc=Depends(service)): return svc.save(body)
@router.get('/{proposal_id}')
def detail(proposal_id:str,svc=Depends(service)): return svc.detail(proposal_id)
@router.put('/{proposal_id}')
def revise(proposal_id:str,body:ProposalEdit,svc=Depends(service)): return svc.save(body,proposal_id)
@router.post('/{proposal_id}/status')
def status(proposal_id:str,body:ProposalStatusAction,svc=Depends(service)): return svc.status(proposal_id,body)
@router.post('/{proposal_id}/reviews')
def review(proposal_id:str,body:ReviewInput,svc=Depends(service)): return svc.review(proposal_id,body)
@router.post('/{proposal_id}/estimates')
def estimate(proposal_id:str,body:EstimateInput,svc=Depends(service)): return svc.estimate(proposal_id,body)
@router.post('/{proposal_id}/prototypes')
def prototype(proposal_id:str,body:PrototypeInput,svc=Depends(service)): return svc.prototype(proposal_id,body)
@router.post('/{proposal_id}/prototypes/{prototype_id}/tests')
def test(proposal_id:str,prototype_id:str,body:PrototypeTest,svc=Depends(service)): return svc.test(proposal_id,prototype_id,body)
@router.post('/{proposal_id}/convert')
def convert(proposal_id:str,body:ConversionInput,svc=Depends(service)): return svc.convert(proposal_id,body)
@router.post('/{proposal_id}/comments')
def comment(proposal_id:str,body:Note,svc=Depends(service)):
    svc.get(proposal_id,True); svc.repo.activity(svc.actor,'Comment',proposal=proposal_id,details={'text':body.text})
    return svc.detail(proposal_id)
@router.post('/{proposal_id}/documents')
def document(proposal_id:str,body:DocumentInput,svc=Depends(service)):
    svc.get(proposal_id,True)
    return JobService(svc.repo,svc.actor).document(body,proposal=proposal_id)
@router.get('/{proposal_id}/documents/{document_id}')
def download(proposal_id:str,document_id:str,svc=Depends(service)):
    svc.get(proposal_id)
    return attachment_response(svc.repo.one('select * from public.production_workflow_documents where proposal_id=%s and id=%s',(proposal_id,document_id)))
