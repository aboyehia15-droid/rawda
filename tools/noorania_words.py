import cv2,numpy as np,json
cells=json.load(open('nr_cells.json'))
# words per line (counted from the pages); key: page -> list over that page's single-line rows, top to bottom
COUNTS={20:[6,6,6,5,6,6,6,5,5],21:[5,5,5,5,5,4,5,4,4,5],22:[5,4,5,4,4,5,5,4,6,4],23:[4,5,5,6,6,3],
        24:[5,6],25:[5,5,6,5,6,5,4,3,3,5],26:[5,6,4,4,4,5,6,5,2],27:[4,5,5,4,4,4,5,5],28:[6,5,6,5,5,5,6,7,5,6],29:[4,7,6,6]}
def cuts_for(g,box,W,H,n):
    x,y,w,h=box;L,T,R,B=int(x*W)+12,int(y*H)+3,int((x+w)*W)-12,int((y+h)*H)-3
    sub=g[T:B,L:R];hh=B-T;ink=(sub<140);core=ink[int(hh*.30):int(hh*.82)];cnt=core.sum(0)
    col=cnt>0;N=len(col)
    gaps=[];st=None
    for i,v in enumerate(list(col)+[True]):
        if not v and st is None: st=i
        elif v and st is not None:
            if st>3 and i<N-3: gaps.append((i-st,(st+i)//2))
            st=None
    # ink extent: no cut outside the written part
    nz=np.where(col)[0];lo,hi=(nz[0],nz[-1]) if len(nz) else (0,N)
    gaps=[(wd,c) for wd,c in gaps if lo+N/(n*3.5)<c<hi-N/(n*3.5)]
    gaps.sort(reverse=True);chosen=[]
    minsep=N/(n*2.2)
    for wdt,c in gaps:
        if len(chosen)>=n-1: break
        if wdt<2: break
        if all(abs(c-o)>minsep for o in chosen): chosen.append(c)
    # not enough real gaps: cut at the thinnest ink column near the even split
    if len(chosen)<n-1:
        tg=[lo+(hi-lo)*(k+1)/n for k in range(n-1)]
        for t in tg:
            if len(chosen)>=n-1: break
            if any(abs(t-o)<minsep for o in chosen): continue
            a=int(max(0,t-N/(n*3)));b=int(min(N,t+N/(n*3)));c=a+int(np.argmin(cnt[a:b]));chosen.append(c)
    chosen.sort()
    edges=[0]+chosen+[N];out=[]
    for a,b in zip(edges,edges[1:]):
        seg=col[a:b];idx=np.where(seg)[0]
        if not len(idx): idx=np.array([0,b-a-1])
        a2,b2=a+idx[0],a+idx[-1]
        out.append([round((L+a2-4)/W,4),round(y,4),round((b2-a2+8)/W,4),round(h,4)])
    out.sort(key=lambda c:-c[0]);return out
res={}
for pg,cn in COUNTS.items():
    im=cv2.imread(f'nrp/p-{pg:02d}.png');H,W=im.shape[:2];g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    rows=[list(r) for r in cells[str(pg)]]
    if pg==24 and rows[6][0][0]!='H':
        x,y,w,h=rows[6][0];rows[6:7]=[[['H',x,y,w,h/2]],[[x,y+h/2,w,h/2]]]
    if pg==26:
        x,y,w,h=rows[-1][0];rows.append([['H',x+w*.5,y+h,w*.5,h],[x,y+h,w*.5,h]])
    singles=[i for i,r in enumerate(rows) if r[0][0]!='H' and len(r)==1 and r[0][2]>.5]
    if pg==26: singles.append(len(rows)-1)
    assert len(singles)>=len(cn),(pg,len(singles),len(cn))
    for i,n in zip(singles,cn):
        if pg==26 and i==len(rows)-1:
            hb,tb=rows[i];rows[i]=[hb]+cuts_for(g,tb,W,H,n)
        else: rows[i]=cuts_for(g,rows[i][0],W,H,n)
    res[str(pg)]=rows
    for r in rows:
        for c in r:
            if c[0]=='H':x,y,w,h=c[1:];cv2.rectangle(im,(int(x*W),int(y*H)),(int((x+w)*W),int((y+h)*H)),(0,160,0),3);continue
            x,y,w,h=c;cv2.rectangle(im,(int(x*W),int(y*H)+3),(int((x+w)*W),int((y+h)*H)-3),(0,0,255),2)
    cv2.imwrite(f'nrp/w-{pg:02d}.png',im)
    print(pg,[len(r) for r in rows])
json.dump(res,open('nr_words.json','w'))
