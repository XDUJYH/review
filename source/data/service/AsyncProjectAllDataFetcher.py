# coding=gbk
import asyncio
import json
import os
import time
from datetime import datetime
import random
import numpy as np

from pandas import DataFrame

from source.config.configPraser import configPraser
from source.config.projectConfig import projectConfig
from source.data.bean.PRTimeLineRelation import PRTimeLineRelation
from source.data.service.ApiHelper import ApiHelper
from source.data.service.AsyncApiHelper import AsyncApiHelper
from source.data.service.AsyncSqlHelper import AsyncSqlHelper
from source.data.service.PRTimeLineUtils import PRTimeLineUtils
from source.database.AsyncSqlExecuteHelper import getMysqlObj
from source.database.SqlUtils import SqlUtils
from source.utils.Logger import Logger
from source.utils.StringKeyUtils import StringKeyUtils
from source.utils.pandas.pandasHelper import pandasHelper
from source.utils.statisticsHelper import statisticsHelper


class AsyncProjectAllDataFetcher:
    # ��ȡ��Ŀ��������Ϣ ������Ϣ�����첽��ȡ

    @staticmethod
    def getPullRequestNodes(repo_full_name):
        loop = asyncio.get_event_loop()
        coro = AsyncProjectAllDataFetcher.fetchPullRequestNodes(loop, repo_full_name)
        task = loop.create_task(coro)
        loop.run_until_complete(task)
        return task.result()

    @staticmethod
    async def fetchPullRequestNodes(loop, repo_full_name):
        mysql = await getMysqlObj(loop)
        print("mysql init success")

        sql = SqlUtils.STR_SQL_QUERY_PR_FOR_TIME_LINE
        results = await AsyncSqlHelper.query(mysql, sql, [repo_full_name])

        return results

    @staticmethod
    def getPullRequestTimeLine(owner, repo, nodes):
        # ��ȡ�����pull request��ʱ�����������Ϣ ���������comment��ƴ��
        AsyncApiHelper.setRepo(owner, repo)
        t1 = datetime.now()

        statistic = statisticsHelper()
        statistic.startTime = t1

        semaphore = asyncio.Semaphore(configPraser.getSemaphore())  # ���ٶ���������
        loop = asyncio.get_event_loop()
        coro = getMysqlObj(loop)
        task = loop.create_task(coro)
        loop.run_until_complete(task)
        mysql = task.result()

        # nodes = np.array(nodes).reshape(10, -1)
        nodesGroup = []
        if nodes.__len__() % 10 == 0:
            nodesGroup = np.array(nodes).reshape(10, -1)
        else:
            for index in range(0, nodes.__len__(), 10):
                if index + 10 < nodes.__len__():
                    nodesGroup.append(nodes[index:index + 10])
                else:
                    nodesGroup.append(nodes[index:nodes.__len__()])

        tasks = [
            asyncio.ensure_future(AsyncApiHelper.downloadRPTimeLine(nodegroup.tolist(), semaphore, mysql, statistic))
            for nodegroup in nodesGroup]  # ����ͨ��nodes �����Ƕ�׽�ʡ��������
        tasks = asyncio.gather(*tasks)
        loop.run_until_complete(tasks)
        print('cost time:', datetime.now() - t1)
        return tasks.result()

    @staticmethod
    async def fetchPullRequestTimelineNodesFromDB(mysql, pr_nodes):
        sql = "select * from PRTimeLine " \
              "where pullrequest_node in %s"
        results = await AsyncSqlHelper.query(mysql, sql, [pr_nodes])
        return results

    @staticmethod
    def analyzePullRequestReview(pr, pr_timeline_items):
        statistic = statisticsHelper()
        statistic.startTime = datetime.now()

        loop = asyncio.get_event_loop()
        coro = AsyncProjectAllDataFetcher.analyzePRTimeline(pr, pr_timeline_items, loop, statistic)
        task = loop.create_task(coro)
        loop.run_until_complete(task)
        return task.result()

    @staticmethod
    async def analyzePRTimeline(pr_node_id, prOriginTimeLineItems, loop, statistic):
        """����prʱ���ߣ��ҳ�������change_trigger��comment
           ������Ԫ�飨reviewer, comment_node, comment_type, file, change_trigger��
           ����issue_comment�����践��file��Ĭ�ϻ�trigger��pr�������ļ�
        """

        """��ʼ�����ݿ�"""
        mysql = await getMysqlObj(loop)
        prTimeLineItems = []
        for item in prOriginTimeLineItems:
            origin = item.get(StringKeyUtils.STR_KEY_ORIGIN)
            prTimeLineRelation = PRTimeLineRelation.Parser.parser(origin)
            prTimeLineItems.append(prTimeLineRelation)
        """����review->changes���ҳ�������change_trigger��comment"""
        changeTriggerComments = []
        pairs = PRTimeLineUtils.splitTimeLine(prTimeLineItems)
        for pair in pairs:
            review = pair[0]
            changes = pair[1]
            """��issueComment�Һ����н����ŵ�change������Ϊ��issueComment������change_trigger"""
            if (review.typename == StringKeyUtils.STR_KEY_ISSUE_COMMENT) and changes:
                change_trigger_issue_comment = {
                    "pullrequest_node": pr_node_id,
                    "user_login": review.user_login,
                    "comment_id": review.timeline_item_node,
                    "comment_type": StringKeyUtils.STR_LABEL_ISSUE_COMMENT,
                    "change_trigger": 1,
                    "filepath": None
                }
                changeTriggerComments.append(tuple(change_trigger_issue_comment.values()))
                continue
            """��Ϊ��ͨreview���򿴺�������ŵ�commit�Ƿ��reviewCommit���ļ��غϵĸĶ�"""
            change_trigger_review_comments = await AsyncApiHelper.analyzeReviewChangeTrigger(pr_node_id, pair, mysql,
                                                                                             statistic)
            if change_trigger_review_comments is not None:
                changeTriggerComments.extend(review.user_login)
        return changeTriggerComments

    @staticmethod
    def getDataForRepository(owner, repo, limit=-1, start=-1):
        """ָ��Ŀ��owner/repo ��ȡstart��  start - limit��ŵ�pull-request���������Ϣ"""

        """�趨start �� limit"""
        if start == -1:
            # ��ȡ��Ŀpull request������ ����ʹ��ͬ��������ȡ
            requestNumber = ApiHelper(owner, repo).getMaxSolvedPullRequestNumberForProject()
            print("total pull request number:", requestNumber)

            startNumber = requestNumber
        else:
            startNumber = start

        if limit == -1:
            limit = startNumber

        """��ȡrepo��Ϣ"""
        AsyncApiHelper.setRepo(owner, repo)
        t1 = datetime.now()

        statistic = statisticsHelper()
        statistic.startTime = t1

        """�첽��Э��������ȡpull-request��Ϣ"""
        loop = asyncio.get_event_loop()
        task = [asyncio.ensure_future(AsyncProjectAllDataFetcher.preProcess(loop, limit, start, statistic))]
        tasks = asyncio.gather(*task)
        loop.run_until_complete(tasks)

        print("useful pull request:", statistic.usefulRequestNumber,
              " useful review:", statistic.usefulReviewNumber,
              " useful review comment:", statistic.usefulReviewCommentNumber,
              " useful issue comment:", statistic.usefulIssueCommentNumber,
              " useful commit:", statistic.usefulCommitNumber,
              " cost time:", datetime.now() - statistic.startTime)

    @staticmethod
    async def preProcess(loop, limit, start, statistic):
        """׼������"""
        semaphore = asyncio.Semaphore(configPraser.getSemaphore())  # ���ٶ���������
        """��ʼ�����ݿ�"""
        mysql = await getMysqlObj(loop)

        if configPraser.getPrintMode():
            print("mysql init success")

        """��Э��"""
        if configPraser.getApiVersion() == StringKeyUtils.API_VERSION_RESET:
            tasks = [asyncio.ensure_future(AsyncApiHelper.downloadInformation(pull_number, semaphore, mysql, statistic))
                     for pull_number in range(start, max(start - limit, 0), -1)]
        elif configPraser.getApiVersion() == StringKeyUtils.API_VERSION_GRAPHQL:
            tasks = [
                asyncio.ensure_future(AsyncApiHelper.downloadInformationByV4(pull_number, semaphore, mysql, statistic))
                for pull_number in range(start, max(start - limit, 0), -1)]
        await asyncio.wait(tasks)

    @staticmethod
    def getUnmatchedCommits():
        # ��ȡ ���ݿ���û�л�õ�commit�㣬һ�����2000��
        t1 = datetime.now()

        statistic = statisticsHelper()
        statistic.startTime = t1

        loop = asyncio.get_event_loop()
        task = [asyncio.ensure_future(AsyncProjectAllDataFetcher.preProcessUnmatchCommits(loop, statistic))]
        tasks = asyncio.gather(*task)
        loop.run_until_complete(tasks)

        print('cost time:', datetime.now() - t1)

    @staticmethod
    def getUnmatchedCommitFile():
        # ��ȡ ���ݿ���û�л��file�� commit�㣬һ�����2000��
        t1 = datetime.now()

        statistic = statisticsHelper()
        statistic.startTime = t1

        loop = asyncio.get_event_loop()
        task = [asyncio.ensure_future(AsyncProjectAllDataFetcher.preProcessUnmatchCommitFile(loop, statistic))]
        tasks = asyncio.gather(*task)
        loop.run_until_complete(tasks)

        print('cost time:', datetime.now() - t1)

    @staticmethod
    async def preProcessUnmatchCommits(loop, statistic):

        semaphore = asyncio.Semaphore(configPraser.getSemaphore())  # ���ٶ���������
        mysql = await getMysqlObj(loop)

        if configPraser.getPrintMode():
            print("mysql init success")

        res = await AsyncSqlHelper.query(mysql, SqlUtils.STR_SQL_QUERY_UNMATCH_COMMITS, None)
        print(res)

        tasks = [asyncio.ensure_future(AsyncApiHelper.downloadCommits(item[0], item[1], semaphore, mysql, statistic))
                 for item in res]  # ����ͨ��nodes �����Ƕ�׽�ʡ��������
        await asyncio.wait(tasks)

    @staticmethod
    def getPRTimeLine(owner, repo):
        """1. ��ȡ�òֿ����е�pr_node"""
        repo_fullname = owner + "/" + repo
        pr_nodes = AsyncProjectAllDataFetcher.getPullRequestNodes(repo_fullname)
        pr_nodes = list(pr_nodes)
        pr_nodes = [node[0] for node in pr_nodes]
        # ��ʼλ��
        pos = 0
        # ÿ�λ�ȡ����������
        fetchLimit = 200
        size = pr_nodes.__len__()
        # """PRTimeLine��ͷ"""
        # PRTIMELINE_COLUMNS = ["pullrequest_node", "timelineitem_node",
        #                       "typename", "position", "origin"]
        """��ʼ���ļ�"""
        target_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_prtimeline.tsv'
        # target_content = DataFrame(columns=PRTIMELINE_COLUMNS)
        # pandasHelper.writeTSVFile(target_filename, target_content)
        Logger.logi("--------------begin--------------")
        """2. �ָ��ȡpr_timeline"""
        while pos < size:
            loop_begin_time = datetime.now()
            Logger.logi("start: {0}, end: {1}, all: {2}".format(pos, pos + fetchLimit, size))
            pr_sub_nodes = pr_nodes[pos:pos + fetchLimit]
            results = AsyncProjectAllDataFetcher.getPullRequestTimeLine(owner=configPraser.getOwner(),
                                                                        repo=configPraser.getRepo(), nodes=pr_sub_nodes)
            if results is None:
                Logger.loge("start: {0}, end: {1} meet error".format(pos, pos + fetchLimit))
                pos += fetchLimit
                continue
            target_content = DataFrame()
            for result in results:
                pr_timelines = result
                if pr_timelines is None:
                    continue
                Logger.logi("fetched, cost time: {1}".format(pr_timelines.__len__(), datetime.now() - loop_begin_time))
                for pr_timeline in pr_timelines:
                    target_content = target_content.append(pr_timeline.toTSVFormat(), ignore_index=True)
            pandasHelper.writeTSVFile(target_filename, target_content)
            pos += fetchLimit
            sleepSec = random.randint(10, 20)
            Logger.logi("sleep {0}s...".format(sleepSec))
            time.sleep(sleepSec)
        Logger.logi("--------------end---------------")

    @staticmethod
    def checkPRTimeLineResult():
        """���PRTimeline�����Ƿ�������ȡ"""
        """1. ��ȡ�òֿ����е�pr_node"""
        repo_fullname = configPraser.getOwner() + "/" + configPraser.getRepo()
        pr_nodes = AsyncProjectAllDataFetcher.getPullRequestNodes(repo_fullname)
        pr_nodes = list(pr_nodes)
        pr_nodes = [node[0] for node in pr_nodes]
        """2. ��ȡprtimeline�ļ����Ա�pr"""
        target_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_prtimeline.tsv'
        PRTIMELINE_COLUMNS = ["pullrequest_node", "timelineitem_node",
                              "typename", "position", "origin"]
        df = pandasHelper.readTSVFile(fileName=target_filename, header=0)
        # """3. prtimelineȥ��(�������ŵ������)"""
        # df = df.drop_duplicates(subset=['pullrequest_node', 'timelineitem_node'])
        """4. ��ȡ��Ҫfetch��PR"""
        fetched_prs = list(df['pullrequest_node'])
        need_fetch_prs = list(set(pr_nodes).difference(set(fetched_prs)))
        Logger.logi("there are {0} pr_timeline need to fetch".format(need_fetch_prs.__len__()))
        """3. ��ʼ��ȡ"""
        results = AsyncProjectAllDataFetcher.getPullRequestTimeLine(owner=configPraser.getOwner(),
                                                                    repo=configPraser.getRepo(), nodes=need_fetch_prs)
        Logger.logi("successfully fetched! ")
        target_content = DataFrame()
        for result in results:
            pr_timelines = result
            if pr_timelines is None:
                continue
            for pr_timeline in pr_timelines:
                target_content = target_content.append(pr_timeline.toTSVFormat(), ignore_index=True)
        pandasHelper.writeTSVFile(target_filename, target_content)

    @staticmethod
    def getPRChangeTriggerData(owner, repo):
        """ ����
            ALL_{repo}_data_pullrequest.tsv
            ALL_{repo}_data_prtimeline.tsv
            ��ȡpr change_trigger����
        """
        AsyncApiHelper.setRepo(owner, repo)
        """PRTimeLine��ͷ"""
        PR_CHANGE_TRIGGER_COLUMNS = ["pullrequest_node", "user_login",
                                     "comment_id", "comment_type", "filepath", "change_trigger"]

        """��ʼ��Ŀ���ļ�"""
        target_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_pr_change_trigger.tsv'
        # target_content = DataFrame(columns=PR_CHANGE_TRIGGER_COLUMNS)
        # pandasHelper.writeTSVFile(target_filename, target_content)
        """��ȡPRTimeline"""
        pr_timeline_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_prtimeline.tsv'
        pr_timeline_df = pandasHelper.readTSVFile(fileName=pr_timeline_filename, header=0)
        prs = list(set(list(pr_timeline_df['pullrequest_node'])))
        pos = 0
        size = prs.__len__()
        Logger.logi("there are {0} prs need to analyze".format(prs.__len__()))
        """һ��һ������"""
        while pos < size:
            # pr = prs[pos]
            pr = "MDExOlB1bGxSZXF1ZXN0MjE3Mzc2MDk0"
            Logger.logi("start to analyze pos: {0} pr: {1}".format(pos, pr))
            pr_timeline_items = pr_timeline_df[pr_timeline_df['pullrequest_node'] == pr].to_dict(orient='index')
            if pr_timeline_items is None or pr_timeline_items.__len__() == 0:
                Logger.loge("{0}'s timeline_items is none ".format(pr))
                pos += 1
                continue
            pr_change_trigger_comments = AsyncProjectAllDataFetcher.analyzePullRequestReview(pr,
                                                                                             pr_timeline_items.values())
            target_content = DataFrame()
            target_content = target_content.append(pr_change_trigger_comments, ignore_index=True)
            if not target_content.empty:
                pandasHelper.writeTSVFile(target_filename, target_content)
            Logger.logi("successfully analyzed pos: {0} pr: {1}".format(pos, pr))
            pos += 1

    @staticmethod
    async def preProcessUnmatchCommitFile(loop, statistic):

        semaphore = asyncio.Semaphore(configPraser.getSemaphore())  # ���ٶ���������
        mysql = await getMysqlObj(loop)

        if configPraser.getPrintMode():
            print("mysql init success")
        print("mysql init success")

        res = await AsyncSqlHelper.query(mysql, SqlUtils.STR_SQL_QUERY_UNMATCH_COMMIT_FILE, None)
        print(res)

        tasks = [asyncio.ensure_future(AsyncApiHelper.downloadCommits(item[0], item[1], semaphore, mysql, statistic))
                 for item in res]  # ����ͨ��nodes �����Ƕ�׽�ʡ��������
        await asyncio.wait(tasks)


if __name__ == '__main__':
    # # ȫ����ȡprʱ������Ϣ��д��prTimeData�ļ���
    # AsyncProjectAllDataFetcher.getPRTimeLine(owner=configPraser.getOwner(), repo=configPraser.getRepo())

    # ȫ����ȡpr change_trigger��Ϣ��д��prTimeData�ļ���
    AsyncProjectAllDataFetcher.getPRChangeTriggerData(owner=configPraser.getOwner(), repo=configPraser.getRepo())

    # AsyncProjectAllDataFetcher.getDataForRepository(owner=configPraser.getOwner(), repo=configPraser.getRepo()
    #                                                 , start=configPraser.getStart(), limit=configPraser.getLimit())

    # AsyncProjectAllDataFetcher.getUnmatchedCommitFile()
