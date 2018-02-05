import re
import json

from bs4 import BeautifulSoup
from .forums_objects import *
from pymitter import EventEmitter
from .socketioclient import SocketIOCli

fxp_events = EventEmitter(wildcards=True)

REPLACEMENTS = {
    '&amp;quot;': '"',
    'amp;amp;': '^',
    '&amp;lt;': '<',
    '&amp;gt;': '>'
}


class FxpLive(object):
    def __init__(self, user):
        super(FxpLive, self).__init__()
        self.user = user
        self._live_connection_forums = []
        self.socketIO = None

    # connect function
    def connect(self, debug=False):
        if self.socketIO is None:
            if self.user.liveupdatetoken is None:
                print('[*] Please login before you try to init live connection')
                return False
            self.socketIO = SocketIOCli('https://socket5.fxp.co.il')
            self.socketIO.on_connect = lambda cli: print('[*] Connected')

            # login to the live events system
            self.socketIO.emit(
                ['message', json.dumps({'userid': self.user.liveupdatetoken})])
            # self.addForum('', raw=True)

            self.socketIO.on('newtread', callback=self._on_new_tread_parse)
            self.socketIO.on('update_post', callback=self._on_new_post_parse)
            self.socketIO.on('newpmonpage',
                             callback=self._on_new_private_message_parse)


            if debug:
                def on_message(ws, msg):
                    return ws.on_message, print(msg)

                self.socketIO.ws.on_message = on_message

        return self.socketIO

    # ---------------Help Functions---------------#
    def add_forum(self, forum_id_node_js, raw=False):
        forum_name = forum_id_node_js
        if forum_id_node_js == '':
            forum_name = '-'

        if not raw:
            forum_data = self.get_forum_node_id_by_id(forum_id_node_js)
            if not forum_data:
                print('[*] Error, Can\'t add "%s"' % forum_id_node_js)
                return
            forum_id_node_js, forum_name = forum_data['id'], forum_data['name']

        if forum_id_node_js not in self._live_connection_forums:
            self.socketIO.emit(['message', json.dumps(
                {'userid': self.user.liveupdatetoken,
                 'froum': forum_id_node_js})])
            self._live_connection_forums.append(forum_id_node_js)
            print('[*] Add new forum to live connection: %s' % forum_name[::-1])

    def get_forum_node_id_by_id(self, forum_id):
        try:
            url = 'https://www.fxp.co.il/forumdisplay.php?f={}'.format(forum_id)
            r = self.user.sess.get(url)
            forum_id_node_js = re.search(',"froum":"(.+?)"}', r.text).group(1)
            forum_name = re.search('forumname = "(.+?)";', r.text).group(1)
            forum_name = forum_name.replace('&quot;', '"')  # fix
            return {'id': forum_id_node_js, 'name': forum_name}
        except Exception:
            return False
    # /---------------Help Functions---------------/#

    # ---------------Socket.io events Functions---------------#
    def _on_new_private_message_parse(self, io, data, *ex_prms):
        if data['send'] == self.user.userid:
            return

        for old, new in REPLACEMENTS.items():
            data['messagelist'] = data['messagelist'].replace(old, new)

        fxp_events.emit('newpm', data)

    def _on_new_tread_parse(self, io, data, *ex_prms):
        if (data['username'] == self.user.username or
                data['username'] == self.user.userid):
            return

        try:
            params = dict(t=data['id'], web_fast_fxp=1)
            r = self.user.sess.get('https://www.fxp.co.il/showthread.php',
                                   params=params)

            soup = BeautifulSoup(r.text, "html.parser")

            # FIRST PARSER - 4/2/2018 (web_fast_fxp)
            thread_content = soup.find(class_='postcontent restore simple')
            content = '\n'.join(filter(None, thread_content.text.splitlines()))
            comment_id = soup.find(id=re.compile('post_message_(.*?)')) \
                .attrs['id'].replace('post_message_', '')

            fxp_events.emit('newthread', FxpThread(
                username=data['username'],
                user_id=data['poster'],
                id_=data['id'],
                title=data['title'],
                content=content,
                comment_id=comment_id,
                prefix=data['prefix']
            ))

        except Exception:
            # print (e)
            pass

    def _on_new_post_parse(self, io, data, *ex_prms):
        username = data['lastpostuser']
        user_id = data['lastpostuserid']
        if username == self.user.username or user_id == self.user.userid:
            return

        try:
            params = dict(t=data['id'], page=data['pages'], web_fast_fxp=1)
            r = self.user.sess.get('https://www.fxp.co.il/showthread.php',
                                   params=params)

            soup = BeautifulSoup(r.text, "html.parser")

            # NEW PARSER - 4/2/2018 (web_fast_fxp)
            comment_html = soup.find_all(class_='user_pic_%s' % user_id)[-1] \
                .parent.parent.parent.parent.parent

            content_parent_html = comment_html.find(class_='content')

            msg_id = content_parent_html.find(
                id=re.compile('post_message_(.*?)')
            ).attrs['id'].replace('post_message_', '')

            post_content = content_parent_html.find(
                class_='postcontent restore '
            )

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

            # remove quotes from the message
            if post_content.find(class_='bbcode_quote') is not None:
                post_content.find(class_='bbcode_container').decompose()
            # return

            # filter youtube content
            if post_content.find(class_='videoyoudiv') is not None:
                return

            # filter messages that contain images
            if post_content.find('img') is not None:
                return

            # filter messages that contain videos
            if post_content.find('video') is not None:
                return

            # remove empty lines
            content = '\n'.join(filter(None, post_content.text.splitlines()))

            fxp_events.emit('newcomment', FxpComment(
                username=username,
                user_id=user_id,
                content=content,
                thread_id=int(data['id']),
                thread_title=data['title'],
                comment_id=int(msg_id),
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
        except Exception:
            # print (e)
            pass

    # /---------------Socket.io events Functions---------------/#

    # ---------------------New---------------------
    def user_node_data(self):
        url = 'https://www.fxp.co.il/showthread.php?t=1239165'
        r = self.user.sess.get(url)  # MUST SEE THAT
        user_id_node_js = re.search('var useridnodejs = "(.+?)";',
                                    r.text).group(1)
        user_name_node_js = re.search('var usernamenodejs = "(.+?)";',
                                      r.text).group(1)
        return {'id': user_id_node_js, 'username': user_name_node_js}

    # ---------------------New---------------------

    # ---------------------TEST--------------------
    def get_node_id(self, thread_id):
        url = 'https://www.fxp.co.il/showthread.php?t={}'.format(thread_id)
        r = self.user.sess.get(url)
        return re.search('var threadidnode = "(.*?)";', r.text).group(1)
    # ---------------------TEST--------------------
