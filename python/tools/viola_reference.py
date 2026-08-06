"""Independent VIOLA reference engine (transcribed from the MATLAB sources).
S via conventional nodal MNA with nullors (numpy LU) -- NOT fermenta's Q/B path.
Z_D via the getMnaData/updateS transcription pinned against real .mat artifacts.
Per-sample loops transcribed from generated plugins (DEMO.m/Screamo.m/DOD.m)."""
import numpy as np, re

def omegaW(x):
    if x<-3.6: y=0.929404810843623*np.exp(0.986418416898303*x)-6.79639452545093e-06
    elif x<0: y=-0.00431200176082888*np.exp(3.55275697783407*x)+0.00792228971991872*x**3+0.0907827580611564*x**2+0.375633000771424*x+0.571426071298747
    elif x<2.5: y=-0.531567672565454*np.exp(0.267412600010990*x)-0.00273225759962195*x**3+0.0953348873301105*x**2+0.503184890060992*x+1.09876994061414
    elif x<7: y=1.32189881177891*np.exp(-2.05642141379680*x)-0.00164391849625201*x**3+0.0428488786259462*x**2+0.481822411934234*x+0.418369998866986
    elif x<30: b=np.log(x+0.217073722991741); y=1.00007068672705*x-1.00147317311501*b+1.08561409526715*b/x+0.516677184575301*b*(b-2)/x**2
    else: b=np.log(x); y=x-b+b/x+0.5*b*(b-2)/x**2
    e=np.exp(x-y); f=y-e; f1=1+e; return y-f*(1-0.5*(f*e/f1)**2)/f1

def anti_scat(a,Z,Is,eta,Vth,Rs,Rp):
    ma=abs(a); sa=np.sign(a) if a!=0 else 0.0
    al=(2*Rp*Is*Z+ma*(Rp+Rs-Z))/(Rp+Rs+Z); be=2*eta*Vth*Z/(Rs+Z)
    ga=Rp*Is*(Rs+Z)/(eta*Vth*(Rp+Rs+Z)); de=ma*(Z-Rs)/(2*eta*Vth*Z)
    return sa*(al-be*omegaW(np.log(ga)+de+al/be))

def d_scat(a,Z,Is,eta,Vth,Rs,Rp):
    al=(2*Rp*Is*Z+a*(Rp+Rs-Z))/(Rp+Rs+Z); be=2*eta*Vth*Z/(Rs+Z)
    ga=Rp*Is*(Rs+Z)/(eta*Vth*(Rp+Rs+Z)); de=a*(Z-Rs)/(2*eta*Vth*Z)
    return al-be*omegaW(np.log(ga)+de+al/be)

def anti_res(v,i,Is,eta,Vth,Rs,Rp):
    be=eta*Vth; h=2*Is*np.cosh((v-Rs*i)/be)/be; gi=1/Rp
    return (Rs*(h+gi)+1)/(h+gi)

def d_res(v,i,Is,eta,Vth,Rs,Rp):
    be=eta*Vth; e=np.exp((v-Rs*i)/be)/be; gi=1/Rp
    dfi=-1-Rs*(gi+Is*e); dfv=gi+Is*e
    return -dfi/dfv

def taper(pt,role,x,Rp,tol=1e-6):
    ra=(role=="Ra")
    if pt=="log": return (0.0125*Rp*(81**x-1) if ra else 1.0125*Rp*(1-81**(x-1)))+tol
    if pt=="ilog": return (0.25*np.log(1+x/0.0125)*Rp/np.log(3) if ra
                           else 0.25*np.log(1.0125/(x+0.0125))*Rp/np.log(3))+tol
    return (Rp*x if ra else Rp*(1-x))+tol

class ViolaRef:
    """elements: list of (id,type,nodes,value,params) from a neutral parser."""
    def __init__(self, nl, fs, pot_x=None):
        self.fs=float(fs); self.pot_x=pot_x or {}
        self.els=[e for e in nl.elements if e.type!="OA"]
        self.opamps=[e for e in nl.elements if e.type=="OA"]
        self.input_id=nl.input_id
        labels={"0"}
        for e in self.els: labels|=set(e.nodes[:2])
        for e in self.opamps: labels|=set(e.nodes[:3])
        def num(l):
            m=re.findall(r"\d+",l); return int(m[-1]) if m else None
        if all(l=="0" or num(l) is not None for l in labels):
            self.nodes=sorted(labels,key=lambda l:0 if l=="0" else num(l))
        else:
            self.nodes=["0"]+sorted(l for l in labels if l!="0")
        self.idx={l:i for i,l in enumerate(self.nodes)}
        self.ne=len(self.els); self.nN=len(self.nodes); self.nO=len(self.opamps)
        self.dix=[k for k,e in enumerate(self.els) if e.type in ("D","Dser","Dap")]
        self.Z=self._portZ()
        self.b=np.zeros(self.ne); self.a=np.zeros(self.ne)
        self.Rth=np.ones(self.ne)*(1.0+1000.0)   # DSR init (VIOLA: 1+tolDSR)
        self.tolSLV=1e-5; self.tolDSR=1000.0
        self.sim=len(self.dix)>=2
        if len(self.dix)==1:
            self.Z[self.dix[0]]=self._Zn(self.dix[0])
        if self.sim:
            for d in self.dix: self.Z[d]=1.0
        self.S=self._buildS()
        self.v=np.zeros(self.ne); self.v_old=self.v+self.tolSLV
    def _portZ(self):
        Z=np.zeros(self.ne)
        for k,e in enumerate(self.els):
            t=e.type
            if t=="V": Z[k]=1e-9
            elif t=="I": Z[k]=1e9
            elif t=="R":
                if e.params and "pot" in e.params:
                    nm=e.params["pot"]; x=self.pot_x.get(nm, e.params.get("x",0.5))
                    pt={"Plin":"lin","Plog":"log","Pilog":"ilog"}[e.params.get("type","Plin")]
                    role="Ra" if e.id.endswith("_Ra") else "Rb"
                    Z[k]=taper(pt,role,x,e.params["Rp"])
                else: Z[k]=float(e.value)
            elif t=="C": Z[k]=1.0/(2*float(e.value)*self.fs)
            elif t=="L": Z[k]=2*float(e.value)*self.fs
            elif t in ("D","Dser","Dap"): Z[k]=1.0   # placeholder
            else: raise ValueError(t)
        return Z
    def _Zn(self,d):
        de=self.els[d]
        lin=[(k,e) for k,e in enumerate(self.els) if k!=d]
        Ainc=np.zeros((self.nN,len(lin))); z=np.zeros(len(lin))
        for c,(k,e) in enumerate(lin):
            Ainc[self.idx[e.nodes[0]],c]-=1; Ainc[self.idx[e.nodes[1]],c]+=1; z[c]=self.Z[k]
        al=self.idx[de.nodes[0]]; be=self.idx[de.nodes[1]]
        Ap=np.delete(Ainc,al,axis=0)
        # plain LAPACK inv, exactly like MATLAB's inv() in the deployed plugin
        Yni=np.linalg.inv(Ap@np.diag(1/z)@Ap.T)
        if self.nO:
            U=np.zeros((self.nN,self.nO)); K=np.zeros((self.nO,self.nN))
            for k,e in enumerate(self.opamps):
                neg,pos,out=e.nodes[:3]
                U[self.idx["0"],k]+=1; U[self.idx[out],k]-=1
                K[k,self.idx[neg]]+=1; K[k,self.idx[pos]]-=1
            Up=np.delete(U,al,axis=0); Kp=np.delete(K,al,axis=1)
            H=np.zeros((self.nO,self.nO))
            Zn=Yni@(np.eye(self.nN-1)+Up@np.linalg.inv(H-Kp@Yni@Up)@Kp@Yni)
        else: Zn=Yni
        b=be if be<Zn.shape[0] else be-1
        return float(Zn[b,b])
    def _buildS(self):
        """S column-by-column via conventional nodal MNA with nullors."""
        nN,ne,nO=self.nN,self.ne,self.nO
        dim=(nN-1)+nO       # node voltages (minus ground) + norator currents
        Am=np.zeros((dim,dim))
        gidx=lambda l: self.idx[l]-1     # ground first (index0) -> removed
        for k,e in enumerate(self.els):
            g=1.0/self.Z[k]; n1,n2=e.nodes[0],e.nodes[1]
            for (na,nb,sg) in [(n1,n1,g),(n2,n2,g),(n1,n2,-g),(n2,n1,-g)]:
                if na!="0" and nb!="0": Am[gidx(na),gidx(nb)]+=sg
        for k,e in enumerate(self.opamps):
            neg,pos,out=e.nodes[:3]; r=(nN-1)+k
            if out!="0": Am[gidx(out),r]+=1.0       # norator current into out node
            if neg!="0": Am[r,gidx(neg)]+=1.0       # nullator: v(neg)=v(pos)
            if pos!="0": Am[r,gidx(pos)]-=1.0
        # 80-bit precision to keep the reference itself accurate despite g=1e9
        Am=Am.astype(np.longdouble)
        lu=np.linalg.inv(Am.astype(np.double)).astype(np.longdouble)
        for _ in range(3):                       # Newton refinement in longdouble
            R=np.eye(Am.shape[0],dtype=np.longdouble)-Am@lu
            if float(np.max(np.abs(R)))<1e-17: break
            lu=lu+lu@R
        S=np.zeros((ne,ne))
        self.N2B=np.zeros((nN,ne))          # node voltage per unit b_j (ground row = 0)
        for j in range(ne):
            rhs=np.zeros(dim); e=self.els[j]; g=1.0/self.Z[j]
            n1,n2=e.nodes[0],e.nodes[1]
            if n1!="0": rhs[gidx(n1)]+=g
            if n2!="0": rhs[gidx(n2)]-=g
            x=np.asarray(lu@rhs.astype(np.longdouble),dtype=np.double)
            for l,lab in enumerate(self.nodes):
                if lab!="0": self.N2B[l,j]=x[gidx(lab)]
            for k,ek in enumerate(self.els):
                v1=x[gidx(ek.nodes[0])] if ek.nodes[0]!="0" else 0.0
                v2=x[gidx(ek.nodes[1])] if ek.nodes[1]!="0" else 0.0
                vk=v1-v2
                S[k,j]=2*vk-(1.0 if k==j else 0.0)
        return S
    def dparams(self,k):
        p=self.els[k].params
        return (p["Is"],p["eta"],p["Vth"],p["Rs"],p["Rp"])
    def scat(self,k,a):
        f=anti_scat if self.els[k].type=="Dap" else d_scat
        return f(a,self.Z[k],*self.dparams(k))
    def res(self,k,v,i):
        f=anti_res if self.els[k].type=="Dap" else d_res
        return f(v,i,*self.dparams(k))
    def process(self,x,node=None):
        node_out=self.idx[node] if node else None
        nv=np.zeros(len(x)) if node else None
        out=np.zeros((len(x),self.ne))     # port voltages, all ports
        a=self.a; b=self.b
        for n,inp in enumerate(x):
            for k,e in enumerate(self.els):
                t=e.type
                if t=="V": b[k]=inp if e.id==self.input_id else (e.value or 0.0)
                elif t=="I": b[k]=e.value or 0.0
                elif t=="R": b[k]=0.0
                elif t=="C": b[k]=a[k]
                elif t=="L": b[k]=-a[k]
                # diode: keep previous reflection (VIOLA semantics)
            if not self.sim:
                if self.dix:
                    d=self.dix[0]
                    b[d]=self.scat(d,float(self.S[d,:]@b))
                a[:]=self.S@b
            else:
                drift=sum(abs(self.Z[d]-self.Rth[d]) for d in self.dix)
                if drift>=self.tolDSR:
                    for d in self.dix: self.Z[d]=self.Rth[d]
                    self.S=self._buildS()
                self.v_old=self.v+self.tolSLV
                it=0
                while np.linalg.norm(self.v-self.v_old)>=self.tolSLV and it<200:
                    self.v_old=self.v.copy()
                    for d in self.dix: b[d]=self.scat(d,a[d])
                    a[:]=self.S@b
                    self.v=0.5*(a+b); it+=1
                i=0.5*(a-b)/self.Z
                for d in self.dix: self.Rth[d]=self.res(d,self.v[d],i[d])
            out[n,:]=0.5*(a+b)
            if node_out is not None: nv[n]=float(self.N2B[node_out,:]@b)
        return (out,nv) if node_out is not None else out
