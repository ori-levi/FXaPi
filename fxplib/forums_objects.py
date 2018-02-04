from abc import ABCMeta, abstractmethod


class FxpBaseObject(object, metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, username, user_id, id_, content):
        super(FxpBaseObject, self).__init__()
        self.username = username
        self.user_id = user_id
        self.id = id_
        self.content = content


class FxpThread(FxpBaseObject):
    def __init__(self, username, user_id, id_, title, content, comment_id,
                 prefix=''):
        super(FxpThread, self).__init__(username, user_id, id_, content)

        self.title = title
        self.prefix = prefix
        self.comment_id = comment_id


class FxpComment(FxpBaseObject):
    def __init__(self, username, user_id, content, thread_id, thread_title,
                 comment_id, posts_number):
        super(FxpComment, self).__init__(username, user_id, comment_id, content)

        self.thread_id = thread_id
        self.thread_title = thread_title
        self.posts_number = posts_number
