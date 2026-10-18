from html import escape
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4, landscape


def path_data(geometry):
    return ' '.join('M '+' L '.join(f'{x:g},{y:g}' for x,y in ring)+' Z' for ring in geometry['coordinates'])


def svg(layout, index=0):
    page=layout['sheets'][index];s=page['sheet'];w,h=s['w'],s['h']
    items=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w+120}mm" height="{h+160}mm" viewBox="-60 -80 {w+120} {h+160}">',
           '<title>Dimensioned visual cutting plan — not machine instructions</title>',f'<rect width="{w}" height="{h}" fill="#f5e5e1" stroke="#334155"/>']
    for o in page['offcuts']: items.append(f'<path d="{path_data(o["geometry"])}" fill="#f6d790" fill-rule="evenodd"/>')
    for p in page['placements']:
        if p['radius']:
            x,y=p['geometry']['coordinates'];items.append(f'<circle cx="{x}" cy="{y}" r="{p["radius"]}" fill="#a5d9c8" stroke="#234859"/>')
        else: items.append(f'<path d="{path_data(p["geometry"])}" fill="#a5cce9" stroke="#234859" fill-rule="evenodd"/>')
        items.append(f'<text x="{p["x"]+p["w"]/2}" y="{p["y"]+p["h"]/2}" text-anchor="middle" font-family="sans-serif" font-size="{min(24,p["w"]/10,p["h"]/5)}">{escape(p["name"])} #{p["instance"]} · {escape(p["dimensions"])} mm</text>')
    items.extend([f'<text x="0" y="-25" font-size="24">{w:g} × {h:g} mm · {layout["utilization"]:.2f}% utilization</text>',
        f'<text x="0" y="{h+40}" font-size="18">Visual plan only; verify machine setup. All coordinates in mm.</text>','</svg>'])
    return ''.join(items)


def pdf(layout):
    output=BytesIO();canvas=Canvas(output,pagesize=landscape(A4));pw,ph=landscape(A4)
    for page in layout['sheets']:
        s=page['sheet'];scale=min((pw-80)/s['w'],(ph-110)/s['h'])
        canvas.setFont('Helvetica',11);canvas.drawString(35,ph-25,f"Cutting plan | {s['w']:g} x {s['h']:g} mm | {layout['utilization']:.2f}% utilization")
        canvas.setFont('Helvetica',8);canvas.drawString(35,20,'Visual plan only. Not machine instructions. Dimensions in mm; diagram scaled to page.')
        canvas.saveState();canvas.translate(40,ph-65);canvas.scale(scale,-scale)
        canvas.setLineWidth(1/scale);canvas.setFillColorRGB(.95,.93,.91);canvas.rect(0,0,s['w'],s['h'],fill=1)
        def poly(geo):
            path=canvas.beginPath()
            for ring in geo['coordinates']:
                path.moveTo(*ring[0])
                for xy in ring[1:]:path.lineTo(*xy)
                path.close()
            canvas.drawPath(path,fill=1,stroke=1,fillMode=0)
        canvas.setFillColorRGB(.96,.84,.56)
        for o in page['offcuts']: poly(o['geometry'])
        for p in page['placements']:
            canvas.setFillColorRGB(.64,.8,.9)
            if p['radius']:canvas.circle(*p['geometry']['coordinates'],p['radius'],fill=1)
            else:poly(p['geometry'])
            canvas.saveState();canvas.translate(p['x']+p['w']/2,p['y']+p['h']/2);canvas.scale(1,-1);canvas.setFillColorRGB(.1,.2,.3);canvas.setFont('Helvetica',min(22,p['w']/12,p['h']/6));canvas.drawCentredString(0,0,f"{p['name']} #{p['instance']}");canvas.drawCentredString(0,-min(25,p['h']/5),p['dimensions']+' mm');canvas.restoreState()
        canvas.restoreState();canvas.showPage()
    canvas.save();return output.getvalue()
