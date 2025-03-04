# coding=gbk
import asyncio
import difflib
import json
import random
import time
import traceback
from datetime import datetime

import aiohttp

from source.config.configPraser import configPraser
from source.data.bean.Blob import Blob
from source.data.bean.Comment import Comment
from source.data.bean.CommentRelation import CommitRelation
from source.data.bean.Commit import Commit
from source.data.bean.CommitPRRelation import CommitPRRelation
from source.data.bean.File import File
from source.data.bean.IssueComment import IssueComment
from source.data.bean.PRChangeFile import PRChangeFile
from source.data.bean.PRTimeLine import PRTimeLine
from source.data.bean.PRTimeLineRelation import PRTimeLineRelation
from source.data.bean.PullRequest import PullRequest
from source.data.bean.Review import Review
from source.data.bean.ReviewComment import ReviewComment
from source.data.bean.TreeEntry import TreeEntry
from source.data.bean.User import User
from source.data.bean.UserFollowRelation import UserFollowRelation
from source.data.bean.UserWatchRepoRelation import UserWatchRepoRelation
from source.data.service.AsyncSqlHelper import AsyncSqlHelper
from source.data.service.BeanParserHelper import BeanParserHelper
from source.data.service.GraphqlHelper import GraphqlHelper
from source.data.service.PRTimeLineUtils import PRTimeLineUtils
from source.data.service.ProxyHelper import ProxyHelper
from source.data.service.TextCompareUtils import TextCompareUtils
from source.utils.Logger import Logger
from source.utils.StringKeyUtils import StringKeyUtils
from operator import itemgetter, attrgetter


class AsyncApiHelper:
    """使用aiohttp异步通讯"""

    owner = None
    repo = None

    @staticmethod
    def setRepo(owner, repo):  # 使用之前设置项目名和所有者
        AsyncApiHelper.owner = owner
        AsyncApiHelper.repo = repo

    @staticmethod
    def getAuthorizationHeaders(header):
        """设置Github 的Token用于验证"""
        if header is not None and isinstance(header, dict):
            if configPraser.getAuthorizationToken():
                header[StringKeyUtils.STR_HEADER_AUTHORIZAITON] = (StringKeyUtils.STR_HEADER_TOKEN
                                                                   + configPraser.getAuthorizationToken())
        return header

    @staticmethod
    def getUserAgentHeaders(header):
        """爬虫策略： 随机请求的agent"""
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
        """获取代理ip池中的ip  详细看 ProxyHelper"""
        if configPraser.getProxy():
            proxy = await ProxyHelper.getAsyncSingleProxy()
            if configPraser.getPrintMode():
                print(proxy)
            if proxy is not None:
                return StringKeyUtils.STR_PROXY_HTTP_FORMAT.format(proxy)
        return None

    @staticmethod
    async def parserPullRequest(resultJson, pull_number=None, rawData=None):
        try:
            res = None
            if configPraser.getApiVersion() == StringKeyUtils.API_VERSION_RESET:
                if not AsyncApiHelper.judgeNotFind(resultJson):
                    res = PullRequest.parser.parser(resultJson)
            elif configPraser.getApiVersion() == StringKeyUtils.API_VERSION_GRAPHQL:
                res = PullRequest.parserV4.parser(resultJson)
                if res is not None:
                    res.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo
                """对于v4接口 pr获取不到的情况，如果确认不存在，则是视为等issue的情况"""
                """读取errors 信息"""
                if res is None:
                    errorMessage = rawData.get(StringKeyUtils.STR_KEY_ERRORS)[0]. \
                        get(StringKeyUtils.STR_KEY_MESSAGE)
                    if errorMessage.find(StringKeyUtils.STR_KEY_ERRORS_PR_NOT_FOUND) != -1:
                        res = PullRequest()
                        res.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo
                        res.number = pull_number
                        res.is_pr = False
            if res is not None:
                res.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo
                return res
        except Exception as e:
            print(e)

    @staticmethod
    def judgeNotFind(resultJson):
        if resultJson is not None and isinstance(json, dict):
            if resultJson.get(StringKeyUtils.STR_KEY_MESSAGE) == StringKeyUtils.STR_NOT_FIND:
                return True
            if resultJson.get(StringKeyUtils.STR_KEY_MESSAGE) == StringKeyUtils.STR_FAILED_FETCH:
                return True
        return False

    @staticmethod
    def judgeNotFindV4(resultJson):
        """v4 接口的not find判断和v3的不大相同"""
        if resultJson is not None and isinstance(json, dict):
            if resultJson.get(StringKeyUtils.STR_KEY_ERRORS) is not None:
                return True
        return False

    @staticmethod
    async def parserUserFollowingList(resultJson):
        try:
            res = None
            res = UserFollowRelation.parserV4.parser(resultJson)
            return res
        except Exception as e:
            print(e)

    @staticmethod
    async def parserUserWatchRepoList(resultJson):
        try:
            res = None
            res = UserWatchRepoRelation.parserV4.parser(resultJson)
            return res
        except Exception as e:
            print(e)


    @staticmethod
    async def downloadInformation(pull_number, semaphore, mysql, statistic):
        """获取一个项目 单个pull-request 相关的信息"""

        """增加issue  需要仿写downloadInformation函数 
           只是pull-request的获取转换为issue
        """
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []  # 用来收集需要存储的bean类
                    """先获取pull request信息"""
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

                        reviewCommits = []  # review中涉及的Commit的点

                        """获取review信息"""
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

                        """获取review comment信息"""
                        api = AsyncApiHelper.getReviewCommentForPullRequestApi(pull_number)
                        json = await AsyncApiHelper.fetchBeanData(session, api, isMediaType=True)
                        reviewComments = await AsyncApiHelper.parserReviewComment(json)

                        if configPraser.getPrintMode():
                            print(reviewComments)
                        usefulReviewCommentsCount = 0
                        if reviewComments is not None:
                            for reviewComment in reviewComments:
                                """补全 reivew comment 的 pull_request_review_node_id"""
                                for r in reviews:
                                    if r.id == reviewComment.pull_request_review_id:
                                        reviewComment.pull_request_review_node_id = r.node_id

                                usefulReviewCommentsCount += 1
                                beanList.append(reviewComment)
                                if reviewComment.user is not None:
                                    beanList.append(reviewComment.user)

                        '''获取 pull request对应的issue comment信息'''
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

                        '''获取 pull request对应的commit信息'''
                        api = AsyncApiHelper.getCommitForPullRequestApi(pull_number)
                        json = await AsyncApiHelper.fetchBeanData(session, api, isMediaType=True)
                        Commits, Relations = await AsyncApiHelper.parserCommitAndRelation(json, pull_number)

                        for commit in Commits:
                            if commit.sha in reviewCommits:
                                reviewCommits.remove(commit.sha)

                        """有些review涉及的commit的点没有在PR线中收集到 这些点主要是中间存在最后
                        没有的点 但是最后需要在特征提取中用到 所以也需要收集"""

                        """剩下的点需要依次获取"""
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
                                """作为资源节约   commit comment不做采集"""

                        for relation in Relations:
                            beanList.append(relation)

                        print(beanList)

                    """数据库存储"""
                    await AsyncSqlHelper.storeBeanDateList(beanList, mysql)

                    # 做了同步处理
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
        """获取一个项目 单个pull-request 相关的信息
           主要接口请求迁移到GraphQl的v4接口上   这样可以一次性获取pr信息
           保证了pr信息的完整性
           但是commit的具体信息无法获取  这个准备单独开函数获取

           即gitFile的信息和其他信息获取分离
        """
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []  # 用来收集需要存储的bean类
                    """先获取pull request信息"""
                    args = {"number": pull_number, "owner": AsyncApiHelper.owner, "name": AsyncApiHelper.repo}
                    api = AsyncApiHelper.getGraphQLApi()
                    query = GraphqlHelper.getPrInformationByNumber()
                    resultJson = await AsyncApiHelper.postGraphqlData(session, api, query, args)
                    print(resultJson)

                    """解析pull request"""
                    allData = resultJson.get(StringKeyUtils.STR_KEY_DATA, None)
                    if allData is not None and isinstance(allData, dict):
                        repoData = allData.get(StringKeyUtils.STR_KEY_REPOSITORY, None)
                        if repoData is not None and isinstance(repoData, dict):
                            prData = repoData.get(StringKeyUtils.STR_KEY_ISSUE_OR_PULL_REQUEST, None)

                            pull_request = await AsyncApiHelper.parserPullRequest(prData, pull_number, resultJson)

                            usefulPullRequestsCount = 0
                            usefulReviewsCount = 0
                            usefulReviewCommentsCount = 0
                            usefulIssueCommentsCount = 0
                            usefulCommitsCount = 0

                            """添加pul request 和 branch"""
                            if pull_request is not None:
                                usefulPullRequestsCount = 1
                                beanList.append(pull_request)
                                if pull_request.head is not None:
                                    beanList.append(pull_request.head)
                                if pull_request.base is not None:
                                    beanList.append(pull_request.base)

                            if pull_request is not None and pull_request.is_pr:
                                users = []
                                """解析 user 直接从pr的participate获取"""
                                user_list = prData.get(StringKeyUtils.STR_KEY_PARTICIPANTS, None)
                                if user_list is not None and isinstance(user_list, dict):
                                    user_list_nodes = user_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if user_list_nodes is not None and isinstance(user_list_nodes, list):
                                        for userData in user_list_nodes:
                                            user = User.parserV4.parser(userData)
                                            if user is not None:
                                                users.append(user)
                                """添加用户"""
                                beanList.extend(users)

                                """解析 review, review comment, review 涉及的 commit 信息"""
                                reviews = []
                                reviewComments = []
                                commits = []

                                """新增考虑解析review和解析reviewThread的互斥性，对于新的pr来说，是两者都存在的。
                                   所以如果解析到review对象的话，reviewThread对象就不解析了 @ 张逸凡 2020.12.14
                                """
                                isReviewExist = False  # 用于判断Review对象是否存在
                                review_list = prData.get(StringKeyUtils.STR_KEY_REVIEWS, None)
                                if review_list is not None and isinstance(review_list, dict):
                                    review_list_nodes = review_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if review_list_nodes is not None and isinstance(review_list_nodes, list):
                                        if review_list_nodes.__len__() > 0:
                                            isReviewExist = True  # 说明是新的pr
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
                                                            , list):
                                                        for commentData in comment_list_nodes:
                                                            commentData[StringKeyUtils.STR_KEY_REPO_FULL_NAME] = AsyncApiHelper.owner + "/" + AsyncApiHelper.repo
                                                            comment = ReviewComment.parserV4.parser(commentData)
                                                            comment.pull_request_review_id = review.id
                                                            comment.pull_request_review_node_id = review.node_id
                                                            reviewComments.append(comment)

                                                commitData = reviewData.get(StringKeyUtils.STR_KEY_COMMIT, None)
                                                if commitData is not None and isinstance(commitData, dict):
                                                    commit = Commit.parserV4.parser(commitData)
                                                    commit.has_file_fetched = False
                                                    isFind = False
                                                    for c in commits:
                                                        if c.sha == commit.sha:
                                                            isFind = True
                                                            break
                                                    if not isFind:
                                                        commits.append(commit)

                                if not isReviewExist:
                                    """对于没有获取到review的pr，我们获取reviewThread"""
                                    review_thread_list = prData.get(StringKeyUtils.STR_KEY_REVIEW_THREAD_V4, None)
                                    if review_thread_list is not None and isinstance(review_thread_list, dict):
                                        review_thread_list_nodes = review_thread_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                        if review_thread_list_nodes is not None and isinstance(review_thread_list_nodes, list):
                                            for reviewThreadData in review_thread_list_nodes:
                                                if reviewThreadData is not None and isinstance(reviewThreadData, dict):
                                                    baseReviewThreadId = reviewThreadData.get(StringKeyUtils.STR_KEY_ID, None)
                                                    comment_list = reviewThreadData.get(StringKeyUtils.STR_KEY_COMMENTS, None)
                                                    if comment_list is not None and isinstance(comment_list, dict):
                                                        comment_list_nodes = comment_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                                        if comment_list_nodes is not None and isinstance(comment_list_nodes, list):
                                                            for index, commentData in enumerate(comment_list_nodes):
                                                                commentData[StringKeyUtils.STR_KEY_REPO_FULL_NAME] = AsyncApiHelper.owner + "/" + AsyncApiHelper.repo
                                                                comment = ReviewComment.parserV4.parser(commentData)
                                                                """对于单独一个comment，造一个review与之配对
                                                                   review的id 是自己做的，node_id 就用 reviewThread自己的id
                                                                """
                                                                review = Review()
                                                                review.pull_number = pull_number
                                                                review.repo_full_name = pull_request.repo_full_name
                                                                review.node_id = baseReviewThreadId
                                                                review.user_login = comment.user_login
                                                                review.submitted_at = comment.created_at
                                                                review.author_association = comment.author_association
                                                                review.commit_id = comment.original_commit_id
                                                                """review的 id 作为 node_id +  / + 序号"""
                                                                review.id = baseReviewThreadId + '/' + str(index)
                                                                reviews.append(review)

                                                                comment.pull_request_review_id = review.id
                                                                comment.pull_request_review_node_id = review.node_id
                                                                reviewComments.append(comment)

                                """prTimeLine信息不在这个接口获取，直接注掉  2020.12.14"""
                                # """对于2016年之前的数据  没有review数据项，而PullRequestReviewThread
                                #    可以获取对应 review、review comment和 commit
                                # """
                                # itemLineItem_list = prData.get(StringKeyUtils.STR_KEY_TIME_LINE_ITEMS, None)
                                # if itemLineItem_list is not None and isinstance(itemLineItem_list, dict):
                                #     itemLineItem_list_edges = itemLineItem_list.get(StringKeyUtils.STR_KEY_EDGES, None)
                                #     if itemLineItem_list_edges is not None and isinstance(itemLineItem_list_edges,
                                #                                                           list):
                                #         for itemLineItem_list_edge_node in itemLineItem_list_edges:
                                #             if itemLineItem_list_edge_node is not None and \
                                #                     isinstance(itemLineItem_list_edge_node, dict):
                                #                 itemLineItem_list_edge_node = itemLineItem_list_edge_node. \
                                #                     get(StringKeyUtils.STR_KEY_NODE, None)
                                #                 typename = itemLineItem_list_edge_node.get(
                                #                     StringKeyUtils.STR_KEY_TYPE_NAME_JSON, None)
                                #                 if typename == StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW_THREAD:
                                #                     """ReviewThread 作为Review 存储到数据库中  但是只有node_id 信息"""
                                #                     review = Review()
                                #                     review.pull_number = pull_request
                                #                     review.repo_full_name = pull_request.repo_full_name
                                #                     review.node_id = itemLineItem_list_edge_node.get(
                                #                         StringKeyUtils.STR_KEY_ID, None)
                                #                     reviews.append(review)
                                #
                                #                     """解析 review 涉及的review comment"""
                                #                     comment_list = itemLineItem_list_edge_node.get(
                                #                         StringKeyUtils.STR_KEY_COMMENTS, None)
                                #                     if comment_list is not None and isinstance(comment_list, dict):
                                #                         comment_list_nodes = comment_list.get(
                                #                             StringKeyUtils.STR_KEY_NODES
                                #                             , None)
                                #                         if comment_list_nodes is not None and isinstance(
                                #                                 comment_list_nodes
                                #                                 , list):
                                #                             for commentData in comment_list_nodes:
                                #                                 comment = ReviewComment.parserV4.parser(commentData)
                                #                                 comment.pull_request_review_id = review.id
                                #                                 comment.pull_request_review_node_id = review.node_id
                                #                                 reviewComments.append(comment)
                                #
                                #                                 """"从commentData 解析 original commit"""
                                #                                 commitData = commentData.get(
                                #                                     StringKeyUtils.STR_KEY_ORIGINAL_COMMIT, None)
                                #                                 if commitData is not None and isinstance(commitData,
                                #                                                                          dict):
                                #                                     commit = Commit.parserV4.parser(commitData)
                                #                                     commit.has_file_fetched = False
                                #                                     isFind = False
                                #                                     for c in commits:
                                #                                         if c.sha == commit.sha:
                                #                                             isFind = True
                                #                                             break
                                #                                     if not isFind:
                                #                                         commits.append(commit)

                                if configPraser.getPrintMode():
                                    print(reviews)
                                    print(reviewComments)

                                usefulReviewsCount += reviews.__len__()
                                usefulReviewCommentsCount += reviewComments.__len__()

                                """添加review reviewComments"""
                                beanList.extend(reviews)
                                beanList.extend(reviewComments)

                                """issue comment 信息获取"""
                                issueComments = []
                                issue_comment_list = prData.get(StringKeyUtils.STR_KEY_COMMENTS, None)
                                if issue_comment_list is not None and isinstance(issue_comment_list, dict):
                                    issue_comment_list_nodes = issue_comment_list.get(StringKeyUtils.STR_KEY_NODES,
                                                                                      None)
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
                                beanList.extend(issueComments)

                                """获取 pr 中直接关联的 commit 信息"""
                                commit_list = prData.get(StringKeyUtils.STR_KEY_COMMITS, None)
                                if commit_list is not None and isinstance(commit_list, dict):
                                    commit_list_nodes = commit_list.get(StringKeyUtils.STR_KEY_NODES, None)
                                    if commit_list_nodes is not None and isinstance(commit_list_nodes, list):
                                        for commitData in commit_list_nodes:
                                            if commitData is None:
                                                continue
                                            commitData = commitData.get(StringKeyUtils.STR_KEY_COMMIT, None)
                                            commit = Commit.parserV4.parser(commitData)
                                            commit.has_file_fetched = False
                                            isFind = False
                                            for c in commits:
                                                if c.sha == commit.sha:
                                                    isFind = True
                                                    break
                                            if not isFind:
                                                commits.append(commit)

                                """整合 commitPrRelation 和 commitRelation"""
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
                                beanList.extend(CommitPrRelations)
                                beanList.extend(CommitRelations)
                                beanList.extend(commits)

                                """新增 pull request 涉及的文件变动，而不是commit文件变动的累加"""
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

                                beanList.extend(files)

                            """beanList 添加各个数据项"""

                            """数据库存储"""
                            if beanList.__len__() > 0:
                                await AsyncSqlHelper.storeBeanDateList(beanList, mysql)

                            # 做了同步处理
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
                    res.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo  # 对repo_full_name 做一个补全
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
    def getSingleReviewCommentApiWithProjectName(owner, repo, comment_id):
        api = StringKeyUtils.API_GITHUB + StringKeyUtils.API_COMMENT_FOR_REVIEW_SINGLE
        api = api.replace(StringKeyUtils.STR_OWNER, owner)
        api = api.replace(StringKeyUtils.STR_REPO, repo)
        api = api.replace(StringKeyUtils.STR_COMMENT_ID, str(comment_id))
        return api

    @staticmethod
    async def fetchBeanData(session, api, isMediaType=False):
        """异步获取数据通用接口（重要）"""

        """初始化请求头"""
        headers = {}
        headers = AsyncApiHelper.getUserAgentHeaders(headers)
        headers = AsyncApiHelper.getAuthorizationHeaders(headers)
        if isMediaType:
            headers = AsyncApiHelper.getMediaTypeHeaders(headers)
        while True:
            """对单个请求循环判断 直到请求成功或者错误"""

            """获取代理ip  ip获取需要运行代理池"""
            proxy = await AsyncApiHelper.getProxy()
            if configPraser.getProxy() and proxy is None:  # 对代理池没有ip的情况做考虑
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
            """非 403的网络请求出错  循环重试"""
            print(e)
            if proxy is not None:
                proxy = proxy.split('//')[1]
                await ProxyHelper.judgeProxy(proxy, ProxyHelper.INT_NEGATIVE_POINT)
            # print("judge end")
            """循环重试"""
            return await AsyncApiHelper.fetchBeanData(session, api, isMediaType=isMediaType)

    @staticmethod
    async def postGraphqlData(session, api, query=None, args=None):
        """通过 github graphhql接口 通过post请求"""
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
            if configPraser.getProxy() and proxy is None:  # 对代理池没有ip的情况做考虑
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
            print("judge end")
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
                    """信息补全"""
                    res.repo_full_name = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo  # 对repo_full_name 做一个补全
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
                """v3 接口认为有gitFile信息"""
                res.has_file_fetched = True
                return res
        except Exception as e:
            print(e)

    @staticmethod
    async def parserSingleReviewComment(resultJson):
        try:
            if not AsyncApiHelper.judgeNotFind(resultJson):
                res = ReviewComment.parser.parser(resultJson)
                return res
        except Exception as e:
            print(e)

    @staticmethod
    async def downloadRPTimeLine(node_ids, semaphore, mysql, statistic):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    args = {"ids": node_ids}
                    """从GitHub v4 API 中获取多个pull-request的TimeLine对象"""
                    api = AsyncApiHelper.getGraphQLApi()
                    query = GraphqlHelper.getTimeLineQueryByNodes()
                    resultJson = await AsyncApiHelper.postGraphqlData(session, api, query, args)
                    print("successfully fetched Json! nodeIDS: {0}".format(json.dumps(node_ids)))
                    """用于 肉眼观测 403 或者 rate等情况 = ="""
                    print(resultJson)

                    if AsyncApiHelper.judgeNotFindV4(resultJson):
                        Logger.loge("not found")
                        raise Exception("not found")

                    """处理异常情况"""
                    if not isinstance(resultJson, dict):
                        return None
                    data = resultJson.get(StringKeyUtils.STR_KEY_DATA, None)
                    if data is None or not isinstance(data, dict):
                        return None
                    nodes = data.get(StringKeyUtils.STR_KEY_NODES, None)
                    if nodes is None:
                        return None

                    prTimeLines = []
                    for node in nodes:
                        """从回应结果解析出pr时间线对象"""
                        node[StringKeyUtils.STR_KEY_REPO_FULL_NAME] = AsyncApiHelper.repo + "/" + AsyncApiHelper.owner
                        prTimeLine = PRTimeLine.Parser.parser(node)
                        if prTimeLine is None:
                            continue
                        prTimeLineItems = prTimeLine.timeline_items
                        """存储数据库中"""
                        try:
                            await AsyncSqlHelper.storeBeanDateList(prTimeLineItems, mysql)
                        except Exception as e:
                            Logger.loge(json.dumps(e.args))
                            Logger.loge(
                                "this pr's timeline: {0} fail to insert".format(node.get(StringKeyUtils.STR_KEY_ID)))
                        # 做同步处理
                        statistic.lock.acquire()
                        statistic.usefulTimeLineCount += 1
                        print(f" usefulTimeLineCount:{statistic.usefulTimeLineCount}",
                              f" change trigger count:{statistic.usefulChangeTrigger}",
                              f" twoParents case:{statistic.twoParentsNodeCase}",
                              f" outOfLoop case:{statistic.outOfLoopCase}")
                        statistic.lock.release()
                        prTimeLines.append(prTimeLine)
                    return prTimeLines
                except Exception as e:
                    print(e)

    @staticmethod
    async def analyzeReviewChangeTrigger(pr_node_id, pair, mysql, statistic):
        """分析review和随后的changes是否有trigger关系"""
        """目前算法暂时先不考虑comment的change_trigger，只考虑文件层面"""
        """算法说明：  通过reviewCommit和changeCommit来比较两者之间的代码差异"""
        """大体思路:   reviewCommit和它的祖宗节点组成一个commit的集合reviewGroup
                      changeCommit同样组成了changeGroup

                      在Group中每一个commit点都有以下信息：
                      1. oid (commit-sha)
                      2. 父节点的 oid
                      3. 这个commit涉及的文件改动

                      Group中包含两种类型节点，一种是信息已经获取，还有一种是信息尚未获取。
                      信息已经获取代表了这个commit上面三个信息都知道，而未获取代表了这个commit
                      只有oid信息。

                      Group一次迭代是指，每次获取类型为未获取信息的commit点，并将这些点加入Group中，
                      commit指向的父节点也作为未获取信息节点加入Group中。

                      两个commit作为起点不断做迭代操作，直到某个Group中未获取信息的点集合包含在了
                      另外一个Group的总体节点中

                      迭代结束之后分别找到两个Group差异的commit点集合，作为后续算法的输入
        """

        """缺点： 现在算法无法处理commit点有两个父类的情况，如merge操作出现的点
                  现在算法感觉怪怪的，效率可能不是很高
                  这个问题应该是LCA问题的变种
        """

        """算法限制:  1、commit点获取次数越少越好
                     2、两个commit点版本差异过过大的时候可以检测，并妥善处理 
        """

        """commit node工具类"""

        class CommitNode:
            willFetch = None
            oid = None
            parents = None  # [sha1, sha2 ...]

            def __init__(self, will_fetch=True, oid=None, parents=None):
                self.willFetch = will_fetch
                self.oid = oid
                self.parents = parents

        """node group工具方法start"""

        def findNodes(nodes, oid):
            for node in nodes:
                if node.oid == oid:
                    return node

        def isExist(nodes, oid):
            for node in nodes:
                if node.oid == oid:
                    return True
            return False

        def isNodesContains(nodes1, nodes2):
            """nodes2所有未探索的点是否被nodes1包含"""
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

        async def fetNotFetchedNodes(nodes, mysql):
            async with aiohttp.ClientSession() as session:
                """获取commit点信息 包括数据库获取的GitHub API获取 nodes就是一个Group"""
                needFetchList = [node.oid for node in nodes if node.willFetch]
                """先尝试从数据库中读取"""
                localExistList, localRelationList = await AsyncApiHelper.getCommitsFromStore(needFetchList, mysql)
                needFetchList = [oid for oid in needFetchList if oid not in localExistList]
                print("need fetch list:", needFetchList)
                webRelationList = await AsyncApiHelper.getCommitsFromApi(needFetchList, mysql, session)

                for node in nodes:
                    node.willFetch = False

                relationList = []
                relationList.extend(localRelationList)
                relationList.extend(webRelationList)

                """原有的node 补全parents"""
                for relation in relationList:
                    node = findNodes(nodes, relation.child)
                    if node is not None:
                        if relation.parent not in node.parents:
                            node.parents.append(relation.parent)

                addNode = []
                for relation in relationList:
                    isFind = False
                    """确保在两个地方都不存在"""
                    for node in nodes:
                        if relation.parent == node.oid:
                            isFind = True
                            break
                    for node in addNode:
                        if relation.parent == node.oid:
                            isFind = True
                            break

                    if not isFind:
                        """新加入为获取的点"""
                        newNode = CommitNode(will_fetch=True, oid=relation.parent, parents=[])
                        addNode.append(newNode)
                nodes.extend(addNode)
                return nodes

        """node group工具方法end"""

        review = pair[0]
        changes = pair[1]
        if changes is None or changes.__len__() == 0:
            return None

        """从数据库获取review comments(注：一个review 可能会关联多个comment，每个comment会指定一个文件和对应代码行)"""
        comments = await AsyncApiHelper.getReviewCommentsByNodeFromStore(review.timeline_item_node, mysql)
        if comments is None:
            return None
        """通过comment的 position、originalPosition信息补全originalLine, side 需要对应commit的file的patch"""
        oids = [comment.original_commit_id for comment in comments]
        """获取这些的changes files"""
        files = await AsyncApiHelper.getFilesFromStore(oids, mysql)
        """依次补全"""
        for comment in comments:
            """comment默认未触发change_trigger"""
            comment.change_trigger = -1
            for file in files:
                if file.commit_sha == comment.original_commit_id and file.filename == comment.path:
                    """计算 line 和 origin line"""
                    original_line, side = TextCompareUtils.getStartLine(file.patch, comment.original_position)
                    comment.side = side
                    comment.original_line = original_line

                    """line 是改动后文本评论指向的行数， original line 是改动前的文本评论指向行数
                       有 line 就别用 original line
                    """

        twoParentsBadCase = 0  # 记录一个commit有两个根节点的情况 发现这个情况直接停止
        outOfLoopCase = 0  # 记录寻找两个commit点的最近祖宗节点 使用上级追溯的次数超过限制情况

        """遍历review之后的changes，判断是否有comment引起change的情况"""
        change_trigger_comments = []
        for change in changes:  # 对后面连续改动依次遍历
            reviewCommit = review.pull_request_review_commit
            changeCommit = None
            if change.typename == StringKeyUtils.STR_KEY_PULL_REQUEST_COMMIT:
                changeCommit = change.pull_request_commit
            elif change.typename == StringKeyUtils.STR_KEY_HEAD_REF_PUSHED_EVENT:
                changeCommit = change.headRefForcePushedEventAfterCommit

            if changeCommit is None or reviewCommit is None:
                break
            try:
                # TODO 后续研究如何直接比较两个commit的版本差异
                """两个Group的迭代过程"""
                reviewGroup = []
                changeGroup = []

                reviewGroupStartNode = CommitNode(oid=reviewCommit, parents=[])
                reviewGroup.append(reviewGroupStartNode)
                changeGroupStartNode = CommitNode(oid=changeCommit, parents=[])
                changeGroup.append(changeGroupStartNode)

                # 已全部Fetch的group
                completeFetch = None
                loop = 0
                while loop < configPraser.getCommitFetchLoop():
                    """迭代次数有限制"""
                    loop += 1
                    print("fetch nodes loop: ", loop)
                    printNodes(reviewGroup, changeGroup)

                    """判断包含关系，先拉取changeGroup"""
                    if isNodesContains(reviewGroup, changeGroup):
                        completeFetch = 'CHANGE_GROUP'
                        break
                    if isNodesContains(changeGroup, reviewGroup):
                        completeFetch = 'REVIEW_GROUP'
                        break
                    await fetNotFetchedNodes(changeGroup, mysql)

                    """判断包含关系，再拉取reviewGroup"""
                    printNodes(reviewGroup, changeGroup)
                    if isNodesContains(reviewGroup, changeGroup):
                        completeFetch = 'CHANGE_GROUP'
                        break
                    if isNodesContains(changeGroup, reviewGroup):
                        completeFetch = 'REVIEW_GROUP'
                        break
                    await fetNotFetchedNodes(reviewGroup, mysql)

                if completeFetch is None:
                    outOfLoopCase += 1
                    raise Exception('out of the loop !')

                """找出两组不同的node进行比较"""

                """被包含的那里开始行走测试 找出两者差异的点  并筛选出一些特殊情况做舍弃"""

                # 范围较大的group
                groupInclude = None
                groupIncludeStartNode = None
                # 被包含的group
                groupIncluded = None
                groupIncludedStartNode = None

                """依据包含关系 确认包含和被包含对象"""
                if completeFetch == 'CHANGE_GROUP':
                    groupInclude = reviewGroup
                    groupIncluded = changeGroup  # 2号位为被包含
                    groupIncludeStartNode = reviewGroupStartNode.oid
                    groupIncludedStartNode = changeGroupStartNode.oid
                if completeFetch == 'REVIEW_GROUP':
                    groupInclude = changeGroup
                    groupIncluded = reviewGroup
                    groupIncludeStartNode = changeGroupStartNode.oid
                    groupIncludedStartNode = reviewGroupStartNode.oid

                # 用于存储两边差集
                diff_nodes1 = []
                diff_nodes2 = [x for x in groupIncluded if not findNodes(groupInclude, x.oid)]

                # diff_nodes1 先包含所有点，然后找出从2出发到达不了的点
                diff_nodes1 = groupInclude.copy()
                for node in groupIncluded:
                    if not findNodes(groupInclude, node.oid):  # 去除
                        diff_nodes1.append(node)

                temp = [groupIncludedStartNode]
                while temp.__len__() > 0:
                    oid = temp.pop(0)
                    node = findNodes(diff_nodes1, oid)
                    if node is not None:
                        temp.extend(node.parents)
                    diff_nodes1.remove(node)

                for node in diff_nodes1:
                    if node.willFetch:
                        twoParentsBadCase += 1
                        raise Exception('will fetch node in set 1 !')  # 去除分叉节点未经之前遍历的情况

                """diff_node1 和 diff_node2 分别存储两边的差异点"""
                printNodes(diff_nodes1, diff_nodes2)

                """除去差异点中的merge节点"""
                for node in diff_nodes1:
                    if node.parents.__len__() >= 2:
                        twoParentsBadCase += 1
                        raise Exception('merge node find in set1 !')
                for node in diff_nodes2:
                    if node.parents.__len__() >= 2:
                        twoParentsBadCase += 1
                        raise Exception('merge node find in set 2!')
                """获得commit 所有的change file"""
                file1s = await AsyncApiHelper.getFilesFromStore([x.oid for x in diff_nodes1], mysql)
                file2s = await AsyncApiHelper.getFilesFromStore([x.oid for x in diff_nodes2], mysql)

                """文件差异"""
                changed_files = file1s.copy()
                changed_files.extend(file2s)
                for comment in comments:  # 对每一个comment统计change trigger
                    """comment 对应的文件"""
                    commentFile = comment.path
                    for file in changed_files:
                        if file.filename == commentFile:
                            comment.change_trigger = 1
                    # TODO 目前暂不考虑comment细化到行的change_trigger
                    # """comment 对应的文件行"""
                    # commentLine = comment.original_line
                    #
                    # diff_patch1 = []  # 两边不同的patch patch就是不同文本集合
                    # diff_patch2 = []

                    # """只要在改动路径上出现过和commentFile相同的文件，就认定该条comment是有效的"""
                    # startNode = [groupIncludeStartNode]  # 从commit源头找到根中每一个commit的涉及文件名的patch
                    # while startNode.__len__() > 0:
                    #     """类似DFS算法"""
                    #     node_oid = startNode.pop(0)
                    #     for node in diff_nodes1:
                    #         if node.oid == node_oid:
                    #             for file in file1s:
                    #                 if file.filename == commentFile and file.commit_sha == node.oid:
                    #                     comment.change_trigger = 1
                    #                     # TODO 目前暂不考虑comment细化到行的change_trigger
                    #                     # """patch是一个含有某些行数变化的文本，需要后面单独的解析"""
                    #                     # diff_patch1.insert(0, file.patch)
                    #             startNode.extend(node.parents)
                    #
                    # startNode = [groupIncludedStartNode]
                    # while startNode.__len__() > 0:
                    #     node_oid = startNode.pop(0)
                    #     for node in diff_nodes2:
                    #         if node.oid == node_oid:
                    #             for file in file2s:
                    #                 if file.filename == commentFile and file.commit_sha == node.oid:
                    #                     comment.change_trigger = 1
                    #                     # TODO 目前暂不考虑comment细化到行的change_trigger
                    #                     # diff_patch2.insert(0, file.patch)
                    #             startNode.extend(node.parents)
                    # TODO 目前暂不考虑comment细化到行的change_trigger
                    # """通过比较commit集合来计算距离comment最近的文件变化"""
                    # closedChange = TextCompareUtils.getClosedFileChange(diff_patch1, diff_patch2, commentLine)
                    # print("closedChange :", closedChange)
                    # if comment.change_trigger is None:
                    #     comment.change_trigger = closedChange
                    # else:
                    #     comment.change_trigger = min(comment.change_trigger, closedChange)
            except Exception as e:
                print(e)
                continue
        for comment in comments:
            change_trigger_comments.append({
                "pullrequest_node": pr_node_id,
                "user_login": comment.user_login,
                "comment_node": comment.node_id,
                "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                "change_trigger": comment.change_trigger,
                "filepath": comment.path
            })
        statistic.lock.acquire()
        statistic.outOfLoopCase += outOfLoopCase
        statistic.usefulChangeTrigger += [x for x in comments if x.change_trigger > 0].__len__()
        statistic.lock.release()

        # 更新comments的change_trigger, line, original_line信息"""
        await AsyncSqlHelper.updateBeanDateList(comments, mysql)
        return change_trigger_comments

    @staticmethod
    async def analyzeReviewChangeTriggerByBlob(pr_node_id, changes, review, mysql, statistic, comments, pr_author,
                                               is_in_gap):
        """changes目前是逆序的,做分析要先换回来"""
        changes.reverse()

        t1 = datetime.now()
        # """从数据库获取review comments(注：一个review 可能会关联多个comment，每个comment会指定一个文件和对应代码行)"""
        # comments = await AsyncApiHelper.getReviewCommentsByNodeFromStore(review.timeline_item_node, mysql)

        """现在进入这个逻辑的都是有comment的review comment
           2020.10.31
        """
        # if comments is None:
        #     print("comment is None! review id:", review.timeline_item_node)
        #     return None

        """时间线上面获取的comment都是初始review的comment，而系列的回复comment需要从数据库读"""
        commentList = []
        for comment in comments:
            bean = ReviewComment()
            bean.in_reply_to_id = comment.id
            commentList.append(bean)
        results = await AsyncSqlHelper.queryBeanData(commentList, mysql,
                                                     [[StringKeyUtils.STR_KEY_IN_REPLY_TO_ID]] * commentList.__len__())
        # print(results)
        """commentMap 用于 comment的补救。由于回复的comment与第一个comment指向相同，不用重复算"""
        commentMap = {}
        for index, result in enumerate(results):
            commentMap[comments[index].id] = BeanParserHelper.getBeansFromTuple(ReviewComment(),
                                                                                ReviewComment.getItemKeyList(),
                                                                                result)

        """遍历review之后的changes，判断是否有comment引起change的情况"""
        change_trigger_comments = []

        """新增判断是否在gap中，如果是，则没有判断的必要"""
        if is_in_gap:
            """缺失的review comment 弥补"""
            for comment in comments:
                change_trigger_review_comment = {
                    "pullrequest_node": pr_node_id,
                    "user_login": comment.user_login,
                    "comment_node": comment.node_id,
                    "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                    "change_trigger": StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_BETWEEN_REOPEN,
                    "filepath": comment.path
                }
                """如果是作者  改为-2"""
                if comment.user_login == pr_author:
                    change_trigger_review_comment['change_trigger'] = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR
                change_trigger_comments.append(change_trigger_review_comment)
                for c in commentMap[comment.id]:
                    change_trigger_review_comment = {
                        "pullrequest_node": pr_node_id,
                        "user_login": c.user_login,
                        "comment_node": c.node_id,
                        "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                        "change_trigger": StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_BETWEEN_REOPEN,
                        "filepath": c.path
                    }
                    """如果是作者  改为-2"""
                    if c.user_login == pr_author:
                        change_trigger_review_comment['change_trigger'] = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR
                    change_trigger_comments.append(change_trigger_review_comment)

            return change_trigger_comments

        """新增判断是否在正常pr流程中间，如果是，则没有判断的必要"""
        if changes is None or changes.__len__() == 0:
            """缺失的review comment 弥补"""
            for comment in comments:
                change_trigger_review_comment = {
                    "pullrequest_node": pr_node_id,
                    "user_login": comment.user_login,
                    "comment_node": comment.node_id,
                    "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                    "change_trigger": StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_OUT_PR,
                    "filepath": comment.path
                }
                """如果是作者  改为-2"""
                if comment.user_login == pr_author:
                    change_trigger_review_comment['change_trigger'] = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR
                change_trigger_comments.append(change_trigger_review_comment)
                for c in commentMap[comment.id]:
                    change_trigger_review_comment = {
                        "pullrequest_node": pr_node_id,
                        "user_login": c.user_login,
                        "comment_node": c.node_id,
                        "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                        "change_trigger": StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_OUT_PR,
                        "filepath": c.path
                    }
                    """如果是作者  改为-2"""
                    if c.user_login == pr_author:
                        change_trigger_review_comment['change_trigger'] = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR
                    change_trigger_comments.append(change_trigger_review_comment)

            return change_trigger_comments

        # """临时  对于有changetrigger 的 comment，无需计算"""
        # for comment in comments:
        #     if comment.change_trigger is not None:
        #         change_trigger_comments.append({
        #             "pullrequest_node": pr_node_id,
        #             "user_login": comment.user_login,
        #             "comment_node": comment.node_id,
        #             "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
        #             "change_trigger": comment.change_trigger,
        #             "filepath": comment.path
        #         })
        #         for c in commentMap[comment.id]:
        #             change_trigger_comments.append({
        #                 "pullrequest_node": pr_node_id,
        #                 "user_login": c.user_login,
        #                 "comment_node": c.node_id,
        #                 "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
        #                 "change_trigger": comment.change_trigger,
        #                 "filepath": c.path
        #             })
        #         comments.remove(comment)
        #         print("skip now comment len:", comments.__len__())
        #
        # if comments.__len__() == 0:
        #     return change_trigger_comments

        # """通过comment的 position、originalPosition信息补全line, originalLine 需要对应commit的file的patch"""

        isFileNeedFetched = False
        """遍历comment 如果没有LEFT则不获取"""
        for comment in comments:
            if comment.side == 'LEFT':
                isFileNeedFetched = True
                break

        oids = list(set([comment.original_commit_id for comment in comments]))
        """获取这些的changes files"""

        files = []
        if isFileNeedFetched:
            files = await AsyncApiHelper.getFilesFromStore(oids, mysql)
        # t21 = datetime.now()
        # print("get file cost:", t21-t11, " total:", t21 - t1)
        # """依次补全"""
        #
        # needFetch = False
        for comment in comments:
            """comment默认未触发change_trigger"""
            comment.change_trigger = -1
        #     # if comment.original_line is None:
        #     #     needFetch = True
        #     #     break
        #     if comment.original_line is not None and comment.side is not None:
        #         continue
        #
        #     for file in files:
        #         if file.commit_sha == comment.original_commit_id and file.filename == comment.path:
        #             """计算origin line 和 side"""
        #             original_line, side = TextCompareUtils.getStartLine(file.patch, comment.original_position)
        #
        #             """如果Patch有两个 子patch 组成，则网络获取"""
        #             try:
        #                 if TextCompareUtils.patchParser(file.patch).__len__() >= 2:
        #                     needFetch = True
        #             except Exception as e:
        #                 print("parser patch fail!")
        #                 print(e)
        #
        #             """
        #              注 ： 2020.07.09 在patch是多个patch组合的时候， 自己计算出来的original_line 可能会有1行的误差
        #                    具体原因不明  对比例子: https://github.com/gib94927855/Review/pull/3#pullrequestreview-445279262
        #                                           https://github.com/yarnpkg/yarn/pull/2723
        #             """
        #
        #             comment.side = side
        #             comment.original_line = original_line
        #
        #             """line 是改动后文本评论指向的行数， original line 是改动前的文本评论指向行数
        #                有 line 就别用 original line
        #             """
        #
        #             """如果计算之后还是为空 则从网络获取"""
        #             if comment.side is None or comment.original_line is None:
        #                 needFetch = True
        #
        # """"现阶段妥协  先看comment 有没有 original_line 字段， 没有的话comment 重新获取补全"""
        # if needFetch:
        #     statistic.lock.acquire()
        #     statistic.needFetchCommentForLineCount += 1
        #     statistic.lock.release()
        #     print("now needFetchCommentForLine Count:", statistic.needFetchCommentForLineCount, ' not need:',
        #           statistic.notNeedFetchCommentForLineCount)
        #
        #     async with aiohttp.ClientSession() as session:
        #         """数据库获取 pr"""
        #         tempPR = PullRequest()
        #         tempPR.node_id = pr_node_id
        #         pr_number = None
        #         result = await AsyncSqlHelper.queryBeanData([tempPR], mysql, [[StringKeyUtils.STR_KEY_NODE_ID]])
        #         if result[0].__len__() > 0:
        #             pr_number = result[0][0][PullRequest.getItemKeyList().index(StringKeyUtils.STR_KEY_NUMBER)]
        #         """v3 获取comments"""
        #         if pr_number is not None:
        #             """获取review comment信息"""
        #             api = AsyncApiHelper.getReviewCommentForPullRequestApi(pr_number)
        #             json = await AsyncApiHelper.fetchBeanData(session, api, isMediaType=True)
        #             reviewComments = await AsyncApiHelper.parserReviewComment(json)
        #             await AsyncSqlHelper.updateBeanDateList(reviewComments, mysql)
        #             for comment in comments:
        #                 for comment_t in reviewComments:
        #                     if comment.node_id == comment_t.node_id:
        #                         comment.side = comment_t.side
        #                         comment.original_line = comment_t.original_line
        # else:
        #     statistic.lock.acquire()
        #     statistic.notNeedFetchCommentForLineCount += 1
        #     statistic.lock.release()
        #     print("now needFetchCommentForLine Count:", statistic.needFetchCommentForLineCount, ' not need:',
        #           statistic.notNeedFetchCommentForLineCount)

        """对于entry对象  增加本地缓存"""
        treeEntryLocalList = []

        """storeBeanList 用于收集需要存储的bean 最后统一保存, updateBeanList 同理"""
        storeBeanList = []
        updateBeanList = []

        """comment 的blob提前获取，不要在大循环里面反复获取"""
        """获取tree_id"""
        commitTreeList = await AsyncApiHelper.getCommitsByCheckTreeOID(oids, mysql, pr_node_id,
                                                                       storeBeanList, updateBeanList)

        if (None, None) in commitTreeList:
            """异常直接返回"""
            print("commit Tree fetch failed for oids:", oids, '  pr:', pr_node_id, " count:",
                  statistic.commitNotFoundErrorCount)
            statistic.lock.acquire()
            statistic.commitNotFoundErrorCount += 1
            statistic.lock.release()
            for comment in comments:
                change_trigger_comments.append({
                    "pullrequest_node": pr_node_id,
                    "user_login": comment.user_login,
                    "comment_node": comment.node_id,
                    "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                    "change_trigger": StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_ERROR,
                    "filepath": comment.path
                })
                for c in commentMap[comment.id]:
                    change_trigger_comments.append({
                        "pullrequest_node": pr_node_id,
                        "user_login": c.user_login,
                        "comment_node": c.node_id,
                        "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                        "change_trigger": StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_ERROR,
                        "filepath": c.path
                    })

            return change_trigger_comments

        reviewCommentTreeOidMap = {}
        for t in commitTreeList:
            reviewCommentTreeOidMap[t[0]] = t[1]

        blobMap = {}
        for comment in comments:
            blobMap[comment.id] = await AsyncApiHelper.getBlob(reviewCommentTreeOidMap[comment.original_commit_id]
                                                               , comment.path, mysql, pr_node_id, storeBeanList,
                                                               treeEntryLocalList)

        """运行时候需要保证 reviewComment的orignal_line 和 side存在 
           见AsyncProjectAllDataFetcher.getNoOriginLineReviewComment"""

        """遍历comment，对于comment的side是 LEFT 的场景，需要把相对行数转换到 RIGHT 的行数版本
            LEFT 大概只有 3% 如果有误差应该可以接受
        """
        for comment in comments:
            if comment.side == 'LEFT':
                for file in files:
                    if file.commit_sha == comment.original_commit_id and file.filename == comment.path:
                        comment.temp_original_line = TextCompareUtils.ConvertLeftToRight(file.patch,
                                                                                         comment.original_position)
            else:
                comment.temp_original_line = comment.original_line

        t2 = datetime.now()
        print("update comment cost time:", t2 - t1, '  total:', t2 - t1)

        for change in changes:  # 对后面连续改动依次遍历
            reviewCommit = review.pull_request_review_commit
            changeCommit = None
            if change.typename == StringKeyUtils.STR_KEY_PULL_REQUEST_COMMIT:
                changeCommit = change.pull_request_commit
            elif change.typename == StringKeyUtils.STR_KEY_HEAD_REF_PUSHED_EVENT:
                changeCommit = change.headRefForcePushedEventAfterCommit

            if changeCommit is None or reviewCommit is None:
                continue
            try:
                """获取两个commit 对应的 tree_id"""
                commitTreeList = await AsyncApiHelper.getCommitsByCheckTreeOID([changeCommit], mysql,
                                                                               pr_node_id, storeBeanList,
                                                                               updateBeanList)
                print("commitTreeList", commitTreeList, " changecommit:", changeCommit, 'reviewCommit:', reviewCommit)
                changeCommitTreeOid = None
                for oid, tree_oid in commitTreeList:
                    if oid == changeCommit:
                        changeCommitTreeOid = tree_oid

                for comment in comments:

                    """加速"""
                    if comment.change_trigger == 0 or \
                            comment.change_trigger == StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR:
                        continue

                    t3 = datetime.now()

                    """依次遍历每一个 comment, 寻找 comment 对应的文件的blob
                       在两个commit版本中的文本
                    """
                    if comment.temp_original_line is None or comment.side is None:
                        comment.change_trigger = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_ERROR
                        continue

                    fileName = comment.path
                    reviewBlob = blobMap.get(comment.id)
                    changeBlob = await AsyncApiHelper.getBlob(changeCommitTreeOid, fileName, mysql, pr_node_id
                                                              , storeBeanList, treeEntryLocalList)

                    if reviewBlob == changeBlob:
                        comment.change_trigger = -1
                        continue

                    if reviewBlob is None or changeBlob is None:
                        print("--" * 50)
                        print("blob is None!")
                        print(fileName)
                        print(comment.getValueDict())
                        print([reviewCommit, changeCommit])
                        print("--" * 50)
                        if comment.change_trigger != StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR\
                                and comment.change_trigger < 0:
                            comment.change_trigger = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_FILE_MOVE
                        continue

                    print("review blob len:", reviewBlob.__len__(), ' changeblob len:', changeBlob.__len__())

                    t4 = datetime.now()
                    print("fetch blob cost time:", t4 - t3, '  total:', t4 - t1)

                    if not configPraser.getIsChangeTriggerByLine():
                        """对于不细致的ChangeTrigger版本  两个内容不相同即可"""
                        if reviewBlob != changeBlob:
                            comment.change_trigger = 1
                        else:
                            if comment.change_trigger == -1:
                                comment.change_trigger = -1
                    else:
                        """获取两个Blob的文本内容之后，比较差异"""
                        review_text_lines = reviewBlob.splitlines()
                        change_text_lines = changeBlob.splitlines()

                        diff = difflib.unified_diff(
                            review_text_lines,
                            change_text_lines,
                            lineterm='',
                        )

                        patch = '\n'.join(diff)
                        # print(patch)
                        """解析 patch"""
                        """patch 的前两行  
                           --- 
                           +++
                        去除"""
                        textChanges = TextCompareUtils.patchParser(patch[10:])
                        dis = 10000000
                        """依次遍历每个patch 找到每个patch 中距离 original_line 最进的改动距离"""
                        for textChange in textChanges:
                            start_left, _, start_right, _ = textChange[0]
                            status = textChange[1]
                            """curPos 选取 left， 因为对于变动，comment 的行数属于老版本"""
                            curPos = start_left - 1
                            for s in status:
                                if s != '+':
                                    curPos += 1
                                if s != ' ':
                                    dis = min(dis, abs(comment.temp_original_line - curPos))
                        if dis <= 10:
                            if comment.change_trigger < 0:
                                comment.change_trigger = dis
                            else:
                                comment.change_trigger = min(comment.change_trigger, dis)
                        else:
                            if comment.change_trigger == -1:
                                comment.change_trigger = -1

                        t5 = datetime.now()
                        print("compare comment cost time:", t5 - t4, '  total:', t5 - t1)
            except Exception as e:
                print(e)
                continue
        for comment in comments:
            change_trigger_review_comment = {
                "pullrequest_node": pr_node_id,
                "user_login": comment.user_login,
                "comment_node": comment.node_id,
                "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                "change_trigger": comment.change_trigger,
                "filepath": comment.path
            }
            """判断作者的情况"""
            if comment.user_login == pr_author:
                change_trigger_review_comment['change_trigger'] = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR
            change_trigger_comments.append(change_trigger_review_comment)
            for c in commentMap[comment.id]:
                change_trigger_review_comment = {
                    "pullrequest_node": pr_node_id,
                    "user_login": c.user_login,
                    "comment_node": c.node_id,
                    "comment_type": StringKeyUtils.STR_LABEL_REVIEW_COMMENT,
                    "change_trigger": comment.change_trigger,
                    "filepath": c.path
                }
                if c.user_login == pr_author:
                    change_trigger_review_comment['change_trigger'] = StringKeyUtils.STR_CHANGE_TRIGGER_REVIEW_COMMENT_AUTHOR
                change_trigger_comments.append(change_trigger_review_comment)
        statistic.lock.acquire()
        statistic.usefulChangeTrigger += [x for x in comments if x.change_trigger > 0].__len__()
        statistic.lock.release()

        updateBeanList.extend(comments)

        # 更新comments的change_trigger, line, original_line信息"""
        await AsyncSqlHelper.storeBeanDateList(storeBeanList, mysql)
        await AsyncSqlHelper.updateBeanDateList(updateBeanList, mysql)
        t6 = datetime.now()
        print("single pair all total:", t6 - t1)
        return change_trigger_comments

    @staticmethod
    async def getReviewCommentsByNodeFromStore(node_id, mysql):
        """从数据库中读取review id 到时候更新只要从数据库中增加就ok了"""

        review = Review()
        review.node_id = node_id

        reviews = await AsyncSqlHelper.queryBeanData([review], mysql, [[StringKeyUtils.STR_KEY_NODE_ID]])
        # print("reviews:", reviews)
        if reviews is not None and reviews[0] is not None and reviews[0].__len__() > 0:
            review_id = reviews[0][0][2]
            # print("review_id:", review_id)
            comment = ReviewComment()
            comment.pull_request_review_id = review_id

            result = await AsyncSqlHelper.queryBeanData([comment], mysql,
                                                        [[StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW_ID]])
            # print(result)
            if result is not None and result[0] is not None and result[0].__len__() > 0:
                comments = BeanParserHelper.getBeansFromTuple(ReviewComment(), ReviewComment.getItemKeyList(),
                                                              result[0])

                """获取comment 以及对应的sha 和nodeId 和行数,fileName"""
                for comment in comments:
                    pass
                    # print(comment.getValueDict())
                return comments

    @staticmethod
    async def getFilesFromStore(oids, mysql):
        """从数据库中读取多个oid的file changes"""

        print("query file oids:", oids)

        queryFiles = []
        for oid in oids:
            file = File()
            file.commit_sha = oid
            queryFiles.append(file)

        gitFiles = []

        if queryFiles is not None and queryFiles.__len__() > 0:
            results = await AsyncSqlHelper.queryBeanData(queryFiles, mysql,
                                                         [[StringKeyUtils.STR_KEY_COMMIT_SHA]] * queryFiles.__len__())
            print("files:", results)
            for result in results:
                if result is not None and result.__len__() > 0:
                    files = BeanParserHelper.getBeansFromTuple(File(), File.getItemKeyList(), result)
                    gitFiles.extend(files)

        return gitFiles

    @staticmethod
    async def getCommitsFromStore(oids, mysql):

        beans = []

        existList = []  # 存在列表
        relationList = []  # 查询得到的关系列表 在子列表出现代表了系统有存储

        """先从sha(oid)转化为commit对象"""
        for oid in oids:
            bean = CommitRelation()
            bean.child = oid
            beans.append(bean)

        results = await AsyncSqlHelper.queryBeanData(beans, mysql, [[StringKeyUtils.STR_KEY_CHILD]] * beans.__len__())
        print("result:", results)

        """从本地返回的结果做解析"""
        for relationTuple in results:
            if relationTuple is not None and relationTuple.__len__() > 0:
                existList.append(relationTuple[0][0])
                for relation in relationTuple:
                    r = CommitRelation()
                    r.child = relation[0]
                    r.parent = relation[1]
                    relationList.append(r)
        """去重处理"""
        existList = list(set(existList))
        relationList = list(set(relationList))
        return existList, relationList

    @staticmethod
    async def getCommitsFromApi(oids, mysql, session):

        beanList = []
        relationList = []  # 查询得到的关系列表

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
    async def getCommitsByCheckTreeOID(oids, mysql, pr_node_id, storeBeanList_all, updateBeanList_all):
        """获取 oids 列表的commit
           注： 2020.7.8 commit新增字段 tree_oid 因为commit点在数据库有 22W+
                一次性更新比较困难  做兼容
                先从本地数据库获取，如果有但是没有tree_oid 则也重新获取
                
                本地没有或者数据库没有tree_oid字段的commit也重新获取
                没有的点是store 而已经有的点是 update
        """

        """先从本地读取"""
        beans = []
        needUpdateList = []
        needFetchList = oids.copy()
        resultCommitList = []

        """update 与 fetch 一个 update,一个store 使用不同sql"""
        updateBeanList = []
        fetchBeanList = []
        for oid in oids:
            bean = Commit()
            bean.sha = oid
            beans.append(bean)

        results = await AsyncSqlHelper.queryBeanData(beans, mysql, [[StringKeyUtils.STR_KEY_SHA]] * beans.__len__())
        # print("result:", results)
        treeOidPos = Commit.getItemKeyList().index(StringKeyUtils.STR_KEY_TREE_OID)
        shaPos = Commit.getItemKeyList().index(StringKeyUtils.STR_KEY_SHA)

        for pos, result in enumerate(results):
            if result.__len__() > 0:
                sha = result[0][shaPos]
                treeOid = result[0][treeOidPos]
                print("query commit for tree:", pos, " sha:", sha, " tree:", treeOid, ' all:', oids, ' pr:', pr_node_id)

                """根据结果更新列表"""
                needFetchList.remove(sha)
                if treeOid is None:
                    needUpdateList.append(sha)
                else:
                    resultCommitList.append((sha, treeOid))

        print("need update:", needUpdateList)
        print("need fetched:", needFetchList)

        async with aiohttp.ClientSession() as session:
            """从api 获取 commit 信息，用于更新"""
            for oid in needUpdateList:
                api = AsyncApiHelper.getCommitApi(oid)
                json = await AsyncApiHelper.fetchBeanData(session, api)
                print("fetch data v3 for commit tree oid for update:", oid, ' all:', oids, ' pr:', pr_node_id)
                commit = await AsyncApiHelper.parserCommit(json)
                commit.has_file_fetched = True
                resultCommitList.append((commit.sha, commit.tree_oid))

                if commit.parents is not None:
                    updateBeanList.extend(commit.parents)
                if commit.files is not None:
                    updateBeanList.extend(commit.files)

                updateBeanList.append(commit)
            # await AsyncSqlHelper.updateBeanDateList(updateBeanList, mysql)
            updateBeanList_all.extend(updateBeanList)

            for oid in needFetchList:
                api = AsyncApiHelper.getCommitApi(oid)
                json = await AsyncApiHelper.fetchBeanData(session, api)
                print("fetch data v3 for commit tree oid for store:", oid, ' all:', oids, ' pr:', pr_node_id)
                commit = await AsyncApiHelper.parserCommit(json)
                commit.has_file_fetched = True
                resultCommitList.append((commit.sha, commit.tree_oid))

                if commit.parents is not None:
                    fetchBeanList.extend(commit.parents)
                if commit.files is not None:
                    fetchBeanList.extend(commit.files)

                fetchBeanList.append(commit)
            # await AsyncSqlHelper.storeBeanDateList(fetchBeanList, mysql)
            storeBeanList_all.extend(fetchBeanList)

        return resultCommitList

    @staticmethod
    async def getBlob(tree_oid, path, mysql, pr_node_id, beanList, treeEntryLocalList):
        """获取 给定 Tree对应的 path的blob对象
           路径按照 循环获取，不走递归
        """
        async with aiohttp.ClientSession() as session:
            """分割路径"""
            t1 = datetime.now()
            paths = path.split('/')
            print(paths, ' pr_node_id:', pr_node_id, ' tree:', tree_oid)
            blobText = None

            """先获取tree的根节点"""
            curOid = tree_oid
            curPos = 0
            isBlobFind = False  # 确认blob是否获取
            isEntryBroken = False  # 确认TreeEntry是否中断

            while curPos < paths.__len__():
                treeEntryList = []
                isEntryFind = False

                """先尝试本地缓存读"""
                for entry in treeEntryLocalList:
                    if entry.child_path == paths[curPos] and entry.parent_oid == curOid:
                        curOid = entry.child_oid
                        childType = entry.child_type
                        curPos += 1
                        isEntryFind = True
                        if curPos == paths.__len__() and childType == StringKeyUtils.STR_KEY_BLOB:
                            isBlobFind = True
                        break

                if not isEntryFind:
                    """先尝试数据库中读取"""
                    tempEntry = TreeEntry()
                    tempEntry.repository = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo
                    tempEntry.parent_oid = curOid
                    results = await AsyncSqlHelper.queryBeanData([tempEntry], mysql, [[StringKeyUtils.STR_KEY_REPOSITORY,
                                                                                       StringKeyUtils.STR_KEY_PARENT_OID]])

                    """新增本地缓存"""
                    if results[0] is not None:
                        entrys = BeanParserHelper.getBeansFromTuple(TreeEntry(), TreeEntry.getItemKeyList(), results[0])
                        treeEntryLocalList.extend(entrys)

                    """查询改为所有Entry 查询"""
                    isFind = False
                    for result in results[0]:
                        if result[TreeEntry.getItemKeyList().index(StringKeyUtils.STR_KEY_CHILD_PATH)] == paths[curPos]:
                            curOid = result[TreeEntry.getItemKeyList().index(StringKeyUtils.STR_KEY_CHILD_OID)]
                            childType = result[TreeEntry.getItemKeyList().index(StringKeyUtils.STR_KEY_CHILD_TYPE)]
                            curPos += 1
                            isFind = True
                            isEntryFind = True
                            if curPos == paths.__len__() and childType == StringKeyUtils.STR_KEY_BLOB:
                                isBlobFind = True
                            break

                    if results[0].__len__() > 0 and not isFind:
                        print("not find in database for fetched entrys!", tree_oid, '  path:', path)
                        isEntryBroken = True
                        break

                if isEntryBroken:
                    isBlobFind = False
                    break

                if not isEntryFind:
                    """从v4接口获得tree 关系"""
                    args = {"expression": "", "owner": AsyncApiHelper.owner,
                            "name": AsyncApiHelper.repo, "oid": curOid}
                    api = AsyncApiHelper.getGraphQLApi()
                    query = GraphqlHelper.getTreeByOid()
                    resultJson = await AsyncApiHelper.postGraphqlData(session, api, query, args)
                    print("fetch from v4 relation:", curOid, 'treeOid:', tree_oid, ' pr:', pr_node_id)
                    print("relation result:", resultJson)

                    if isinstance(resultJson, dict):
                        rawData = resultJson.get(StringKeyUtils.STR_KEY_DATA, None)
                        if isinstance(rawData, dict):
                            repoData = rawData.get(StringKeyUtils.STR_KEY_REPOSITORY, None)
                            if isinstance(repoData, dict):
                                objectData = repoData.get(StringKeyUtils.STR_KEY_OBJECT, None)
                                treeEntryList = TreeEntry.parserV4.parser(objectData)
                                beanList.extend(treeEntryList)
                                treeEntryLocalList.extend(treeEntryList)

                    isFind = False
                    for entry in treeEntryList:
                        if entry.child_path == paths[curPos]:
                            curPos += 1
                            curOid = entry.child_oid
                            isFind = True

                            if curPos == paths.__len__() and entry.child_type == StringKeyUtils.STR_KEY_BLOB:
                                isBlobFind = True
                            break

                    if not isFind:
                        """tree 被删除"""
                        isBlobFind = False
                        isEntryBroken = True
                        break

            if isBlobFind:
                """curOid 就是目标的blob对象"""
                print('blob curoid:', curOid)

                """先从数据库获取blob"""
                tempBlob = Blob()
                tempBlob.repository = AsyncApiHelper.owner + '/' + AsyncApiHelper.repo
                tempBlob.oid = curOid
                result = await AsyncSqlHelper.queryBeanData([tempBlob], mysql, [[StringKeyUtils.STR_KEY_REPOSITORY,
                                                                                 StringKeyUtils.STR_KEY_OID]])
                if result[0].__len__() > 0:
                    blobText = result[0][0][Blob.getItemKeyList().index(StringKeyUtils.STR_KEY_TEXT)]

                if blobText is None:
                    """从api获取Blob对象"""
                    args = {"expression": "", "owner": AsyncApiHelper.owner,
                            "name": AsyncApiHelper.repo, "oid": curOid}
                    api = AsyncApiHelper.getGraphQLApi()
                    query = GraphqlHelper.getTreeByOid()
                    resultJson = await AsyncApiHelper.postGraphqlData(session, api, query, args)
                    print(resultJson)
                    print("fetch from v4 blob:", curOid, ' treeOid:', tree_oid, ' pr:', pr_node_id)

                    if isinstance(resultJson, dict):
                        rawData = resultJson.get(StringKeyUtils.STR_KEY_DATA, None)
                        if isinstance(rawData, dict):
                            repoData = rawData.get(StringKeyUtils.STR_KEY_REPOSITORY, None)
                            if isinstance(repoData, dict):
                                objectData = repoData.get(StringKeyUtils.STR_KEY_OBJECT, None)
                                blob = Blob.parserV4.parser(objectData)
                                blobText = blob.text
                                beanList.append(blob)

            # await  AsyncSqlHelper.storeBeanDateList(beanList, mysql)

            print("blob cost time:", datetime.now() - t1)

            return blobText

    @staticmethod
    async def downloadUserFollowList(userLogin, semaphore, mysql, statistic):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []  # 用来收集需要存储的bean类
                    """先获取pull request信息"""
                    args = {"login": userLogin}
                    api = AsyncApiHelper.getGraphQLApi()
                    """第一次加载"""
                    query = GraphqlHelper.getFollowingListByLoginFirst()
                    resultJson = await AsyncApiHelper.postGraphqlData(session, api, query, args)
                    print(resultJson)

                    res = await AsyncApiHelper.parserUserFollowingList(resultJson)

                    if res is not None:
                        [followingList, followingCount, lastFollowingCursor, followerList, followerCount, lastFollowerCursor] = res
                        beanList.extend(followingList)
                        beanList.extend(followerList)

                    res = await AsyncApiHelper.parserUserWatchRepoList(resultJson)
                    if res is not None:
                        [watchList, watchCount, lastWatchCursor] = res
                        beanList.extend(watchList)

                    await AsyncSqlHelper.storeBeanDateList(beanList, mysql)
                    # 做了同步处理
                    statistic.lock.acquire()
                    statistic.usefulCommitNumber += 1
                    print(f" usefulCommitCount:{statistic.usefulCommitNumber}")
                    statistic.lock.release()
                except Exception as e:
                    print(e)

    @staticmethod
    async def downloadCommits(projectName, oid, semaphore, mysql, statistic):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []
                    owner, repo = projectName.split('/')
                    api = AsyncApiHelper.getCommitApiWithProjectName(owner, repo, oid)
                    json = await AsyncApiHelper.fetchBeanData(session, api)
                    print(json)
                    commit = await AsyncApiHelper.parserCommit(json)
                    """过v3的接口视为有GitFile"""
                    commit.has_file_fetched = True

                    if commit.parents is not None:
                        beanList.extend(commit.parents)
                    if commit.files is not None:
                        beanList.extend(commit.files)

                    # beanList.append(commit)
                    await AsyncSqlHelper.storeBeanDateList(beanList, mysql)
                    """commit 信息更新"""
                    await AsyncSqlHelper.updateBeanDateList([commit], mysql)

                    # 做了同步处理
                    statistic.lock.acquire()
                    statistic.usefulCommitNumber += 1
                    print(f" usefulCommitCount:{statistic.usefulCommitNumber}")
                    statistic.lock.release()
                except Exception as e:
                    print(e)

    @staticmethod
    async def downloadSingleReviewComment(projectName, comment_id, semaphore, mysql, statistic):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    beanList = []
                    owner, repo = projectName.split('/')
                    api = AsyncApiHelper.getSingleReviewCommentApiWithProjectName(owner, repo, comment_id)
                    json = await AsyncApiHelper.fetchBeanData(session, api)
                    print(json)
                    comment = await AsyncApiHelper.parserSingleReviewComment(json)

                    await AsyncSqlHelper.updateBeanDateList([comment], mysql)

                    # 做了同步处理
                    statistic.lock.acquire()
                    statistic.usefulReviewCommentNumber += 1
                    print(f" usefulReviewCommentCount:{statistic.usefulReviewCommentNumber}")
                    statistic.lock.release()
                except Exception as e:
                    print(e)
