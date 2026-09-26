#!/usr/bin/env python3
"""Generates 20-bloques-presentacion.svg (1920x1080, presentation-oriented).

Hand-drawn diagram, no Mermaid: this script is the source. To change
the SVG, edit here and run `python3 20-bloques-presentacion.py`.
"""
from xml.sax.saxutils import escape as e
W,H=1920,1080
FONT="'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO="'JetBrains Mono','SFMono-Regular',Consolas,monospace"
TXT="#1f2937"; SUB="#4b5563"
pal={'fund':('#eaf1ff','#2563eb'),'prot':('#fff5e6','#c2410c'),'app':('#e9f7ee','#15803d'),'ops':('#f4ecff','#7e22ce'),'plat':('#f3f4f6','#6b7280'),'out':('#ecfeff','#0e7490')}
o=[]
def rect(x,y,w,h,fill,stroke,rx=14,sw=2,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def text(x,y,s,size=16,weight=400,fill=TXT,anchor='start',font=FONT,italic=False):
    st=' font-style="italic"' if italic else ''
    o.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{st}>{e(s)}</text>')
def stack(x,y,w,h,key,num,name,purpose,bullets):
    bg,fg=pal[key]
    rect(x,y,w,h,'#ffffff',fg,rx=12,sw=2)
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="46" rx="12" fill="{bg}"/>')
    o.append(f'<rect x="{x}" y="{y+34}" width="{w}" height="12" fill="{bg}"/>')
    o.append(f'<line x1="{x}" y1="{y+46}" x2="{x+w}" y2="{y+46}" stroke="{fg}" stroke-width="1"/>')
    o.append(f'<circle cx="{x+24}" cy="{y+23}" r="14" fill="{fg}"/>')
    text(x+24,y+29,str(num),15,700,'#ffffff','middle')
    text(x+48,y+31,name,21,700,fg,font=MONO)
    text(x+16,y+76,purpose,16,600,TXT)
    yy=y+104
    for b in bullets:
        o.append(f'<circle cx="{x+22}" cy="{yy-5}" r="3" fill="{fg}"/>')
        text(x+32,yy,b,14,400,SUB); yy+=24
def arrow(x1,y1,x2,y2,color='#9ca3af',w=3):
    o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}" marker-end="url(#ah)"/>')

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="sonarqube archetype: blocks and stacks">')
o.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9ca3af"/></marker>'
         '<filter id="sh" x="-5%" y="-5%" width="110%" height="115%"><feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#111827" flood-opacity="0.08"/></filter></defs>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# title
text(60,72,"SonarQube Community — layer-5 archetype",40,800)
text(60,108,"Instance sonarqube-main · environment qa · GCP disasterproject-qa · europe-west1 · 9 stacks, 1 chart, one helm_release per stack",19,400,SUB)
o.append(f'<rect x="60" y="124" width="120" height="5" rx="2" fill="{pal["app"][1]}"/>')

# left panel: consumes
LX,LY,LW,LH=40,160,330,670
rect(LX,LY,LW,LH,pal['plat'][0],'#d1d5db',rx=18,sw=1.5)
text(LX+24,LY+44,"Consumes from the platform",22,700)
text(LX+24,LY+70,"one capability, one provider",15,400,SUB,italic=True)
caps=[("cluster","GKE Standard · sonar node pool"),("policy","Gatekeeper · PSS restricted"),("ingress","Envoy Gateway · Gateway API"),
      ("secrets","ESO + Secret Manager"),("oidc-idp","Keycloak → Entra ID"),("database-platform","CloudNativePG"),("monitoring","Prometheus · Grafana · Loki")]
y=LY+92
for c,d in caps:
    rect(LX+20,y,LW-40,74,'#ffffff','#d1d5db',rx=10,sw=1.5)
    text(LX+38,y+32,c,18,700,'#374151',font=MONO)
    text(LX+38,y+57,d,15,400,SUB)
    y+=81

# archetype container
CX,CY,CW,CH=420,160,1100,670
o.append(f'<g filter="url(#sh)">'); rect(CX,CY,CW,CH,'#fbfdfb',pal['app'][1],rx=22,sw=3); o.append('</g>')
text(CX+30,CY+44,"archetypes/sonarqube",24,800,pal['app'][1],font=MONO)
text(CX+CW-30,CY+44,"kind: catalog · layer 5 · v0.1.0",17,500,SUB,'end',font=MONO)

cols=[('fund',"1 · Foundation"),('prot',"2 · Protection and identity"),('app',"3 · Application"),('ops',"4 · Publishing and operations")]
colw=245; gap=25; x0=CX+30; ytop=CY+72
xs=[x0+i*(colw+gap) for i in range(4)]
for (k,t),x in zip(cols,xs):
    text(x,ytop+18,t,17,700,pal[k][1])
    o.append(f'<line x1="{x}" y1="{ytop+28}" x2="{x+colw}" y2="{ytop+28}" stroke="{pal[k][1]}" stroke-width="2" opacity="0.35"/>')
by=ytop+42; bh=170; bg=14
stack(xs[0],by,colw,bh,'fund',1,"iam","Namespace and identities",["namespace sonarqube","PSS restricted","KSA: sonarqube · eso · db"])
stack(xs[0],by+bh+bg,colw,bh,'fund',2,"secrets","Secrets by reference",["5 secrets in Secret Manager","IAM per secret (WI)","ESO → K8s Secrets"])
stack(xs[0],by+2*(bh+bg),colw,bh,'fund',3,"data-tenant","Dedicated PostgreSQL",["CNPG · primary + replica","WAL + daily backup → GCS","the archetype's own bucket"])
stack(xs[1],by,colw,bh,'prot',4,"firewall","Closed network by default",["default-deny ingress and egress","label-based exceptions","no internet egress"])
stack(xs[1],by+bh+bg,colw,bh,'prot',5,"sso","SAML client",["realm qa in Keycloak","Entra app roles → groups","before app: URL known upfront"])
# note in col2 bottom
nx,ny=xs[1],by+2*(bh+bg)
rect(nx,ny,colw,bh,'#fffaf3',pal['prot'][1],rx=12,sw=1.5,dash="6 5")
text(nx+16,ny+34,"No OIDC SecurityPolicy",16,700,pal['prot'][1])
for i,l in enumerate(["The route is used by people and","by the scanner with its own token:","authentication is done by","SonarQube (SAML + tokens)."]):
    text(nx+16,ny+64+i*24,l,14,400,SUB)
# app big
ax,ay,aw,ah=xs[2],by,colw,3*bh+2*bg
bgc,fg=pal['app']
rect(ax,ay,aw,ah,'#ffffff',fg,rx=12,sw=3)
o.append(f'<rect x="{ax}" y="{ay}" width="{aw}" height="46" rx="12" fill="{bgc}"/><rect x="{ax}" y="{ay+34}" width="{aw}" height="12" fill="{bgc}"/>')
o.append(f'<line x1="{ax}" y1="{ay+46}" x2="{ax+aw}" y2="{ay+46}" stroke="{fg}"/>')
o.append(f'<circle cx="{ax+24}" cy="{ay+23}" r="14" fill="{fg}"/>'); text(ax+24,ay+29,"6",15,700,'#ffffff','middle')
text(ax+48,ay+31,"app",21,700,fg,font=MONO)
text(ax+16,ay+76,"SonarQube Community Build",15,600)
text(ax+16,ay+98,"own image · by digest",14,400,SUB)
jv=[("JVM web","-Xmx2g"),("JVM compute engine","-Xmx3g · 1 worker"),("JVM search (ES)","-Xmx3g + mmap")]
yy=ay+118
for n,d in jv:
    rect(ax+16,yy,aw-32,62,bgc,fg,rx=8,sw=1.2)
    text(ax+30,yy+26,n,15,700,TXT); text(ax+30,yy+48,d,14,400,SUB,font=MONO); yy+=72
text(ax+16,yy+14,"12 GiB · no CPU limit",14,600,fg)
yy+=34
rect(ax+16,yy,aw-32,52,'#ffffff',fg,rx=8,sw=1.2,dash="4 4")
text(ax+30,yy+22,"PVC 50 GiB · ES indices",14,600,TXT); text(ax+30,yy+42,"rebuildable from the database",13,400,SUB)
yy+=64
rect(ax+16,yy,aw-32,74,'#f9fafb','#9ca3af',rx=8,sw=1.2)
text(ax+30,yy+24,"sonar node pool",14,700,TXT,font=MONO); text(ax+30,yy+45,"n2-standard-8 · taint",13,400,SUB); text(ax+30,yy+64,"vm.max_map_count on the node",13,400,SUB)
# col4
stack(xs[3],by,colw,bh,'ops',7,"frontdoor","Publishing",["HTTPRoute sonar.qa.…","120 s timeout","wildcard cert. at the edge"])
stack(xs[3],by+bh+bg,colw,bh,'ops',8,"config","Configuration as code",["groups/permissions: teams.yaml","default quality gate","hash-idempotent Job"])
stack(xs[3],by+2*(bh+bg),colw,bh,'ops',9,"observability","Operations",["metrics, alerts, dashboard","compute engine queue","external blackbox probe"])
# chevrons between columns
for i in range(3):
    cx=xs[i]+colw+gap/2; cy=by+ah/2
    o.append(f'<path d="M{cx-6},{cy-14} L{cx+6},{cy} L{cx-6},{cy+14}" fill="none" stroke="#9ca3af" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
# arrows panels
arrow(LX+LW+4,CY+CH/2,CX-6,CY+CH/2)

# right panel: delivers
RX,RY,RW,RH=1570,160,310,670
rect(RX,RY,RW,RH,pal['out'][0],'#a5f3fc',rx=18,sw=1.5)
text(RX+24,RY+44,"Delivers",22,700)
text(RX+24,RY+70,"no capability: consumed over HTTP",15,400,SUB,italic=True)
outs=[("People","UI with SAML login","sonar.qa.disasterproject.com"),
      ("GitHub Actions","main analysis · quality gate","200 projects · token per repo"),
      ("CMDB","url · digest · version","backup · secret ids")]
y=RY+96
for t,a,b in outs:
    rect(RX+20,y,RW-40,160,'#ffffff','#a5f3fc',rx=10,sw=1.5)
    text(RX+38,y+38,t,19,700,pal['out'][1]); text(RX+38,y+72,a,15,400,SUB); text(RX+38,y+100,b,14,400,SUB,font=MONO if '.' in b and ' ' not in b else FONT)
    y+=182
arrow(CX+CW+6,CY+CH/2,RX-6,CY+CH/2)

# bottom controls band
BY=858
text(60,BY+30,"Controls",20,700)
ctrl=[("assert","digest · heaps · no privileged"),("G1 conftest","input ↔ after · IAM per resource"),("G2 Checkov","private, uniform bucket"),
      ("G3 plan.json","no secrets in state"),("Gatekeeper","PSS · labels · registry")]
x=60; cw=364
for i,(a,b) in enumerate(ctrl):
    rect(x,BY+48,cw-20,74,'#ffffff','#d1d5db',rx=10,sw=1.5)
    text(x+18,BY+78,a,17,700,'#374151',font=MONO); text(x+18,BY+104,b,14,400,SUB)
    if i<4: o.append(f'<path d="M{x+cw-16},{BY+78} l8,7 l-8,7" fill="none" stroke="#9ca3af" stroke-width="2.5"/>')
    x+=cw
text(W-60,H-20,"docs/proposals/sonarqube-qa/02-archetype-sonarqube.md",13,400,'#9ca3af','end',font=MONO)
o.append('</svg>')
import os
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'20-bloques-presentacion.svg'),'w').write('\n'.join(o))
