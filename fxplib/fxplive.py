from __future__ import print_function #Fix lambda print
from pymitter import EventEmitter
from .socketioclient import SocketIOCli
import requests
from bs4 import BeautifulSoup
import time
import json
import re
from .forums_objects import *

FxpEvents = EventEmitter(wildcards=True)



class fxpLive():
	def __init__(self, user):
		self.user = user
		self._liveConnectionForums = []
		self.socketIO = None

	#connect function
	def connect(self, debug=False):
		if self.socketIO == None:
			if self.user.liveupdatetoken == None: 
				print ('[*] Please login before you try to init live connection')
				return False
			self.socketIO = SocketIOCli('https://socket5.fxp.co.il')
			self.socketIO.on_connect = print ('[*] Connected')
			
			#login to the live events system
			self.socketIO.emit(['message', json.dumps({'userid':self.user.liveupdatetoken})])
			#self.addForum('', raw=True)


			self.socketIO.on('newpmonpage', callback=self._on_newpm_parse)
			self.socketIO.on('update_post', callback=self._on_newpost_parse)
			self.socketIO.on('newtread', callback=self._on_newtread_parse)

			if debug == True:
				self.socketIO.ws.on_message = lambda ws, msg: (ws.on_message, print(msg))

		return self.socketIO

	#---------------Help Functions---------------#
	def addForum(self, forumidNodejs, raw=False):
		forumname = forumidNodejs
		if forumidNodejs == '': forumname = '-'
		if not raw:
			forumData = self.getForumNodeidById(forumidNodejs) #livefxp.getForumNodeidById(21)
			if forumData == False:
				print ('[*] Error, Can\'t add "%s"' % forumidNodejs)
				return
			forumidNodejs, forumname = forumData['id'], forumData['name']

		if not forumidNodejs in self._liveConnectionForums:
			self.socketIO.emit(['message', json.dumps({'userid':self.user.liveupdatetoken,'froum':forumidNodejs})])
			self._liveConnectionForums.append(forumidNodejs)
			print ('[*] Add new forum to live connection: %s' % forumname[::-1])


	def getForumNodeidById(self, froumid):
		try:
			r = self.user.sess.get('https://www.fxp.co.il/forumdisplay.php?f=%s' % froumid)
			forumidNodejs = re.search(',"froum":"(.+?)"}', r.text).group(1)
			forumname = re.search('forumname = "(.+?)";', r.text).group(1)
			forumname = forumname.replace('&quot;','"') #fix
			return {'id': forumidNodejs, 'name':forumname}		
		except Exception as e:
			return False
	#/---------------Help Functions---------------/#

	#---------------Socket.io events Functions---------------#
	def _on_newpm_parse(self, io, data, *ex_prms):
		if data['send'] == self.user.userid: 
			return
		data['messagelist'] = data['messagelist'].replace('&amp;quot;','"').replace('amp;amp;', '^').replace('&amp;lt;','<').replace('&amp;gt;','>')
		FxpEvents.emit('newpm', data)

	def _on_newtread_parse(self, io, data, *ex_prms):
		if data['username'] == self.user.username or data['username'] == self.user.userid: return
		try:
			r = self.user.sess.get('https://www.fxp.co.il/showthread.php', params={
				't':data['id'],
				'web_fast_fxp':1 #make page length smaller
			})
			soup = BeautifulSoup(r.text, "html.parser")

			#FIRST PARSER - 4/2/2018 (web_fast_fxp)
			threadContent = soup.find(class_='postcontent restore simple')
			content = '\n'.join( list(filter(None, threadContent.text.splitlines())) )
			commentid = soup.find(id=re.compile('post_message_(.*?)')).attrs['id'].replace('post_message_', '')


			FxpEvents.emit('newthread', FxpThread(
				username=data['username'],
				user_id=data['poster'],
				id=data['id'],
				title=data['title'],
				content=content,
				comment_id=commentid,
				prefix=data['prefix']
			))

		except Exception as e:	
			#print (e)		
			pass

	def _on_newpost_parse(self, io, data, *ex_prms):	
		username = data['lastpostuser']
		userid = data['lastpostuserid']
		if username == self.user.username or userid == self.user.userid: return
		try:
			r = self.user.sess.get('https://www.fxp.co.il/showthread.php', params={
				't':data['id'],
				'page':data['pages'],
				'web_fast_fxp':1 #make page length smaller
			})
			soup = BeautifulSoup(r.text, "html.parser")
			
			#NEW PARSER - 4/2/2018 (web_fast_fxp)
			commentHtml = soup.find_all(class_='user_pic_%s'%userid)[-1].parent.parent.parent.parent.parent
			contentParentHtml = commentHtml.find(class_='content')
			msgid = contentParentHtml.find(id=re.compile('post_message_(.*?)')).attrs['id'].replace('post_message_', '')
			postcontent = contentParentHtml.find(class_='postcontent restore ')

			'''
			#UPDATED ON 31/12/2017 
			msgid = soup.find(class_='postcounter', text='#%s'%str(data['posts']+1)).attrs['name'].replace('post','')
			postcontent = soup.find(id='post_message_%s' % msgid).find(class_='postcontent restore')
			'''

			'''
			#FIRST PARSER
			print (soup.find_all('li', class_='postbit postbitim postcontainer')[0].find(class_='username'))
			userHtml = soup.find_all('div', attrs={'data-user-id':userid})[-1].parent.parent #not working properly (not all the time)
			postcontent = userHtml.find(class_='postcontent restore')
			msgid = int(re.search('post_message_(.+)', userHtml.find(class_='content').find('div').get('id')).group(1))
			'''

			#remove quotes from the message
			if postcontent.find(class_='bbcode_quote') != None:
				postcontent.find(class_='bbcode_container').decompose()
				#return

			#filter youtube content
			if postcontent.find(class_='videoyoudiv') != None:
				return

			#filter messages that contain images
			if postcontent.find('img') != None:
				return

			#filter messages that contain vides
			if postcontent.find('video') != None:
				return
			
			#remove empty lines
			content = '\n'.join( list(filter(None, postcontent.text.splitlines())) )

			FxpEvents.emit('newcomment', FxpComment(
				username=username,
				user_id=userid,
				content=content,
				thread_id=int(data['id']),
				thread_title=data['title'],
				comment_id=int(msgid),
				posts_number=int(data['posts'])
			))
			'''
			postData = {
				'username': username,
				'userid': userid,
				'eshkolid': int(data['id']),
				'eshkoltitle': data['title'],
				'commentid': int(msgid),
				'content': content,
				'postsnumber': int(data['posts'])
			}

			FxpEvents.emit('newcomment', postData)
			'''
		except Exception as e:	
			#print (e)		
			pass		

	#/---------------Socket.io events Functions---------------/#


	#---------------------New---------------------
	def userNodeData(self):
		r = self.user.sess.get('https://www.fxp.co.il/showthread.php?t=1239165') #MUST SEE THAT
		useridnodejs = re.search('var useridnodejs = "(.+?)";', r.text).group(1)
		usernamenodejs = re.search('var usernamenodejs = "(.+?)";', r.text).group(1)
		return {'id':useridnodejs, 'username':usernamenodejs}
	#---------------------New---------------------

	#---------------------TEST--------------------
	def getnodeid(self, THREAD_ID):
		r = self.user.sess.get('https://www.fxp.co.il/showthread.php?t=%s' % THREAD_ID)
		return re.search('var threadidnode = "(.*?)";', r.text).group(1)
	#---------------------TEST--------------------
