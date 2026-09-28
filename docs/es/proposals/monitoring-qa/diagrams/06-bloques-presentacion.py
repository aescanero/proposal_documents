#!/usr/bin/env python3
"""Genera 06-bloques-presentacion.svg (1920x1080, orientado a presentación).

Diagrama dibujado a mano, sin Mermaid: la fuente es este script. Para cambiar
el SVG se edita aquí y se ejecuta `python3 06-bloques-presentacion.py`.
Mismo estilo que keycloak-qa/diagrams/09-bloques-presentacion.py.
"""
import os
from xml.sax.saxutils import escape as e
W,H=1920,1080
FONT="'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO="'JetBrains Mono','SFMono-Regular',Consolas,monospace"
TXT="#1f2937"; SUB="#4b5563"
pal={'fund':('#eaf1ff','#2563eb'),'prot':('#fff5e6','#c2410c'),'app':('#e9f7ee','#15803d'),'ops':('#f4ecff','#7e22ce'),'plat':('#f3f4f6','#6b7280'),'out':('#ecfeff','#0e7490'),'up':('#fef9c3','#a16207')}
o=[]
def rect(x,y,w,h,fill,stroke,rx=14,sw=2,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def text(x,y,s,size=16,weight=400,fill=TXT,anchor='start',font=FONT,italic=False):
    st=' font-style="italic"' if italic else ''
    o.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{st}>{e(s)}</text>')
def header(x,y,w,key,num,name):
    bg,fg=pal[key]
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="46" rx="12" fill="{bg}"/>')
    o.append(f'<rect x="{x}" y="{y+34}" width="{w}" height="12" fill="{bg}"/>')
    o.append(f'<line x1="{x}" y1="{y+46}" x2="{x+w}" y2="{y+46}" stroke="{fg}" stroke-width="1"/>')
    o.append(f'<circle cx="{x+24}" cy="{y+23}" r="14" fill="{fg}"/>')
    text(x+24,y+29,str(num),15,700,'#ffffff','middle')
    text(x+48,y+31,name,21,700,fg,font=MONO)
def stack(x,y,w,h,key,num,name,purpose,bullets):
    rect(x,y,w,h,'#ffffff',pal[key][1],rx=12,sw=2)
    header(x,y,w,key,num,name)
    text(x+16,y+76,purpose,16,600,TXT)
    yy=y+104
    for b in bullets:
        o.append(f'<circle cx="{x+22}" cy="{yy-5}" r="3" fill="{pal[key][1]}"/>')
        text(x+32,yy,b,14,400,SUB); yy+=24
def arrow(x1,y1,x2,y2,color='#9ca3af',w=3):
    o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}" marker-end="url(#ah)"/>')

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Arquetipo monitoring-oss: bloques y stacks">')
o.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9ca3af"/></marker>'
         '<filter id="sh" x="-5%" y="-5%" width="110%" height="115%"><feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#111827" flood-opacity="0.08"/></filter></defs>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# título
text(60,72,"Monitorización — arquetipo de capa 3, proveedor de monitoring",40,800)
text(60,108,"monitoring-oss · entorno qa · GCP disasterproject-nonprod · 9 stacks · Prometheus, Alertmanager, Loki, Fluent Bit, Grafana · capa 1b vigila a la capa 3",19,400,SUB)
o.append(f'<rect x="60" y="124" width="120" height="5" rx="2" fill="{pal["fund"][1]}"/>')

LX,LY,LW,LH=40,160,330,670
rect(LX,LY,LW,LH,pal['plat'][0],'#d1d5db',rx=18,sw=1.5)
text(LX+24,LY+44,"Consume de la plataforma",22,700)
text(LX+24,LY+70,"una capability, un proveedor",15,400,SUB,italic=True)
caps=[("cluster","daemonset-privileged · hostpath",False),("policy","Gatekeeper · excepción acotada",False),("secrets","ESO · trait eso",False),
      ("certs","webhook del operador",False),("ingress","HTTPRoute de Grafana",False),("oidc-idp","NO: ciclo; URL por convención",True)]
y=LY+92
for c,d,dashed in caps:
    rect(LX+20,y,LW-40,74,'#ffffff','#d1d5db',rx=10,sw=1.5,dash="5 4" if dashed else None)
    text(LX+38,y+32,c,18,700,'#374151',font=MONO)
    text(LX+38,y+57,d,15,400,SUB)
    y+=94

CX,CY,CW,CH=420,160,1100,670
o.append(f'<g filter="url(#sh)">'); rect(CX,CY,CW,CH,'#fbfcff',pal['fund'][1],rx=22,sw=3); o.append('</g>')
text(CX+30,CY+44,"archetypes/monitoring-oss",24,800,pal['fund'][1],font=MONO)
text(CX+CW-30,CY+44,"kind: catalog · layer 3 · v0.1.0",17,500,SUB,'end',font=MONO)
cols=[('fund',"1 · Fundación"),('prot',"2 · Seguridad y CRDs"),('app',"3 · Métricas y alertas"),('ops',"4 · Logs y visualización")]
colw=245; gap=25; x0=CX+30; ytop=CY+72
xs=[x0+i*(colw+gap) for i in range(4)]
for (k,t),x in zip(cols,xs):
    text(x,ytop+18,t,17,700,pal[k][1])
    o.append(f'<line x1="{x}" y1="{ytop+28}" x2="{x+colw}" y2="{ytop+28}" stroke="{pal[k][1]}" stroke-width="2" opacity="0.35"/>')
by=ytop+42; bh=170; bg=14
stack(xs[0],by,colw,bh,'fund',1,"iam","Namespaces e identidades",["monitoring: restricted","monitoring-agents: privileged","KSA eso · loki · grafana"])
stack(xs[0],by+bh+bg,colw,bh,'fund',2,"secrets","Por ESO",["admin y OIDC de Grafana","receptores de Alertmanager","qa-monitoring-oss-*"])
stack(xs[0],by+2*(bh+bg),colw,bh,'fund',3,"storage","Bucket de Loki",["GCS regional · 35 días","objectAdmin solo al bucket","monitoring.viewer: Grafana"])
stack(xs[1],by,colw,bh,'prot',4,"firewall","Red cerrada por defecto",["scrape a todos los ns","webhook en 10250","NAT: receptores y sondas"])
stack(xs[1],by+bh+bg,colw,bh,'prot',5,"crds","prometheus-operator",["stack propio","resource-policy: keep","borrarlos = sin alertas"])
nx,ny=xs[1],by+2*(bh+bg)
rect(nx,ny,colw,bh,'#fffaf3',pal['prot'][1],rx=12,sw=1.5,dash="6 5")
text(nx+16,ny+34,"Agentes privilegiados",16,700,pal['prot'][1])
for i,l in enumerate(["node-exporter y Fluent Bit","en su namespace; solo","dos imágenes por digest,","hostPath de lista cerrada."]):
    text(nx+16,ny+64+i*24,l,14,400,SUB)

ax,ay,aw,ah=xs[2],by,colw,3*bh+2*bg
bgc,fg=pal['app']
rect(ax,ay,aw,ah,'#ffffff',fg,rx=12,sw=3)
header(ax,ay,aw,'app',6,"metrics")
text(ax+16,ay+76,"kube-prometheus-stack",15,600)
text(ax+16,ay+98,"+ blackbox · reglas de plataforma",14,400,SUB)
blocks=[("Prometheus","1 réplica · 15 días · 50 GiB"),("Alertmanager × 2","críticas siempre, avisos 8–19"),("KSM · node-exporter","blackbox: http_2xx")]
yy=ay+118
for n,d in blocks:
    rect(ax+16,yy,aw-32,62,bgc,fg,rx=8,sw=1.2)
    text(ax+30,yy+26,n,15,700,TXT); text(ax+30,yy+48,d,14,400,SUB); yy+=72
text(ax+16,yy+14,"prometheus=qa en todo",14,600,fg,font=MONO)
yy+=34
rect(ax+16,yy,aw-32,52,'#ffffff',fg,rx=8,sw=1.2,dash="4 4")
text(ax+30,yy+22,"límites forzados",14,600,TXT); text(ax+30,yy+42,"20 000 muestras por scrape",13,400,SUB)
yy+=64
rect(ax+16,yy,aw-32,74,'#f9fafb','#9ca3af',rx=8,sw=1.2)
text(ax+30,yy+24,"reglas de capa ≤ 3",14,700,TXT); text(ax+30,yy+45,"GKE · Gatekeeper · ESO",13,400,SUB); text(ax+30,yy+64,"cert-manager · Envoy",13,400,SUB)

stack(xs[3],by,colw,bh,'ops',7,"logs","Loki monolítico",["Fluent Bit en cada nodo","30 días · un tenant","sin tokens ni cookies"])
stack(xs[3],by+bh+bg,colw,bh,'ops',8,"grafana","Dashboards como código",["OIDC con Keycloak","sre: Admin · equipos: Viewer","Explore solo para SRE"])
stack(xs[3],by+2*(bh+bg),colw,bh,'ops',9,"frontdoor","Publicación",["grafana.tqbvzkr.…","sin SecurityPolicy","Prometheus y Loki: no"])
for i in range(3):
    cx=xs[i]+colw+gap/2; cy=by+ah/2
    o.append(f'<path d="M{cx-6},{cy-14} L{cx+6},{cy} L{cx-6},{cy+14}" fill="none" stroke="#9ca3af" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
arrow(LX+LW+4,CY+CH/2,CX-6,CY+CH/2)

RX,RY,RW,RH=1570,160,310,670
rect(RX,RY,RW,RH,pal['out'][0],'#a5f3fc',rx=18,sw=1.5)
text(RX+24,RY+44,"Provee monitoring 1.8.0",22,700)
text(RX+24,RY+70,"trait prometheus-operator-crds",15,400,SUB,italic=True)
items=[('out',"SonarQube · Keycloak","PodMonitor · Probe · reglas","dashboards por ConfigMap"),
       ('out',"Plataforma (capa ≤ 3)","reglas declaradas aquí","sin ciclo en la capa 3"),
       ('out',"Personas","Grafana por OIDC","carpetas por equipo"),
       ('up',"Capa 1b (vigila)","dead-man's switch","Cloud Monitoring · mismo canal")]
y=RY+92
for k,t,a,b in items:
    fill='#fffdf0' if k=='up' else '#ffffff'
    rect(RX+20,y,RW-40,128,fill,pal[k][1] if k=='up' else '#a5f3fc',rx=10,sw=1.5)
    text(RX+38,y+36,t,19,700,pal[k][1]); text(RX+38,y+68,a,15,400,SUB); text(RX+38,y+96,b,14,400,SUB)
    y+=142
arrow(CX+CW+6,CY+CH/2,RX-6,CY+CH/2)

BY=858
text(60,BY+30,"Controles",20,700)
ctrl=[("assert","CRDs keep · límites · 10250"),("G1 promtool","reglas válidas · prometheus=qa"),("Gatekeeper","namespace de agentes acotado"),
      ("G1 conftest","monitoring.viewer: excepción"),("capa 1b","Prometheus caído → aviso")]
x=60; cw=364
for i,(a,b) in enumerate(ctrl):
    rect(x,BY+48,cw-20,74,'#ffffff','#d1d5db',rx=10,sw=1.5)
    text(x+18,BY+78,a,17,700,'#374151',font=MONO); text(x+18,BY+104,b,14,400,SUB)
    if i<4: o.append(f'<path d="M{x+cw-16},{BY+78} l8,7 l-8,7" fill="none" stroke="#9ca3af" stroke-width="2.5"/>')
    x+=cw
text(W-60,H-20,"docs/es/proposals/monitoring-qa/README.md",13,400,'#9ca3af','end',font=MONO)
o.append('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'06-bloques-presentacion.svg'),'w').write('\n'.join(o))
