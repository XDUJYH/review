# coding=gbk
import asyncio
import json
import random
import time
import traceback
from datetime import datetime

import aiohttp

from source.config.configPraser import configPraser
from source.data.bean.Comment import Comment
from source.data.bean.CommentRelation import CommitRelation
from source.data.bean.Commit import Commit
from source.data.bean.CommitPRRelation import CommitPRRelation
from source.data.bean.File import File
from source.data.bean.IssueComment import IssueComment
from source.data.bean.PRChangeFile import PRChangeFile
from source.data.bean.PRTimeLineRelation import PRTimeLineRelation
from source.data.bean.PullRequest import PullRequest
from source.data.bean.Review import Review
from source.data.bean.ReviewComment import ReviewComment
from source.data.bean.User import User
from source.data.service.AsyncSqlHelper import AsyncSqlHelper
from source.data.service.BeanParserHelper import BeanParserHelper
from source.data.service.GraphqlHelper import GraphqlHelper
from source.data.service.PRTimeLineUtils import PRTimeLineUtils
from source.data.service.ProxyHelper import ProxyHelper
from source.data.service.TextCompareUtils import TextCompareUtils
from source.utils.StringKeyUtils import StringKeyUtils


class AsyncApiHelper:
    """ʹ��aiohttp�첽ͨѶ"""

    owner = None
    repo = None

    @staticmethod
    def setRepo(owner, repo):  # ʹ��֮ǰ������Ŀ����������
        AsyncApiHelper.owner = owner
        AsyncApiHelper.repo = repo

    @staticmethod
    def getAuthorizationHeaders(header):
        """����Github ��Token������֤"""
        if header is not None and isinstance(header, dict):
            if configPraser.getAuthorizationToken():
                header[StringKeyUtils.STR_HEADER_AUTHORIZAITON] = (StringKeyUtils.STR_HEADER_TOKEN
                                                                   + configPraser.getAuthorizationToken())
        return header

    @staticmethod
    def getUserAgentHeaders(header):
        """������ԣ� ��������agent"""
        if header is not None and isinstance(header, dict):
            # header[self.STR_HEADER_USER_AGENT] = self.STR_HEADER_USER_AGENT_SET
            header[StringKeyUtils.STR_HEADER_USER_AGENT] = random.choice(StringKeyUtils.USER_AGENTS)
        return header

    @staticmethod
    def getMediaTypeHeaders(header):
        if header is not None and isinstance(header, dict):
            header[StringKeyUtils.STR_HEADER_ACCEPT] = StringKeyUtils.STR_HEADER_MEDIA_TYPE
        return header

    @staticmethod
    async def getProxy():
        """��ȡ����ip���е�ip  ��ϸ�� ProxyHelper"""
        if configPraser.getProxy():
            proxy = await ProxyHelper.getAsyncSingleProxy()
            if configPraser.getPrintMode():
                print(proxy)
            if proxy is not None:
                return StringKeyUtils.STR_PROXY_HTTP_FORMAT.format(proxy)
        return None

    @staticmethod
    async def parserPullRequest(resultJson):
        try:
            if not AsyncApiHelper.judgeNotFind(resultJson):
                if configPraser.getApiVersion() == StringKeyUtils.API_VERSION_RESET:
                    res = PullRequest.parser.parser(resultJson)
                elif configPraser.getApiVersion() == StringKeyUtils.API_VERSION_GRAPHQL:
                    res = PullRequest.parserV4.parser(resultJson)
                if res is not None and res.base is not None:
                    res.repo_full_name = res.base.repo_full_name  # ��pull_request��repo_full_name ��һ����ȫ
                return res
        except Exception as e:
            print(e)

    @staticmethod
    def judgeNotFind(resultJson):
        if configPraser.getApiVersion() == StringKeyUtils.API_VERSION_RESET:
            if resultJson is not None and isinstance(json, dict):
                if resultJson.get(StringKeyUtils.STR_KEY_MESSAGE) == StringKeyUtils.STR_NOT_FIND:
                    return True
                if resultJson.get(StringKeyUtils.STR_KEY_MESSAGE) == StringKeyUtils.STR_FAILED_FETCH:
                    return True
            return False
        elif configPraser.getApiVersion() == StringKeyUtils.API_VERSION_GRAPHQL:
            if resultJson is not None and isinstance(json, dict):
                if resultJson.get(StringKeyUtils.STR_KEY_ERRORS) is not None:
                    return True
            return False

    @staticmethod
    async def downloadInformation(pull_number, semaphore, mysql, statistic):
        """��ȡһ����Ŀ ����pull-request ��ص���Ϣ"""

        """����issue  ��Ҫ��дdownloadInformation���� 
           ֻ��pull-request�Ļ�ȡת��Ϊissue
        """
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []  # �����ռ���Ҫ�洢��bean��
                    """�Ȼ�ȡpull request��Ϣ"""
                    api = AsyncApiHelper.getPullRequestApi(pull_number)
                    json = await AsyncApiHelper.fetchBeanData(session, api)
                    pull_request = await AsyncApiHelper.parserPullRequest(json)
                    print(pull_request)
                    usefulPullRequestsCount = 0
                    usefulReviewsCount = 0
                    usefulReviewCommentsCount = 0
                    usefulIssueCommentsCount = 0
                    usefulCommitsCount = 0

                    if pull_request is not None:
                        usefulPullRequestsCount = 1
                        beanList.append(pull_request)

                        if pull_request.head is not None:
                            beanList.append(pull_request.head)
                        if pull_request.base is not None:
                            beanList.append(pull_request.base)
                        if pull_request.user is not None:
                            beanList.append(pull_request.user)

                        reviewCommits = []  # review���漰��Commit�ĵ�

                        """��ȡreview��Ϣ"""
                        api = AsyncApiHelper.getReviewForPullRequestApi(pull_number)
                        json = await AsyncApiHelper.fetchBeanData(session, api)
                        reviews = await AsyncApiHelper.parserReview(json, pull_number)
                        if configPraser.getPrintMode():
                            print(reviews)

                        usefulReviewsCount = 0
                        if reviews is not None:
                            for review in reviews:
                                usefulReviewsCount += 1
                                beanList.append(review)
                                if review.user is not None:
                                    beanList.append(review.user)
                                if review.commit_id not in reviewCommits:
                                    reviewCommits.append(review.commit_id)

                        """��ȡreview comment��Ϣ"""
                        api = AsyncApiHelper.getReviewCommentForPullRequestApi(pull_number)
                        json = await AsyncApiHelper.fetchBeanData(session, api, isMediaType=True)
                        reviewComments = await AsyncApiHelper.parserReviewComment(json)

                        if configPraser.getPrintMode():
                            print(reviewComments)
                        usefulReviewCommentsCount = 0
                        if reviewComments is not None:
                            for reviewComment in reviewComments:
                                usefulReviewCommentsCount += 1
                                beanList.append(reviewComment)
                                if reviewComment.user is not None:
                                    beanList.append(reviewComment.user)

                        '''��ȡ pull request��Ӧ��issue comment��Ϣ'''
                        api = AsyncApiHelper.getIssueCommentForPullRequestApi(pull_number)
                        json = await AsyncApiHelper.fetchBeanData(session, api, isMediaType=True)
                        issueComments = await  AsyncApiHelper.parserIssueComment(json, pull_number)
                        usefulIssueCommentsCount = 0
                        if issueComments is not None:
                            for issueComment in issueComments:
                                usefulIssueCommentsCount += 1
                                beanList.append(issueComment)
                                if issueComment.user is not None:
                                    beanList.append(issueComment.user)

                        '''��ȡ pull request��Ӧ��commit��Ϣ'''
                        api = AsyncApiHelper.getCommitForPullRequestApi(pull_number)
                        json = await AsyncApiHelper.fetchBeanData(session, api, isMediaType=True)
                        Commits, Relations = await AsyncApiHelper.parserCommitAndRelation(json, pull_number)

                        for commit in Commits:
                            if commit.sha in reviewCommits:
                                reviewCommits.remove(commit.sha)

                        """��Щreview�漰��commit�ĵ�û����PR�����ռ��� ��Щ����Ҫ���м�������
                        û�еĵ� ���������Ҫ��������ȡ���õ� ����Ҳ��Ҫ�ռ�"""

                        """ʣ�µĵ���Ҫ���λ�ȡ"""
                        for commit_id in reviewCommits:
                            api = AsyncApiHelper.getCommitApi(commit_id)
                            json = await AsyncApiHelper.fetchBeanData(session, api)
                            commit = await AsyncApiHelper.parserCommit(json)
                            Commits.append(commit)

                        usefulCommitsCount = 0
                        for commit in Commits:
                            if commit is not None:
                                usefulCommitsCount += 1
                                api = AsyncApiHelper.getCommitApi(commit.sha)
                                json = await AsyncApiHelper.fetchBeanData(session, api)
                                commit = await AsyncApiHelper.parserCommit(json)
                                beanList.append(commit)

                                if commit.committer is not None:
                                    beanList.append(commit.committer)
                                if commit.author is not None:
                                    beanList.append(commit.author)
                                if commit.files is not None:
                                    for file in commit.files:
                                        beanList.append(file)
                                if commit.parents is not None:
                                    for parent in commit.parents:
                                        beanList.append(parent)
                                """��Ϊ��Դ��Լ   commit comment�����ɼ�"""

                        for relation in Relations:
                            beanList.append(relation)

                        print(beanList)

                    """���ݿ�洢"""
                    await AsyncSqlHelper.storeBeanDateList(beanList, mysql)

                    # ����ͬ������
                    statistic.lock.acquire()
                    statistic.usefulRequestNumber += usefulPullRequestsCount
                    statistic.usefulReviewNumber += usefulReviewsCount
                    statistic.usefulReviewCommentNumber += usefulReviewCommentsCount
                    statistic.usefulIssueCommentNumber += usefulIssueCommentsCount
                    statistic.usefulCommitNumber += usefulCommitsCount
                    print("useful pull request:", statistic.usefulRequestNumber,
                          " useful review:", statistic.usefulReviewNumber,
                          " useful review comment:", statistic.usefulReviewCommentNumber,
                          " useful issue comment:", statistic.usefulIssueCommentNumber,
                          " useful commit:", statistic.usefulCommitNumber,
                          " cost time:", datetime.now() - statistic.startTime)
                    statistic.lock.release()
                except Exception as e:
                    print(e)

    @staticmethod
    async def downloadInformationByV4(pull_number, semaphore, mysql, statistic):
        """��ȡһ����Ŀ ����pull-request ��ص���Ϣ
           ��Ҫ�ӿ�����Ǩ�Ƶ�GraphQl��v4�ӿ���   ��������һ���Ի�ȡpr��Ϣ
           ��֤��pr��Ϣ��������
           ����commit�ľ�����Ϣ�޷���ȡ  ���׼��������������ȡ

           ��gitFile����Ϣ��������Ϣ��ȡ����
        """
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []  # �����ռ���Ҫ�洢��bean��
                    """�Ȼ�ȡpull request��Ϣ"""
                    args = {"number": pull_number, "owner": AsyncApiHelper.owner, "name": AsyncApiHelper.repo}
                    api = AsyncApiHelper.getGraphQLApi()
                    query = GraphqlHelper.getPrInformationByNumber()
                    resultJson = await AsyncApiHelper.postGraphqlData(session, api, query, args)
                    print(resultJson)

                    """����pull request"""
                    allData = resultJson.get(StringKeyUtils.STR_KEY_DATA, None)
                    if allData is not None and isinstance(allData, dict):
                        repoData = allData.get(StringKeyUtils.STR_KEY_REPOSITORY, None)
                        if repoData is not None and isinstance(repoData, dict):
                            prData = repoData.get(StringKeyUtils.STR_KEY_ISSUE_OR_PULL_REQUEST, None)

                            pull_request = await AsyncApiHelper.parserPullRequest(prData)

                            usefulPullRequestsCount = 0
                            usefulReviewsCount = 0
                            usefulReviewCommentsCount = 0
                            usefulIssueCommentsCount = 0
                            usefulCommitsCount = 0

                            if pull_request is not None and pull_request.is_pr:
                                usefulPullRequestsCount = 1
                                beanList.append(pull_request)

                                if pull_request.head is not None:
                                    beanList.append(pull_request.head)
                                if pull_request.base is not None:
                                    beanList.append(pull_request.base)

                                users = []
                                """���� user ֱ�Ӵ�pr��participate��ȡ"""
                                user_list = prData.get(StringKeyUtils.STR_KEY_PARTICIPANTS, None)
                                if user_list is not None and isinstance(user_list, dict):
                                    user_list_nodes = user_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if user_list_nodes is not None and isinstance(user_list_nodes, list):
                                        for userData in user_list_nodes:
                                            user = User.parserV4.parser(userData)
                                            if user is not None:
                                                users.append(user)

                                """���� review, review comment, review �漰�� commit ��Ϣ"""
                                reviews = []
                                reviewComments = []
                                commits = []
                                review_list = prData.get(StringKeyUtils.STR_KEY_REVIEWS, None)
                                if review_list is not None and isinstance(review_list, dict):
                                    review_list_nodes = review_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if review_list_nodes is not None and isinstance(review_list_nodes, list):
                                        for reviewData in review_list_nodes:
                                            review = Review.parserV4.parser(reviewData)
                                            if review is not None:
                                                review.repo_full_name = pull_request.repo_full_name
                                                review.pull_number = pull_number
                                                reviews.append(review)

                                            if reviewData is not None and isinstance(reviewData, dict):
                                                comment_list = reviewData.get(StringKeyUtils.STR_KEY_COMMENTS, None)
                                                if comment_list is not None and isinstance(comment_list, dict):
                                                    comment_list_nodes = comment_list.get(StringKeyUtils.STR_KEY_NODES
                                                                                          , None)
                                                    if comment_list_nodes is not None and isinstance(comment_list_nodes
                                                            ,list):
                                                        for commentData in comment_list_nodes:
                                                            comment = ReviewComment.parserV4.parser(commentData)
                                                            comment.pull_request_review_id = review.id
                                                            reviewComments.append(comment)

                                                commitData = reviewData.get(StringKeyUtils.STR_KEY_COMMIT, None)
                                                if commitData is not None and isinstance(commitData, dict):
                                                    commit = Commit.parserV4.parser(commitData)
                                                    isFind = False
                                                    for c in commits:
                                                        if c.sha == commit.sha:
                                                            isFind = True
                                                            break
                                                    if not isFind:
                                                        commits.append(commit)

                                if configPraser.getPrintMode():
                                    print(reviews)
                                    print(reviewComments)

                                usefulReviewsCount += reviews.__len__()
                                usefulReviewCommentsCount += reviewComments.__len__()

                                """issue comment ��Ϣ��ȡ"""
                                issueComments = []
                                issue_comment_list = prData.get(StringKeyUtils.STR_KEY_COMMENTS, None)
                                if issue_comment_list is not None and isinstance(issue_comment_list, dict):
                                    issue_comment_list_nodes = issue_comment_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if issue_comment_list_nodes is not None and isinstance(issue_comment_list_nodes,
                                                                                           list):
                                        for commentData in issue_comment_list_nodes:
                                            issueComment = IssueComment.parserV4.parser(commentData)
                                            issueComment.pull_number = pull_number
                                            issueComment.repo_full_name = pull_request.repo_full_name
                                            issueComments.append(issueComment)

                                if configPraser.getPrintMode():
                                    print(issueComments)
                                usefulIssueCommentsCount += issueComments.__len__()

                                """��ȡ pr ��ֱ�ӹ����� commit ��Ϣ"""
                                commit_list = prData.get(StringKeyUtils.STR_KEY_COMMITS, None)
                                if commit_list is not None and isinstance(commit_list, dict):
                                    commit_list_nodes = commit_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if commit_list_nodes is not None and isinstance(commit_list_nodes, list):
                                        for commitData in commit_list_nodes:
                                            commitData = commitData.get(StringKeyUtils.STR_KEY_COMMIT, None)
                                            commit = Commit.parserV4.parser(commitData)
                                            isFind = False
                                            for c in commits:
                                                if c.sha == commit.sha:
                                                    isFind = True
                                                    break
                                            if not isFind:
                                                commits.append(commit)

                                """���� commitPrRelation �� commitRelation"""
                                CommitPrRelations = []
                                CommitRelations = []
                                for commit in commits:
                                    relation = CommitPRRelation()
                                    relation.repo_full_name = pull_request.repo_full_name
                                    relation.pull_number = pull_number
                                    relation.sha = commit.sha
                                    CommitPrRelations.append(relation)
                                    CommitRelations.extend(commit.parents)

                                usefulCommitsCount += commits.__len__()

                                """���� pull request �漰���ļ��䶯��������commit�ļ��䶯���ۼ�"""
                                files = []
                                files_list = prData.get(StringKeyUtils.STR_KEY_FILES, None)
                                if files_list is not None and isinstance(files_list, dict):
                                    files_list_nodes = files_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if files_list_nodes is not None and isinstance(files_list_nodes, list):
                                        for fileData in files_list_nodes:
                                            file = PRChangeFile.parserV4.parser(fileData)
                                            file.pull_number = pull_number
                                            file.repo_full_name = pull_request.repo_full_name
                                            files.append(file)

                                if configPraser.getPrintMode():
                                    print(files)

                                """beanList ��Ӹ���������"""

                                # """���ݿ�洢"""
                                # await AsyncSqlHelper.storeBeanDateList(beanList, mysql)

                                # ����ͬ������
                                statistic.lock.acquire()
                                statistic.usefulRequestNumber += usefulPullRequestsCount
                                statistic.usefulReviewNumber += usefulReviewsCount
                                statistic.usefulReviewCommentNumber += usefulReviewCommentsCount
                                statistic.usefulIssueCommentNumber += usefulIssueCommentsCount
                                statistic.usefulCommitNumber += usefulCommitsCount
                                print("useful pull request:", statistic.usefulRequestNumber,
                                      " useful review:", statistic.usefulReviewNumber,
                                      " useful review comment:", statistic.usefulReviewCommentNumber,
                                      " useful issue comment:", statistic.usefulIssueCommentNumber,
                                      " useful commit:", statistic.usefulCommitNumber,
                                      " cost time:", datetime.now() - statistic.startTime)
                                statistic.lock.release()
                except Exception as e:
                    print(e)

    @staticmethod
    async def parserReview(resultJson, pull_number):
        try:
            if not AsyncApiHelper.judgeNotFind(resultJson):
                items = []
                for item in resultJson:
                    res = Review.parser.parser(item)
                    res.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo  # ��repo_full_name ��һ����ȫ
                    res.pull_number = pull_number
                    items.append(res)
                return items
        except Exception as e:
            print(e)

    @staticmethod
    def getPullRequestApi(pull_number):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_PULL_REQUEST
        api = api.replace(StringKeyUtils.STR_OWNER, AsyncApiHelper.owner)
        api = api.replace(StringKeyUtils.STR_REPO, AsyncApiHelper.repo)
        api = api.replace(StringKeyUtils.STR_PULL_NUMBER, str(pull_number))
        return api

    @staticmethod
    def getReviewCommentForPullRequestApi(pull_number):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_COMMENTS_FOR_PULL_REQUEST
        api = api.replace(StringKeyUtils.STR_OWNER, AsyncApiHelper.owner)
        api = api.replace(StringKeyUtils.STR_REPO, AsyncApiHelper.repo)
        api = api.replace(StringKeyUtils.STR_PULL_NUMBER, str(pull_number))
        return api

    @staticmethod
    def getReviewForPullRequestApi(pull_number):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_REVIEWS_FOR_PULL_REQUEST
        api = api.replace(StringKeyUtils.STR_OWNER, AsyncApiHelper.owner)
        api = api.replace(StringKeyUtils.STR_REPO, AsyncApiHelper.repo)
        api = api.replace(StringKeyUtils.STR_PULL_NUMBER, str(pull_number))
        return api

    @staticmethod
    def getIssueCommentForPullRequestApi(issue_number):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_ISSUE_COMMENT_FOR_ISSUE
        api = api.replace(StringKeyUtils.STR_OWNER, AsyncApiHelper.owner)
        api = api.replace(StringKeyUtils.STR_REPO, AsyncApiHelper.repo)
        api = api.replace(StringKeyUtils.STR_ISSUE_NUMBER, str(issue_number))
        return api

    @staticmethod
    def getCommitForPullRequestApi(pull_number):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_COMMITS_FOR_PULL_REQUEST
        api = api.replace(StringKeyUtils.STR_OWNER, AsyncApiHelper.owner)
        api = api.replace(StringKeyUtils.STR_REPO, AsyncApiHelper.repo)
        api = api.replace(StringKeyUtils.STR_PULL_NUMBER, str(pull_number))
        return api

    @staticmethod
    def getGraphQLApi():
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_GRAPHQL
        return api

    @staticmethod
    def getCommitApi(commit_sha):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_COMMIT
        api = api.replace(StringKeyUtils.STR_OWNER, AsyncApiHelper.owner)
        api = api.replace(StringKeyUtils.STR_REPO, AsyncApiHelper.repo)
        api = api.replace(StringKeyUtils.STR_COMMIT_SHA, str(commit_sha))
        return api

    @staticmethod
    def getCommitApiWithProjectName(owner, repo, commit_sha):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_COMMIT
        api = api.replace(StringKeyUtils.STR_OWNER, owner)
        api = api.replace(StringKeyUtils.STR_REPO, repo)
        api = api.replace(StringKeyUtils.STR_COMMIT_SHA, str(commit_sha))
        return api


    @staticmethod
    async def fetchBeanData(session, api, isMediaType=False):
        """�첽��ȡ����ͨ�ýӿڣ���Ҫ��"""

        """��ʼ������ͷ"""
        headers = {}
        headers = AsyncApiHelper.getUserAgentHeaders(headers)
        headers = AsyncApiHelper.getAuthorizationHeaders(headers)
        if isMediaType:
            headers = AsyncApiHelper.getMediaTypeHeaders(headers)
        while True:
            """�Ե�������ѭ���ж� ֱ������ɹ����ߴ���"""

            """��ȡ����ip  ip��ȡ��Ҫ���д����"""
            proxy = await AsyncApiHelper.getProxy()
            if configPraser.getProxy() and proxy is None:  # �Դ����û��ip�����������
                print('no proxy and sleep!')
                await asyncio.sleep(20)
            else:
                break

        try:
            async with session.get(api, ssl=False, proxy=proxy
                    , headers=headers, timeout=configPraser.getTimeout()) as response:
                print("rate:", response.headers.get(StringKeyUtils.STR_HEADER_RATE_LIMIT_REMIAN))
                print("status:", response.status)
                if response.status == 403:
                    await ProxyHelper.judgeProxy(proxy.split('//')[1], ProxyHelper.INT_KILL_POINT)
                    raise 403
                elif proxy is not None:
                    await ProxyHelper.judgeProxy(proxy.split('//')[1], ProxyHelper.INT_POSITIVE_POINT)
                return await response.json()
        except Exception as e:
            """�� 403�������������  ѭ������"""
            print(e)
            if proxy is not None:
                proxy = proxy.split('//')[1]
                await ProxyHelper.judgeProxy(proxy, ProxyHelper.INT_NEGATIVE_POINT)
            # print("judge end")
            """ѭ������"""
            return await AsyncApiHelper.fetchBeanData(session, api, isMediaType=isMediaType)

    @staticmethod
    async def postGraphqlData(session, api, query=None, args=None):
        """ͨ�� github graphhql�ӿ� ͨ��post����"""
        headers = {}
        headers = AsyncApiHelper.getUserAgentHeaders(headers)
        headers = AsyncApiHelper.getAuthorizationHeaders(headers)

        body = {}
        body = GraphqlHelper.getGraphlQuery(body, query)
        body = GraphqlHelper.getGraphqlVariables(body, args)
        bodyJson = json.dumps(body)
        # print("bodyjson:", bodyJson)

        while True:
            proxy = await AsyncApiHelper.getProxy()
            if configPraser.getProxy() and proxy is None:  # �Դ����û��ip�����������
                print('no proxy and sleep!')
                await asyncio.sleep(20)
            else:
                break

        try:
            async with session.post(api, ssl=False, proxy=proxy,
                                    headers=headers, timeout=configPraser.getTimeout(),
                                    data=bodyJson) as response:
                print("rate:", response.headers.get(StringKeyUtils.STR_HEADER_RATE_LIMIT_REMIAN))
                print("status:", response.status)
                if response.status == 403:
                    await ProxyHelper.judgeProxy(proxy.split('//')[1], ProxyHelper.INT_KILL_POINT)
                    raise 403
                elif proxy is not None:
                    await ProxyHelper.judgeProxy(proxy.split('//')[1], ProxyHelper.INT_POSITIVE_POINT)
                return await response.json()
        except Exception as e:
            print(e)
            if proxy is not None:
                proxy = proxy.split('//')[1]
                await ProxyHelper.judgeProxy(proxy, ProxyHelper.INT_NEGATIVE_POINT)
            # print("judge end")
            return await AsyncApiHelper.postGraphqlData(session, api, query, args)

    @staticmethod
    async def parserReviewComment(resultJson):
        try:
            if not AsyncApiHelper.judgeNotFind(resultJson):
                items = []
                for item in resultJson:
                    res = ReviewComment.parser.parser(item)
                    items.append(res)
                return items
        except Exception as e:
            print(e)

    @staticmethod
    async def parserIssueComment(resultJson, issue_number):
        try:
            if not AsyncApiHelper.judgeNotFind(json):
                items = []
                for item in resultJson:
                    res = IssueComment.parser.parser(item)
                    """��Ϣ��ȫ"""
                    res.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo  # ��repo_full_name ��һ����ȫ
                    res.pull_number = issue_number

                    items.append(res)
                return items
        except Exception as e:
            print(e)

    @staticmethod
    async def parserCommitAndRelation(resultJson, pull_number):
        try:
            if not AsyncApiHelper.judgeNotFind(resultJson):
                items = []
                relations = []
                for item in resultJson:
                    res = Commit.parser.parser(item)
                    relation = CommitPRRelation()
                    relation.sha = res.sha
                    relation.pull_number = pull_number
                    relation.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo
                    relations.append(relation)
                    items.append(res)
                return items, relations
        except Exception as e:
            print(e)

    @staticmethod
    async def parserCommit(resultJson):
        try:
            if not AsyncApiHelper.judgeNotFind(resultJson):
                res = Commit.parser.parser(resultJson)
                return res
        except Exception as e:
            print(e)

    @staticmethod
    async def parserPRItemLine(resultJson):
        try:
            if not AsyncApiHelper.judgeNotFind(resultJson):
                res, items = PRTimeLineRelation.parser.parser(resultJson)
                return res, items
        except Exception as e:
            print(e)

    @staticmethod
    async def downloadRPTimeLine(nodeIds, semaphore, mysql, statistic):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    args = {"ids": nodeIds}
                    """��GitHub v4 API �л�ȡ ĳ��pull-request��TimeLine����"""
                    api = AsyncApiHelper.getGraphQLApi()
                    query = GraphqlHelper.getTimeLineQueryByNodes()
                    resultJson = await AsyncApiHelper.postGraphqlData(session, api, query, args)
                    beanList = []
                    print(type(resultJson))
                    print("post json:", resultJson)
                    """�ӻ�Ӧ������� timeLineItems �� Relations"""
                    timeLineRelations, timeLineItems = await  AsyncApiHelper.parserPRItemLine(resultJson)

                    usefulTimeLineItemCount = 0
                    usefulTimeLineCount = 0

                    beanList.extend(timeLineRelations)
                    beanList.extend(timeLineItems)
                    """�洢���ݿ���"""
                    await AsyncSqlHelper.storeBeanDateList(beanList, mysql)

                    """���ƻ�ȡ������commit ��Ϣ"""
                    pairs = PRTimeLineUtils.splitTimeLine(timeLineRelations)
                    for pair in pairs:
                        print(pair)
                        """����ÿһ��review�ͺ��������commit���ж����reivew��comment����Ч��"""
                        """completeCommitInformation ���������ȡ�ò���"""
                        await AsyncApiHelper.completeCommitInformation(pair, mysql, session, statistic)

                    # ����ͬ������
                    statistic.lock.acquire()
                    statistic.usefulTimeLineCount += 1
                    print(f" usefulTimeLineCount:{statistic.usefulTimeLineCount}",
                          f" change trigger count:{statistic.usefulChangeTrigger}",
                          f" twoParents case:{statistic.twoParentsNodeCase}",
                          f" outOfLoop case:{statistic.outOfLoopCase}")
                    statistic.lock.release()
                except Exception as e:
                    print(e)

    @staticmethod
    async def completeCommitInformation(pair, mysql, session, statistic):
        """���� review������¼���ص�commit"""
        """����commit���ж�review��comment����Ч��"""
        review = pair[0]
        changes = pair[1]

        """review �� comments ��ȡһ�μ���"""

        """���review comments"""
        """һ��review ���ܻ�������comment  
        ÿ��comment��ָ��һ���ļ��Ͷ�Ӧ������"""
        comments = await AsyncApiHelper.getReviewCommentsByNodeFromStore(review.timelineitem_node, mysql)

        twoParentsBadCase = 0  # ��¼һ��commit���������ڵ����� ����������ֱ��ֹͣ
        outOfLoopCase = 0  # ��¼Ѱ������commit���������ڽڵ� ʹ���ϼ�׷�ݵĴ��������������

        """changes ��ָreview���������commit ���ξ�changeTrigger����������ж�"""
        for change in changes:  # �Ժ��������Ķ����α���
            """ͨ��commit1��commit2 ���Ƚ�����֮��Ĵ������"""
            """commit1 : review���漰��commit
               commit2 : reivew�������߸Ķ���commit
            """
            commit1 = review.pullrequestReviewCommit
            commit2 = None
            if change.typename == StringKeyUtils.STR_KEY_PULL_REQUEST_COMMIT:
                commit2 = change.pullrequestCommitCommit
            elif change.typename == StringKeyUtils.STR_KEY_HEAD_REF_PUSHED_EVENT:
                commit2 = change.headRefForcePushedEventAfterCommit

            """�����㷨����  ͨ��commit1��commit2 ���Ƚ�����֮��Ĵ������"""
            """����˼·��  commit1���������ڽڵ����һ��commit�ļ���Group1
                          commit2ͬ�������Group2
                          
                          ��Group��ÿһ��commit�㶼��������Ϣ��
                          1. oid (commit-sha)
                          2. ���ڵ�� oid
                          3. ���commit�漰���ļ��Ķ�
                          
                          Group�а����������ͽڵ㣬һ������Ϣ�Ѿ���ȡ������һ������Ϣ��δ��ȡ��
                          ��Ϣ�Ѿ���ȡ���������commit����������Ϣ��֪������δ��ȡ���������commit
                          ֻ��oid��Ϣ��
                          
                          Groupһ�ε�����ָ��ÿ�λ�ȡ����ΪΪ��ȡ��Ϣ��commit�㣬����Ϊ��ȡ��Ϣ�Ľڵ�
                          ����Group�У���commitָ��ĸ��ڵ���Ϊδ��ȡ��Ϣ�ڵ����Group�С�
                          
                          ����commit��Ϊ��㲻��������������ֱ��ĳ��Group��δ�����ĵ㼯�ϰ�������
                          ����һ��Group������ڵ���
                          
                          ��������֮��ֱ��ҵ�����Group���ص�commit�㼯�ϣ���Ϊ�����㷨������
            """

            """ȱ�㣺 �����㷨�޷�����commit��������������������merge�������ֵĵ�
                      �����㷨�о��ֵֹģ�Ч�ʿ��ܲ��Ǻܸ�
                      
                      �������Ӧ����LCA����ı���
            """

            """�㷨���ƣ� 1��commit���ȡ����Խ��Խ��
                         2������commit��汾����������ʱ����Լ�⣬�����ƴ��� 
            """

            loop = 0
            if commit2 is not None and commit1 is not None:

                class CommitNode:
                    willFetch = None
                    oid = None
                    parents = None  # [sha1, sha2 ...]

                """Ϊ��ͳ��ʹ�õĹ�����"""

                def findNodes(nodes, oid):
                    for node in nodes:
                        if node.oid == oid:
                            return node

                def isExist(nodes, oid):
                    for node in nodes:
                        if node.oid == oid:
                            return True
                    return False

                def isNodesContains(nodes1, nodes2):  # nodes2 ������δ̽���ĵ㱻nodes1 ����
                    isContain = True
                    for node in nodes2:
                        isFind = False
                        for node1 in nodes1:
                            if node1.oid == node.oid:
                                isFind = True
                                break
                        if not isFind and node.willFetch:
                            isContain = False
                            break
                    return isContain

                def printNodes(nodes1, nodes2):
                    print('node1')
                    for node in nodes1:
                        print(node.oid, node.willFetch, node.parents)
                    print('node2')
                    for node in nodes2:
                        print(node.oid, node.willFetch, node.parents)

                async def fetNotFetchedNodes(nodes, mysql, session):
                    """��ȡcommit����Ϣ �������ݿ��ȡ��GitHub API��ȡ nodes����һ��Group"""
                    fetchList = [node.oid for node in nodes if node.willFetch]
                    """�ȳ��Դ����ݿ��ж�ȡ"""
                    localExistList, localRelationList = await AsyncApiHelper.getCommitsFromStore(fetchList, mysql)
                    fetchList = [oid for oid in fetchList if oid not in localExistList]
                    # print("res fetch list:", fetchList)
                    webRelationList = await AsyncApiHelper.getCommitsFromApi(fetchList, mysql, session)

                    for node in nodes:
                        node.willFetch = False

                    # for node in nodes:
                    #     print("after fetched 1: " + f"{node.oid}  {node.willFetch}")

                    relationList = []
                    relationList.extend(localRelationList)
                    relationList.extend(webRelationList)
                    # print("relationList:", relationList)
                    # for relation in relationList:
                    #     print(relation.child, "    ", relation.parent)

                    """ԭ�е�node ��ȫparents"""
                    for relation in relationList:
                        node = findNodes(nodes, relation.child)
                        if node is not None:
                            if relation.parent not in node.parents:
                                node.parents.append(relation.parent)

                    addNode = []
                    for relation in relationList:
                        isFind = False
                        """ȷ���������ط���������"""
                        for node in nodes:
                            if relation.parent == node.oid:
                                isFind = True
                                break
                        for node in addNode:
                            if relation.parent == node.oid:
                                isFind = True
                                break

                        if not isFind:
                            """�¼���Ϊ��ȡ�ĵ�"""
                            newNode = CommitNode()
                            newNode.willFetch = True
                            newNode.oid = relation.parent
                            newNode.parents = []
                            addNode.append(newNode)
                    nodes.extend(addNode)

                    # for node in nodes:
                    #     print("after fetched  2: " + f"{node.oid}  {node.willFetch}")

                    return nodes

                try:
                    """����Group�ĵ�������"""
                    commit1Nodes = []
                    commit2Nodes = []

                    node1 = CommitNode()
                    node1.oid = commit1
                    node1.willFetch = True
                    node1.parents = []
                    commit1Nodes.append(node1)
                    node2 = CommitNode()
                    node2.oid = commit2
                    commit2Nodes.append(node2)
                    node2.willFetch = True
                    node2.parents = []

                    completeFetch = 0
                    while loop < configPraser.getCommitFetchLoop():
                        """��������������"""

                        loop += 1

                        print("loop:", loop, " 1")
                        printNodes(commit1Nodes, commit2Nodes)

                        if isNodesContains(commit1Nodes, commit2Nodes):
                            completeFetch = 2
                            break

                        if isNodesContains(commit2Nodes, commit1Nodes):
                            completeFetch = 1
                            break

                        await fetNotFetchedNodes(commit2Nodes, mysql, session)
                        print("loop:", loop, " 2")
                        printNodes(commit1Nodes, commit2Nodes)

                        if isNodesContains(commit1Nodes, commit2Nodes):
                            completeFetch = 2
                            break
                        if isNodesContains(commit2Nodes, commit1Nodes):
                            completeFetch = 1
                            break

                        await fetNotFetchedNodes(commit1Nodes, mysql, session)

                        print("loop:", loop, " 3")
                        printNodes(commit1Nodes, commit2Nodes)

                    if completeFetch == 0:
                        outOfLoopCase += 1
                        raise Exception('out of the loop !')

                    """�ҳ����鲻ͬ��node���бȽ�"""

                    """�����������￪ʼ���߲��� �ҳ����߲���ĵ�  ��ɸѡ��һЩ�������������"""
                    finishNodes1 = None
                    finishNodes2 = None
                    startNode1 = None
                    startNode2 = None

                    """���ݰ�����ϵ ȷ��1��2λ����"""
                    if completeFetch == 2:
                        finishNodes1 = commit1Nodes
                        finishNodes2 = commit2Nodes  # 2��λΪ������
                        startNode1 = node1.oid
                        startNode2 = node2.oid
                    if completeFetch == 1:
                        finishNodes1 = commit2Nodes
                        finishNodes2 = commit1Nodes
                        startNode1 = node2.oid
                        startNode2 = node1.oid

                    diff_nodes1 = []  # ���ڴ洢���߲�ͬ����ĵ�
                    diff_nodes2 = [x for x in finishNodes2 if not findNodes(finishNodes1, x.oid)]

                    # diff_nodes1 �Ȱ������е㣬Ȼ���ҳ���2�������ﲻ�˵ĵ�

                    diff_nodes1 = finishNodes1.copy()
                    for node in finishNodes2:
                        if not findNodes(finishNodes1, node.oid):  # ȥ��
                            diff_nodes1.append(node)

                    temp = [startNode2]
                    while temp.__len__() > 0:
                        oid = temp.pop(0)
                        node = findNodes(diff_nodes1, oid)
                        if node is not None:
                            temp.extend(node.parents)
                        diff_nodes1.remove(node)

                    for node in diff_nodes1:
                        if node.willFetch:
                            twoParentsBadCase += 1
                            raise Exception('will fetch node in set 1 !')  # ȥ���ֲ�ڵ�δ��֮ǰ���������

                    """diff_node1 �� diff_node2 �ֱ�洢���߶�����ĵ�"""
                    printNodes(diff_nodes1, diff_nodes2)

                    """��ȥ����ĵ�����merge �ڵ�Ĵ���"""
                    for node in diff_nodes1:
                        if node.parents.__len__() >= 2:
                            twoParentsBadCase += 1
                            raise Exception('merge node find in set1 !')
                    for node in diff_nodes2:
                        if node.parents.__len__() >= 2:
                            twoParentsBadCase += 1
                            raise Exception('merge node find in set 2!')

                    if comments is not None:

                        """���commit ���е�change file"""
                        file1s = await AsyncApiHelper.getFilesFromStore([x.oid for x in diff_nodes1], mysql)
                        file2s = await AsyncApiHelper.getFilesFromStore([x.oid for x in diff_nodes2], mysql)

                        for comment in comments:  # ��ÿһ��commentͳ��change trigger
                            """comment ��Ӧ���ļ����ļ���"""
                            commentFile = comment.path
                            commentLine = comment.original_line

                            diff_patch1 = []  # ���߲�ͬ��patch patch���ǲ�ͬ�ı�����
                            diff_patch2 = []

                            startNode = [startNode1]  # ��commitԴͷ�ҵ�����ÿһ��commit���漰�ļ�����patch
                            while startNode.__len__() > 0:
                                """����DFS�㷨"""
                                node_oid = startNode.pop(0)
                                for node in diff_nodes1:
                                    if node.oid == node_oid:
                                        for file in file1s:
                                            if file.filename == commentFile and file.commit_sha == node.oid:
                                                """patch��һ������ĳЩ�����仯���ı�����Ҫ���浥���Ľ���"""
                                                diff_patch1.insert(0, file.patch)
                                        startNode.extend(node.parents)

                            startNode = [startNode2]
                            while startNode.__len__() > 0:
                                node_oid = startNode.pop(0)
                                for node in diff_nodes2:
                                    if node.oid == node_oid:
                                        for file in file2s:
                                            if file.filename == commentFile and file.commit_sha == node.oid:
                                                diff_patch2.insert(0, file.patch)
                                        startNode.extend(node.parents)

                            """ͨ���Ƚ�commit�������������comment������ļ��仯"""
                            closedChange = TextCompareUtils.getClosedFileChange(diff_patch1, diff_patch2, commentLine)
                            print("closedChange :", closedChange)
                            if comment.change_trigger is None:
                                comment.change_trigger = closedChange
                            else:
                                comment.change_trigger = min(comment.change_trigger, closedChange)
                except Exception as e:
                    print(e)
                    continue

            statistic.lock.acquire()
            statistic.outOfLoopCase += outOfLoopCase
            statistic.usefulChangeTrigger += [x for x in comments if x.change_trigger is not None].__len__()
            statistic.lock.release()

        await AsyncSqlHelper.updateBeanDateList(comments, mysql)

    @staticmethod
    async def getReviewCommentsByNodeFromStore(node_id, mysql):
        """�����ݿ��ж�ȡreview id ��ʱ�����ֻҪ�����ݿ������Ӿ�ok��"""

        review = Review()
        review.node_id = node_id

        reviews = await AsyncSqlHelper.queryBeanData([review], mysql, [[StringKeyUtils.STR_KEY_NODE_ID]])
        print("reviews:", reviews)
        if reviews[0].__len__() > 0:
            review_id = reviews[0][0][2]
            print("review_id:", review_id)
            comment = ReviewComment()
            comment.pull_request_review_id = review_id

            result = await AsyncSqlHelper.queryBeanData([comment], mysql,
                                                        [[StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW_ID]])
            print(result)
            if result[0].__len__() > 0:
                comments = BeanParserHelper.getBeansFromTuple(ReviewComment(), ReviewComment.getItemKeyList(),
                                                              result[0])

                """��ȡcomment �Լ���Ӧ��sha ��nodeId ������,fileName"""
                for comment in comments:
                    print(comment.getValueDict())
                return comments

    @staticmethod
    async def getFilesFromStore(oids, mysql):
        """�����ݿ��ж�ȡ���oid��file changes"""

        print("query file oids:", oids)

        queryFiles = []
        for oid in oids:
            file = File()
            file.commit_sha = oid
            queryFiles.append(file)

        gitFiles = []

        if queryFiles.__len__() > 0:
            results = await AsyncSqlHelper.queryBeanData(queryFiles, mysql,
                                                         [[StringKeyUtils.STR_KEY_COMMIT_SHA]] * queryFiles.__len__())
            print("files:", results)
            for result in results:
                if result.__len__() > 0:
                    files = BeanParserHelper.getBeansFromTuple(File(), File.getItemKeyList(), result)
                    gitFiles.extend(files)

        return gitFiles

    @staticmethod
    async def getCommitsFromStore(oids, mysql):

        beans = []

        existList = []  # �����б�
        relationList = []  # ��ѯ�õ��Ĺ�ϵ�б� �����б���ִ�����ϵͳ�д洢

        """�ȴ�sha(oid)ת��Ϊcommit����"""
        for oid in oids:
            bean = CommitRelation()
            bean.child = oid
            beans.append(bean)

        results = await AsyncSqlHelper.queryBeanData(beans, mysql, [[StringKeyUtils.STR_KEY_CHILD]] * beans.__len__())
        print("result:", results)

        """�ӱ��ط��صĽ��������"""
        for relationTuple in results:
            if relationTuple.__len__() > 0:
                existList.append(relationTuple[0][0])
                for relation in relationTuple:
                    r = CommitRelation()
                    r.child = relation[0]
                    r.parent = relation[1]
                    relationList.append(r)
        """ȥ�ش���"""
        existList = list(set(existList))
        relationList = list(set(relationList))
        return existList, relationList

    @staticmethod
    async def getCommitsFromApi(oids, mysql, session):

        beanList = []
        relationList = []  # ��ѯ�õ��Ĺ�ϵ�б�

        for oid in oids:
            api = AsyncApiHelper.getCommitApi(oid)
            json = await AsyncApiHelper.fetchBeanData(session, api)
            # print(json)
            commit = await AsyncApiHelper.parserCommit(json)

            if commit.parents is not None:
                relationList.extend(commit.parents)
            if commit.files is not None:
                beanList.extend(commit.files)

            beanList.append(commit)
        beanList.extend(relationList)
        await AsyncSqlHelper.storeBeanDateList(beanList, mysql)
        return relationList

    @staticmethod
    async def downloadCommits(projectName, oid, semaphore, mysql, statistic):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []
                    owner, repo = projectName.split('/')
                    api = AsyncApiHelper.getCommitApiWithProjectName(owner, repo, oid)
                    json = await AsyncApiHelper.fetchBeanData(session, api)
                    # print(json)
                    commit = await AsyncApiHelper.parserCommit(json)

                    if commit.parents is not None:
                        beanList.extend(commit.parents)
                    if commit.files is not None:
                        beanList.extend(commit.files)

                    beanList.append(commit)
                    await AsyncSqlHelper.storeBeanDateList(beanList, mysql)

                    # ����ͬ������
                    statistic.lock.acquire()
                    statistic.usefulCommitNumber += 1
                    print(f" usefulCommitCount:{statistic.usefulCommitNumber}")
                    statistic.lock.release()
                except Exception as e:
                    print(e)
