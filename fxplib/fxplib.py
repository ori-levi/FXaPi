from __future__ import print_function  # Fix lambda print

import time
import random
import hashlib
import os.path

from .user import User
from .helpers import *
from .fxp_live import *
from .forums_objects import *
from requests_toolbelt.multipart.encoder import MultipartEncoder
from .constants import *

COMMENT_ID_RE = re.compile('<newpostid>(.*?)</newpostid>')


def fxp_register(username, password, email):
    # TODO: check this function
    md5password = hashlib.md5(password.encode('utf-8')).hexdigest()

    data = dict(
        username=username,
        password='',
        passwordconfirm='',
        email=email,
        emailconfirm=email,
        agree=1,
        s='',
        securitytoken='guest',
        do='addmember',
        url='https://www.fxp.co.il/forumdisplay.php?f=21',
        password_md5=md5password,
        passwordconfirm_md5=md5password,
        day='',
        month='',
        year=''
    )

    r = requests.post('https://www.fxp.co.il/register.php?do=addmember', data)
    if 'תודה לך' in r.text:
        return Fxp(username, password)
    return None


class Fxp(object):
    def __init__(self, username, password, is_live_connection=True):
        super(Fxp, self).__init__()

        self.user = User(username, password)
        self.live_fxp = FxpLive(self.user) if is_live_connection else None

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWeb'
                          'Kit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132'
                          ' Safari/537.36'
        })

    def login(self):
        return self.user.login(self.session)

    def create_thread(self, title, content, forum_id, prefix=''):
        """
        :type title: str
        :type content: str
        :type forum_id: int
        :type prefix: str
        :rtype: dict|None
        """
        thread_params = dict(
            prefixid=prefix,
            subject=title,
            message_backup='',
            message=content,
            wysiwyg=1,
            s=None,
            securitytoken=self.security_token,
            f=forum_id,
            do='postthread',
            posthash='',
            poststarttime='',
            loggedinuser=self.user_id,
            sbutton='צור אשכול חדש',
            signature=1,
            parseurl=1
        )

        url = NEW_THREAD_URL.format.format(forum_id)
        response = self.session.post(url, thread_params)

        if 'https://www.fxp.co.il/newthread.php?' in response.url:
            return None

        n_re = re.search('t=(.*?)&p=(.*?)#post', response.url)
        return dict(
            eshkolid=n_re.group(1),
            postid=n_re.group(2),
            url=response.url
        )

    def comment(self, thread_id, content):
        comment_params = dict(
            securitytoken=self.security_token,
            ajax='1',
            message_backup=content,
            message=content,
            wysiwyg='1',
            signature='1',
            fromquickreply='1',
            s='',
            do='postreply',
            t=int(thread_id),
            p='who cares',
            specifiedpost=1,
            parseurl=1,
            loggedinuser=self.user_id,
            poststarttime=int(time.time())
        )

        url = COMMENT_URL.format(thread_id)
        response = self.session.post(url, comment_params)

        if 'newreply' in response.text:
            return COMMENT_ID_RE.search(response.text).group(1)
        return None

    def reply(self, reply_to_comment, content, spam_prevention=True):
        # TODO: Add to repo option list

        if spam_prevention:
            content += ' [COLOR=#fafafa]{:03}[/COLOR]'.format(
                random.randrange(1, 10 ** 4)
            )

        if isinstance(reply_to_comment, FxpComment):
            content = '[QUOTE={};{}]{}[/QUOTE]{}'.format(
                reply_to_comment.username,
                reply_to_comment.id,
                reply_to_comment.content,
                content
            )
            new_comment_id = self.comment(reply_to_comment.thread_id, content)

        elif isinstance(reply_to_comment, FxpThread):
            content = '[QUOTE={};{}]{}[/QUOTE]{}'.format(
                reply_to_comment.username,
                reply_to_comment.comment_id,
                reply_to_comment.content,
                content
            )
            new_comment_id = self.comment(reply_to_comment.id, content)
        else:
            return False

        return new_comment_id

    # ######################################################################

    def edit_comment(self, comment_id, message, add=False):
        url = 'https://www.fxp.co.il/ajax.php?do=quickedit&p={}'\
            .format(comment_id)
        r = self.session.post(
            url,
            data={
                'securitytoken': self.security_token,
                'do': 'quickedit',
                'p': int(comment_id),
                'editorid': 'vB_Editor_QE_1',
            })

        old_comment = re.search('tabindex="1">([^<]+)</textarea>', r.text)
        if not old_comment:
            return False
        old_comment = old_comment.group(1)

        if add:
            message = '%s\n%s' % (old_comment, message)

        r = self.session.post(
            'https://www.fxp.co.il/editpost.php?do=updatepost&postid=%s' % str(
                comment_id), data={
                'securitytoken': self.security_token,
                'do': 'updatepost',
                'ajax': 1,
                'postid': int(comment_id),
                'message': str(message),
                'poststarttime': int(time.time()),  # 1507850377
            })
        return '<postbit><![CDATA[' in r.text

    def like(self, msg_id):
        self.session.post('https://www.fxp.co.il/ajax.php', data={
            'do': 'add_like',
            'postid': msg_id,
            'securitytoken': self.security_token
        })
        r = self.session.get(
            'https://www.fxp.co.il/showthread.php?p=%s#post%s' % (msg_id, msg_id))

        id_ = '%s_removelike' % msg_id
        return BeautifulSoup(r.text, "html.parser").find(id=id_) is None

    def create_private_chat(self, to, title, message):
        r = self.session.post('https://www.fxp.co.il/private_chat.php', data={
            'securitytoken': self.security_token,
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
            return {'pmid': r.json()['parentpmid'], 'to': to}
        else:
            return False

    def send_private_chat(self, to, private_message_id, message):
        r = self.session.post('https://www.fxp.co.il/private_chat.php', data={
            "message": str(message),
            "fromquickreply": "1",
            "securitytoken": self.security_token,
            "do": "insertpm",
            "pmid": int(private_message_id),
            "loggedinuser": self.user_id,
            "parseurl": "1",
            "signature": "1",
            "title": "תגובה להודעה: ",
            "recipients": to,
            "forward": "0",
            "savecopy": "1",
            "fastchatpm": "1",
            "randoomconv": "20770018",
            "wysiwyg": "1"
        })
        if 'pmid' in r.text:
            return True
        else:
            return False

    def update_profile_image(self, image_path):
        image_ext = image_path.lower().split('.')[-1]
        if image_ext not in ['gif', 'png', 'jpg', 'jpeg']:
            return False
        if image_ext == 'jpg':
            image_ext = 'jpeg'

        image_data = None
        if url_alive(image_path):
            image_data = requests.get(image_path).content
        else:
            if os.path.isfile(image_path):
                image_data = open(image_path, 'rb')
            else:
                return False

        print('[*] Uploading image to fxp server')

        multipart_data = MultipartEncoder(
            fields=
            {
                'fileToUpload': (
                    'image.%s' % image_ext, image_data, 'image/%s' % image_ext)
            }
        )
        r = requests.post('https://www.fxp.co.il/uploads/difup.php',
                          data=multipart_data,
                          headers={'Content-Type': multipart_data.content_type})

        if 'image_link' not in r.text:
            return False
        else:
            image_url = r.json()['image_link']
            print(image_url)

            r = self.session.post('https://www.fxp.co.il/private_chat.php', data={
                'do': 'update_profile_pic',
                'profile_url': image_url,
                'user_id': self.user_id,
                'securitytoken': self.security_token
            })
            return r.text == 'ok'

    # [Middleware] Is user logged in?
    def __getattribute__(self, attr):
        import types
        method = object.__getattribute__(self, attr)
        if type(method) == types.MethodType:
            # See me - Allow login function
            if not self.logged_in and attr != 'login':
                print('[*] Please login to use "%s" function' % attr)
                return lambda *args: None
            else:
                return method
        else:
            return method

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
