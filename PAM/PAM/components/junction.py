from __future__ import division
from PAM.components import Interpolant
import numpy, pylab, time, scipy.sparse
import PAM.PAMlib as PAMlib
        


class Junction(Interpolant):

    def __init__(self, fComp, fFace, fRot, fNW, mComp, mComp0=None, mComp1=None, mSide=-1, ni=None, nj=None):
        super(Junction,self).__init__() 

        self.fComp = fComp
        self.fFace = fFace
        self.fRot = fRot
        self.fNW = fNW
        self.mComp = mComp
        self.mSide = mSide
        self.mComp0 = mComp0
        self.mComp1 = mComp1
        self.initializeIndices(ni, nj)
        self.initializeFaces()
        self.initializeSurfaces()
        self.removeSurfaces()

    def initializeIndices(self, ni, nj):
        if not ni==None:
            self.ni = numpy.array(ni,int)
        if not nj==None:
            self.nj = numpy.array(nj,int)
        if self.mSide==-1:
            if ni==None:
                self.ni = [1,self.mComp.ms[0].shape[0],1]
            if nj==None:
                self.nj = [1,self.mComp.ms[2].shape[0],1]
        else:
            if ni==None:
                self.ni = [1,0,1]
            if nj==None:
                self.nj = [1,self.mComp.ms[0].shape[0],1]

        if self.fRot==0:
            self.rotate = lambda P: P
            self.flip = lambda nu, nv: [nu,nv]
        elif self.fRot==1:
            self.rotate = lambda P: numpy.swapaxes(P,0,1)[::-1,:]
            self.flip = lambda nu, nv: [nv[::-1],nu]
        elif self.fRot==2:
            self.rotate = lambda P: P[::-1,::-1]
            self.flip = lambda nu, nv: [nu[::-1],nv[::-1]]
        elif self.fRot==3:
            self.rotate = lambda P: numpy.swapaxes(P,0,1)[:,::-1]
            self.flip = lambda nu, nv: [nv,nu[::-1]]

        self.fK = self.rotate(self.fComp.Ks[self.fFace])[self.fNW[0]:self.fNW[0]+sum(self.ni),self.fNW[1]:self.fNW[1]+sum(self.nj)]

    def initializeVerts(self):
        vtx = lambda i, j, u, v: self.rotate(self.fComp.Ps[self.fK[i,j]])[u,v,:]
        vtxM = lambda f, i, j, u, v: self.mComp.Ps[self.mComp.Ks[f][i,j]][u,v,:]

        verts = numpy.zeros((4,4,3),order='F')
        for i in [0,-1]:
            for j in range(3):
                verts[i,j,:] = vtx(i, self.sj[j], i, 0)
                verts[i,j+1,:] = vtx(i, self.sj[j+1]-1, i, -1)
        for j in [0,-1]:
            for i in range(3):
                verts[i,j,:] = vtx(self.si[i], j, 0, j)
                verts[i+1,j,:] = vtx(self.si[i+1]-1, j, -1, j)
        if self.mSide==-1:
            verts[1,1,:] = vtxM(2, -1, 0, -1, 0)
            verts[2,1,:] = vtxM(2, -1, -1, -1, -1)
            verts[1,2,:] = vtxM(0, 0, 0, 0, 0)
            verts[2,2,:] = vtxM(0, 0, -1, 0, -1)
        else:
            if self.mSide==0:
                L = vtxM(0, -1, 0, -1, 0)
                R = vtxM(0, 0, 0, 0, 0)
            else:
                L = vtxM(0, 0, -1, 0, -1)
                R = vtxM(0, -1, -1, -1, -1)
            verts[1,1,:] = L
            verts[2,1,:] = L
            verts[1,2,:] = R
            verts[2,2,:] = R

        return verts

    def initializeSurfaces(self):
        verts = self.initializeVerts()
        
        nP = self.nP
        ni = self.ni
        nj = self.nj
        si = self.si
        sj = self.sj

        self.Ps = []
        self.Ks = [-numpy.ones((si[3],sj[3]),int)]
        counter = 0
        for j in range(sj[3]):
            for i in range(si[3]):
                if i<si[1] or j<sj[1] or i>=si[2] or j>=sj[2]:
                    self.Ps.append(numpy.zeros((nP,nP,3),order='F'))
                    self.Ks[0][i,j] = counter
                    counter += 1

        for b in range(3):
            for a in range(3):
                for j in range(nj[b]):
                    jj = sj[b] + j
                    for i in range(ni[a]):
                        ii = si[a] + i
                        if not self.Ks[0][ii,jj]==-1:
                            self.Ps[self.Ks[0][ii,jj]][:,:,:] = PAMlib.bilinearinterp(nP, ni[a], nj[b], i+1, j+1, verts[a:a+2,b:b+2,:])

        if not self.mSide==-1:
            mComp = self.mComp
            ii = si[1] - 1
            for j in range(nj[1]):
                jj = sj[1] + j
                if self.mSide==0:
                    self.averageEdges(self.Ps[self.Ks[0][ii,jj]][-1,:,:], mComp.Ps[mComp.Ks[0][-1-j,0]][::-1,0,:])
                else:
                    self.averageEdges(self.Ps[self.Ks[0][ii,jj]][-1,:,:], mComp.Ps[mComp.Ks[0][j,-1]][:,-1,:])
            ii = si[2]
            for j in range(nj[1]):
                jj = sj[1] + j
                if self.mSide==0:
                    self.averageEdges(self.Ps[self.Ks[0][ii,jj]][0,:,:], mComp.Ps[mComp.Ks[1][j,0]][:,0,:])
                else:
                    self.averageEdges(self.Ps[self.Ks[0][ii,jj]][0,:,:], mComp.Ps[mComp.Ks[1][j,-1]][::-1,-1,:])

    def removeSurfaces(self):
        fPs = self.fComp.Ps
        fKs = self.fComp.Ks
        fK0 = self.fK

        for j0 in range(fK0.shape[1]):
            for i0 in range(fK0.shape[0]):
                fPs.pop(fK0[i0,j0])
                for f in range(len(fKs)):
                    for j in range(fKs[f].shape[1]):
                        for i in range(fKs[f].shape[0]):
                            if (fKs[f][i,j] > fK0[i0,j0]) and (fKs[f][i,j] != -1):
                                fKs[f][i,j] -= 1
                fK0[i0,j0] = -1
        
    def computeQs(self):
        fu = self.fComp.getms(self.fFace,0)
        fv = self.fComp.getms(self.fFace,1)
        fu,fv = self.flip(fu,fv)
        fu1 = sum(fu[:self.fNW[0]])
        fu2 = sum(fu[:self.fNW[0]+self.si[3]])
        fv1 = sum(fv[:self.fNW[1]])
        fv2 = sum(fv[:self.fNW[1]+self.sj[3]])
        fQ = self.rotate(self.fComp.Qs[self.fFace])[fu1:fu2+1,fv1:fv2+1,:]

        getEdge = self.getEdge
        if self.mSide==-1:
            W = getEdge(self.mComp.Qs[2], i=-1, d=1)
            E = getEdge(self.mComp.Qs[0], i=0, d=1)
            N = getEdge(self.mComp0.Qs[0], i=-1, d=-1)
            S = getEdge(self.mComp1.Qs[0], i=-1, d=1)
        elif self.mSide==0:
            W = numpy.zeros((1,2,3),order='F')
            E = numpy.zeros((1,2,3),order='F')
            N = getEdge(self.mComp.Qs[0], j=0, d=-1)
            S = getEdge(self.mComp.Qs[1], j=0, d=1)
        elif self.mSide==1:
            W = numpy.zeros((1,2,3),order='F')
            E = numpy.zeros((1,2,3),order='F')
            N = getEdge(self.mComp.Qs[0], j=-1, d=1)
            S = getEdge(self.mComp.Qs[1], j=-1, d=-1)

        mu = self.getms(0,0)
        mv = self.getms(0,1)
        nu = range(3)
        nv = range(3)
        for k in range(3):
            nu[k] = sum(mu[self.si[k]:self.si[k+1]]) + 1
            nv[k] = sum(mv[self.sj[k]:self.sj[k+1]]) + 1

        v = self.variables
        self.Qs[0] = PAMlib.computejunction(sum(nu)-2, sum(nv)-2, nu[0], nu[1], nu[2], nv[0], nv[1], nv[2], v['f0'], v['m0'], W, E, N, S, fQ, v['shape'])