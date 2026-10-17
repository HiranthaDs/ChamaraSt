"""Bounded deterministic bottom-left search, with exact finished-circle predicates.

Kerf convention: independently offset contour cuts, no shared-line cutting.
Finished-edge gap = 2*kerf + spacing + heat spacing. The tool centre is
kerf/2 outside the finished edge; the swept tool extends one kerf outside.
Polygonized circles are used ONLY for conservative remnant estimates.
"""
import math
import time
from collections import Counter
from shapely.geometry import Polygon, Point, box, shape, mapping
from shapely.affinity import rotate, translate
from shapely.ops import unary_union
from .cutting_models import Placement

EPS = 1e-7


def polygon(vertices):
    if len(vertices) < 3 or len(vertices) > 100 or any(not math.isfinite(v) or abs(v)>20000 for p in vertices for v in p):
        raise ValueError('Provide 3–100 finite polygon vertices within 20,000 mm.')
    g = Polygon(vertices)
    if not g.is_valid or g.area <= EPS:
        raise ValueError('Polygon must be simple, non-degenerate and non-self-intersecting.')
    return g


def stock(s):
    if not s.geometry:
        return box(0, 0, s.w, s.h)
    if s.geometry.get('type') != 'Polygon' or len(str(s.geometry)) > 120000:
        raise ValueError('Stock geometry must be a bounded GeoJSON Polygon.')
    g = shape(s.geometry)
    if not g.is_valid or g.is_empty or not box(0,0,s.w,s.h).covers(g):
        raise ValueError('Invalid offcut geometry or geometry outside sheet dimensions.')
    return g


def local(part, angle):
    if part.shape == 'circle':
        r=part.diameter/2
        return Point(r,r), r, part.diameter, part.diameter
    if part.shape in {'triangle','polygon'}:
        if part.shape=='triangle' and len(part.vertices)!=3:
            raise ValueError('Triangles require exactly three vertices.')
        g=polygon(part.vertices)
    else:
        g=box(0,0,part.w,part.w if part.shape=='square' else part.h)
    g=rotate(g,angle,origin=(0,0))
    a,b,c,d=g.bounds
    return translate(g,-a,-b),0,c-a,d-b


def geometry(part, placement):
    g,r,w,h=local(part,placement.rotation)
    return translate(g,placement.x,placement.y),r,w,h


def finished_area(g,r):
    return math.pi*r*r if r else g.area


def outline(g,r):
    # Circumscribed 512-gon: never overstates leftover material around circles.
    return g.buffer(r/math.cos(math.pi/512),quad_segs=128) if r else g


def compatible(p,s):
    return (p.material,p.grade,p.thickness)==(s.material,s.grade,s.thickness)


def allowed(part,angle):
    angles=[0] if part.grain else part.rotations
    return any(abs((angle-a+180)%360-180)<EPS for a in angles)


def collides(a,ar,b,br,gap):
    if ar or br:
        return a.distance(b) < ar+br+gap-EPS
    return a.intersection(b).area>EPS or a.distance(b)<gap-EPS


def fits(g,r,usable,zones,placed,gap):
    if r:
        if not usable.covers(g) or g.distance(usable.boundary)<r-EPS: return False
    elif not usable.buffer(EPS).covers(g): return False
    return not any(collides(g,r,z,0,gap/2) for z in zones) and not any(collides(g,r,h,hr,gap) for h,hr in placed)


def prepare(inp):
    c=inp.constraints
    zones=[polygon(z) for z in c.zones]
    prepared={}
    for s in inp.sheets:
        g=stock(s)
        if s.w>c.machine_w or s.h>c.machine_h or s.thickness>c.machine_thickness:
            raise ValueError('Sheet exceeds configured machine cutting capacity.')
        usable=g.buffer(-(c.edge+c.kerf),join_style=2)
        if usable.is_empty: raise ValueError('Edge clearance and kerf leave no usable sheet.')
        prepared[s.id]=(s,g,usable)
    for p in inp.parts:
        for a in ([0] if p.grain else p.rotations): local(p,a)
    return prepared,zones


def validate(inp, placements, mode='fast'):
    prepared,zones=prepare(inp); parts={p.id:p for p in inp.parts}; seen=set(); groups={}; errors=[]
    gap=2*inp.constraints.kerf+inp.constraints.spacing+inp.constraints.heat_spacing
    for i,t in enumerate(placements):
        p=parts.get(t.part_id); entry=prepared.get(t.sheet_id)
        error=None
        if not p or not entry: error='Unknown part or sheet'
        elif t.instance>p.quantity or (t.part_id,t.instance) in seen: error='Duplicate or excess part instance'
        elif t.sheet_instance>entry[0].quantity: error='Sheet quantity exceeded'
        elif not compatible(p,entry[0]): error='Incompatible material, grade or thickness'
        elif not allowed(p,t.rotation): error='Rotation violates grain or allowed angles'
        else:
            g,r,w,h=geometry(p,t); key=(t.sheet_id,t.sheet_instance)
            existing=groups.setdefault(key,[])
            if not fits(g,r,entry[2],zones,[(x[2],x[3]) for x in existing],gap): error='Collision, clearance, restricted zone or sheet boundary violation'
            existing.append((t,p,g,r,w,h))
        seen.add((t.part_id,t.instance))
        if error: errors.append({'index':i,'part_id':t.part_id,'instance':t.instance,'message':error})
    if errors: return {'valid':False,'errors':errors,'placements':[p.model_dump() for p in placements]}
    sheets=[]
    for (sid,number),rows in groups.items():
        s,raw,_=prepared[sid]; c=inp.constraints
        contours=[outline(g,r) for _,_,g,r,_,_ in rows]
        swept=unary_union([g.buffer(c.kerf,quad_segs=32,join_style=2) for g in contours]).intersection(raw)
        part_area=sum(finished_area(g,r) for _,_,g,r,_,_ in rows)
        kerf=max(0,swept.area-part_area)
        remaining=raw.difference(swept.union(unary_union(zones)))
        # Morphological opening excludes narrow remnants; original holes are retained.
        radius=c.min_offcut/2
        reusable=remaining.buffer(-radius).buffer(radius).intersection(remaining)
        regions=list(reusable.geoms) if reusable.geom_type=='MultiPolygon' else ([reusable] if reusable.geom_type=='Polygon' and not reusable.is_empty else [])
        offcuts=[{'id':f'{sid}:{number}:{i}', 'geometry':mapping(g),'area':g.area} for i,g in enumerate(regions) if g.area>EPS]
        off_area=sum(x['area'] for x in offcuts)
        part_cost=math.floor(s.cost*part_area/raw.area); off_cost=math.floor(s.cost*off_area/raw.area)
        sheets.append({'sheet_id':sid,'sheet_instance':number,'sheet':s.model_dump(),'placements':[
            {**t.model_dump(),'name':p.name,'shape':p.shape,'w':w,'h':h,'radius':r,'area':finished_area(g,r),
             'geometry':mapping(g),'dimensions':f'Ø {p.diameter:g}' if r else f'{w:g} × {h:g}'} for t,p,g,r,w,h in rows],
            'offcuts':offcuts,'total_area':raw.area,'part_area':part_area,'kerf_area':kerf,'offcut_area':off_area,
            'scrap_area':max(0,raw.area-part_area-kerf-off_area),'material_cost':s.cost,'part_cost':part_cost,
            'offcut_cost':off_cost,'scrap_cost':s.cost-part_cost-off_cost})
    used=Counter(t.part_id for t in placements)
    missing=[{'part_id':p.id,'name':p.name,'quantity':p.quantity-used[p.id]} for p in inp.parts if used[p.id]<p.quantity]
    totals={k:sum(s[k] for s in sheets) for k in ['total_area','part_area','kerf_area','offcut_area','scrap_area','material_cost','part_cost','offcut_cost','scrap_cost']}
    return {'valid':True,'errors':[],'mode':mode,'placements':[p.model_dump() for p in placements], 'sheets':sheets,
            'missing':missing,'placed':len(placements),'feasible':not missing,'totals':totals,
            'utilization':100*totals['part_area']/totals['total_area'] if totals['total_area'] else 0,
            # Existing manufacturing insight reports use these names.
            'totalArea':totals['total_area'],'partArea':totals['part_area'],'offcutArea':totals['offcut_area'],
            'kerfArea':totals['kerf_area'],'lossArea':totals['scrap_area']+totals['kerf_area'],
            'partCost':totals['part_cost'],'offcutCost':totals['offcut_cost'],'lossCost':totals['scrap_cost'],'cuttingCost':0}


def candidates(p,s,usable,rows,angle,gap,orientation):
    _,r,w,h=local(p,angle); x0,y0,x1,y1=usable.bounds
    xs={x0}; ys={y0}; contacts=[]
    for t,other,gr,rr,ow,oh in rows:
        xs.update([t.x,t.x+ow+gap]); ys.update([t.y,t.y+oh+gap])
        if r and rr:
            distance=r+rr+gap
            for deg in range(0,360,30):
                a=math.radians(deg)
                contacts.append((gr.x+distance*math.cos(a)-r,gr.y+distance*math.sin(a)-r))
    # Grid and both stagger orientations for circles, including finite sheet edges.
    if r:
        pitch=2*r+gap; row_pitch=pitch*(math.sqrt(3)/2 if orientation else 1)
        for j in range(min(150,int((y1-y0)/row_pitch)+1)):
            y=y0+j*row_pitch
            for i in range(min(150,int((x1-x0)/pitch)+1)):
                contacts.append((x0+i*pitch+(pitch/2 if orientation and j%2 else 0),y))
        if orientation==2:
            contacts.extend((x0+(y-y0),y0+(x-x0)) for x,y in list(contacts))
    # Limit search sites deterministically while retaining early bottom-left contacts.
    contacts.extend((x,y) for y in sorted(ys)[:50] for x in sorted(xs)[:50])
    return sorted({(round(x,7),round(y,7)) for x,y in contacts if x>=x0-EPS and y>=y0-EPS and x+w<=x1+EPS and y+h<=y1+EPS},key=lambda q:(q[1],q[0]))[:5000]


def optimize(inp,mode='fast'):
    start=time.monotonic(); deadline=start+inp.constraints.seconds
    prepared,zones=prepare(inp); gap=2*inp.constraints.kerf+inp.constraints.spacing+inp.constraints.heat_spacing
    pieces=[(p,i) for p in inp.parts for i in range(1,p.quantity+1)]
    best=None; attempts=0; timed_out=False
    for strategy in range(1 if mode=='fast' else 4):
        if time.monotonic()>deadline: timed_out=True; break
        seq=sorted(pieces,key=lambda q:(-q[0].priority, -(finished_area(*local(q[0],0)[:2]) if strategy%2==0 else max(local(q[0],0)[2:])),q[0].id,q[1]))
        stock_order=sorted(inp.sheets,key=lambda s:((not s.offcut) if mode=='offcut-first' else 0,s.cost/(s.w*s.h),-(s.w*s.h)))
        opened={}; placements=[]
        for p,instance in seq:
            placed=False
            # Fill open sheets before opening additional sheets.
            keys=list(opened)+[(s.id,n) for s in stock_order for n in range(1,s.quantity+1) if (s.id,n) not in opened]
            for key in keys:
                s,raw,usable=prepared[key[0]]
                if not compatible(p,s): continue
                rows=opened.get(key,[])
                for angle in ([0] if p.grain else p.rotations):
                    for x,y in candidates(p,s,usable,rows,angle,gap,strategy%3):
                        if time.monotonic()>deadline: timed_out=True; break
                        t=Placement(part_id=p.id,instance=instance,sheet_id=s.id,sheet_instance=key[1],x=max(0,x),y=max(0,y),rotation=angle)
                        g,r,w,h=geometry(p,t)
                        if fits(g,r,usable,zones,[(a[2],a[3]) for a in rows],gap):
                            opened.setdefault(key,[]).append((t,p,g,r,w,h));placements.append(t);placed=True;break
                    if placed or timed_out: break
                if placed or timed_out: break
            if timed_out: break
        result=validate(inp,placements,mode); attempts+=1
        score=lambda a:(sum(x['quantity'] for x in a['missing']),len(a['sheets']),a['totals']['total_area'],a['totals']['scrap_area'],a['totals']['material_cost'])
        if best is None or score(result)<score(best): best=result
        if timed_out: break
    if best is None: best=validate(inp,[],mode)
    best.update(duration_ms=round((time.monotonic()-start)*1000),attempts=attempts,timed_out=timed_out)
    return best
