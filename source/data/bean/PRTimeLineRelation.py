# coding=gbk
from datetime import datetime

from source.data.bean.Beanbase import BeanBase
from source.data.bean.HeadRefForcePushedEvent import HeadRefForcePushedEvent
from source.data.bean.IssueComment import IssueComment
from source.data.bean.PullRequestCommit import PullRequestCommit
from source.utils.StringKeyUtils import StringKeyUtils
import json


class PRTimeLineRelation(BeanBase):
    """github��pull request��timeline ��ϵ"""

    def __init__(self):
        self.repo_full_name = None
        self.pull_request_node = None
        self.timeline_item_node = None
        self.typename = None
        self.position = None
        self.origin = None
        self.create_at = None

        """��ѡ���� ����ʹ�õ� ʵ�ʲ�����洢"""
        """force push���"""
        self.headRefForcePushedEventAfterCommit = None
        self.headRefForcePushedEventBeforeCommit = None

        """review���"""
        self.comments = []
        self.pull_request_review_commit = None
        self.pull_request_review_original_commit = None

        """issueComment����"""
        self.body = None

        """pullrequestCommit���"""
        self.pull_request_commit = None
        self.message = None

        """merge���"""
        self.merge_commit = None

        """�¼�author"""
        self.user_login = None


    @staticmethod
    def getIdentifyKeys():
        return [StringKeyUtils.STR_KEY_PULL_REQUEST_NODE, StringKeyUtils.STR_KEY_TIME_LINE_ITEM_NODE]

    @staticmethod
    def getItemKeyList():
        items = [StringKeyUtils.STR_KEY_REPO_FULL_NAME, StringKeyUtils.STR_KEY_PULL_REQUEST_NODE, StringKeyUtils.STR_KEY_TIME_LINE_ITEM_NODE,
                 StringKeyUtils.STR_KEY_TYPE_NAME, StringKeyUtils.STR_KEY_POSITION, StringKeyUtils.STR_KEY_ORIGIN,
                 StringKeyUtils.STR_KEY_CREATE_AT]

        return items

    @staticmethod
    def getItemKeyListWithType():
        items = [(StringKeyUtils.STR_KEY_REPO_FULL_NAME, BeanBase.DATA_TYPE_STRING),
                (StringKeyUtils.STR_KEY_PULL_REQUEST_NODE, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_TIME_LINE_ITEM_NODE, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_TYPE_NAME, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_POSITION, BeanBase.DATA_TYPE_INT),
                 (StringKeyUtils.STR_KEY_ORIGIN, BeanBase.DATA_TYPE_STRING),
                 StringKeyUtils.STR_KEY_CREATE_AT, BeanBase.DATA_TYPE_DATE_TIME]

        return items

    def getValueDict(self):
        items = {StringKeyUtils.STR_KEY_REPO_FULL_NAME: self.repo_full_name,
                 StringKeyUtils.STR_KEY_PULL_REQUEST_NODE: self.pull_request_node,
                 StringKeyUtils.STR_KEY_TIME_LINE_ITEM_NODE: self.timeline_item_node,
                 StringKeyUtils.STR_KEY_TYPE_NAME: self.typename,
                 StringKeyUtils.STR_KEY_POSITION: self.position,
                 StringKeyUtils.STR_KEY_ORIGIN: self.origin,
                 StringKeyUtils.STR_KEY_CREATE_AT: self.create_at}

        return items

    class Parser(BeanBase.parser):

        @staticmethod
        def parser(item):
            if item is not None and isinstance(item, str):
                item = json.loads(item)
            relation = PRTimeLineRelation()  # ���ؽ��Ϊһϵ�й�ϵ
            relation.repo_full_name = item.get(StringKeyUtils.STR_KEY_REPO_FULL_NAME, None)
            """����ÿ��Item��TypeName���ж�Item�ľ�������"""
            """item������������Բο� https://developer.github.com/v4/union/pullrequesttimelineitems/"""
            relation.typename = item.get(StringKeyUtils.STR_KEY_TYPE_NAME_JSON, None)
            relation.timeline_item_node = item.get(StringKeyUtils.STR_KEY_ID, None)
            relation.position = item.get(StringKeyUtils.STR_KEY_POSITION, None)
            relation.origin = json.dumps(item)

            """���ո���Ȥ������ ������������"""
            # ע�����ܻ�����©�Ĵ���commit�ĳ���û�п���
            if relation.typename == StringKeyUtils.STR_KEY_HEAD_REF_PUSHED_EVENT:
                """force push"""
                afterCommit = item.get(StringKeyUtils.STR_KEY_AFTER_COMMIT)
                if afterCommit is not None:
                    relation.headRefForcePushedEventAfterCommit = afterCommit.get(StringKeyUtils.STR_KEY_OID, None)
                beforeCommit = item.get(StringKeyUtils.STR_KEY_BEFORE_COMMIT)
                if beforeCommit is not None:
                    relation.headRefForcePushedEventBeforeCommit = beforeCommit.get(StringKeyUtils.STR_KEY_OID, None)
                if item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4, None) is not None:
                    relation.create_at = datetime.strptime(item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4),
                                                                           StringKeyUtils.STR_STYLE_DATA_DATE)
                return relation
            elif relation.typename == StringKeyUtils.STR_KEY_PULL_REQUEST_COMMIT:
                """commit"""
                commit = item.get(StringKeyUtils.STR_KEY_COMMIT)
                if commit is not None and isinstance(commit, dict):
                    relation.pull_request_commit = commit.get(StringKeyUtils.STR_KEY_OID, None)
                    if commit.get(StringKeyUtils.STR_KEY_COMMIT_COMMITTED_DATE_V4, None) is not None:
                        relation.create_at = datetime.strptime(commit.get(StringKeyUtils.STR_KEY_COMMIT_COMMITTED_DATE_V4),
                                                                           StringKeyUtils.STR_STYLE_DATA_DATE)
                return relation
            elif relation.typename == StringKeyUtils.STR_KEY_MERGED_EVENT:
                """merge"""
                commit = item.get(StringKeyUtils.STR_KEY_COMMIT)
                if commit is not None and isinstance(commit, dict):
                    relation.merge_commit = commit.get(StringKeyUtils.STR_KEY_OID, None)
                if item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4, None) is not None:
                    relation.create_at = datetime.strptime(item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4),
                                                                           StringKeyUtils.STR_STYLE_DATA_DATE)
                return relation
            elif relation.typename == StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW:
                """review ��Ҫ��ȡcomments, commit��original_commit"""
                comments = item.get(StringKeyUtils.STR_KEY_COMMENTS).get(StringKeyUtils.STR_KEY_NODES)
                relation.comments = comments
                commit = item.get(StringKeyUtils.STR_KEY_COMMIT)
                if commit is not None and isinstance(commit, dict):
                    relation.pull_request_review_commit = commit.get(StringKeyUtils.STR_KEY_OID, None)
                author = item.get(StringKeyUtils.STR_KEY_AUTHOR)
                if author is not None and isinstance(author, dict):
                    relation.user_login = author.get(StringKeyUtils.STR_KEY_LOGIN)
                if item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4, None) is not None:
                    relation.create_at = datetime.strptime(item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4),
                                                                           StringKeyUtils.STR_STYLE_DATA_DATE)
                return relation
            elif relation.typename == StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW_THREAD:
                """review thread û��createAt�ֶΣ��õ�һ��comment��ʱ����Ϊreviewʱ��"""
                comments = item.get(StringKeyUtils.STR_KEY_COMMENTS).get(StringKeyUtils.STR_KEY_NODES)
                relation.comments = comments
                if comments is not None and len(comments) > 0 and isinstance(comments, list):
                    original_commit = comments[0].get(StringKeyUtils.STR_KEY_ORIGINAL_COMMIT)
                    if comments[0].get(StringKeyUtils.STR_KEY_CREATE_AT_V4, None) is not None:
                        relation.create_at = datetime.strptime(comments[0].get(StringKeyUtils.STR_KEY_CREATE_AT_V4),
                                                                           StringKeyUtils.STR_STYLE_DATA_DATE)
                    relation.user_login = comments[0].get(StringKeyUtils.STR_KEY_AUTHOR).get(
                        StringKeyUtils.STR_KEY_LOGIN)
                    if original_commit is not None and isinstance(original_commit, dict):
                        relation.pull_request_review_commit = original_commit.get(StringKeyUtils.STR_KEY_OID, None)
                return relation
            elif relation.typename == StringKeyUtils.STR_KEY_ISSUE_COMMENT:
                """issueComment��Ҳ����review��һ�֣�"""
                author = item.get(StringKeyUtils.STR_KEY_AUTHOR)
                if author is not None:
                    relation.user_login = author.get(StringKeyUtils.STR_KEY_LOGIN)
                relation.body = item.get(StringKeyUtils.STR_KEY_BODY_V4)
                if item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4, None) is not None:
                    relation.create_at = datetime.strptime(item.get(StringKeyUtils.STR_KEY_CREATE_AT_V4),
                                                                           StringKeyUtils.STR_STYLE_DATA_DATE)
                return relation
            else:
                return None
