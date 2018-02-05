import re
import hashlib
import requests

from .constants import INDEX_URL, LOGIN_URL

USER_ID = 'USER_ID_FXP'
BANNED = 'הושעת'
SECURITY_TOKEN_RE = re.compile('SECURITYTOKEN = "(.+?)";')


class User(object):
    def __init__(self, username, password):
        super(User, self).__init__()
        self.username = username
        self.password = hashlib.md5(password.encode('utf-8')).hexdiget()
        self.user_id = None
        self.logged_in = False
        self.security_token = 'guest'
        self.live_update_token = None

    def login(self, session):
        """
        :type session: requests.Session
        :rtype: bool
        """
        if not self.logged_in:
            login_params = dict(
                do='login',
                vb_login_md5password=self.password,
                vb_login_md5password_utf=self.password,
                s=None,
                securitytoken=self.security_token,
                url=INDEX_URL,
                vb_login_username=self.username,
                vb_login_password=None,
                cookieuser=1
            )

            login_response = session.post(LOGIN_URL, login_params)

            if USER_ID not in login_response.text:
                return False

            home_res = session.get('https://www.fxp.co.il')
            if BANNED in home_res.text:
                return False

            self.security_token = SECURITY_TOKEN_RE.search(home_res.text).group(1)
            self.user_id = login_response.cookies.get_dict()['bb_userid']
            self.live_update_token = session.cookies.get_dict()['bb_livefxpext']
            self.logged_in = True

            return True
        else:
            return True


