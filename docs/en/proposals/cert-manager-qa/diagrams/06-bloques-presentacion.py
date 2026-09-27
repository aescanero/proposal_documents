#!/usr/bin/env python3
"""Generates 06-bloques-presentacion.svg (1920x1080, for presentations).

Hand-drawn diagram, no Mermaid: this script is the source. To change the SVG,
edit here and run `python3 06-bloques-presentacion.py`.
Same style as keycloak-qa/diagrams/09-bloques-presentacion.py.
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

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="cert-manager archetype: blocks">')
o.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9ca3af"/></marker>'
         '<filter id="sh" x="-5%" y="-5%" width="110%" height="115%"><feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#111827" flood-opacity="0.08"/></filter></defs>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# title
text(60,72,"cert-manager — layer-3 archetype, certs provider",40,800)
text(60,108,"gcp-qa-certs · environment qa · 2 stacks (controllers, ca) · internal CA · approver-policy · trust-manager · the public certificate belongs to layer 1",19,400,SUB)
o.append(f'<rect x="60" y="124" width="120" height="5" rx="2" fill="{pal["fund"][1]}"/>')

LX,LY,LW,LH=40,160,330,670
rect(LX,LY,LW,LH,pal['plat'][0],'#d1d5db',rx=18,sw=1.5)
text(LX+24,LY+44,"Consumes from the platform",22,700)
text(LX+24,LY+70,"one capability, one provider",15,400,SUB,italic=True)
caps=[("cluster","GKE · KMS on etcd",False),("policy","Gatekeeper · layer 2b",False),("secrets","NO: ESO requires certs",True),
      ("monitoring","NO: requires certs (cycle)",True),("cert (layer 1)","public: Certificate Manager",True)]
y=LY+92
for c,d,dashed in caps:
    rect(LX+20,y,LW-40,90,'#ffffff','#d1d5db',rx=10,sw=1.5,dash="5 4" if dashed else None)
    text(LX+38,y+38,c,18,700,'#374151',font=MONO)
    text(LX+38,y+66,d,15,400,SUB)
    y+=110

CX,CY,CW,CH=420,160,1100,670
o.append(f'<g filter="url(#sh)">'); rect(CX,CY,CW,CH,'#fbfcff',pal['fund'][1],rx=22,sw=3); o.append('</g>')
text(CX+30,CY+44,"archetypes/cert-manager",24,800,pal['fund'][1],font=MONO)
text(CX+CW-30,CY+44,"kind: catalog · layer 3 · v1.0.4",17,500,SUB,'end',font=MONO)
cols=[('fund',"1 · Issuance"),('prot',"2 · Approval"),('app',"3 · Internal CA"),('ops',"4 · Trust and operations")]
colw=245; gap=25; x0=CX+30; ytop=CY+72
xs=[x0+i*(colw+gap) for i in range(4)]
for (k,t),x in zip(cols,xs):
    text(x,ytop+18,t,17,700,pal[k][1])
    o.append(f'<line x1="{x}" y1="{ytop+28}" x2="{x+colw}" y2="{ytop+28}" stroke="{pal[k][1]}" stroke-width="2" opacity="0.35"/>')
by=ytop+42; bh=170; bg=14
stack(xs[0],by,colw,bh,'fund',1,"controller","cert-manager",["CRDs with keep","no owner reference","default approver: off"])
stack(xs[0],by+bh+bg,colw,bh,'fund',2,"webhook","Validates its kinds",["port 10250 (GKE)","self-managed certificate","cert-manager kinds only"])
stack(xs[0],by+2*(bh+bg),colw,bh,'fund',3,"cainjector","CA into other webhooks",["ESO","prometheus-operator","inject-ca-from"])
stack(xs[1],by,colw,bh,'prot',4,"approver-policy","Who asks for which name",["only *.<its ns>.svc","no IP SAN, no isCA","≤ 90 days · ECDSA P-256"])
stack(xs[1],by+bh+bg,colw,bh,'prot',5,"policies","CertificateRequestPolicy",["namespace-services","platform-webhooks","internal-ca-root"])
nx,ny=xs[1],by+2*(bh+bg)
rect(nx,ny,colw,bh,'#fffaf3',pal['prot'][1],rx=12,sw=1.5,dash="6 5")
text(nx+16,ny+34,"Without approver-policy…",16,700,pal['prot'][1])
for i,l in enumerate(["any namespace asks for","keycloak-service.keycloak","and impersonates Keycloak","to whoever trusts the CA."]):
    text(nx+16,ny+64+i*24,l,14,400,SUB)

ax,ay,aw,ah=xs[2],by,colw,3*bh+2*bg
bgc,fg=pal['app']
rect(ax,ay,aw,ah,'#ffffff',fg,rx=12,sw=3)
header(ax,ay,aw,'app',6,"ca")
text(ax+16,ay+76,"Own stack · prevent_destroy",15,600)
text(ax+16,ay+98,"root in KMS-encrypted etcd",14,400,SUB)
blocks=[("Issuer SelfSigned","bootstrap only"),("internal-ca-root","ECDSA P-384 · 10 years"),("ClusterIssuer","internal-ca")]
yy=ay+118
for n,d in blocks:
    rect(ax+16,yy,aw-32,62,bgc,fg,rx=8,sw=1.2)
    text(ax+30,yy+26,n,15,700,TXT,font=MONO if n!="Issuer SelfSigned" else FONT); text(ax+30,yy+48,d,14,400,SUB); yy+=72
text(ax+16,yy+14,"leaves: 90 days, renew on 60",14,600,fg)
yy+=34
rect(ax+16,yy,aw-32,52,'#ffffff',fg,rx=8,sw=1.2,dash="4 4")
text(ax+30,yy+22,"no intermediate",14,600,TXT); text(ax+30,yy+42,"one CA, no external clients",13,400,SUB)
yy+=64
rect(ax+16,yy,aw-32,74,'#f9fafb','#9ca3af',rx=8,sw=1.2)
text(ax+30,yy+24,"if the cluster is lost",14,700,TXT); text(ax+30,yy+45,"new root and re-issue;",13,400,SUB); text(ax+30,yy+64,"nothing outside the cluster",13,400,SUB)

stack(xs[3],by,colw,bh,'ops',7,"trust-manager","Bundle internal-ca-bundle",["ConfigMap in labelled ns","public certificates only","two roots while rotating"])
stack(xs[3],by+bh+bg,colw,bh,'ops',8,"rotation","Leaves alone, root by PR",["Envoy and webhooks reload","root in four steps","no TLS outage"])
stack(xs[3],by+2*(bh+bg),colw,bh,'ops',9,"alerts","Declared in monitoring",["not Ready 15 min","leaf < 14 d · root < 365 d","SERVED certificate"])
for i in range(3):
    cx=xs[i]+colw+gap/2; cy=by+ah/2
    o.append(f'<path d="M{cx-6},{cy-14} L{cx+6},{cy} L{cx-6},{cy+14}" fill="none" stroke="#9ca3af" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
arrow(LX+LW+4,CY+CH/2,CX-6,CY+CH/2)

RX,RY,RW,RH=1570,160,310,670
rect(RX,RY,RW,RH,pal['out'][0],'#a5f3fc',rx=18,sw=1.5)
text(RX+24,RY+44,"Provides certs 1.1.0",22,700)
text(RX+24,RY+70,"trait cert-manager",15,400,SUB,italic=True)
items=[("Envoy Gateway","backend certificate","the one the GLB sees"),("Keycloak","pod TLS","keycloak-service.keycloak.svc"),
       ("ESO · prometheus-op.","webhook certificates","caBundle via cainjector"),("Trust the CA","Envoy · Grafana · blackbox","Keycloak reconciler")]
y=RY+92
for t,a,b in items:
    rect(RX+20,y,RW-40,128,'#ffffff','#a5f3fc',rx=10,sw=1.5)
    text(RX+38,y+36,t,19,700,pal['out'][1]); text(RX+38,y+68,a,15,400,SUB); text(RX+38,y+96,b,14,400,SUB,font=MONO if '.svc' in b else FONT)
    y+=142
arrow(CX+CW+6,CY+CH/2,RX-6,CY+CH/2)

BY=858
text(60,BY+30,"Controls",20,700)
ctrl=[("assert","keep · no owner ref · 10250"),("approver-policy","names of its own ns"),("Gatekeeper","no tenant CA or ClusterIssuer"),
      ("G1 conftest","well-formed Certificate · trait"),("blackbox","served certificate < 14 d")]
x=60; cw=364
for i,(a,b) in enumerate(ctrl):
    rect(x,BY+48,cw-20,74,'#ffffff','#d1d5db',rx=10,sw=1.5)
    text(x+18,BY+78,a,17,700,'#374151',font=MONO); text(x+18,BY+104,b,14,400,SUB)
    if i<4: o.append(f'<path d="M{x+cw-16},{BY+78} l8,7 l-8,7" fill="none" stroke="#9ca3af" stroke-width="2.5"/>')
    x+=cw
text(W-60,H-20,"docs/en/proposals/cert-manager-qa/README.md",13,400,'#9ca3af','end',font=MONO)
o.append('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'06-bloques-presentacion.svg'),'w').write('\n'.join(o))
