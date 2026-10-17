"""Browser-test bridge to the real geometry engine; no database writes."""
import json
import sys
from backend.app.features.manufacturing.cutting_models import CuttingInput,LayoutInput
from backend.app.features.manufacturing.cutting_engine import optimize,validate
body=json.load(sys.stdin)
try:
    if sys.argv[1]=='preview':
        inp=CuttingInput.model_validate(body)
        result={'inputs':inp.model_dump(),'candidates':[optimize(inp,m) for m in ['fast','maximum','offcut-first']]}
    else:
        req=LayoutInput.model_validate(body)
        result=validate(req.inputs,req.placements,req.mode)
    print(json.dumps(result))
except ValueError as e:
    print(json.dumps({'detail':str(e)}))
