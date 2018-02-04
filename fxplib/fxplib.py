from __future__ import print_function #Fix lambda print
import hashlib
import re
import requests
import time
import json
from bs4 import BeautifulSoup
from requests_toolbelt.multipart.encoder import MultipartEncoder
import os.path
import random

from .fxplive import *
from .helpers import *  
from .forums_objects import *

def fxpRegister(username, password, email):
	md5password = hashlib.md5(password.encode('utf-8')).hexdigest()
	r = requests.post('https://www.fxp.co.il/register.php?do=addmember', data={
		'username':username,
		'password':'',
		'passwordconfirm':'',
		'email':email,
		'emailconfirm':email,
		'agree':1,
		's':'',
		'securitytoken':'guest',
		'do':'addmember',
		'url':'https://www.fxp.co.il/forumdisplay.php?f=21',
		'password_md5':md5password,
		'passwordconfirm_md5':md5password,
		'day':'',
		'month':'',
		'year':''
	})
	if 'תודה לך' in r.text:
		return fxp(username, password)
	else:
		return False

class fxp():
	def __init__(self, username, password):
		self.loggedin = False
		self.sess = requests.Session()
		self.username = username
		#self.password = password #Security issue - Not needed 
		self.md5password = hashlib.md5(password.encode('utf-8')).hexdigest()
		self.securitytoken = 'guest'
		self.userid = None
		self.liveupdatetoken = None #For Socket.io connection
		self.sess.headers.update({
			'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
		})
		self.livefxp = fxpLive(self)

	#[Middleware] Is user logged in?
	def __getattribute__(self, attr):
		import types
		method = object.__getattribute__(self, attr)
		if type(method) == types.MethodType:
			if not self.loggedin and attr != 'login': #See me - Allow login function
				print ('[*] Please login to use "%s" function' % attr)
				return (lambda *args : None)
			else:
				return method
		else:
			return method

	#Login with user data
	def login(self):
		if self.loggedin != True:
			login_req = self.sess.post('https://www.fxp.co.il/login.php?do=login', data={
				'do':'login',
				'vb_login_md5password':self.md5password,
				'vb_login_md5password_utf':self.md5password,
				's':None,
				'securitytoken':self.securitytoken,
				'url':'https://www.fxp.co.il/index.php',
				'vb_login_username':self.username,
				'vb_login_password':None,
				'cookieuser':1
			})
			if 'USER_ID_FXP' in login_req.text:
				home_req = self.sess.get('https://www.fxp.co.il')
				if 'הושעת' in home_req.text: return False
				self.securitytoken = re.search('SECURITYTOKEN = "(.+?)";', home_req.text).group(1)
				self.userid = login_req.cookies.get_dict()['bb_userid']
				self.liveupdatetoken = self.sess.cookies.get_dict()['bb_livefxpext']
				self.loggedin = True
				return True
			else: 
				return False
		else:
			return True

	#user.createThread(TITLE, CONTENT, FORUM_ID)
	def createThread(self, title, content, froumid, prefix=''):
		#if prefix == '': fxpData.prefixIds[froumid][prefix]
		r = self.sess.post('https://www.fxp.co.il/newthread.php?do=newthread&f=%s' % froumid, data={
			'prefixid':prefix,
			'subject':title,
			'message_backup':'',
			'message':content,
			'wysiwyg':1,
			's':None,
			'securitytoken':self.securitytoken,
			'f':int(froumid),
			'do':'postthread',
			'posthash':'',
			'poststarttime':'',
			'loggedinuser':self.userid,
			'sbutton':'צור אשכול חדש',
			'signature':1,
			'parseurl':1
		})
		if 'https://www.fxp.co.il/newthread.php?' in r.url:
			return False
		else:
			nRe = re.search('t=(.*?)&p=(.*?)#post', r.url)
			return {'eshkolid':nRe.group(1), 'postid': nRe.group(2), 'url': r.url}
		
	def comment(self, threadid, content):
		if hasattr(self, '_lastComment'):
			if self._lastComment == content:
				return False
			self._lastComment = content
		else:
			self._lastComment = None

		r = self.sess.post('https://www.fxp.co.il/newreply.php?do=postreply&t=%s' % str(threadid), data={
			'securitytoken': self.securitytoken, 
			'ajax': '1', 
			'message_backup': content,
			'message': content, 
			'wysiwyg': '1', 
			'signature': '1',
			'fromquickreply': '1',
			's': '', 
			'do': 'postreply',
			't': int(threadid),
			'p': 'who cares',
			'specifiedpost': 1, 
			'parseurl': 1, 
			'loggedinuser': self.userid,
			'poststarttime':int(time.time())
		})
		if 'newreply' in r.text:
			return re.search('<newpostid>(.*?)</newpostid>', r.text).group(1)
		else:
			return False
	
	#TODO: Add to repo option list
	def reply(self, replyToComment, content, spamPrevention=False):
		if spamPrevention:
			content += ' [COLOR=#fafafa]%s[/COLOR]' % str('{:03}'.format(random.randrange(1, 10**4))) #Spam prevention
		
		if type(replyToComment) == FxpComment:
			newCommentid = self.comment(
				replyToComment.threadid, 
				'[QUOTE=%s;%s]%s[/QUOTE]%s' % (replyToComment.username, replyToComment.id, replyToComment.content, content)
			)
		elif type(replyToComment) == FxpThread:
			newCommentid = self.comment(
				replyToComment.id, 
				'[QUOTE=%s;%s]%s[/QUOTE]%s' % (replyToComment.username, replyToComment.commentid, replyToComment.content, content)
			)
		else:
			return False


		if newCommentid:
			return newCommentid
		else:
			return False


	def editComment(self, commentid, message, add=False):
		r = self.sess.post('https://www.fxp.co.il/ajax.php?do=quickedit&p=%s' % str(commentid), data={
			'securitytoken':self.securitytoken,
			'do':'quickedit',
			'p':int(commentid),
			'editorid':'vB_Editor_QE_1',
		})

		oldComment = re.search('tabindex="1">([^<]+)<\/textarea>',r.text)
		if oldComment == None:
			return False
		oldComment = oldComment.group(1)

		if add == True:
			message = '%s\n%s' % (oldComment, message)

		r = self.sess.post('https://www.fxp.co.il/editpost.php?do=updatepost&postid=%s' % str(commentid), data={
			'securitytoken':self.securitytoken,
			'do':'updatepost',
			'ajax':1,
			'postid':int(commentid),
			'message':str(message),
			'poststarttime':int(time.time()), #1507850377
		})
		return '<postbit><![CDATA[' in r.text
		
	def like(self, msgid):
		r = self.sess.post('https://www.fxp.co.il/ajax.php', data={
			'do':'add_like',
			'postid': msgid,
			'securitytoken': self.securitytoken
		})
		r = self.sess.get('https://www.fxp.co.il/showthread.php?p=%s#post%s' % (msgid, msgid))
		return BeautifulSoup(r.text, "html.parser").find(id='%s_removelike' % msgid) == None

	def createPrivateChat(self, to, title, message):
		r = self.sess.post('https://www.fxp.co.il/private_chat.php', data={
			'securitytoken': self.securitytoken, 
			'do': 'insertpm', 
			'recipients': to, 
			'title': title, 
			'message': message, 
			'savecopy': '1', 
			'signature': '1', 
			'parseurl': '1', 
			'frompage': '1',
		})
		if 'parentpmid' in r.text:
			return {'pmid':r.json()['parentpmid'],'to':to}
		else:
			return False

	def sendPrivateChat(self, to, pmid, message):
		r = self.sess.post('https://www.fxp.co.il/private_chat.php', data={
		   "message":str(message),
		   "fromquickreply":"1",
		   "securitytoken":self.securitytoken,
		   "do":"insertpm",
		   "pmid":int(pmid),
		   "loggedinuser":self.userid,
		   "parseurl":"1",
		   "signature":"1",
		   "title":"תגובה להודעה: ",
		   "recipients":to,
		   "forward":"0",
		   "savecopy":"1",
		   "fastchatpm":"1",
		   "randoomconv":"20770018",
		   "wysiwyg":"1"
		})
		if 'pmid' in r.text:
			return True
		else:
			return False 

	def updateProfileImage(self, imagePath):
		imageExt = imagePath.lower().split('.')[-1]
		if not imageExt in ['gif','png','jpg','jpeg']:
			return False
		if imageExt == 'jpg':
			imageExt = 'jpeg'

		imageData = None
		if urlAlive(imagePath):
			imageData = requests.get(imagePath).content
		else:
			if os.path.isfile(imagePath):
				imageData = open(imagePath, 'rb') 
			else:
				return False
		

		print ('[*] Uploading image to fxp server')
		
		multipart_data = MultipartEncoder(
			fields=
			{
				'fileToUpload': ('image.%s' % imageExt, imageData, 'image/%s' % imageExt)
			}
		)
		r = requests.post('https://www.fxp.co.il/uploads/difup.php', data=multipart_data, headers={'Content-Type': multipart_data.content_type})
		
		if not 'image_link' in r.text:
			return False
		else:
			image_url = r.json()['image_link']
			print (image_url)
			
			r = self.sess.post('https://www.fxp.co.il/private_chat.php', data={
				'do':'update_profile_pic',
				'profile_url':image_url,
				'user_id':self.userid,
				'securitytoken':self.securitytoken
			})
			return r.text == 'ok'


	'''
	def ForumThreadsList(self, forum, page=0):
		page = page + 1 #fix bug - i think
		r = self.sess.get('https://www.fxp.co.il/forumdisplay.php?f=%s&page=%s' % (forum,page))
		return re.findall('id="thread_title_(.*?)"',r.text)



	def searchFourmId(self, name=None):
		if name == None:
			return self.sess.get('https://www.fxp.co.il/ajax.php?do=forumdisplayqserach').json()
		else:
			return self.sess.get('https://www.fxp.co.il/ajax.php?do=forumdisplayqserach&name_startsWith=%s' % name).json()
	'''