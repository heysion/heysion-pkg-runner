#!/usr/bin/env python2
# -*- coding: utf-8 -*-
'''
@author: Heysion
@copyright: 2019 By Heysion heysion@users.noreply.github.com
@license: GPL v3.0
'''
import sys
import time
import os
import Queue as queue
import subprocess
import pickle
from multiprocessing.pool import Pool
from multiprocessing.pool import ThreadPool
import datetime
import base64
import logging

logging.basicConfig(level = logging.DEBUG,
                    format='%(process)d# %(asctime)-15s %(levelname)s %(filename)s %(lineno)d %(message)s',
                    filename='/tmp/hpr.log',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filemode='a')

_repo_metadata_pkgs = {}
def DEBUG(off=True):
    if off:
        import pdb;pdb.set_trace()
    else:
        pass

def Fakee(name,notnull=True):
    fake_key = "_%s"%name
    
    @property
    def faker(self):
        return getattr(self,fake_key,None)

    @faker.setter
    def faker(self,value):
        if value or not notnull:
            #logging.debug("key:{k} v:{v}".format(k=fake_key,v=value))
            setattr(self,fake_key,value)
        else:
            self.msg = "please set %s !"%name
            self.state = False
            logging.debug(self.msg)
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
            #logging.debug("key:{k} v:{v}".format(k=fake_key,v=value))
            setattr(self,fake_key,value)
        else:
            self.msg = "can't found %s !"%name
            self.state = False
            logging.debug(self.msg)
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
        logging.debug("Running cmd: %s (ret :%d)"%(cmd,ret))
        if ret%255 == 0:
            return (True,"OK")
        else:
            return (False,"Failed : %s"%cmd)
        
    @staticmethod
    def Runpipe(cmd):
        output = subprocess.Popen(cmd,shell=True,
                                  stdout=subprocess.PIPE,
                                  universal_newlines=True,
                                  stderr=subprocess.STDOUT)

        logging.debug("Running cmd: {c} (ret:{r})".format(c=cmd,r=output.returncode))
        if output.returncode is not 0:
            return (False,output.communicate()[0])
        else:
            return (True,output.communicate()[0])

    @staticmethod
    def Runpipe0(cmd):
        
        output = subprocess.Popen(cmd,shell=True,
                                  stdout=subprocess.PIPE,
                                  universal_newlines=True,
                                  stderr=subprocess.STDOUT)
        
        rc = output.communicate()[0].split("\n")
        logging.debug("Running cmd: {c} (ret:{x}{r})".format(c=cmd,r=rc,x=output.returncode))
        if output.returncode is not 0:
            return (False,rc)
        else:
            return (True,rc)

class CorePkg(Runner):
    def InstSrpm(self):
        self.Runshell("rpm -ivh %s"%self.srpm)

    def InstOrpm(self):
        self.Runshell("echo FIXME")

    def InstallOALL(self,pkg):
        rc = self.Runpipe0(cmd='''find %s/%s/ -name "*.rpm" | grep -i %s '''%(self._srpmbuild,"RPMS",pkg))
        if rc[0]:
            logging.debug(rc[1])
            if rc[1] != ['']:
                self.Runshell("sudo rpm -i %s |& tee %s/.log/inst-%s"%(" ".join(rc[1]),self._buildroot,pkg))
        return True

    def InstNeed(self,pkg):
        self.Runshell("sudo yum install %s -y |& tee %s/.log/inst-%s"%(pkg,self._buildroot,pkg))

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
        logging.info("Need orig pkgs {pkgs}".format(pkgs=self.need_pkg))
        for pkg in self.need_pkg:
           if  pkg in _repo_metadata_pkgs["provides"]:
               real_pkgs.append(_repo_metadata_pkgs["provides"].get(pkg))
        logging.debug("need real pkgs {pkgs}".format(pkgs=real_pkgs))
        for pkg in real_pkgs:
            cmd = "yum list | grep -i %s"%pkg
            if self.Runshell(cmd)[0]:
               self.InstNeed(pkg)
            else:
                self._pkg_list.put(pkg)
            #FIXME DEBUG
            #logging.debug("FXIME %s"%pkg)
            #self._pkg_list.put(pkg)

    def CheckSrpm(self):
        rc,output = self.Runpipe0('find %s -name "%s" | grep %s'%(self._srpmroot,
                                                                  self.orig_srpm.replace(self.release,"*"),
                                                                  self.pkgname))
        if rc:
            logging.debug("{0} found srpm list:{1}\n will got top 1 in list".format(self.pkgname,output))
            self.srpm = output[0][0]
        else:
            math  = self.orig_srpm.replace(self.release,"*")
            rc,output = self.Runpipe0('find %s -name "%s" | grep %s'%(self._srpmroot,
                                                                      math.replace(self.version,"*"),
                                                                      self.pkgname))

            if rc:
                logging.debug("{0} found srpm list:{1}\n will got top 1 in list".format(self.pkgname,output))
                self.srpm = output[0][0]
            else:
                self.msg = "can't found %s srpm"%self.pkgname
                self.state = False
                raise self

class WorkCore(CorePkg):
    pkgname = Fakee("pkgname")
    version = Fakee("version")
    release = Fakee("release")
    need_pkg = Fakee("need_pkg",notnull=False)
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
        elif isinstance(v7_pkgs_key,unicode):
            #DEBUG(True)
            self.pkgname,self.version,self.release = [ x.encode("utf-8") for x in pkgs[v7_pkgs_key][1][:3]]
            self.orig_srpm,self.orig_spec = [ x.encode("utf-8") for x in pkgs[v7_pkgs_key][1][4:]]
            self.need_pkg = [ x.encode("utf-8") for x in pkgs[v7_pkgs_key][1][3]] if pkgs[v7_pkgs_key][1][3] else None
        pass
        
        self._wid = wid
        # os.environ["hpsrpms"]="/mnt/srpm"
        # os.environ["hpbuild"]="/home/deepin/rpmbuild"
        # os.environ["hproot"]="/home/deepin/.hp"
        self._srpmroot = os.environ.get("hpsrpms")
        self._srpmbuild = os.environ.get("hpbuild")
        self._buildroot = os.environ.get("hproot")
        logging.debug("fetch rpms dir on {0},work in {1} ,save log to {2}".format(self._srpmroot,
                                                                                  self._srpmbuild,
                                                                                  self._buildroot))
        self._pkg_list = queue.Queue()
        self._pkg_err_list = queue.LifoQueue()

    def Init(self,release=None,version=None):
        if release:
            self.orig_srpm = self.orig_srpm.replace(self.release,release)
        if version:
            self.orig_srpm = self.orig_srpm.replace(self.version,version)
        try:
            self.srpm = "%s/%s"%(self._srpmroot,self.orig_srpm)
        except Errores as e:
            self.CheckSrpm()
        self.InstSrpm()
        self.spec = "%s/SPECS/%s"%(self._srpmbuild,self.orig_spec)

def Loadfile(name="/tmp/centosv7.bson"):
    if os.path.exists(name):
        f = open(name,"rb")
        data = pickle.loads(base64.b64decode(f.read()))
        return data
    else:
        return None

def _init_work_core(core):
    logging.debug("init core")
    try:
        core.CheckSrpm()
        logging.debug("{pkg} {srpm}".format(pkg=core,srpm=core.srpm))
        core.InstSrpm()
        core.spec = "%s/SPECS/%s"%(core._srpmbuild,core._orig_spec)
        return True
    except Errores as e:
        logging.debug("Error {e}".format(e=e))
        return False
    pass

def workee(pkgname):
    logging.info("Workee: %d start %s"%(os.getpid(),pkgname))
    work_core = WorkCore(pkgname,wid=3)
    try:
        if _init_work_core(core=work_core):
            work_core.CheckNeedpkg()
            if work_core._pkg_list.empty():
                work_core.BuildRpmOnly(work_core.spec,pkgname)
            else:
                work_core.BuildRpmForce(work_core.spec,pkgname)
                work_core.InstallOALL(pkgname)
            return (True,os.getpid())
        else:
            return (True,os.getpid())
    except Errores as e:
        logging.info("Workee Errors {e}".format(e=e))
        return (False,os.getpid())
    except Exception as e:
        logging.info("Workee Errors {e}".format(e=e))
        return (False,os.getpid())
    return (False,os.getpid())

def worker(pkgname):
    logging.info("Worker: %d start %s"%(os.getpid(),pkgname))
    work_core = WorkCore(pkgname,wid=2)
    try:
        if _init_work_core(core=work_core):
            work_core.CheckNeedpkg()
            logging.debug("Worker: {pkg} need {pkglist}".format(pkg=pkgname,pkglist=work_core.need_pkg))
            if work_core._pkg_list.empty():
                work_core.BuildRpmOnly(work_core.spec,pkgname)
            else:
                work_result_list = []
                pool = Pool(processes=4)
                while True:
                    if not work_core._pkg_list.empty():
                        pkg = work_core._pkg_list.get()
                        logging.debug("Worker: %s need %s"%(pkgname,pkg))
                        if pkg is None:
                            break
                        work_result_list.append(pool.apply_async(workee,(pkg,)))
                        work_core._pkg_list.task_done()
                        continue
                    else:
                        break
                    logging.debug("Worker: %s have not need pkg"%(pkgname))
                pool.close()
                pool.join()
                rc,pid = (False,0)
                for index, value in enumerate(work_result_list, 0):
                    rc_orig = value.get()
                    if rc_orig:
                        rc,pid = rc_orig
                        logging.debug("Worker: %d state %s"%(pid,rc))
                        if not rc:
                            work_core._pkg_err_list(pkg)
                    logging.info("Worker {p} task#{idex} result:{r}".format(idex=index, r=rc, p=pid ))
                work_core.BuildRpmForce(work_core.spec,pkgname)
            work_core.InstallOALL(pkgname)
            return (True,os.getpid())
        return (True,os.getpid())
    except Errores as e:
        logging.info("Worker Errors {e}".format(e=e))
        return (False,os.getpid())
    except Exception as e:
        logging.info("Worker Errors {e}".format(e=e))
        return (False,os.getpid())
    return (True,os.getpid())

def runner():
    if not len(sys.argv) == 2:
        logging.info("Runner: {0} start".format(sys.argv))
        raise Errors("Please read spec or configure !")
        return
    global _repo_metadata_pkgs
    pkg_name = sys.argv[1]
    _repo_metadata_pkgs = Loadfile("centosv7.bson")
    run_build = WorkCore(pkgname=pkg_name,wid=0)
    try:
        run_build.Init()
        run_build.CheckNeedpkg()
        
        if run_build._pkg_list.empty():
            run_build.BuildRpmOnly(run_build.spec,pkg_name)
        else:
            pool = Pool(processes=4)
            work_result_list = []
            startTime = datetime.datetime.now()
            while True:
                if not run_build._pkg_list.empty():
                    pkg = run_build._pkg_list.get()
                    if pkg is None:
                        break
                    work_result_list.append(pool.apply_async(worker,(pkg,)))
                    run_build._pkg_list.task_done()
                else:
                    break
                time.sleep(1)
            pool.close()
            pool.join()
            time.sleep(5)
            rc,pid = (False,0)
            for index, value in enumerate(work_result_list, 0):
                rc_orig = value.get()
                if rc_orig:
                    rc,pid = rc_orig
                logging.info("runner {p} task#{idex} result:{r}".format(idex=index, r=rc, p=pid ))
            print(datetime.datetime.now() - startTime)
        run_build.BuildRpmForce(run_build.spec,pkg_name)
        run_build.InstallOALL(pkg_name)
    except Errores as e:
        logging.info("Runner Errors {e}".format(e=e))


if __name__ == "__main__":
    runner()
