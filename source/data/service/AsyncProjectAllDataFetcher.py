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
from source.data.bean.ReviewChangeRelation import ReviewChangeRelation
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
            offset = 10 - nodes.__len__() % 10
            nodes.extend([None for i in range(0, offset)])
            nodesGroup = np.array(nodes).reshape(10, -1)
            # for index in range(0, nodes.__len__(), 10):
            #     if index + 10 < nodes.__len__():
            #         nodesGroup.append(nodes[index:index + 10])
            #     else:
            #         nodesGroup.append(nodes[index:nodes.__len__()])

        tasks = [
            asyncio.ensure_future(AsyncApiHelper.downloadRPTimeLine([x for x in nodegroup.tolist() if x is not None],
                                                                    semaphore, mysql, statistic))
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
    def analyzePullRequestReview(pr_timeline_item_groups):
        """һ�ν������pr��change_trigger��Ϣ"""
        t1 = datetime.now()

        statistic = statisticsHelper()
        statistic.startTime = t1

        loop = asyncio.get_event_loop()
        coro = getMysqlObj(loop)
        task = loop.create_task(coro)
        loop.run_until_complete(task)
        mysql = task.result()

        loop = asyncio.get_event_loop()
        tasks = [asyncio.ensure_future(
            AsyncProjectAllDataFetcher.analyzePRTimeline(mysql, pr_timeline_item_group, statistic))
            for pr_timeline_item_group in pr_timeline_item_groups]
        tasks = asyncio.gather(*tasks)
        loop.run_until_complete(tasks)
        print('cost time:', datetime.now() - t1)
        return tasks.result()

    @staticmethod
    async def analyzePRTimeline(mysql, prOriginTimeLineItems, statistic):
        """����prʱ���ߣ��ҳ�������change_trigger��comment
           ������Ԫ�飨reviewer, comment_node, comment_type, file, change_trigger��
           ����issue_comment�����践��file��Ĭ�ϻ�trigger��pr�������ļ�
        """

        """��ԭʼ����ת��ΪprTimeLineItem�б�"""
        if prOriginTimeLineItems is None:
            return None
        pr_node_id = None
        prTimeLineItems = []
        for item in prOriginTimeLineItems:
            """��ĳһ��item���ȡpr_node_id"""
            if pr_node_id is None:
                pr_node_id = item.get(StringKeyUtils.STR_KEY_PULL_REQUEST_NODE)
            origin = item.get(StringKeyUtils.STR_KEY_ORIGIN)
            prTimeLineRelation = PRTimeLineRelation.Parser.parser(origin)
            prTimeLineRelation.position = item.get(StringKeyUtils.STR_KEY_POSITION, None)
            prTimeLineRelation.pull_request_node = item.get(StringKeyUtils.STR_KEY_PULL_REQUEST_NODE, None)
            prTimeLineItems.append(prTimeLineRelation)

        """����prʱ���ߣ��ҳ�������change_trigger��comment"""
        changeTriggerComments = []
        ReviewChangeRelations = []
        pairs = PRTimeLineUtils.splitTimeLine(prTimeLineItems)
        for pair in pairs:
            review = pair[0]
            changes = pair[1]

            reviewChangeRelationList = ReviewChangeRelation.parserV4.parser(pair)
            ReviewChangeRelations.extend(reviewChangeRelationList)

            """��issueComment�Һ����н����ŵ�change������Ϊ��issueComment������change_trigger"""
            if (review.typename == StringKeyUtils.STR_KEY_ISSUE_COMMENT) and changes.__len__() > 0:
                change_trigger_issue_comment = {
                    "pullrequest_node": pr_node_id,
                    "user_login": review.user_login,
                    "comment_node": review.timeline_item_node,
                    "comment_type": StringKeyUtils.STR_LABEL_ISSUE_COMMENT,
                    "change_trigger": 1,
                    "filepath": None
                }
                changeTriggerComments.append(change_trigger_issue_comment)
                continue
            elif (review.typename == StringKeyUtils.STR_KEY_ISSUE_COMMENT) and changes.__len__() == 0:
                change_trigger_issue_comment = {
                    "pullrequest_node": pr_node_id,
                    "user_login": review.user_login,
                    "comment_node": review.timeline_item_node,
                    "comment_type": StringKeyUtils.STR_LABEL_ISSUE_COMMENT,
                    "change_trigger": -1,
                    "filepath": None
                }
                changeTriggerComments.append(change_trigger_issue_comment)
                continue
            """��Ϊ��ͨreview���򿴺�������ŵ�commit�Ƿ��reviewCommit���ļ��غϵĸĶ�"""
            change_trigger_review_comments = await AsyncApiHelper.analyzeReviewChangeTriggerByBlob(pr_node_id, pair, mysql, statistic)
            if change_trigger_review_comments is not None:
                changeTriggerComments.extend(change_trigger_review_comments)
            if reviewChangeRelationList.__len__() > 0:
                ReviewChangeRelations.extend(reviewChangeRelationList)

        await AsyncSqlHelper.storeBeanDateList(ReviewChangeRelations, mysql)

        """����"""
        statistic.lock.acquire()
        statistic.usefulRequestNumber += 1
        print("analyzed pull request:", statistic.usefulRequestNumber,
              " cost time:", datetime.now() - statistic.startTime)
        statistic.lock.release()

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
    def getNoOriginLineReviewComment(owner, repo, min_num, max_num):
        # ��ȡ ���ݿ���û�л��review comment��һ�����2000��
        t1 = datetime.now()

        statistic = statisticsHelper()
        statistic.startTime = t1

        loop = asyncio.get_event_loop()
        task = [asyncio.ensure_future(AsyncProjectAllDataFetcher.preProcessNoOriginLineReviewComment(loop, statistic,
                                                                                                     owner, repo,
                                                                                                     min_num, max_num))]
        tasks = asyncio.gather(*task)
        loop.run_until_complete(tasks)

        print('cost time:', datetime.now() - t1)

    @staticmethod
    async def preProcessNoOriginLineReviewComment(loop, statistic, owner, repo, min_num, max_num):

        semaphore = asyncio.Semaphore(configPraser.getSemaphore())  # ���ٶ���������
        mysql = await getMysqlObj(loop)

        if configPraser.getPrintMode():
            print("mysql init success")
        print("mysql init success")

        repoName = owner + '/' + repo
        values = [repoName, repoName, min_num, max_num]
        res = await AsyncSqlHelper.query(mysql, SqlUtils.STR_SQL_QUERY_NO_ORIGINAL_LINE_REVIEW_COMMENT
                                         , values)
        print("fetched size:", res.__len__())

        tasks = [asyncio.ensure_future(AsyncApiHelper.downloadSingleReviewComment(repoName, item[0], semaphore, mysql, statistic))
                 for item in res]  # ����ͨ��nodes �����Ƕ�׽�ʡ��������
        await asyncio.wait(tasks)

    @staticmethod
    async def preProcessUnmatchCommitFile(loop, statistic):

        semaphore = asyncio.Semaphore(configPraser.getSemaphore())  # ���ٶ���������
        mysql = await getMysqlObj(loop)

        if configPraser.getPrintMode():
            print("mysql init success")
        print("mysql init success")

        res = await AsyncSqlHelper.query(mysql, SqlUtils.STR_SQL_QUERY_UNMATCH_COMMIT_FILE_BY_HAS_FETCHED_FILE, None)
        print(res)

        tasks = [asyncio.ensure_future(AsyncApiHelper.downloadCommits(item[0], item[1], semaphore, mysql, statistic))
                 for item in res]  # ����ͨ��nodes �����Ƕ�׽�ʡ��������
        await asyncio.wait(tasks)

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
        PRTIMELINE_COLUMNS = ["pullrequest_node", "timelineitem_node",
                              "create_at", "typename", "position", "origin"]
        """��ʼ���ļ�"""
        target_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{repo}_data_prtimeline.tsv'
        target_content = DataFrame(columns=PRTIMELINE_COLUMNS)
        pandasHelper.writeTSVFile(target_filename, target_content, pandasHelper.STR_WRITE_STYLE_APPEND_NEW)
        Logger.logi("--------------begin--------------")
        print("start fetch")
        """2. �ָ��ȡpr_timeline"""
        while pos < size:
            print("total:", size, "  now:", pos)
            loop_begin_time = datetime.now()
            Logger.logi("start: {0}, end: {1}, all: {2}".format(pos, pos + fetchLimit, size))
            pr_sub_nodes = pr_nodes[pos:pos + fetchLimit]
            results = AsyncProjectAllDataFetcher.getPullRequestTimeLine(owner=owner,
                                                                        repo=repo, nodes=pr_sub_nodes)
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
            if not target_content.empty:
                target_content = target_content[PRTIMELINE_COLUMNS].copy(deep=True)
                pandasHelper.writeTSVFile(target_filename, target_content, pandasHelper.STR_WRITE_STYLE_APPEND_NEW,
                                          header=pandasHelper.INT_WRITE_WITHOUT_HEADER)
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
        df = pandasHelper.readTSVFile(fileName=target_filename, header=pandasHelper.INT_READ_FILE_WITH_HEAD)
        # """3. prtimelineȥ��(�������ŵ������)"""
        # df = df.drop_duplicates(subset=['pullrequest_node', 'timelineitem_node'])
        """4. ��ȡ��Ҫfetch��PR"""
        fetched_prs = list(df['pullrequest_node'])
        need_fetch_prs = list(set(pr_nodes).difference(set(fetched_prs)))
        Logger.logi("there are {0} pr_timeline need to fetch".format(need_fetch_prs.__len__()))

        """����fetch����"""
        pos = 0
        fetchLimit = 200
        size = need_fetch_prs.__len__()
        while pos < size:
            sub_need_fetch_prs = need_fetch_prs[pos:pos + fetchLimit]
            Logger.logi("start: {0}, end: {1}, all: {2}".format(pos, pos + fetchLimit, size))
            """3. ��ʼ��ȡ"""
            results = AsyncProjectAllDataFetcher.getPullRequestTimeLine(owner=configPraser.getOwner(),
                                                                    repo=configPraser.getRepo(), nodes=sub_need_fetch_prs)
            Logger.logi("successfully fetched {0} pr! ".format(pos + fetchLimit))
            target_content = DataFrame()
            for result in results:
                pr_timelines = result
                if pr_timelines is None:
                    continue
                for pr_timeline in pr_timelines:
                    target_content = target_content.append(pr_timeline.toTSVFormat(), ignore_index=True)
            PRTIMELINE_COLUMNS = ["pullrequest_node", "timelineitem_node",
                                  "create_at", "typename", "position", "origin"]
            target_content = target_content[PRTIMELINE_COLUMNS].copy(deep=True)
            pandasHelper.writeTSVFile(target_filename, target_content, pandasHelper.STR_WRITE_STYLE_APPEND,
                                      pandasHelper.INT_WRITE_WITHOUT_HEADER)

            pos += fetchLimit

    @staticmethod
    def checkChangeTriggerResult():
        """���PRChangeTrigger�Ƿ��������"""
        """���л������ʱ�����ݿ����ӻ�Ͽ�������comments��Ϣ�鲻��������©review comment�����"""
        """������һ��pr��change_trigger���Ƿ���review_comment���ݣ����û�У����»�ȡһ��"""

        """1. ��ȡ�òֿ����е�pr_node"""
        repo_fullname = configPraser.getOwner() + "/" + configPraser.getRepo()
        pr_nodes = AsyncProjectAllDataFetcher.getPullRequestNodes(repo_fullname)
        pr_nodes = list(pr_nodes)
        pr_nodes = [node[0] for node in pr_nodes]

        """2. ��ȡpr_change_trigger�ļ�"""
        change_trigger_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_pr_change_trigger.tsv'
        change_trigger_df = pandasHelper.readTSVFile(fileName=change_trigger_filename, header=0)

        """3. ��ȡpr_timeline�ļ�"""
        timeline_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_prtimeline.tsv'
        timeline_df = pandasHelper.readTSVFile(fileName=timeline_filename, header=0)

        """4. ��change_trigger����pull_request_node����"""
        grouped_timeline = change_trigger_df.groupby((['pullrequest_node']))
        """5. ����pullrequest_node��change_trigger��Ϣ�Ƿ��������������Ҫ���»�ȡ��pr��Ϣ"""
        re_analyze_prs = []
        for pr, group in grouped_timeline:
            if pr not in pr_nodes:
                re_analyze_prs.append(pr)
            else:
                review_comment_trigger = group.loc[(group['comment_type'] == StringKeyUtils.STR_LABEL_REVIEW_COMMENT) & (group['change_trigger'] >= 0)]
                if review_comment_trigger is None or review_comment_trigger.empty:
                    re_analyze_prs.append(pr)
        Logger.logi("there are {0} prs need to re analyze".format(re_analyze_prs.__len__()))

        """����fetch����"""
        pos = 0
        fetchLimit = 40
        size = re_analyze_prs.__len__()
        while pos < size:
            Logger.logi("start: {0}, end: {1}, all: {2}".format(pos, pos + fetchLimit, size))
            sub_re_analyze_prs = re_analyze_prs[pos:pos + fetchLimit]
            """6. ���»�ȡ��Щpr��timeline"""
            re_analyze_prs_timeline_df = timeline_df[timeline_df['pullrequest_node'].isin(sub_re_analyze_prs)]
            grouped_timeline = re_analyze_prs_timeline_df.groupby((['pullrequest_node']))
            formated_data = []
            for pr, group in grouped_timeline:
                formated_data.append(group.to_dict(orient='records'))

            """7. ��ʼ����"""
            pr_change_trigger_comments = AsyncProjectAllDataFetcher.analyzePullRequestReview(formated_data)
            pr_change_trigger_comments = [x for y in pr_change_trigger_comments for x in y]

            """8. ���������ȥ�ز�׷�ӵ�change_trigger����"""
            target_content = DataFrame()
            target_content = target_content.append(pr_change_trigger_comments, ignore_index=True)
            target_content.drop_duplicates(subset=['pullrequest_node', 'comment_node'], inplace=True, keep='first')
            if not target_content.empty:
                pandasHelper.writeTSVFile(change_trigger_filename, target_content, writeStyle=pandasHelper.STR_WRITE_STYLE_APPEND_NEW)
            Logger.logi("successfully analyzed {0} prs".format(re_analyze_prs.__len__()))
            pos += fetchLimit

    @staticmethod
    def getPRChangeTriggerData(owner, repo):
        """ ����
            ALL_{repo}_data_prtimeline.tsv
            ��ȡpr change_trigger����
        """
        AsyncApiHelper.setRepo(owner, repo)
        """PRTimeLine��ͷ"""
        PR_CHANGE_TRIGGER_COLUMNS = ["pullrequest_node", "user_login", "comment_node",
                                     "comment_type", "change_trigger", "filepath"]
        """��ʼ��Ŀ���ļ�"""
        target_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_pr_change_trigger.tsv'
        target_content = DataFrame(columns=PR_CHANGE_TRIGGER_COLUMNS)
        pandasHelper.writeTSVFile(target_filename, target_content, pandasHelper.STR_WRITE_STYLE_APPEND_NEW,
                                  header=pandasHelper.INT_WRITE_WITH_HEADER)

        """��ȡPRTimeline����ȡ��Ҫ����change_trigger��pr�б�"""
        pr_timeline_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_prtimeline.tsv'
        pr_timeline_df = pandasHelper.readTSVFile(fileName=pr_timeline_filename, header=0)
        pr_nodes = list(set(list(pr_timeline_df['pullrequest_node'])))
        pr_nodes.sort()

        """����fetch����"""
        pos = 0
        fetchLimit = 200
        size = pr_nodes.__len__()
        Logger.logi("there are {0} prs need to analyze".format(pr_nodes.__len__()))
        t1 = datetime.now()

        while pos < size:
            print("now:", pos, ' total:', size, 'cost time:', datetime.now() - t1)
            Logger.logi("start: {0}, end: {1}, all: {2}".format(pos, pos + fetchLimit, size))

            """������ȡ����ȡ�Ӽ�"""
            sub_prs = pr_nodes[pos:pos + fetchLimit]
            pr_timeline_items = pr_timeline_df[pr_timeline_df['pullrequest_node'].isin(sub_prs)]
            """���Ӽ�����pull_request_node����"""
            grouped_timeline = pr_timeline_items.groupby((['pullrequest_node']))
            """������������Ϊ�ֵ�{pr->pr_timeline_items}"""
            formated_data = []
            for pr, group in grouped_timeline:
                formated_data.append(group.to_dict(orient='records'))

            """������Щpr��timeline"""
            pr_change_trigger_comments = AsyncProjectAllDataFetcher.analyzePullRequestReview(formated_data)
            pr_change_trigger_comments = [x for y in pr_change_trigger_comments for x in y]

            """���������ȥ�ز�׷�ӵ�change_trigger����"""
            if pr_change_trigger_comments.__len__() > 0:
                target_content = DataFrame()
                target_content = target_content.append(pr_change_trigger_comments, ignore_index=True)
                target_content = target_content[PR_CHANGE_TRIGGER_COLUMNS].copy(deep=True)
                target_content.drop_duplicates(subset=['pullrequest_node', 'comment_node'], inplace=True, keep='first')
                if not target_content.empty:
                    pandasHelper.writeTSVFile(target_filename, target_content, pandasHelper.STR_WRITE_STYLE_APPEND_NEW,
                                              header=pandasHelper.INT_WRITE_WITHOUT_HEADER)
                Logger.logi("successfully analyzed {0} prs".format(pos))
                pos += fetchLimit

if __name__ == '__main__':
    # AsyncProjectAllDataFetcher.getDataForRepository(configPraser.getOwner(), configPraser.getRepo(),
    #                                                 configPraser.getLimit(), configPraser.getStart())
    # AsyncProjectAllDataFetcher.getUnmatchedCommitFile()
    # AsyncProjectAllDataFetcher.getDataForRepository("django", "django", 3500, 11000)
    # AsyncProjectAllDataFetcher.getPRTimeLine("yarnpkg", "yarn")
    # AsyncProjectAllDataFetcher.checkPRTimeLineResult()
    # AsyncProjectAllDataFetcher.getPRChangeTriggerData(owner=configPraser.getOwner(), repo=configPraser.getRepo())
    AsyncProjectAllDataFetcher.checkChangeTriggerResult()
    # AsyncProjectAllDataFetcher.getNoOriginLineReviewComment('yarnpkg', 'yarn', 2000, 7000)

    #AsyncProjectAllDataFetcher.checkPRTimeLineResult();
    # ȫ����ȡprʱ������Ϣ��д��prTimeData�ļ���
    # AsyncProjectAllDataFetcher.getPRTimeLine("django", 'django')
    # AsyncProjectAllDataFetcher.getPRTimeLine("akka", 'akka')
    # AsyncProjectAllDataFetcher.checkPRTimeLineResult()

    # # ȫ����ȡpr change_trigger��Ϣ��д��prTimeData�ļ���
    # AsyncProjectAllDataFetcher.getPRChangeTriggerData(owner=configPraser.getOwner(), repo=configPraser.getRepo())
    # AsyncProjectAllDataFetcher.checkChangeTriggerResult()

    # pr timelineȥ��
    # source_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_prtimeline.tsv'
    # target_filename = projectConfig.getPRTimeLineDataPath() + os.sep + f'ALL_{configPraser.getRepo()}_data_prtimeline_drop.tsv'
    # df = pandasHelper.readTSVFile(fileName=source_filename, header=0)
    # df.drop_duplicates(subset=["pullrequest_node", "timelineitem_node"], inplace=True, keep='first')
    # pandasHelper.writeTSVFile(target_filename, df)

    # ȫ����ȡpr change_trigger��Ϣ��д��prTimeData�ļ���
    # AsyncProjectAllDataFetcher.getPRChangeTriggerData(owner=configPraser.getOwner(), repo=configPraser.getRepo())