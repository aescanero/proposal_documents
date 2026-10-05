#!/usr/bin/env python3
"""Genera 03-presentation-blocks.svg (1920x1080, orientado a presentación).

Diagrama dibujado a mano, sin Mermaid: la fuente es este script. Para cambiar
el SVG se edita aquí y se ejecuta `python3 03-presentation-blocks.py`.
Mismo estilo que network-qa/diagrams/06-bloques-presentacion.py.
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


T=dict(
 aria="Seguridad del ciclo de vida en qa: bloques",
 arch="archetypes/{defectdojo,dast,aig}", kind="layers 4-5 · vuln-mgmt 1.0.0",
 title="Seguridad del ciclo de vida en qa — DefectDojo, DAST y A.I.G",
 subtitle="cuatro fases · el CI escanea · el cluster solo aloja DefectDojo y los jobs DAST · A.I.G en una VM aislada · nada contra prod",
 left="Consume de la plataforma", left_sub="capas 1-4",
 caps=[("cluster · apps","DefectDojo, ZAP y Nuclei",False),("database-platform","Cloud SQL propia",False),("oidc-idp","Keycloak · cliente tenant",False),
       ("secrets · eso","tokens en Secret Manager",False),("network","NAT · subred de la VM",False)],
 cols=["1 · CI","2 · Consolidar","3 · DAST","4 · IA"],
 blocks=[
  [("sonarqube","SAST y quality gate",["escáner en CI","servidor ya propuesto","API Import a DefectDojo"]),
   ("trivy","SCA, secretos, imagen",["PR: secretos y CRITICAL","nocturno sobre lo desplegado","la imagen se promueve"]),
   ("checkov","IaC, Dockerfile, Helm",["G1/G2 en infra","checks bloqueantes por lista","plantilla en las apps"])],
  [("defectdojo","Capa 4 · vuln-mgmt",["un product type por equipo","importer-<equipo>: Writer","solo main y programados"]),
   ("datos","Cloud SQL propia",["qa-defectdojo · PITR 7 días","Valkey: componente","media en bucket (GCS FUSE)"]),
   ("acceso","SSO y tokens",["OIDC con Keycloak","tokens en Secret Manager","dojo.<public_id>…"])],
  [("zap","Baseline y API",["pasivo cada noche","API con OpenAPI","full: bajo demanda"]),
   ("nuclei","Plantillas fijadas",["semanal, medium o más","sin dos, fuzz, intrusive","imagen por versión"]),
   ("borde","Por el borde público",["Cloud Armor, prioridad 800","NAT MANUAL_ONLY · 2 IPs","objetivos de la resolución"])],
  [("vm","Aislada del cluster",["SYS_ADMIN, sin seccomp","sin IP pública · COS","subred /28 propia"]),
   ("iap","Acceso por túnel",["8088 solo por IAP","appsec-redteam@","nada hacia el cluster"]),
   ("import","Generic Findings",["conversor programado","importer-platform-aig","claves con límite de gasto"])]],
 right="Provee", right_sub="vuln-mgmt 1.0.0",
 items=[("equipos","appsec.yml reutilizable","product type por equipo"),("seguridad","hallazgos deduplicados","SLA y riesgos aceptados"),
        ("prod","sin DefectDojo propio","engagement deployed-prod"),("nocturno","CVEs posteriores al build","sobre lo desplegado")],
 controls="Controles",
 ctrl=[("assert","BD de database-platform"),("G1","prod no enlaza dast"),("Gatekeeper","P2 · P3 · P11"),
       ("Cloud Armor","regla 800 solo no-prod"),("IAP","VM sin IP pública")],
 foot="docs/es/proposals/appsec-qa/README.md")

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{e(T["aria"])}">')
o.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9ca3af"/></marker>'
         '<filter id="sh" x="-5%" y="-5%" width="110%" height="115%"><feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#111827" flood-opacity="0.08"/></filter></defs>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

text(60,72,T['title'],40,800)
text(60,108,T['subtitle'],19,400,SUB)
o.append(f'<rect x="60" y="124" width="120" height="5" rx="2" fill="{pal["fund"][1]}"/>')

LX,LY,LW,LH=40,160,330,670
rect(LX,LY,LW,LH,pal['plat'][0],'#d1d5db',rx=18,sw=1.5)
text(LX+24,LY+44,T['left'],22,700)
text(LX+24,LY+70,T['left_sub'],15,400,SUB,italic=True)
y=LY+92
for c,d,dashed in T['caps']:
    rect(LX+20,y,LW-40,90,'#ffffff','#d1d5db',rx=10,sw=1.5,dash="5 4" if dashed else None)
    text(LX+38,y+38,c,18,700,'#374151',font=MONO)
    text(LX+38,y+66,d,15,400,SUB)
    y+=110

CX,CY,CW,CH=420,160,1100,670
o.append(f'<g filter="url(#sh)">'); rect(CX,CY,CW,CH,'#fbfcff',pal['fund'][1],rx=22,sw=3); o.append('</g>')
text(CX+30,CY+44,T["arch"],24,800,pal['fund'][1],font=MONO)
text(CX+CW-30,CY+44,T["kind"],17,500,SUB,'end',font=MONO)
keys=['fund','prot','app','ops']
colw=245; gap=25; x0=CX+30; ytop=CY+72
xs=[x0+i*(colw+gap) for i in range(4)]
for k,t,x in zip(keys,T['cols'],xs):
    text(x,ytop+18,t,17,700,pal[k][1])
    o.append(f'<line x1="{x}" y1="{ytop+28}" x2="{x+colw}" y2="{ytop+28}" stroke="{pal[k][1]}" stroke-width="2" opacity="0.35"/>')
by=ytop+42; bh=170; bg=14
n=1
for ci,col in enumerate(T['blocks']):
    for ri,(name,purpose,bullets) in enumerate(col):
        if name is None:
            nx,ny=xs[ci],by+ri*(bh+bg)
            rect(nx,ny,colw,bh,'#fffaf3',pal[keys[ci]][1],rx=12,sw=1.5,dash="6 5")
            text(nx+16,ny+34,purpose,16,700,pal[keys[ci]][1])
            for i,l in enumerate(bullets): text(nx+16,ny+64+i*24,l,14,400,SUB)
            continue
        stack(xs[ci],by+ri*(bh+bg),colw,bh,keys[ci],n,name,purpose,bullets); n+=1
ah=3*bh+2*bg
for i in range(3):
    cx=xs[i]+colw+gap/2; cy=by+ah/2
    o.append(f'<path d="M{cx-6},{cy-14} L{cx+6},{cy} L{cx-6},{cy+14}" fill="none" stroke="#9ca3af" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
arrow(LX+LW+4,CY+CH/2,CX-6,CY+CH/2)

RX,RY,RW,RH=1570,160,310,670
rect(RX,RY,RW,RH,pal['out'][0],'#a5f3fc',rx=18,sw=1.5)
text(RX+24,RY+44,T['right'],22,700)
text(RX+24,RY+70,T['right_sub'],15,400,SUB,italic=True)
y=RY+92
for t,a,b in T['items']:
    rect(RX+20,y,RW-40,128,'#ffffff','#a5f3fc',rx=10,sw=1.5)
    text(RX+38,y+36,t,19,700,pal['out'][1]); text(RX+38,y+68,a,15,400,SUB); text(RX+38,y+96,b,14,400,SUB)
    y+=142
arrow(CX+CW+6,CY+CH/2,RX-6,CY+CH/2)

BY=858
text(60,BY+30,T['controls'],20,700)
x=60; cw=364
for i,(a,b) in enumerate(T['ctrl']):
    rect(x,BY+48,cw-20,74,'#ffffff','#d1d5db',rx=10,sw=1.5)
    text(x+18,BY+78,a,17,700,'#374151',font=MONO); text(x+18,BY+104,b,14,400,SUB)
    if i<4: o.append(f'<path d="M{x+cw-16},{BY+78} l8,7 l-8,7" fill="none" stroke="#9ca3af" stroke-width="2.5"/>')
    x+=cw
text(W-60,H-20,T['foot'],13,400,'#9ca3af','end',font=MONO)
o.append('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'03-presentation-blocks.svg'),'w').write('\n'.join(o))
