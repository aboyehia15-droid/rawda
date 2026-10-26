import cv2,numpy as np,json,re
SC='/tmp/claude-0/-home-claude/1b0bb190-6a7a-5f61-a2fc-1b91ce10d1e6/scratchpad/'
orig=json.load(open(SC+'nr_cells.json'))
H_=.0857
def rows_y(p):return [r[0][1] for r in orig[str(p)]]
SPEC={
20:[("H",)]+[("w",w) for w in ["أنت إهد بعد بطش سعى كنت","لست أمر بردا جمعا حبل خسر","خلقا سبحا سبقا شأن صبحا ضبحا","عبدا عدن عشر عصف غرقا","غلبا فصل قدحا قضبا كأسا كدحا","لغوا مسك نخلا نشطا نفس نقعا","يسرا أبقى ترضى تنسى يخشى يسعى","يتلوا يدعوا تجري يهدي يغني","ألقت أمهل اقرأ فارغب فانصب"]],
21:[("w",w) for w in ["وانحر أخرج أرسل أغطش أفلح","أكرم ألهم أنشر أنقض دمدم","عسعس أعبد نعبد يخرج يحسب","يشرب يشهد ترهق تعرف أقسم","يبدئ ينفخ ينقلب يوسوس ثقلت","حشرت سطحت كشطت نشرت","نصبت أثرن وسطن فرغت تأتون","يسقون يفعلون يعملون يعلمون","يضحكون يكسبون يدخلون ينظرون","تعبدون أنعمت أنذرنا أنزلنا خلقنا"]],
22:[("w",w) for w in ["رفعنا وضعنا نطفة عبرة زجرة","تذكرة مسفرة مؤصدة مسغبة","مقربة متربة تضليل تقويم تكذيب","تسنيم مسكينا ممنون محفوظ","مختوم مسرورا مشهود أبوابا","مصفوفة أزواجا أشتاتا إطعام أعنابا","أفواجا ألفافا قرآن الحمد والفجر","والفتح والعصر من المعصرات","مع العسر ما القارعة وإذا الموءودة","ينظر المرء كالفراش المبثوث"]],
23:[("w",w) for w in ["كالعهن المنفوش ليلة القدر","أخرجت الأرض من أهل الكتاب","عند ذي العرش يمنعون الماعون","وهو الغفور الودود ذو العرش المجيد","لقد خلقنا الإنسان في أحسن تقويم","أعطيناك الكوثر الآن"]]+[("H",),("g",7),("g",7),("g",7)],
24:[("g",7)]*6+[("g",6),("H",),("w","برز حصل صدق عدد قدر"),("w","كذب نعم يظن يحض جنة ذرة")],
25:[("w",w) for w in ["قوة كرة سعرت قدمت كذبت","زوجت سجرت فجرت سيرت عطلت","كورت تطلع تحدث نيسر هم البينة","قيمة عشية مذكر أيان إياك","لله تجلى تصدى تزكى تولى توابا","ثجاجا غساقا فعال كذابا وهاجا","ممددة مكرمة مطهرة والسماء","والترائب والناشطات والنازعات","والسابحات فالسابقات فالمدبرات","تبلى السرائر فمهل الكافرين بالخنس"]],
26:[("w","الجوار الكنس اهدنا الصراط المستقيم"),("H",)]+[("w",w) for w in ["مروا ربي مدت حقت خفت تبت","تخلت قدمت والصبح والشمس","والشفع بالصبر والصيف والليل","والتين والزيتون سجيل سجين","منفكين فإن الجنة لحب الخير","إذا السماء انشقت ما الطارق النجم","الثاقب من شر الوسواس الخناس"]]+[("hw","يزكى يذكر")],
27:[("w",w) for w in ["المدثر المزمل عليين عليون","إن الذين إلا الذين من","شر النفاثات فعال لما يريد"]]+[("H",)]+[("w",w) for w in ["ضالا دابة حاجك حاجوك","لضالون ولا الضالين أتحاجوني","ولا تحاضون والصافات جاءت","الصاخة فإذا جاءت الطامة الكبرى"]]+[("H",),("w","جزاء الملائكة إنا أعطيناك إلينا")],
28:[("w",w) for w in ["إيابهم خيرا يره شرا يره ميقاتا","يوم فمن يعمل يومئذ يصدر","الناس من ربك رسول من الله","صحفا مطهرة صفا لا يتكلمون","قلوب يومئذ واجفة أبصارها سراجا","وهاجا وأنزلنا أكلا لما وتحبون","المال حبا جما غثاء أحوى معتد","أثيم إذا تتلى نارا حامية تسقى من","عين آنية من بخل لينبذن","من بعد من بين الصلب لنسفعا"]],
29:[("w",w) for w in ["بالناصية بذنبهم مطهرة بأيدي","سفرة كرام بررة هم فيها لكم دينكم","ولي دين إن ربهم بهم ترميهم","بحجارة لهم ما يشاءون من اللهم"]],
}
def strip(w):return re.sub(r'[^ء-ي]','',w)
def cut_words(g,x0,x1,y,h,words,W,H):
    L,R=int(x0*W)+12,int(x1*W)-12;T,B=int(y*H)+4,int((y+h)*H)-4
    sub=g[T:B,L:R];hh=B-T
    full=(sub<170).mean(0)>.8           # vertical frame lines
    ink=(sub<150)[int(hh*.18):int(hh*.88)];ink[:,full]=False
    cnt=ink.sum(0);col=cnt>0;N=len(col)
    nz=np.where(col)[0];lo,hi=(nz[0],nz[-1]) if len(nz) else (0,N-1)
    wt=[len(strip(w))+1.0 for w in words];tot=sum(wt);n=len(words);avg=(hi-lo)/n
    gaps=[];st=None
    for i in range(lo,hi+2):
        v=col[i] if i<=hi else True
        if not v and st is None:st=i
        elif v and st is not None:
            if i-st>=2:gaps.append(((st+i)/2,i-st))
            st=None
    gaps.sort(key=lambda x:-x[0])        # right to left
    exp=[];acc=0
    for k in range(n-1):acc+=wt[k];exp.append(hi-(hi-lo)*acc/tot)
    G=len(gaps);INF=1e18
    if G>=n-1 and n>1:
        cost=lambda k,j:-3.0*min(gaps[j][1],30)+40*((gaps[j][0]-exp[k])/avg)**2
        dp=[[INF]*G for _ in range(n-1)];bk=[[-1]*G for _ in range(n-1)]
        for j in range(G):dp[0][j]=cost(0,j)
        for k in range(1,n-1):
            best=INF;bj=-1
            for j in range(G):
                if j>0 and dp[k-1][j-1]<best:best=dp[k-1][j-1];bj=j-1
                if best<INF:dp[k][j]=best+cost(k,j);bk[k][j]=bj
        j=min(range(G),key=lambda j:dp[n-2][j]);cuts=[]
        for k in range(n-2,-1,-1):cuts.append(gaps[j][0]);j=bk[k][j]
        cuts=cuts[::-1]
    else:
        cuts=[e for e in exp]
    edges=[hi+1]+cuts+[lo]
    out=[]
    for k in range(n):
        r_,l_=edges[k],edges[k+1]
        seg=col[int(l_):int(r_)];idx=np.where(seg)[0]
        a2=int(l_)+(idx[0] if len(idx) else 0);b2=int(l_)+(idx[-1] if len(idx) else int(r_-l_)-1)
        out.append([round((L+a2-5)/W,4),round(y,4),round((b2-a2+10)/W,4),round(h,4)])
    return out
res={}
for pg,spec in SPEC.items():
    im=cv2.imread(SC+f'nrp/p-{pg:02d}.png');H,W=im.shape[:2];g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    ys=rows_y(pg);y0=ys[0]
    if pg==24:y0=.081
    if pg==29:y0=.083
    rr=[r for r in orig[str(pg)] if r[0][0]!='H'];FX0=min(min(c[0] for c in r) for r in rr);FX1=max(max(c[0]+c[2] for c in r) for r in rr)
    rows=[];y=y0
    for it in spec:
        if it[0]=="H":rows.append([["H",.09,y,.82,H_]])
        elif it[0]=="g":
            n=it[1];x0,x1=.094,.918;cw=(x1-x0)/7
            rows.append([[round(x1-(k+1)*cw,4),round(y,4),round(cw,4),H_] for k in range(n)])
        elif it[0]=="w":rows.append(cut_words(g,FX0,FX1,y,H_,it[1].split(),W,H))
        elif it[0]=="hw":rows.append([["H",.5,y,.42,H_]]+cut_words(g,FX0,.5,y,H_,it[1].split(),W,H))
        y+=H_
    res[str(pg)]=rows
    for r in rows:
        for k,c in enumerate(r):
            if c[0]=='H':x,yy,w,h=c[1:];cv2.rectangle(im,(int(x*W),int(yy*H)),(int((x+w)*W),int((yy+h)*H)),(0,160,0),3);continue
            x,yy,w,h=c;cv2.rectangle(im,(int(x*W),int(yy*H)+3),(int((x+w)*W),int((yy+h)*H)-3),(0,0,255),2);cv2.putText(im,str(k+1),(int(x*W)+3,int(yy*H)+16),0,.5,(255,0,0),1)
    cv2.imwrite(SC+f'nrp/z-{pg:02d}.png',im)
json.dump(res,open(SC+'nr_words3.json','w'))
print('ok',{k:[len(r) for r in v] for k,v in res.items()})
