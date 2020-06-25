# coding=gbk
from datetime import datetime

from source.data.bean.Beanbase import BeanBase
from source.utils.StringKeyUtils import StringKeyUtils
from source.data.bean.User import User
from source.data.bean.Branch import Branch


class PullRequest(BeanBase):
    """����pull request ��������  ����24������
    """

    def __init__(self):
        self.repo_full_name = None
        self.number = None
        self.id = None
        self.node_id = None
        self.state = None
        self.title = None
        self.user = None
        self.body = None
        self.created_at = None
        self.updated_at = None
        self.closed_at = None
        self.merged_at = None
        self.merge_commit_sha = None
        self.author_association = None
        self.merged = None
        self.comments = None
        self.review_comments = None
        self.commits = None
        self.additions = None
        self.deletions = None
        self.changed_files = None
        self.head = None
        self.base = None

        self.user_login = None
        self.head_label = None
        self.base_label = None
        self.is_pr = None

        """�����ֶ�is_pr  true������pr  ����Ϊissue���������ݿ���������ȡ������"""

    @staticmethod
    def getIdentifyKeys():
        return [StringKeyUtils.STR_KEY_REPO_FULL_NAME, StringKeyUtils.STR_KEY_NUMBER]

    @staticmethod
    def getItemKeyList():
        items = [StringKeyUtils.STR_KEY_REPO_FULL_NAME, StringKeyUtils.STR_KEY_NUMBER, StringKeyUtils.STR_KEY_ID,
                 StringKeyUtils.STR_KEY_NODE_ID, StringKeyUtils.STR_KEY_STATE,
                 StringKeyUtils.STR_KEY_TITLE, StringKeyUtils.STR_KEY_USER_LOGIN, StringKeyUtils.STR_KEY_BODY,
                 StringKeyUtils.STR_KEY_CREATE_AT, StringKeyUtils.STR_KEY_UPDATE_AT, StringKeyUtils.STR_KEY_CLOSED_AT,
                 StringKeyUtils.STR_KEY_MERGED_AT, StringKeyUtils.STR_KEY_MERGE_COMMIT_SHA,
                 StringKeyUtils.STR_KEY_AUTHOR_ASSOCIATION, StringKeyUtils.STR_KEY_MERGED,
                 StringKeyUtils.STR_KEY_COMMENTS, StringKeyUtils.STR_KEY_REVIEW_COMMENTS,
                 StringKeyUtils.STR_KEY_COMMITS, StringKeyUtils.STR_KEY_ADDITIONS, StringKeyUtils.STR_KEY_DELETIONS,
                 StringKeyUtils.STR_KEY_CHANGED_FILES, StringKeyUtils.STR_KEY_HEAD_LABEL,
                 StringKeyUtils.STR_KEY_BASE_LABEL, StringKeyUtils.STR_KEY_IS_PR]

        return items

    @staticmethod
    def getItemKeyListWithType():
        items = [(StringKeyUtils.STR_KEY_REPO_FULL_NAME, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_NUMBER, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_ID, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_NODE_ID, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_STATE, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_TITLE, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_USER_LOGIN, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_BODY, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_CREATE_AT, BeanBase.DATA_TYPE_DATE_TIME),
                 (StringKeyUtils.STR_KEY_UPDATE_AT, BeanBase.DATA_TYPE_DATE_TIME),
                 (StringKeyUtils.STR_KEY_CLOSED_AT, BeanBase.DATA_TYPE_DATE_TIME),
                 (StringKeyUtils.STR_KEY_MERGED_AT, BeanBase.DATA_TYPE_DATE_TIME),
                 (StringKeyUtils.STR_KEY_MERGE_COMMIT_SHA, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_AUTHOR_ASSOCIATION, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_MERGED, BeanBase.DATA_TYPE_BOOLEAN),
                 (StringKeyUtils.STR_KEY_COMMENTS, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_REVIEW_COMMENTS, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_COMMITS, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_ADDITIONS, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_DELETIONS, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_CHANGED_FILES, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_HEAD_LABEL, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_BASE_LABEL, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_IS_PR, BeanBase.DATA_TYPE_BOOLEAN)]
        return items

    def getValueDict(self):
        items = {StringKeyUtils.STR_KEY_REPO_FULL_NAME: self.repo_full_name, StringKeyUtils.STR_KEY_NUMBER: self.number,
                 StringKeyUtils.STR_KEY_ID: self.id, StringKeyUtils.STR_KEY_NODE_ID: self.node_id,
                 StringKeyUtils.STR_KEY_STATE: self.state, StringKeyUtils.STR_KEY_TITLE: self.title,
                 StringKeyUtils.STR_KEY_USER_LOGIN: self.user_login, StringKeyUtils.STR_KEY_BODY: self.body,
                 StringKeyUtils.STR_KEY_CREATE_AT: self.created_at, StringKeyUtils.STR_KEY_UPDATE_AT: self.updated_at,
                 StringKeyUtils.STR_KEY_CLOSED_AT: self.closed_at, StringKeyUtils.STR_KEY_MERGED_AT: self.merged_at,
                 StringKeyUtils.STR_KEY_MERGE_COMMIT_SHA: self.merge_commit_sha,
                 StringKeyUtils.STR_KEY_AUTHOR_ASSOCIATION: self.author_association,
                 StringKeyUtils.STR_KEY_MERGED: self.merged, StringKeyUtils.STR_KEY_COMMENTS: self.comments,
                 StringKeyUtils.STR_KEY_REVIEW_COMMENTS: self.review_comments,
                 StringKeyUtils.STR_KEY_COMMITS: self.commits, StringKeyUtils.STR_KEY_ADDITIONS: self.additions,
                 StringKeyUtils.STR_KEY_DELETIONS: self.deletions,
                 StringKeyUtils.STR_KEY_CHANGED_FILES: self.changed_files,
                 StringKeyUtils.STR_KEY_HEAD_LABEL: self.head_label, StringKeyUtils.STR_KEY_BASE_LABEL: self.base_label,
                 StringKeyUtils.STR_KEY_IS_PR: self.is_pr}

        return items

    class parser(BeanBase.parser):

        @staticmethod
        def parser(src):
            res = None
            if isinstance(src, dict):
                res = PullRequest()
                res.number = src.get(StringKeyUtils.STR_KEY_NUMBER, None)
                res.id = src.get(StringKeyUtils.STR_KEY_ID, None)
                res.node_id = src.get(StringKeyUtils.STR_KEY_NODE_ID, None)
                res.state = src.get(StringKeyUtils.STR_KEY_STATE, None)
                res.title = src.get(StringKeyUtils.STR_KEY_TITLE, None)
                # user
                # user_id
                res.body = src.get(StringKeyUtils.STR_KEY_BODY, None)
                res.created_at = src.get(StringKeyUtils.STR_KEY_CREATE_AT, None)
                res.updated_at = src.get(StringKeyUtils.STR_KEY_UPDATE_AT, None)
                res.closed_at = src.get(StringKeyUtils.STR_KEY_CLOSED_AT, None)
                res.merged_at = src.get(StringKeyUtils.STR_KEY_MERGED_AT, None)

                if res.created_at is not None:
                    res.created_at = datetime.strptime(res.created_at, StringKeyUtils.STR_STYLE_DATA_DATE)
                if res.updated_at is not None:
                    res.updated_at = datetime.strptime(res.updated_at, StringKeyUtils.STR_STYLE_DATA_DATE)
                if res.closed_at is not None:
                    res.closed_at = datetime.strptime(res.closed_at, StringKeyUtils.STR_STYLE_DATA_DATE)
                if res.merged_at is not None:
                    res.merged_at = datetime.strptime(res.merged_at, StringKeyUtils.STR_STYLE_DATA_DATE)

                res.merge_commit_sha = src.get(StringKeyUtils.STR_KEY_MERGE_COMMIT_SHA, None)
                res.author_association = src.get(StringKeyUtils.STR_KEY_AUTHOR_ASSOCIATION, None)
                res.merged = src.get(StringKeyUtils.STR_KEY_MERGED, None)
                res.comments = src.get(StringKeyUtils.STR_KEY_COMMENTS, None)
                res.review_comments = src.get(StringKeyUtils.STR_KEY_REVIEW_COMMENTS, None)
                res.commits = src.get(StringKeyUtils.STR_KEY_COMMITS, None)
                res.additions = src.get(StringKeyUtils.STR_KEY_ADDITIONS, None)
                res.deletions = src.get(StringKeyUtils.STR_KEY_DELETIONS, None)
                res.changed_files = src.get(StringKeyUtils.STR_KEY_CHANGED_FILES, None)

                userData = src.get(StringKeyUtils.STR_KEY_USER, None)
                if userData is not None and isinstance(userData, dict):
                    user = User.parser.parser(userData)
                    res.user = user
                    res.user_login = user.login

                # res.head
                # res.base

                headData = src.get(StringKeyUtils.STR_KEY_HEAD, None)
                if headData is not None and isinstance(headData, dict):
                    head = Branch.parser.parser(headData)
                    res.head = head
                    res.head_label = head.label

                baseData = src.get(StringKeyUtils.STR_KEY_BASE, None)
                if baseData is not None and isinstance(baseData, dict):
                    base = Branch.parser.parser(baseData)
                    res.base = base
                    res.base_label = base.label

                # v3�ߵ��������pr
                res.is_pr = True

            return res

    class parserV4(BeanBase.parser):
        @staticmethod
        def parser(src):
            """������ Ŀ����ֵ俪ʼ���� ǰ��ĸ߼�����Ҫ��ǰ����"""
            res = None
            if isinstance(src, dict):
                res = PullRequest()
                """�ж��Ƿ���pr"""
                typename = src.get(StringKeyUtils.STR_KEY_TYPE_NAME_JSON, None)
                if typename == StringKeyUtils.STR_KEY_PULL_REQUEST:
                    res.number = src.get(StringKeyUtils.STR_KEY_NUMBER, None)
                    """ע  v4�нӿ��ṩ��id ��ָnode_id, ��databaseid Ϊ id"""
                    res.id = src.get(StringKeyUtils.STR_KEY_DATABASE_ID, None)
                    res.node_id = src.get(StringKeyUtils.STR_KEY_ID, None)
                    """v4 �ӿڵ�state�� v3��state���岻ͬ
                       v3 �ṩ open �� closed
                       �� v4 �ṩ OPEN CLOSED MERGED
                       Ϊ�˼��� ��Ҫ��v4ת��Ϊv3
                    """
                    res.state = src.get(StringKeyUtils.STR_KEY_STATE, None)
                    if res.state == StringKeyUtils.STR_KEY_OPEN_V4:
                        res.state = StringKeyUtils.STR_KEY_OPEN_V3
                    elif res.state == StringKeyUtils.STR_KEY_CLOSED_V4 or res.state == StringKeyUtils.STR_KEY_MERGED_V4:
                        res.state = StringKeyUtils.STR_KEY_CLOSED_V3
                    res.title = src.get(StringKeyUtils.STR_KEY_TITLE, None)
                    # user
                    # user_id
                    res.body = src.get(StringKeyUtils.STR_KEY_BODY, None)
                    res.created_at = src.get(StringKeyUtils.STR_KEY_CREATE_AT_V4, None)
                    res.updated_at = src.get(StringKeyUtils.STR_KEY_UPDATE_AT_V4, None)
                    res.closed_at = src.get(StringKeyUtils.STR_KEY_CLOSED_AT_V4, None)
                    res.merged_at = src.get(StringKeyUtils.STR_KEY_MERGED_AT_V4, None)

                    if res.created_at is not None:
                        res.created_at = datetime.strptime(res.created_at, StringKeyUtils.STR_STYLE_DATA_DATE)
                    if res.updated_at is not None:
                        res.updated_at = datetime.strptime(res.updated_at, StringKeyUtils.STR_STYLE_DATA_DATE)
                    if res.closed_at is not None:
                        res.closed_at = datetime.strptime(res.closed_at, StringKeyUtils.STR_STYLE_DATA_DATE)
                    if res.merged_at is not None:
                        res.merged_at = datetime.strptime(res.merged_at, StringKeyUtils.STR_STYLE_DATA_DATE)

                    mergeCommit = src.get(StringKeyUtils.STR_KEY_MERGE_COMMIT, None)
                    if mergeCommit is not None and isinstance(mergeCommit, dict):
                        res.merge_commit_sha = mergeCommit.get(StringKeyUtils.STR_KEY_OID, None)
                    res.author_association = src.get(StringKeyUtils.STR_KEY_AUTHOR_ASSOCIATION_V4, None)
                    res.merged = src.get(StringKeyUtils.STR_KEY_MERGED, None)

                    """��������Ҫ����ͨ��list ����"""
                    """issue comment"""
                    comment_list = src.get(StringKeyUtils.STR_KEY_COMMENTS, None)
                    if comment_list is not None and isinstance(comment_list, dict):
                        comment_list_nodes = comment_list.get(StringKeyUtils.STR_KEY_NODES, None)
                        if comment_list_nodes is not None and isinstance(comment_list_nodes, list):
                            res.comments = comment_list_nodes.__len__()

                    """review comment"""
                    review_list = src.get(StringKeyUtils.STR_KEY_REVIEWS, None)
                    if review_list is not None and isinstance(review_list, dict):
                        total_review_comment = 0
                        """���α���ÿ��review ��ȡcomment������"""
                        review_list_nodes = review_list.get(StringKeyUtils.STR_KEY_NODES, None)
                        if review_list_nodes is not None and isinstance(review_list_nodes, list):
                            for review in review_list_nodes:
                                if review is not None and isinstance(review, dict):
                                    review_comments_list = review.get(StringKeyUtils.STR_KEY_COMMENTS, None)
                                    if review_comments_list is not None and isinstance(review_comments_list, dict):
                                        review_comments_list_nodes = review_comments_list. \
                                            get(StringKeyUtils.STR_KEY_NODES, None)
                                        if review_comments_list_nodes is not None and \
                                                isinstance(review_comments_list_nodes, list):
                                            total_review_comment += review_comments_list_nodes.__len__()

                        res.review_comments = total_review_comment

                    """commit"""
                    commit_list = src.get(StringKeyUtils.STR_KEY_COMMITS, None)
                    if comment_list is not None and isinstance(comment_list, dict):
                        commit_list_nodes = commit_list.get(StringKeyUtils.STR_KEY_NODES, None)
                        if commit_list_nodes is not None and isinstance(commit_list_nodes, list):
                            res.commits = commit_list_nodes.__len__()

                    res.additions = src.get(StringKeyUtils.STR_KEY_ADDITIONS, None)
                    res.deletions = src.get(StringKeyUtils.STR_KEY_DELETIONS, None)
                    res.changed_files = src.get(StringKeyUtils.STR_KEY_CHANGED_FILES_V4, None)

                    # �û���Ϣ�߼�ͳһ�鵽 ����participants����
                    res.user = None
                    author = src.get(StringKeyUtils.STR_KEY_AUTHOR, None)
                    if author is not None and isinstance(author, dict):
                        res.user_login = author.get(StringKeyUtils.STR_KEY_LOGIN, None)

                    # res.head
                    # res.base

                    """����headRef ��ȡΪNULL,����branch��parserv4 ����ͨ����Ч
                       �ĳ�ʹ�ý��� headRepository �� pr�������ֶ�ֱ������
                       �� baseRef �Ľ������ڶԳ���ͬ��
                    """
                    headData = src.get(StringKeyUtils.STR_KEY_HEAD_REPOSITORY, None)
                    if headData is not None and isinstance(headData, dict):
                        head = Branch()
                        """�����ֶ��� pull request����"""
                        head.ref = src.get(StringKeyUtils.STR_KEY_HEAD_REF_NAME, None)
                        head.sha = src.get(StringKeyUtils.STR_KEY_HEAD_REF_OID, None)
                        """���� headRepository�ֶ�"""
                        headRepository = src.get(StringKeyUtils.STR_KEY_HEAD_REPOSITORY, None)
                        if headRepository is not None and isinstance(headRepository, dict):
                            head.repo_full_name = headRepository.get(StringKeyUtils.STR_KEY_NAME_WITH_OWNER, None)
                            head.user = None
                            if head.repo_full_name is not None:
                                head.user_login = head.repo_full_name.split('/')[0]
                                head.repo = head.repo_full_name.split('/')[0]
                                head.label = head.user_login + ':' + head.ref
                        res.head = head
                        res.head_label = head.label

                    baseData = src.get(StringKeyUtils.STR_KEY_BASE_REPOSITORY, None)
                    if baseData is not None and isinstance(baseData, dict):
                        base = Branch()
                        """�����ֶ��� pull request����"""
                        base.ref = src.get(StringKeyUtils.STR_KEY_BASE_REF_NAME, None)
                        base.sha = src.get(StringKeyUtils.STR_KEY_BASE_REF_OID, None)
                        """���� headRepository�ֶ�"""
                        baseRepository = src.get(StringKeyUtils.STR_KEY_BASE_REPOSITORY, None)
                        if baseRepository is not None and isinstance(baseRepository, dict):
                            base.repo_full_name = baseRepository.get(StringKeyUtils.STR_KEY_NAME_WITH_OWNER, None)
                            base.user = None
                            if base.repo_full_name is not None:
                                base.user_login = base.repo_full_name.split('/')[0]
                                base.repo = base.repo_full_name.split('/')[1]
                                base.label = base.user_login + ':' + base.ref
                        res.base = base
                        res.base_label = base.label

                    res.is_pr = True

                elif typename == StringKeyUtils.STR_KEY_ISSUE:
                    """issue����� �ж�Ϊ��"""
                    res.number = src.get(StringKeyUtils.STR_KEY_NUMBER, None)
                    res.is_pr = False
            return res
