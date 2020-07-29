# coding=gbk
import os
import time
from datetime import datetime

from source.config.projectConfig import projectConfig
from source.scikit.FPS.FPSAlgorithm import FPSAlgorithm
from source.scikit.HG.Edge import Edge
from source.scikit.HG.HyperGraph import HyperGraph
from source.scikit.HG.Node import Node
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.pandas.pandasHelper import pandasHelper
import numpy as np


class HGTrain:

    """��ͼ�����������������Ƽ�"""

    @staticmethod
    def TestAlgorithm(project, dates):
        """���� ѵ������"""
        recommendNum = 5  # �Ƽ�����
        excelName = f'outputHG_{project}.xlsx'
        sheetName = 'result'

        """�����ۻ�����"""
        topks = []
        mrrs = []
        precisionks = []
        recallks = []
        fmeasureks = []

        """��ʼ��excel�ļ�"""
        ExcelHelper().initExcelFile(fileName=excelName, sheetName=sheetName, excel_key_list=['ѵ����', '���Լ�'])
        for date in dates:
            startTime = datetime.now()
            recommendList, answerList, prList, convertDict, trainSize = HGTrain.algorithmBody(date, project,
                                                                                              recommendNum)
            """�����Ƽ��б�������"""
            topk, mrr, precisionk, recallk, fmeasurek = \
                DataProcessUtils.judgeRecommend(recommendList, answerList, recommendNum)

            topks.append(topk)
            mrrs.append(mrr)
            precisionks.append(precisionk)
            recallks.append(recallk)
            fmeasureks.append(fmeasurek)

            """���д��excel"""
            DataProcessUtils.saveResult(excelName, sheetName, topk, mrr, precisionk, recallk, fmeasurek, date)

            """�ļ��ָ�"""
            content = ['']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            content = ['ѵ����', '���Լ�']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())

            print("cost time:", datetime.now() - startTime)

        """������ʷ�ۻ�����"""
        DataProcessUtils.saveFinallyResult(excelName, sheetName, topks, mrrs, precisionks, recallks,
                                           fmeasureks)

    @staticmethod
    def preProcess(df, dates):
        """����˵��
           df����ȡ��dataframe����
           dates:��Ԫ�飬����λ��Ϊ���Ե����� (,,year,month)
        """

        """ע�⣺ �����ļ����Ѿ�����������"""

        """��comment��review����nan��Ϣ������Ϊ����������õģ�����ֻ��ѵ����ȥ��na"""
        # """����NAN"""
        # df.dropna(how='any', inplace=True)
        # df.reset_index(drop=True, inplace=True)
        # df.fillna(value='', inplace=True)

        """��df���һ�б�ʶѵ�����Ͳ��Լ�"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == dates[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == dates[3]))
        """��reviewer�������ֻ����� �洢����ӳ���ֵ�������"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['author_user_login', 'review_user_login'])

        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pr_number')))

        """���Ѿ��е����������ͱ�ǩ��ѵ�����Ĳ��"""
        train_data = df.loc[df['label'] == False].copy(deep=True)
        test_data = df.loc[df['label']].copy(deep=True)

        train_data.drop(columns=['label'], inplace=True)
        test_data.drop(columns=['label'], inplace=True)

        """����NAN"""
        train_data.dropna(how='any', inplace=True)
        train_data.reset_index(drop=True, inplace=True)
        train_data.fillna(value='', inplace=True)

        """ע�⣺ train_data �� test_data ���ж��comment��filename�����"""
        test_data_y = {}
        for pull_number in test_data.drop_duplicates(['pr_number'])['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            test_data_y[pull_number] = reviewers

        train_data_y = {}
        for pull_number in train_data.drop_duplicates(['pr_number'])['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            train_data_y[pull_number] = reviewers

        return train_data, train_data_y, test_data, test_data_y, convertDict

    @staticmethod
    def algorithmBody(date, project, recommendNum=5):

        """�ṩ�������ں���Ŀ����
           �����Ƽ��б�ʹ�
           ����ӿڿ��Ա�����㷨����
        """
        print(date)
        df = None
        for i in range(date[0] * 12 + date[1], date[2] * 12 + date[3] + 1):  # ��ֵ�������ƴ��
            y = int((i - i % 12) / 12)
            m = i % 12
            if m == 0:
                m = 12
                y = y - 1

            # print(y, m)
            filename = projectConfig.getHGDataPath() + os.sep + f'HG_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """��������ӳ���ֵ�"""
        train_data, train_data_y, test_data, test_data_y, convertDict = HGTrain.preProcess(df, date)

        prList = list(set(test_data['pr_number']))
        prList.sort()

        recommendList, answerList = HGTrain.RecommendByHG(train_data, train_data_y, test_data,
                                                          test_data_y, recommendNum=recommendNum)

        """�������ز��� ѵ������С��������ͳ��"""

        """��������ѵ���� ���Լ���С"""
        trainSize = (train_data.shape[0], test_data.shape[0])
        print(trainSize)

        return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def createTrainDataGraph(train_data, train_data_y, trainPrDis):
        """ͨ��ѵ�����������ͼ ���Զ���Ķ���ı���Ҫ�������"""

        graph = HyperGraph()

        """�����PR�Ķ���"""
        prList = list(set(train_data['pr_number']))
        prList.sort()  # ��С��������
        prList = tuple(prList)
        for pr in prList:
            graph.add_node(nodeType=Node.STR_NODE_TYPE_PR, contentKey=pr, description=f"pr:{pr}")

        """����author�Ķ���"""
        authorList = list(set(train_data['author_user_login']))
        for author in authorList:
            graph.add_node(nodeType=Node.STR_NODE_TYPE_AUTHOR, contentKey=author, description=f"author:{author}")

        """����reviewer�Ķ���"""
        reviewerList = list(set(train_data['review_user_login']))
        for reviewer in reviewerList:
            graph.add_node(nodeType=Node.STR_NODE_TYPE_REVIEWER, contentKey=reviewer, description=f"reviewer:{reviewer}")

        """����pr֮��ı�"""
        for p1 in prList:
            node_1 = graph.get_node_by_content(Node.STR_NODE_TYPE_PR, p1)
            for p2 in prList:
                weight = trainPrDis.get((p1, p2), None)
                if weight is not None:
                    node_2 = graph.get_node_by_content(Node.STR_NODE_TYPE_PR, p2)
                    graph.add_edge(nodes=[node_1.id, node_2.id], edgeType=Edge.STR_EDGE_TYPE_PR_DIS,
                                   weight=weight, description=f"pr distance between {p1} and {p2}",
                                   queryBeforeAdd=True)

        """����pr��reviewer�ı�  ������ʱreviewer���ϲ���һ�� weight��Ҫ����"""
        for pr in prList:
            reviewers = train_data_y[pr]
            for reviewer in reviewers:
                pr_node = graph.get_node_by_content(Node.STR_NODE_TYPE_PR, pr)
                reviewer_node = graph.get_node_by_content(Node.STR_NODE_TYPE_REVIEWER, reviewer)
                graph.add_edge(nodes=[pr_node.id, reviewer_node.id], edgeType=Edge.STR_EDGE_TYPE_PR_REVIEW_RELATION,
                               weight=1, description=f" pr review relation between pr {pr} and reviewer {reviewer}",
                               nodeObjects=[pr_node, reviewer_node])

        """����pr �� author�ı�"""
        for pr in prList:
            author = list(set(train_data.loc[train_data['pr_number'] == pr]['author_user_login']))[0]
            pr_node = graph.get_node_by_content(Node.STR_NODE_TYPE_PR, pr)
            author_node = graph.get_node_by_content(Node.STR_NODE_TYPE_AUTHOR, author)
            graph.add_edge(nodes=[pr_node.id, author_node.id], edgeType=Edge.STR_EDGE_TYPE_PR_AUTHOR_RELATION,
                           weight=1, description=f" pr author relation between pr {pr} and author {author}",
                           nodeObjects=[pr_node, author_node])

        """���� author �� reviewer �ı�"""
        userList = [x for x in authorList if x in reviewerList]
        for user in userList:
            author_node = graph.get_node_by_content(Node.STR_NODE_TYPE_AUTHOR, user)
            reviewer_node = graph.get_node_by_content(Node.STR_NODE_TYPE_REVIEWER, user)
            graph.add_edge(nodes=[author_node.id, reviewer_node.id], edgeType=Edge.STR_EDGE_TYPE_AUTHOR_REVIEWER_RELATION,
                           weight=1, description=f"author reviewer relation for {user}",
                           nodeObjects=[author_node, reviewer_node])

        # """����ͼ�ļ�������"""
        # graph.updateMatrix()
        return graph

    @staticmethod
    def getTrainDataPrDistance(train_data, K, pathDict):
        """������trainData�и��� pr ֮��ľ��� ͨ��·�����ƶȱȽ�
           {(num1, num2) -> s1}  ����num1 < num2
           ÿ������ȡ�����Ƶ� K ����Ϊ���Ӷ��󣬽�Լ�ռ�
           ע��  ������Щ������г���K����
        """
        trainPrDis = {}  # ���ڼ�¼pr�ľ���

        print(train_data.shape)
        data = train_data[['pr_number', 'filename']].copy(deep=True)
        data.drop_duplicates(inplace=True)
        data.reset_index(inplace=True, drop=True)
        prList = list(set(data['pr_number']))
        prList.sort()  # ��С��������
        scoreMap = {}  # ͳ������pr֮�����ƶȵķ���
        for p1 in prList:
            scores = {}  # ��¼
            for p2 in prList:
                if p1 < p2:
                    # paths1 = list(pathDict[p1]['filename'])
                    # paths2 = list(pathDict[p2]['filename'])
                    # score = 0
                    # for filename1 in paths1:
                    #     for filename2 in paths2:
                    #         score += FPSAlgorithm.LCS_2(filename1, filename2) + \
                    #                  FPSAlgorithm.LCSubseq_2(filename1, filename2) + \
                    #                  FPSAlgorithm.LCP_2(filename1, filename2) + \
                    #                  FPSAlgorithm.LCSubstr_2(filename1, filename2)
                    # score /= paths1.__len__() * paths2.__len__()
                    score = 1
                    # TODO Ŀ�����ǳ��ĺ�ʱ�䣬 ����Ѱ���Ż��ķ���
                    scores[p2] = score
                    scoreMap[(p1, p2)] = score
                    scoreMap[(p2, p1)] = score
                elif p1 > p2:
                    score = scoreMap[(p1, p2)]
                    scores[p2] = score
            """�ҳ�K�������pr"""
            KNN = [x[0] for x in sorted(scores.items(), key=lambda d: d[1], reverse=True)[0:K]]
            for p2 in KNN:
                trainPrDis[(p1, p2)] = scores[p2]  # p1,p2��˳����ܻ����Ӱ��
        return trainPrDis

    @staticmethod
    def RecommendByHG(train_data, train_data_y, test_data, test_data_y, recommendNum=5, K=5, alpha=0.98):
        """���ڳ�ͼ�����Ƽ��㷨
           K �����������Ƕ����ڽ���pr
           alpha �������� �����������
        """
        recommendList = []
        answerList = []
        testDict = dict(list(test_data.groupby('pr_number')))

        print("start building hypergraph....")
        start = datetime.now()

        """����ѵ������pr�ľ���"""
        tempData = train_data[['pr_number', 'filename']].copy(deep=True)
        tempData.drop_duplicates(inplace=True)
        tempData.reset_index(inplace=True, drop=True)
        pathDict = dict(list(tempData.groupby('pr_number')))
        trainPrDis = HGTrain.getTrainDataPrDistance(train_data, K, pathDict)
        print(" pr distance cost time:", datetime.now() - start)

        """������ͼ"""
        graph = HGTrain.createTrainDataGraph(train_data, train_data_y, trainPrDis)

        prList = list(set(train_data['pr_number']))
        prList.sort()  # ��С��������
        prList = tuple(prList)

        startTime = datetime.now()

        for test_pull_number, test_df in testDict.items():
            """��ÿһ������������  ���pr�ڵ��K���ߣ��Լ�������ӵ����߽ڵ�
               ���Ƽ�����֮��  ɾ��pr�ڵ��pr�ı� ������ӵ����߽ڵ�Ҳ����ɾ��
            """
            test_df.reset_index(drop=True, inplace=True)

            """���pr�ڵ�"""
            pr_num = list(test_df['pr_number'])[0]
            paths2 = list(set(test_df['filename']))
            node_1 = graph.add_node(nodeType=Node.STR_NODE_TYPE_PR, contentKey=pr_num, description=f"pr:{pr_num}")
            """����K�� pr�ڵ�������ڵ����ӵı�"""
            scores = {}  # ��¼
            for p1 in prList:
                paths1 = list(pathDict[p1]['filename'])
                score = 0
                for filename1 in paths1:
                    for filename2 in paths2:
                        score += FPSAlgorithm.LCS_2(filename1, filename2) + \
                                    FPSAlgorithm.LCSubseq_2(filename1, filename2) + \
                                    FPSAlgorithm.LCP_2(filename1, filename2) + \
                                    FPSAlgorithm.LCSubstr_2(filename1, filename2)
                        score /= paths1.__len__() * paths2.__len__()
                # score = 1
                # TODO Ŀ�����ǳ��ĺ�ʱ�䣬 ����Ѱ���Ż��ķ���
                scores[p1] = score
            """�ҳ�K�������pr"""
            KNN = [x[0] for x in sorted(scores.items(), key=lambda d: d[1], reverse=True)[0:K]]
            """�ҳ���K������ص�pr���ӱ�"""
            for p2 in KNN:
                node_2 = graph.get_node_by_content(Node.STR_NODE_TYPE_PR, p2)
                graph.add_edge(nodes=[node_1.id, node_2.id], edgeType=Edge.STR_EDGE_TYPE_PR_DIS,
                               weight=scores[p2], description=f"pr distance between {pr_num} and {p2}",
                               nodeObjects=[node_1, node_2])

            """�����û�����߽ڵ� �������"""
            author = test_df['author_user_login'][0]
            authorNode = graph.get_node_by_content(Node.STR_NODE_TYPE_AUTHOR, author)
            needAddAuthorNode = False  # ���ΪTrue��������Ҫ�����߽ڵ�Ҳɾ��
            if authorNode is None:
                needAddAuthorNode = True
                authorNode = graph.add_node(nodeType=Node.STR_NODE_TYPE_AUTHOR, contentKey=author, description=f"author:{author}")
            """�������ߺ�pr֮��ı�"""
            graph.add_edge(nodes=[node_1.id, authorNode.id], edgeType=Edge.STR_EDGE_TYPE_PR_AUTHOR_RELATION,
                           weight=1, description=f" pr author relation between pr {pr_num} and author {author}",
                           nodeObjects=[node_1, authorNode])

            """���¼������A"""
            graph.updateMatrix()

            """�½���ѯ����"""
            y = np.zeros((graph.num_nodes, 1))
            """�������ߺ��Ƽ�pr��λ��Ϊ1 �ο���ֵ�ĵ����ַ�ʽ"""
            nodeInverseMap = {v: k for k, v in graph.node_id_map.items()}
            y[nodeInverseMap[node_1.id]][0] = 1
            y[nodeInverseMap[authorNode.id]][0] = 1

            """����˳���б�f"""
            I = np.identity(graph.num_nodes)
            f = np.dot(np.linalg.inv(I - alpha * graph.A), y)

            """�Լ��������� �ҵ������ϸߵļ�λ"""
            scores = {}
            for i in range(0, graph.num_nodes):
                node_id = graph.node_id_map[i]
                node = graph.get_node_by_key(node_id)
                if node.type == Node.STR_NODE_TYPE_REVIEWER:
                    scores[node.contentKey] = f[i][0]

            answer = list(set(test_df['review_user_login']))
            answerList.append(answer)
            recommendList.append([x[0] for x in sorted(scores.items(),
                                                       key=lambda d: d[1], reverse=True)[0:recommendNum]])

            """������߽ڵ���������ӵ�  ��ɾ��"""
            if needAddAuthorNode:
                graph.remove_node_by_key(authorNode.id)
            """ɾ�� pr �ڵ�"""
            graph.remove_node_by_key(node_1.id)

        print("total query cost time:", datetime.now() - startTime)
        return recommendList, answerList


if __name__ == '__main__':
    # dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
    #          (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
    #          (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    # projects = ['opencv', 'cakephp', 'yarn', 'akka', 'django', 'react']
    dates = [(2017, 1, 2017, 2)]
    projects = ['opencv']
    for p in projects:
        HGTrain.TestAlgorithm(p, dates)
