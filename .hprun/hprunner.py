#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@author: Heysion
@copyright: 2019 By Heysion heysion@users.noreply.github.com
@license: GPL v3.0
'''
import sys
import time
import os
import queue
import subprocess
import pickle
from multiprocessing import Pool
import datetime

_repo_metadata_pkgs = {}
def DEBUG(off=True):
    if off:
        import pdb;pdb.set_trace()
    else:
        pass

def Fakee(name):
    fake_key = "_%s"%name
    
    @property
    def faker(self):
        return getattr(self,fake_key,None)

    @faker.setter
    def faker(self,value):
        if value is not None:
            setattr(self,fake_key,value)
        else:
            self.msg = "please set %s !"%name
            self.state = False
            raise self

    return faker

def Fakee0(name):
    fake_key = "_%s"%name
    
    @property
    def faker(self):
        return getattr(self,fake_key,None)

    @faker.setter
    def faker(self,value):
        if os.path.exists(value):
            setattr(self,fake_key,value)
        else:
            self.msg = "can't found %s !"%name
            self.state = False
            raise self

    return faker

class Errores(Exception):
    def __init__(self,msg):
        super(Errores,self).__init__()
        self._msg = msg
        self._state = False

    @property
    def msg(self):
        return self._msg

    @msg.setter
    def msg(self,value):
        self._msg = value

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self,value):
        self._state = value

class Runner(Errores):
    @staticmethod
    def Runshell(cmd):
        ret = os.system(cmd)
        if ret%255 == 0:
            return (True,"OK")
        else:
            return (False,"Failed : %s"%cmd)
        
    @staticmethod
    def Runpipe(cmd):
        output = subprocess.run(cmd,shell=True,stdout=subprocess.PIPE,universal_newlines=True,stderr=subprocess.STDOUT)
        if output.returncode is not 0:
            return (False,output.stdout)
        else:
            return (True,output.stdout)

    @staticmethod
    def Runpipe0(cmd):
        output = subprocess.run(cmd,shell=True,stdout=subprocess.PIPE,universal_newlines=True,stderr=subprocess.STDOUT)
        if output.returncode is not 0:
            return (False,output.stdout.split("\n"))
        else:
            return (True,output.stdout.split("\n"))

class CorePkg(Runner):
    def InstSrpm(self):
        self.Runshell("rpm -ivh %s"%self.srpm)

    def InstOrpm(self):
        self.Runshell("echo test")

    def InstallOALL(self,pkg):
        self.Runshell("sudo rpm -i `ls %s/%s/*.rpm | grep -i %s `"%(self._srpmbuild,"RPMS",pkg))

    def InstNeed(self,pkg):
        self.Runshell("sudo yum install %s -y |& tee -a %s/.log/inst-%s"%(pkg,self._buildroot,pkg))

    def BuildRpm(self,spec,pkg):
        rc = self.Runpipe0(cmd = "rpmbuild -ba %s |& tee %s/.log/build-%s"%(spec,self._buildroot,pkg))
        if rc[0]:
            self.InstallOALL(pkg)
        else:
            self._pkg_err_list.put(pkg)
    
    def BuildRpmOnly(self,spec,pkg):
        rc = self.Runpipe0(cmd = "rpmbuild -ba %s |& tee %s/.log/build-%s"%(spec,self._buildroot,pkg))
        if rc[0]:
            return True
        else:
            return False

    def BuildRpmForce(self,spec,pkg):
        rc = self.Runpipe0(cmd = "rpmbuild -ba %s  --nodeps |& tee %s/.log/build-%s"%(spec,self._buildroot,pkg))
        if rc[0]:
            return True
        else:
            return False
                
    def CheckNeedpkg(self):
        real_pkgs = []
        for pkg in self.need_pkg:
           if  pkg in _repo_metadata_pkgs["provides"]:
               real_pkgs.append(_repo_metadata_pkgs["provides"].get(pkg))
        DEBUG(False)
        print(real_pkgs)
        for pkg in real_pkgs:
            cmd = "yum list | grep -i %s"%pkg
            if self.Runshell(cmd)[0]:
               self.InstNeed(pkg)
            else:
                self._pkg_list.put(pkg)
            self._pkg_list.put(pkg)

    def CheckSrpm(self):
        rc,output = self.Runpipe0('find %s -name "%s"'%(self._srpmroot,self._orig_srpm.replace(self.release,"*")))
        if rc:
           self.srpm = self.output[0]
        else:
            math  = self._orig_srpm.replace(self.release,"*")
            rc,output = self.Runpipe0('find %s -name "%s"'%(self._srpmroot,math.replace(self.version,"*")))
            if rc:
                self.srpm = self.output[0]
            else:
                self.msg = "can't found %s"%self.pkgname
                self.state = False
                raise self

class WorkCore(CorePkg):
    pkgname = Fakee("pkgname")
    version = Fakee("version")
    release = Fakee("release")
    need_pkg = Fakee("need_pkg")
    orig_srpm = Fakee("orig_srpm")
    orig_spec = Fakee("orig_spec")
    srpm = Fakee0("srpm")
    spec = Fakee0("spec")
    
    def __init__(self,pkgname,wid=1):
        def _filter_pkg(context):
            def __filter_pkg(value):
                if value == pkgname:
                    return True
                else:
                    return False
            for x in filter(__filter_pkg,context):return x

        pkgs = _repo_metadata_pkgs["pkgs"]
        v7_pkgs_key = _filter_pkg(pkgs.keys())
        if  isinstance(v7_pkgs_key,str):
            self.pkgname,self.version,self.release,self.need_pkg,self.orig_srpm,self.orig_spec = pkgs[v7_pkgs_key][1]
        elif isinstance(v7_pkgs_key,list):
            pass
        
        self._wid = wid
        # os.environ["hpsrpms"]="/mnt/srpm"
        # os.environ["hpbuild"]="/home/deepin/rpmbuild"
        #os.environ["hproot"]="/home/deepin/.hp/"
        self._srpmroot = os.environ.get("hpsrpms")
        self._srpmbuild = os.environ.get("hpbuild")
        self._buildroot = os.environ.get("hproot")
        self._pkg_list = queue.Queue()
        self._pkg_err_list = queue.LifoQueue()

    def Init(self,release=None,version=None):
        if release:
            self.orig_srpm = self.orig_srpm.replace(self.release,release)
        if version:
            self.orig_srpm = self.orig_srpm.replace(self.version,version)
        try:
            self.srpm = "%s/%s"%(self._srpmroot,self._orig_srpm)
        except Errores as e:
            self.CheckSrpm()
        self.InstSrpm()
        self.spec = "%s/SPECS/%s"%(self._srpmbuild,self._orig_spec)

def Loadfile(name="/tmp/centosv7.bson"):
    if os.path.exists(name):
        f = open(name,"rb")
        data = pickle.load(f)
        return data
    else:
        return None

def _init_work_core(core):
    try:
        core.CheckSrpm()
        core.InstSrpm()
        core.spec = "%s/SPECS/%s"%(core._srpmbuild,core._orig_spec)
        return True
    except Errores as e:
        return False
    pass

def workee(pkgname):
    wid = 3
    work_core = WorkCore(pkgname,wid=3)
    if _init_work_core(core=work_core):
        try:
            work_core.CheckNeedpkg()
            if work_core._pkg_list.empty():
                work_core.BuildRpmOnly(work_core.spec,pkgname)
            else:
                work_core.BuildRpmForce(work_core.spec,pkgname)
                print(datetime.datetime.now() - startTime)
                work_core.InstallOALL(pkgname)
            return (True,os.getpid())
        except Errores as e:
            return (False,os.getpid())
        except Exception as e:
            return (False,os.getpid())
    return (True,os.getpid())

def worker(pkgname):
    wid = 2
    work_core = WorkCore(pkgname,wid=2)
    if _init_work_core(core=work_core):
        try:
            work_core.CheckNeedpkg()
            if work_core._pkg_list.empty():
                work_core.BuildRpmOnly(work_core.spec,pkgname)
            else:
                pool = Pool(processes=4)
                work_result_list = []
                startTime = datetime.datetime.now()
                while True:
                    if not work_core._pkg_list.empty():
                        pkg = work_core._pkg_list.get()
                        if pkg is None:
                            break
                        work_result_list.append(pool.apply_async(worker,(pkg,)))
                        work_core._pkg_list.task_done()
                    else:
                        break
                    time.sleep(1)
                pool.close()
                pool.join()
                DEBUG(False)
                for index, value in enumerate(work_result_list, 0):
                    rc,pid = value.get()
                    print("{p} task#{idex} result:{r}".format(idex=index, r=rc, p=pid ))
                print(datetime.datetime.now() - startTime)
                work_core.BuildRpmForce(work_core.spec,pkgname)
                work_core.InstallOALL(pkgname)
        except Errores as e:
            return (False,os.getpid())
    return (True,os.getpid())
    pass

def runner():
    if len(sys.argv) == 2:
        pass
    else:
        print("%s pkgname"%sys.argv[0])
        pass
    global _repo_metadata_pkgs
    pkg_name = sys.argv[0]
    pkg_name = "atk"
    _repo_metadata_pkgs = Loadfile("centosv7.bson")
    test = WorkCore(pkgname=pkg_name,wid=0)
    try:
        test.Init()
        test.CheckNeedpkg()
        
        if test._pkg_list.empty():
            test.BuildRpmOnly(test.spec,pkg_name)
        else:
            pool = Pool(processes=4)
            work_result_list = []
            startTime = datetime.datetime.now()
            while True:
                if not test._pkg_list.empty():
                    pkg = test._pkg_list.get()
                    if pkg is None:
                        break
                    work_result_list.append(pool.apply_async(worker,(pkg,)))
                    test._pkg_list.task_done()
                else:
                    break
                time.sleep(1)
            pool.close()
            pool.join()
            DEBUG(False)
            for index, value in enumerate(work_result_list, 0):
                rc,pid = value.get()
                print("{p} task#{idex} result:{r}".format(idex=index, r=rc, p=pid ))
            print(datetime.datetime.now() - startTime)

            test.BuildRpmOnly(test.spec,pkg_name)
            test.InstallOALL(pkg_name)
            pass
    except Errores as e:
        print(e.msg)

if __name__ == "__main__":
    runner()



