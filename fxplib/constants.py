from .helpers import url_path_join

BASIC_URL = 'https://www.fxp.co.il'
INDEX_URL = url_path_join(BASIC_URL, 'index.php')
LOGIN_URL = url_path_join(BASIC_URL, 'login.php?do=login')
NEW_THREAD_URL = url_path_join(BASIC_URL, 'newthread.php?do=newthread&f={}')
COMMENT_URL = url_path_join(BASIC_URL, 'newreply.php?do=postreply&t={}')
