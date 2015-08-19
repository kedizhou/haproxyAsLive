#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys, os, time, atexit ,re,httplib, urllib,base64,socket,commands
from signal import SIGTERM 
path=os.path.dirname(os.path.abspath(sys.argv[0]))

class logfile:
	def __init__(self):
		self.open()
	def open(self):
		try:
			self.l=open(path+'/log.dat','a')
		except:
			print 'cannot create file: Permission denied:'+path
			sys.exit(9)
	def w(self,log=''):
		self.l.write(time.strftime('%Y-%m-%d %H:%M:%S  ', time.localtime()))
		self.l.write(str(log)+'\n')
		self.l.flush()
		#print time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) ,log
	def close(self):
		self.l.close()

class Daemon(logfile):
	"""
	A generic daemon class.
	Usage: subclass the Daemon class and override the _run() method
	"""
	def __init__(self, pidfile, list, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
		self.stdin=stdin
		self.stdout=stdout
		self.stderr=stderr
		self.pidfile=pidfile
		self.list=list
		self.w=logfile()

	def _daemonize(self):
		"""
		do the UNIX double-fork magic, see Stevens' "Advanced 
		Programming in the UNIX Environment" for details (ISBN 0201563177)
		http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
		"""

		try: 
			pid = os.fork() 
			if pid > 0:
				sys.exit(0) 
		except OSError, e: 
			sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
			sys.exit(1)

		os.setsid() 
		os.chdir("/") 
		os.umask(0) 

		'''
		try: 
			pid = os.fork() 
			if pid > 0:
				sys.exit(0) 
		except OSError, e: 
			sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
			sys.exit(1) 
		'''

		sys.stdout.flush()
		sys.stderr.flush()
		si = file(self.stdin, 'r')
		so = file(self.stdout, 'a+')
		se = file(self.stderr, 'a+', 0)
		os.dup2(si.fileno(), sys.stdin.fileno())
		os.dup2(so.fileno(), sys.stdout.fileno())
		os.dup2(se.fileno(), sys.stderr.fileno())

		#atexit.register(self.delpid)
		#atexit.register(self.testatexit())
		pid = str(os.getpid())
		file(self.pidfile,'w+').write("%s\n" % pid)
	def testatexit(self):
		f=open('/tmp/b','w+')
		f.write('o')
		f.close()
	def delpid(self):
		os.remove(self.pidfile)
		self.w.close()
	def start(self):
		"""
		Start the daemon
		"""
		self.w.open()
		self.w.w(log='start haproxy monitor daemon process.')
		# Check for a pidfile to see if the daemon already runs
		try:
			pf = file(self.pidfile,'r')
			pid = int(pf.read().strip())
			pf.close()
		except IOError:
			pid = None

		if pid:
			message = "pidfile %s already exist. Daemon already running?\n"
			sys.stderr.write(message % self.pidfile)
			sys.exit(1)

		# Start the daemon
		self._daemonize()
		self._run()
	def stop(self):
		"""
		Stop the daemon
		"""
		# Get the pid from the pidfile
		try:
			pf = file(self.pidfile,'r')
			pid = int(pf.read().strip())
			pf.close()
		except IOError:
			pid = None

		if not pid:
			message = "pidfile %s does not exist. Daemon not running?\n"
			sys.stderr.write(message % self.pidfile)
			return # not an error in a restart
		# Try killing the daemon process    
		self.w.w(log='stop haproxy monitor daemon process.')
		try:
			while 1:
				os.kill(pid, SIGTERM)
				time.sleep(0.1)
		except OSError, err:
			err = str(err)
			if err.find("No such process") > 0:
				if os.path.exists(self.pidfile):
					#os.remove(self.pidfile)
					self.delpid()
			else:
				print str(err)
				sys.exit(1)
	def restart(self):
		"""
		Restart the daemon
		"""
		self.stop()
		self.start()
	def _run(self):
		"""
		You should override this method when you subclass Daemon. It will be called after the process has been
		daemonized by start() or restart().
		"""

class MyDaemon(Daemon,logfile):
	def _run(self):
		while True:
			self.test()
			time.sleep(300)
	def test(self):
		self.w.w(log='*******************************************************************************************************************************')
		#h=haproxy(host='localhost',port='8888',username='admin',password='sfweqoifjonvoirnqewfoknsdoaifiwpqeorh',url="/stats;csv;norefresh")
		j=1
		for hs in self.list:
			h=haproxy(host=hs['host'],port=hs['port'],username=hs['username'],password=hs['password'],url=hs["url"],cfile=hs['cfile'],logfile=self.w)
			if not h.connect():
				self.w.w(log='haproxy instance '+str(j)+' logini auth failed.')
				continue
			if h.downTypeList:
				self.w.w(log="haproxy instance "+str(j)+" down service list:"+str(h.downTypeList))
				'''
				repeat=h.findRepeatServerEntry()
				if repeat:
					w(log='ERROR.configure repeat server list for haproy type.'+repeat)
					return
				else:
				'''
				h.parseConfigFile()
				self.w.w(log= 'test host entry: "'+str(h.realIpandPort)+'"')
				h.probePort()
			else:
				self.w.w(log='haproxy instance '+str(j)+' check all service is ok!')
			j+=1

class haproxy(logfile):
	def __init__(self,host='localhost',port="",username='',password='',cfile='',url="/stats;csv;norefresh",logfile=logfile()):
		self.host=host
		self.port=port
		self.username=username
		self.password=password
		self.url=url
		self.cfile=cfile
		self.downTypeList=[]
		self.repeatServerList=[]
		self.realIpandPort=[]
		self.pidfile=''
		self.w=logfile
	def regexFind(self,c1='',c2=''):
		c=ur''+c1+'\ *'
		j=0
		for i in c2.split(','):
			if j>0:
				if re.search(c,i):
					return True
					break
			j+=1
		return False

	def connect(self):
		params = urllib.urlencode({'stats':'ok'})
		auth = base64.b64encode(self.username+ ':'+ self.password)
		headers = {"Authorization": "Basic "+ auth}
		conn = httplib.HTTPConnection(self.host+":"+self.port)
		conn.request("GET", self.url, params, headers)
		response = conn.getresponse()
		a=response.read().strip().split('\n')
		if response.status != 200:
			return	False
		'''
		print response.status
		print response.reason
		'''
		t=0
		while 1:
			if t == len(a):
				break
			'''
			if 'BACKEND' in a[t].split(',') or \
			'FRONTEND' in a[t].split(',') or \
			'UP' in a[t].split(',') or \
			'hrsp_other' in a[t].split(','):
			'''
			if self.regexFind(c1='BACKEND',c2=a[t])\
			or self.regexFind(c1='FRONTEND',c2=a[t])\
			or self.regexFind(c1='UP',c2=a[t])\
			or self.regexFind(c1='hrsp_other',c2=a[t]):
				del a[t]
			else:
				t+=1
		self.downTypeList=a
		conn.close
		return True

	def findRepeatServerEntry(self):
		chars=''
		r=[]
		for t in self.downTypeList:
			r.append(t.split(',')[0]+','+t.split(',')[1])
		for t in range(0,len(r)-1):#0,3
			b=[]
			p=r[t].split(',')[0]
			m=0
			for o in range(t+1,len(r)):#0,3
				if r[t].split(',')[1] == r[o].split(',')[1] and o not in b:
					m=1
					p=p+" ,"+r[o].split(',')[0]
					b.append(o)
			if m==1:
				chars=chars+ p+'has repeat serverlist:'+r[t].split(',')[1]+'\n'
				self.repeatServerList.append(r[t].split(',')[1])
		return chars
	def parseConfigFile(self):
		#print self.downTypeList
		#r=[]
		for t in self.downTypeList:
			#r.append(t.split(',')[0]+','+t.split(',')[1])
			try:
				if os.path.exists(self.cfile):
					f=open(self.cfile,'r')
					k=0
					for i in f:
						chars1=ur'listen\ .*'+t.split(',')[0]+'\ *'
						chars2=ur'listen.*'
						chars3=ur'\ *pidfile\ *'
						if re.search(chars1,i):
							k+=1
						if k>=1 and k<2:
							try:
								m =  " ".join(i.split())
								if m.strip().split(' ')[1] == t.split(',')[1] and not m.find('#')+1:
									self.realIpandPort.append( m.strip().split(' ')[2].strip())
							except:
								pass
						if re.search(chars2,i) and not re.search(chars1,i) and k>0:
							k+=1
						if re.search(chars3,i):
							self.pidfile=i.strip().split(' ')[1]
			except Exception, e:
				self.w.w(str( e))
				#w(self.cfile+' isn"t exist')
	def probePort(self):
		t=0
		for i in self.realIpandPort:
			try:
				s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
			except socket.error, msg:
				self.w.w(log='Failed to create socket. Error code: ' + str(msg[0]) + ' , Error message : ' + msg[1])
				continue
			s.settimeout(5)
			if not re.findall(r'\d+.\d+.\d+.\d+',i.split(':')[0]):
				try:
					socket.setdefaulttimeout(5)
					remote_ip = socket.gethostbyname(i.split(':')[0])
				except socket.gaierror:
					self.w.w(log='Hostname could not be resolved. Exiting')
					continue
			else:
				self.w.w(log='probe object is ip "'+i.split(':')[0]+'".skip it.')
				continue
			try:
				#s.connect((i.split(':')[0],int(i.split(':')[1])))
				s.connect((remote_ip,int(i.split(':')[1])))
				s.shutdown(2)
				self.w.w(log='forward service type:'+self.downTypeList[t].split(',')[0]+' ,probe host and port,'+ i+ ' open,smooth this service')
				self.restartSmooth()
				s.close()
			except Exception,e:
				try:
					self.w.w(log= 'forward service type:'+self.downTypeList[t].split(',')[0]+' ,probe host and port, open "'+  i+ '" failed.'+' return msg: '+str(e))
				except Exception,e:
					self.w.w(log=str(e)+' unkown error')
				pass
			t+=1
	def restartSmooth(self):
		self.w.w(log=commands.getstatusoutput('source /etc/profile;/opt/app1/sbin/haproxy -f '+self.cfile+' -sf `cat '+self.pidfile+'`'))
		

if __name__ == "__main__":
	list=[{'host':'10.90.90.91','port':'8889','username':'admin','password':'admin','url':'/stats;csv;norefresh','cfile':'/opt/app1/haproxy.cfg'},\
	{'host':'10.90.90.92','port':'8888','username':'admin','password':'admin','url':'/stats;csv;norefresh','cfile':'/opt/app1/haproxy.cfg'}]
	daemon = MyDaemon('/var/run/haproxy-deamon.pid',list)
	#daemon.test()
	#sys.exit(0)
	if len(sys.argv) == 2:
		if 'start' == sys.argv[1]:
			daemon.start()
		elif 'stop' == sys.argv[1]:
			daemon.stop()
		elif 'restart' == sys.argv[1]:
			daemon.restart()
		else:
			print "Unknown command"
			sys.exit(2)
		sys.exit(0)
	else:
		print "usage: %s start|stop|restart" % sys.argv[0]
		sys.exit(2)
