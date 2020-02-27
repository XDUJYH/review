# coding=gbk
from concurrent.futures._base import ALL_COMPLETED, wait
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
import time

from retrying import retry

from source.config.configPraser import configPraser
from source.config.projectConfig import projectConfig
from source.data.service.ApiHelper import ApiHelper
from source.database.SqlExecuteHelper import SqlExecuteHelper
from source.database.SqlUtils import SqlUtils
from source.utils.statisticsHelper import statisticsHelper
from source.database.SqlServerInterceptor import SqlServerInterceptor


class ProjectAllDataFetcher:
    """���ڻ�ȡ��Ŀ������Ϣ����"""

    @staticmethod
    def getAllDataForProject(owner, repo):

        helper = ApiHelper(owner=owner, repo=repo)
        helper.setAuthorization(True)

        statistic = statisticsHelper()
        statistic.startTime = datetime.now()

        '''��ȡ��Ŀ����Ϣ�Լ���Ŀ��owner��Ϣ'''
        ProjectAllDataFetcher.getDataForRepository(helper)
        '''��ȡ��Ŀ��pull request��Ϣ'''
        ProjectAllDataFetcher.getPullRequestForRepositoryUseConcurrent(helper, limit=configPraser.getLimit(),
                                                          statistic=statistic, start=37600)

        statistic.endTime = datetime.now()

        print("useful pull request:", statistic.usefulRequestNumber,
              " useful review:", statistic.usefulReviewNumber,
              " useful review comment:", statistic.usefulReviewCommentNumber,
              " useful issue comment:", statistic.usefulIssueCommentNumber,
              " useful commit:", statistic.usefulCommitNumber,
              " cost time:", (statistic.endTime - statistic.startTime).seconds)

    @staticmethod
    def getDataForRepository(helper):

        exceptionTime = 0
        project = None

        while exceptionTime < configPraser.getRetryTime():
            try:
                project = helper.getInformationForProject()
                break
            except Exception as e:
                if exceptionTime < 5:
                    time.sleep(5)
                else:
                    time.sleep(20)
                exceptionTime += 1
                print(e)

        if exceptionTime == configPraser.getRetryTime():
            raise Exception("error out the limit!")

        if project is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_REPOS
                                                   , project.getItemKeyList()
                                                   , project.getValueDict()
                                                   , project.getIdentifyKeys())
        # �洢��Ŀ��owner��Ϣ
        if project.owner is not None and project.owner.login is not None:
            ProjectAllDataFetcher.saveUserInformationToDB(helper, project.owner)
            # user = helper.getInformationForUser(project.owner.login)
            # #             user = SqlServerInterceptor.convertFromBeanbaseToOutput(user)
            #
            # print(user.getValueDict())
            #
            # SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
            #                                        , user.getItemKeyList()
            #                                        , user.getValueDict()
            #                                        , user.getIdentifyKeys())

    @staticmethod
    def getPullRequestForRepository(helper, statistic, limit=-1, start=-1):

        if start == -1:
            # ��ȡ��Ŀpull request������
            # requestNumber = helper.getTotalPullRequestNumberForProject()
            requestNumber = helper.getMaxSolvedPullRequestNumberForProject()

            print("total pull request number:", requestNumber)

            resNumber = requestNumber
        else:
            resNumber = start
        rr = 0

        # usefulRequestNumber = 0
        # commentNumber = 0
        # usefulReviewNumber = 0  # review����ȡ����
        # usefulReviewCommentNumber = 0  # review comment����ȡ����
        # usefulIssueCommentNumber = 0  # issue comment ����ȡ����
        # usefulCommitNumber = 0  # commit����ȡ����
        # usefulCommitCommentNumber = 0  # commit comment����ȡ����

        while resNumber > 0:
            print("pull request:", resNumber, " now:", rr)
            ProjectAllDataFetcher.getSinglePullRequestWithExceptionCatch(helper, statistic, resNumber)
            resNumber = resNumber - 1
            rr = rr + 1
            if 0 < limit < rr:
                break

    @staticmethod
    def getPullRequestForRepositoryUseConcurrent(helper, statistic, limit=-1, start=-1):
        if start == -1:
            # ��ȡ��Ŀpull request������
            # requestNumber = helper.getTotalPullRequestNumberForProject()
            requestNumber = helper.getMaxSolvedPullRequestNumberForProject()

            print("total pull request number:", requestNumber)

            resNumber = requestNumber
        else:
            resNumber = start

        executor = ThreadPoolExecutor(max_workers=20)
        future_tasks = [executor.submit(ProjectAllDataFetcher.getSinglePullRequestWithExceptionCatch,
                                        helper, statistic,
                                        pull_number) for pull_number in range(resNumber, max(0, resNumber - limit), -1)]
        wait(future_tasks, return_when=ALL_COMPLETED)

    @staticmethod
    def getSinglePullRequestWithExceptionCatch(helper, statistic, pull_number):
        # ProjectAllDataFetcher.getSinglePullRequest(helper, statistic, pull_number)
        print('pull_number:', pull_number)
        exceptionTime = 0
        while exceptionTime < configPraser.getRetryTime():
            try:
                ProjectAllDataFetcher.getSinglePullRequest(helper, statistic, pull_number)
                break
            except Exception as e:
                time.sleep(20)
                exceptionTime += 1
                print(e)

        if exceptionTime == configPraser.getRetryTime():
            raise Exception("error out the limit!")

    @staticmethod
    def getSinglePullRequest(helper, statistic, pull_number):  # ��ȡĳ�����pull request����Ϣ
        pullRequest = helper.getInformationForPullRequest(pull_number)
        if pullRequest is not None:  # pull request���ھʹ���
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_PULL_REQUEST
                                                   , pullRequest.getItemKeyList()
                                                   , pullRequest.getValueDict()
                                                   , pullRequest.getIdentifyKeys())
            head = pullRequest.head
            if head is not None:
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_BRANCH
                                                       , head.getItemKeyList()
                                                       , head.getValueDict()
                                                       , head.getIdentifyKeys())

            base = pullRequest.base
            if base is not None:
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_BRANCH
                                                       , base.getItemKeyList()
                                                       , base.getValueDict()
                                                       , base.getIdentifyKeys())
            # statistic.usefulRequestNumber += 1

            usefulReviewNumber = 0
            ''' ��ȡ pull request��Ӧ��review��Ϣ'''
            reviews = helper.getInformationForReviewWithPullRequest(pullRequest.number)
            for review in reviews:
                if review is not None:
                    ProjectAllDataFetcher.saveReviewInformationToDB(helper, review)
                    # statistic.usefulReviewNumber += 1
                    usefulReviewNumber += 1

            usefulReviewCommentNumber = 0
            '''��ȡ pull request��Ӧ��review comment��Ϣ'''
            reviewComments = helper.getInformationForReviewCommentWithPullRequest(pullRequest.number)
            for comment in reviewComments:
                if comment is not None:
                    ProjectAllDataFetcher.saveReviewCommentInformationToDB(helper, comment)
                    # statistic.usefulReviewCommentNumber += 1
                    usefulReviewCommentNumber += 1

            usefulIssueCommentNumber = 0
            '''��ȡ pull request��Ӧ��issue comment��Ϣ'''
            issueComments = helper.getInformationForIssueCommentWithIssue(pullRequest.number)
            for comment in issueComments:
                if comment is not None:
                    ProjectAllDataFetcher.saveIssueCommentInformationToDB(helper, comment)
                    # statistic.usefulIssueCommentNumber += 1
                    usefulIssueCommentNumber += 1

            usefulCommitNumber = 0
            usefulCommitCommentNumber = 0
            '''��ȡ pull request��Ӧ��commit��Ϣ'''
            commits, relations = helper.getInformationForCommitWithPullRequest(pullRequest.number)
            for commit in commits:
                if commit is not None:
                    commit = helper.getInformationCommit(commit.sha)  # ��status��file��Ϣ�Ĳ���
                    ProjectAllDataFetcher.saveCommitInformationToDB(helper, commit)
                    # statistic.usefulCommitNumber += 1
                    usefulCommitNumber += 1

                    '''��ȡ commit��Ӧ��commit comment'''
                    """������commit comment��Ӧ��ͨ��������Ŀ���е�commit
                       ��Ѱ�ҵ�  ����������Ҫͨ��pull requestΪ������ȡ��Ϣ  ����ͨ����
                       ���ߵ��������ж��Ƿ���Ҫ  �����Ҫ����������һ���Ĵ���

                       �ٸ�����  rails��Ŀcommit 2��+ ����ʵ�����˷���Դ"""

                    commit_comments = helper.getInformationForCommitCommentsWithCommit(commit.sha)
                    if commit_comments is not None:
                        for commit_comment in commit_comments:
                            ProjectAllDataFetcher.saveCommitCommentInformationToDB(helper, commit_comment)
                            # statistic.usefulCommitCommentNumber += 1
                            usefulCommitCommentNumber += 1

            '''�洢 pull request��commit�Ĺ�ϵ'''
            for relation in relations:
                if relation is not None:
                    ProjectAllDataFetcher.saveCommitPRRelationInformationToDB(helper, relation)

            # ����ͬ������
            statistic.lock.acquire()
            statistic.usefulRequestNumber += 1
            statistic.usefulReviewNumber += usefulReviewNumber
            statistic.usefulReviewCommentNumber += usefulReviewCommentNumber
            statistic.usefulIssueCommentNumber += usefulIssueCommentNumber
            statistic.usefulCommitNumber += usefulCommitNumber
            statistic.usefulCommitCommentNumber = usefulCommitCommentNumber
            print("useful pull request:", statistic.usefulRequestNumber,
                  " useful review:", statistic.usefulReviewNumber,
                  " useful review comment:", statistic.usefulReviewCommentNumber,
                  " useful issue comment:", statistic.usefulIssueCommentNumber,
                  " useful commit:", statistic.usefulCommitNumber)
            statistic.lock.release()

    @staticmethod
    def saveReviewInformationToDB(helper, review):  # review��Ϣ¼�����ݿ�
        if review is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_REVIEW
                                                   , review.getItemKeyList()
                                                   , review.getValueDict()
                                                   , review.getIdentifyKeys())

            # if review.user is not None:
            #     user = helper.getInformationForUser(review.user.login)  # ��ȡ���Ƶ��û���Ϣ
            #     SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
            #                                            , user.getItemKeyList()
            #                                            , user.getValueDict()
            #                                            , user.getIdentifyKeys())
            ProjectAllDataFetcher.saveUserInformationToDB(helper, review.user)

    @staticmethod
    def saveReviewCommentInformationToDB(helper, reviewComment):  # review comment��Ϣ¼�����ݿ�
        if reviewComment is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_REVIEW_COMMENT
                                                   , reviewComment.getItemKeyList()
                                                   , reviewComment.getValueDict()
                                                   , reviewComment.getIdentifyKeys())

            # if reviewComment.user is not None:
            #     user = helper.getInformationForUser(reviewComment.user.login)  # ��ȡ���Ƶ��û���Ϣ
            #     SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
            #                                            , user.getItemKeyList()
            #                                            , user.getValueDict()
            #                                            , user.getIdentifyKeys())
            ProjectAllDataFetcher.saveUserInformationToDB(helper, reviewComment.user)

    @staticmethod
    def saveIssueCommentInformationToDB(helper, issueComment):  # issue comment��Ϣ¼�����ݿ�
        if issueComment is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_ISSUE_COMMENT
                                                   , issueComment.getItemKeyList()
                                                   , issueComment.getValueDict()
                                                   , issueComment.getIdentifyKeys())

            # if issueComment.user is not None:
            #     user = helper.getInformationForUser(issueComment.user.login)  # ��ȡ���Ƶ��û���Ϣ
            #     SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
            #                                            , user.getItemKeyList()
            #                                            , user.getValueDict()
            #                                            , user.getIdentifyKeys())
            ProjectAllDataFetcher.saveUserInformationToDB(helper, issueComment.user)

    @staticmethod
    def saveCommitInformationToDB(helper, commit):  # commit��Ϣ¼�����ݿ�
        if commit is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_COMMIT
                                                   , commit.getItemKeyList()
                                                   , commit.getValueDict()
                                                   , commit.getIdentifyKeys())

            # if commit.author is not None:
            #     user = helper.getInformationForUser(commit.author.login)  # ����������Ϣ
            #     SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
            #                                            , user.getItemKeyList()
            #                                            , user.getValueDict()
            #                                            , user.getIdentifyKeys())
            ProjectAllDataFetcher.saveUserInformationToDB(helper, commit.author)

            # if commit.committer is not None:
            #     user = helper.getInformationForUser(commit.committer.login)  # �����ύ����Ϣ
            #     SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
            #                                            , user.getItemKeyList()
            #                                            , user.getValueDict()
            #                                            , user.getIdentifyKeys())
            ProjectAllDataFetcher.saveUserInformationToDB(helper, commit.committer)

            if commit.files is not None:
                for file in commit.files:
                    SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_FILE
                                                           , file.getItemKeyList()
                                                           , file.getValueDict()
                                                           , file.getIdentifyKeys())
            if commit.parents is not None:
                for parent in commit.parents:
                    SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_COMMIT_RELATION
                                                           , parent.getItemKeyList()
                                                           , parent.getValueDict()
                                                           , parent.getIdentifyKeys())

    @staticmethod
    def saveCommitPRRelationInformationToDB(helper, relation):  # commit��Ϣ¼�����ݿ�
        if relation is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_COMMIT_PR_RELATION
                                                   , relation.getItemKeyList()
                                                   , relation.getValueDict()
                                                   , relation.getIdentifyKeys())

    @staticmethod
    def saveCommitCommentInformationToDB(helper, comment):  # commit��Ϣ¼�����ݿ�
        if comment is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_COMMIT_COMMENT
                                                   , comment.getItemKeyList()
                                                   , comment.getValueDict()
                                                   , comment.getIdentifyKeys())

            # if comment.user is not None:
            #     user = helper.getInformationForUser(comment.user.login)
            #     SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
            #                                            , user.getItemKeyList()
            #                                            , user.getValueDict()
            #                                            , user.getIdentifyKeys())
            ProjectAllDataFetcher.saveUserInformationToDB(helper, comment.user)

    @staticmethod
    def saveUserInformationToDB(helper, user):  # user��Ϣ¼�����ݿ�  �Ȳ�ѯ���ݿ��٣������Ϣ������������
        if user is not None and user.login is not None:
            res = SqlExecuteHelper.queryValuesFromTable(SqlUtils.STR_TABLE_NAME_USER,
                                                        user.getIdentifyKeys(), user.getValueDict())
            if res is None or res.__len__() == 0:
                if configPraser.getPrintMode():
                    print('���û�  ��git�л�ȡ��Ϣ')
                user = helper.getInformationForUser(user.login)
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                       , user.getItemKeyList()
                                                       , user.getValueDict()
                                                       , user.getIdentifyKeys())
            else:
                if configPraser.getPrintMode():
                    print(type(configPraser.getPrintMode()))
                    print('���û�  ���ػ�ȡ')


if __name__ == '__main__':
    ProjectAllDataFetcher.getAllDataForProject(configPraser.getOwner(), configPraser.getRepo())
    # ProjectAllDataFetcher.getAllDataForProject('ctripcorp', 'apollo')
    # ProjectAllDataFetcher.getAllDataForProject('kytrinyx', 'rails')
    # print(configPraser.getLimit())
