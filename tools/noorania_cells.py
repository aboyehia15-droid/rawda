import cv2,numpy as np,glob,json,sys
def cells(path,dbg=None):
    im=cv2.imread(path);H,W=im.shape[:2];g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    # thin dark-grey grid lines: low saturation, darker than paper
    m=((g<200)&(hsv[...,1]<60)).astype(np.uint8)*255
    # restrict to the inner frame
    x0,x1,y0,y1=int(W*.07),int(W*.93),int(H*.05),int(H*.95)
    hk=cv2.getStructuringElement(cv2.MORPH_RECT,(int(W*.12),1));vk=cv2.getStructuringElement(cv2.MORPH_RECT,(1,int(H*.05)))
    m2=((g<200)).astype(np.uint8)*255;thick=cv2.morphologyEx(m2,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(6,1)));thin=cv2.subtract(m2,thick)
    hl=cv2.morphologyEx(m,cv2.MORPH_OPEN,hk);vl=cv2.morphologyEx(thin,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,int(H*.025))));vl=cv2.dilate(vl,cv2.getStructuringElement(cv2.MORPH_RECT,(5,1)))
    hl[:, :x0]=0;hl[:,x1:]=0;vl[:y0]=0;vl[y1:]=0;hl[:y0]=0;hl[y1:]=0;vl[:,:x0]=0;vl[:,x1:]=0
    rows=np.where(hl.sum(1)>255*W*.3)[0]
    ys=[];
    for y in rows:
        if not ys or y-ys[-1][-1]>3: ys.append([y])
        else: ys[-1].append(y)
    ys=[int(np.mean(a)) for a in ys]
    out=[];pend=[]
    for a,b in zip(ys,ys[1:]):
        if b-a<H*.04: continue
        band=vl[a+3:b-3]
        cols=np.where(band.sum(0)>255*(b-a-6)*.8)[0]
        xs=[]
        for x in cols:
            if not xs or x-xs[-1][-1]>3: xs.append([x])
            else: xs[-1].append(x)
        xs=[int(np.mean(c)) for c in xs]
        # header bars (red/green) are skipped
        sat=hsv[a:b,x0:x1,1];colfrac=(sat>120).mean()
        if len(xs)<2: xs=None
        if xs is None:
            pend.append((len(out),a,b));out.append(None);continue
        row=[]
        for l,r in zip(xs,xs[1:]):
            if r-l<W*.03: continue
            cs=hsv[a:b,l:r,1];cv=hsv[a:b,l:r,2]
            if ((cs>110)&(cv>80)).mean()>.45:
                if (r-l)/W>.12: row.append(['H',round(l/W,4),round(a/H,4),round((r-l)/W,4),round((b-a)/H,4)])
                continue
            row.append([round(l/W,4),round(a/H,4),round((r-l)/W,4),round((b-a)/H,4)])
        row=[c for c in row if c[0]=='H' or c[3]>.035]
        row.sort(key=lambda c:-(c[1] if c[0]=='H' else c[0]))  # right to left
        out.append(row)
    rows_ok=[[c for c in r if c[0]!='H'] for r in out if r];rows_ok=[r for r in rows_ok if r]
    if rows_ok:
        L=min(c[0] for r in rows_ok for c in r);R=max(c[0]+c[2] for r in rows_ok for c in r)
        for i,a,b in pend:
            sub=g[a+4:b-4,int(L*W)+6:int(R*W)-6];sat=hsv[a+4:b-4,int(L*W)+6:int(R*W)-6]
            cf=((sat[...,1]>110)&(sat[...,2]>80)).mean()
            if cf>=.3: out[i]=[['H',round(L,4),round(a/H,4),round(R-L,4),round((b-a)/H,4)]]
            elif (sub<150).mean()>.02: out[i]=[[round(L,4),round(a/H,4),round(R-L,4),round((b-a)/H,4)]]
    out=[r for r in out if r]
    if dbg is not None:
        for row in out:
            for k,c in enumerate(row):
                if c[0]=='H': continue
                x,y,w,h=c
                cv2.rectangle(im,(int(x*W),int(y*H)),(int((x+w)*W),int((y+h)*H)),(0,0,255),2);cv2.putText(im,str(k),(int(x*W)+4,int(y*H)+18),0,.6,(255,0,0),2)
        cv2.imwrite(dbg,im)
    return out
res={}
for f in sorted(glob.glob('nrp/p-*.png')):
    n=int(f[-6:-4]);r=cells(f,f.replace('p-','d-'));res[n]=r
    print(n,' '.join(''.join('H' if c[0]=='H' else '.' for c in x) for x in r))
json.dump(res,open('nr_cells.json','w'))
