# coding=gbk
from source.data.service.ApiHelper import ApiHelper
from source.database.SqlExecuteHelper import SqlExecuteHelper
from source.database.SqlUtils import SqlUtils
from source.database.SqlServerInterceptor import SqlServerInterceptor


class ProjectAllDataFetcher:
    """���ڻ�ȡ��Ŀ������Ϣ����"""

    @staticmethod
    def getAllDataForProject(owner, repo):

        helper = ApiHelper(owner=owner, repo=repo)
        helper.setAuthorization(True)

        '''��ȡ��Ŀ����Ϣ�Լ���Ŀ��owner��Ϣ'''
        # ProjectAllDataFetcher.getDataForRepository(helper)
        '''��ȡ��Ŀ��pull request��Ϣ'''
        ProjectAllDataFetcher.getPullRequestForRepository(helper, 5)

    @staticmethod
    def getDataForRepository(helper):

        project = helper.getInformationForProject()
        print(project)
        if project is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_REPOS
                                                   , project.getItemKeyList()
                                                   , project.getValueDict()
                                                   , project.getIdentifyKeys())
        # �洢��Ŀ��owner��Ϣ
        if project.owner is not None and project.owner.login is not None:
            user = helper.getInformationForUser(project.owner.login)
            #             user = SqlServerInterceptor.convertFromBeanbaseToOutput(user)

            print(user.getValueDict())

            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                   , user.getItemKeyList()
                                                   , user.getValueDict()
                                                   , user.getIdentifyKeys())

    @staticmethod
    def getPullRequestForRepository(helper, limit=-1):

        # ��ȡ��Ŀpull request������
        # requestNumber = helper.getTotalPullRequestNumberForProject()
        requestNumber = helper.getMaxSolvedPullRequestNumberForProject()

        print("total pull request number:", requestNumber)

        resNumber = requestNumber
        rr = 0

        usefulRequestNumber = 0
        commentNumber = 0
        usefulReviewNumber = 0  # review����ȡ����
        usefulReviewCommentNumber = 0  # review comment����ȡ����
        usefulIssueCommentNumber = 0  # issue comment ����ȡ����
        usefulCommitNumber = 0  # commit����ȡ����

        while resNumber > 0:
            print("pull request:", resNumber, " now:", rr)
            pullRequest = helper.getInformationForPullRequest(resNumber)
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
                usefulRequestNumber += 1

                # ''' ��ȡ pull request��Ӧ��review��Ϣ'''
                # reviews = helper.getInformationForReviewWithPullRequest(pullRequest.number)
                # for review in reviews:
                #     if review is not None:
                #         ProjectAllDataFetcher.saveReviewInformationToDB(helper, review)
                #         usefulReviewNumber += 1
                #
                # '''��ȡ pull request��Ӧ��review comment��Ϣ'''
                # reviewComments = helper.getInformationForReviewCommentWithPullRequest(pullRequest.number)
                # for comment in reviewComments:
                #     if comment is not None:
                #         ProjectAllDataFetcher.saveReviewCommentInformationToDB(helper, comment)
                #         usefulReviewCommentNumber += 1

                # '''��ȡ pull request��Ӧ��issue comment��Ϣ'''
                # issueComments = helper.getInformationForIssueCommentWithIssue(pullRequest.number)
                # for comment in issueComments:
                #     if comment is not None:
                #         ProjectAllDataFetcher.saveIssueCommentInformationToDB(helper, comment)
                #         usefulIssueCommentNumber += 1

                '''��ȡ pull request��Ӧ��commit��Ϣ'''
                commits, relations = helper.getInformationForCommitWithPullRequest(pullRequest.number)
                for commit in commits:
                    if commit is not None:
                        commit = helper.getInformationCommit(commit.sha)  # ��status��file��Ϣ�Ĳ���
                        ProjectAllDataFetcher.saveCommitInformationToDB(helper, commit)
                        usefulCommitNumber += 1

                '''�洢 pull request��commit�Ĺ�ϵ'''
                for relation in relations:
                    if relation is not None:
                        ProjectAllDataFetcher.saveCommitPRRelationInformationToDB(helper, relation)

            resNumber = resNumber - 1
            rr = rr + 1
            if 0 < limit < rr:
                break

        print("useful pull request:", usefulRequestNumber,
              " useful review:", usefulReviewNumber,
              " useful review comment:", usefulReviewCommentNumber,
              " useful issue comment:", usefulIssueCommentNumber,
              " useful commit:", usefulCommitNumber)

    @staticmethod
    def saveReviewInformationToDB(helper, review):  # review��Ϣ¼�����ݿ�
        if review is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_REVIEW
                                                   , review.getItemKeyList()
                                                   , review.getValueDict()
                                                   , review.getIdentifyKeys())

            if review.user is not None:
                user = helper.getInformationForUser(review.user.login)  # ��ȡ���Ƶ��û���Ϣ
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                       , user.getItemKeyList()
                                                       , user.getValueDict()
                                                       , user.getIdentifyKeys())

    @staticmethod
    def saveReviewCommentInformationToDB(helper, reviewComment):  # review comment��Ϣ¼�����ݿ�
        if reviewComment is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_REVIEW_COMMENT
                                                   , reviewComment.getItemKeyList()
                                                   , reviewComment.getValueDict()
                                                   , reviewComment.getIdentifyKeys())

            if reviewComment.user is not None:
                user = helper.getInformationForUser(reviewComment.user.login)  # ��ȡ���Ƶ��û���Ϣ
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                       , user.getItemKeyList()
                                                       , user.getValueDict()
                                                       , user.getIdentifyKeys())

    @staticmethod
    def saveIssueCommentInformationToDB(helper, issueComment):  # issue comment��Ϣ¼�����ݿ�
        if issueComment is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_ISSUE_COMMENT
                                                   , issueComment.getItemKeyList()
                                                   , issueComment.getValueDict()
                                                   , issueComment.getIdentifyKeys())

            if issueComment.user is not None:
                user = helper.getInformationForUser(issueComment.user.login)  # ��ȡ���Ƶ��û���Ϣ
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                       , user.getItemKeyList()
                                                       , user.getValueDict()
                                                       , user.getIdentifyKeys())

    @staticmethod
    def saveCommitInformationToDB(helper, commit):  # commit��Ϣ¼�����ݿ�
        if commit is not None:
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_COMMIT
                                                   , commit.getItemKeyList()
                                                   , commit.getValueDict()
                                                   , commit.getIdentifyKeys())

            if commit.author is not None:
                user = helper.getInformationForUser(commit.author.login)  # ����������Ϣ
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                       , user.getItemKeyList()
                                                       , user.getValueDict()
                                                       , user.getIdentifyKeys())

            if commit.committer is not None:
                user = helper.getInformationForUser(commit.committer.login)  # �����ύ����Ϣ
                SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                       , user.getItemKeyList()
                                                       , user.getValueDict()
                                                       , user.getIdentifyKeys())
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


if __name__ == '__main__':
    ProjectAllDataFetcher.getAllDataForProject('rails', 'rails')
    # ProjectAllDataFetcher.getAllDataForProject('ctripcorp', 'apollo')
    # ProjectAllDataFetcher.getAllDataForProject('kytrinyx', 'rails')
