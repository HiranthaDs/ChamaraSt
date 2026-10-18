export function historyChange(history, next) {
  return {past:[...history.past,history.present].slice(-50),present:next,future:[]};
}
export function historyUndo(h) {return h.past.length?{past:h.past.slice(0,-1),present:h.past.at(-1),future:[h.present,...h.future]}:h;}
export function historyRedo(h) {return h.future.length?{past:[...h.past,h.present],present:h.future[0],future:h.future.slice(1)}:h;}
export function partGeometry(p,t) {
  if(p.shape==='circle')return {circle:true,cx:t.x+p.diameter/2,cy:t.y+p.diameter/2,r:p.diameter/2,w:p.diameter,h:p.diameter};
  const raw=['polygon','triangle'].includes(p.shape)?p.vertices:[[0,0],[p.w,0],[p.w,p.shape==='square'?p.w:p.h],[0,p.shape==='square'?p.w:p.h]];
  const a=t.rotation*Math.PI/180,points=raw.map(([x,y])=>[x*Math.cos(a)-y*Math.sin(a),x*Math.sin(a)+y*Math.cos(a)]);
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),minX=Math.min(...xs),minY=Math.min(...ys),w=Math.max(...xs)-minX,h=Math.max(...ys)-minY;
  return {points:points.map(([x,y])=>[x-minX+t.x,y-minY+t.y]),w,h,cx:t.x+w/2,cy:t.y+h/2};
}
export const geometryPath=g=>g.coordinates.map(r=>'M '+r.map(p=>p.join(',')).join(' L ')+' Z').join(' ');
