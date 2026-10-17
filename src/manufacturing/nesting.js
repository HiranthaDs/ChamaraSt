// Deterministic guillotine heuristics. All geometry is in millimetres.
const area = r => r.w * r.h;
export function optimize(sheet, requests, options = {}) {
  const { kerf = 3, margin = 10, rotate = true, grain = false, minOffcut = 150, rate = 12000, machineW = 3200, machineH = 1600 } = options;
  if (![sheet.w, sheet.h, sheet.thickness].every(n => Number.isFinite(n) && n > 0) || !Number.isInteger(sheet.cost) || sheet.cost < 0) throw Error('Enter valid sheet dimensions, thickness, and price.');
  if (sheet.w > machineW || sheet.h > machineH || sheet.thickness > 12) throw Error('This sheet exceeds the selected machine capacity (3200 × 1600 mm, 12 mm thickness).');
  if (![kerf, margin, minOffcut, rate].every(n => Number.isFinite(n) && n >= 0) || sheet.w <= 2 * margin || sheet.h <= 2 * margin) throw Error('Kerf, margins, and offcut threshold must fit the sheet.');
  if (!requests.length || requests.some(r => ![r.w, r.h, r.qty].every(n => Number.isFinite(n) && n > 0) || !Number.isInteger(r.qty)) || requests.reduce((n,r) => n+r.qty,0) > 200) throw Error('Enter positive dimensions and whole quantities, up to 200 pieces per plan.');
  const pieces = requests.flatMap((r, index) => Array.from({ length: r.qty }, (_, i) => ({ ...r, ref: `${r.label || `P${index + 1}`}-${i + 1}`, request: index })));
  const candidates = ['area', 'width', 'height'].map((strategy, idx) => {
    const pending = [...pieces].sort((a,b) => strategy === 'area' ? area(b)-area(a) : strategy === 'width' ? b.w-a.w || b.h-a.h : b.h-a.h || b.w-a.w);
    const free = [{ x: margin, y: margin, w: sheet.w - margin * 2, h: sheet.h - margin * 2 }];
    const placed = [], cuts = [], missing = [];
    for (const p of pending) {
      let best;
      free.forEach((f, fi) => {
        const orientations = rotate && !grain && p.w !== p.h ? [{w:p.w,h:p.h,rotated:false},{w:p.h,h:p.w,rotated:true}] : [{w:p.w,h:p.h,rotated:false}];
        orientations.forEach(o => { if (o.w <= f.w && o.h <= f.h) { const score = area(f) - area(o) + Math.min(f.w-o.w,f.h-o.h) / 10000; if (!best || score < best.score) best = {f, fi, o, score}; } });
      });
      if (!best) { missing.push(p); continue; }
      const {f,fi,o} = best; free.splice(fi,1);
      placed.push({ ...p, ...o, x:f.x, y:f.y });
      const kx = Math.min(kerf, f.w-o.w), ky = Math.min(kerf, f.h-o.h);
      const dw=f.w-o.w-kx, dh=f.h-o.h-ky;
      // Each split partitions the free rectangle into one part, two remnants, and kerf strips.
      const vertical = idx === 1 || (idx === 0 && dw > dh);
      if (vertical) {
        if(dw>0) free.push({x:f.x+o.w+kx,y:f.y,w:dw,h:f.h});
        if(dh>0) free.push({x:f.x,y:f.y+o.h+ky,w:o.w,h:dh});
        if(kx>0) cuts.push({x:f.x+o.w,y:f.y,w:kx,h:f.h});
        if(ky>0) cuts.push({x:f.x,y:f.y+o.h,w:o.w,h:ky});
      } else {
        if(dw>0) free.push({x:f.x+o.w+kx,y:f.y,w:dw,h:o.h});
        if(dh>0) free.push({x:f.x,y:f.y+o.h+ky,w:f.w,h:dh});
        if(kx>0) cuts.push({x:f.x+o.w,y:f.y,w:kx,h:o.h});
        if(ky>0) cuts.push({x:f.x,y:f.y+o.h,w:f.w,h:ky});
      }
    }
    const reusable = free.filter(f=> f.w>=minOffcut && f.h>=minOffcut);
    const scrap = free.filter(f=> f.w<minOffcut || f.h<minOffcut);
    const totalArea = area(sheet), partArea = placed.reduce((n,p)=>n+area(p),0), offcutArea = reusable.reduce((n,p)=>n+area(p),0);
    const kerfArea = cuts.reduce((n,p)=>n+area(p),0), trimArea=totalArea-(sheet.w-2*margin)*(sheet.h-2*margin);
    const lossArea=totalArea-partArea-offcutArea;
    const partCost=Math.floor(sheet.cost*partArea/totalArea), offcutCost=Math.floor(sheet.cost*offcutArea/totalArea), lossCost=sheet.cost-partCost-offcutCost;
    const cutLength=cuts.reduce((n,c)=>n+Math.max(c.w,c.h),0)/1000;
    const minutes=Math.ceil(4+cutLength/1.2+placed.length*.4), cuttingCost=Math.round(minutes*rate/60);
    return { id: `layout-${idx}`, strategy, placed, cuts, reusable, scrap, missing, totalArea, partArea, offcutArea, kerfArea, trimArea, lossArea, partCost, offcutCost, lossCost, cuttingCost, minutes, cutLength, utilization:partArea/totalArea*100, feasible:missing.length===0 };
  });
  return candidates.sort((a,b)=>Number(b.feasible)-Number(a.feasible)||a.lossArea-b.lossArea||a.cuttingCost-b.cuttingCost);
}

export function planSvg(sheet, plan, grid = false) {
  const rect = (r, fill, label='') => `<g><rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" fill="${fill}" stroke="#fff" stroke-width="3"/>${label ? `<text x="${r.x+r.w/2}" y="${r.y+r.h/2}" text-anchor="middle" dominant-baseline="middle" font-size="${Math.max(16,Math.min(45,r.w/8,r.h/4))}" fill="#153d60" font-family="sans-serif">${label}</text>`:''}</g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-60 -90 ${sheet.w+120} ${sheet.h+160}"><rect x="0" y="0" width="${sheet.w}" height="${sheet.h}" fill="#f1dedb" stroke="#627182" stroke-width="5"/>${grid?`<defs><pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse"><path d="M100 0H0V100" fill="none" stroke="#64748b" stroke-opacity=".12" stroke-width="2"/></pattern></defs><rect width="${sheet.w}" height="${sheet.h}" fill="url(#grid)"/>`:''}${plan.reusable.map(r=>rect(r,'#f3cf81')).join('')}${plan.scrap.map(r=>rect(r,'#e8a8a0')).join('')}${plan.placed.map((r,i)=>rect(r,'#a6cce9',`${i+1} · ${r.w} × ${r.h}`)).join('')}${plan.cuts.map(r=>rect(r,'#d77c70')).join('')}<text x="${sheet.w/2}" y="-35" text-anchor="middle" font-size="40" fill="#64748b" font-family="sans-serif">${sheet.w} mm</text><text x="${sheet.w/2}" y="${sheet.h+55}" text-anchor="middle" font-size="30" fill="#64748b" font-family="sans-serif">${plan.placed.length} pieces · ${plan.utilization.toFixed(1)}% part utilization</text></svg>`;
}
