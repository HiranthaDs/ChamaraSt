import unittest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from backend.app.features.gate_passes.policy import authorize_action, effective_status, token_hash, return_status


class GatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(status='PENDING_APPROVAL', valid_until=datetime.now(timezone.utc)+timedelta(hours=1), requester_id='requester', verified_by='warehouse', approval_roles=['Supervisor'], inspected_by=None, return_required=True)

    def test_requester_cannot_approve(self):
        with self.assertRaises(HTTPException):
            authorize_action({'id':'requester','role':'Supervisor'},self.row,'approve',[])

    def test_warehouse_cannot_approve_own_verification(self):
        with self.assertRaises(HTTPException):
            authorize_action({'id':'warehouse','role':'Supervisor'},self.row,'approve',[])

    def test_independent_supervisor_can_approve(self):
        authorize_action({'id':'approver','role':'Supervisor'},self.row,'approve',[])

    def test_expired_pass_cannot_move(self):
        self.row.update(status='READY_AT_GATE', valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
        self.assertEqual(effective_status(self.row),'EXPIRED')
        with self.assertRaises(HTTPException):
            authorize_action({'id':'security','role':'Gate Security Officer'},self.row,'inspect',[])

    def test_completed_pass_cannot_replay(self):
        self.row['status']='COMPLETED'
        with self.assertRaises(HTTPException):
            authorize_action({'id':'security','role':'Gate Security Officer'},self.row,'confirm',[])

    def test_other_inspector_cannot_confirm(self):
        self.row.update(status='UNDER_GATE_INSPECTION',inspected_by='security1')
        with self.assertRaises(HTTPException):
            authorize_action({'id':'security2','role':'Gate Security Officer'},self.row,'confirm',[])

    def test_return_states(self):
        items=[dict(moved_quantity=5,returned_quantity=2,written_off_quantity=0)]
        self.assertEqual(return_status(items,None),'PARTIALLY_RETURNED')
        self.assertEqual(return_status(items,datetime.now(timezone.utc)-timedelta(days=1)),'OVERDUE')
        items[0]['returned_quantity']=5
        self.assertEqual(return_status(items,None),'FULLY_RETURNED')

    def test_token_is_not_stored_in_plaintext(self):
        self.assertNotEqual(token_hash('secret-token'),'secret-token')
        self.assertNotEqual(token_hash('secret-token'),token_hash('changed-token'))


if __name__=='__main__':
    unittest.main()
