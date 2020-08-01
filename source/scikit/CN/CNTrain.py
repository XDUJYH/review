# coding=gbk
import math
import operator
import os
import time
from datetime import datetime
from functools import cmp_to_key

import pandas
import pyecharts
from pyecharts.options import series_options

from source.config.projectConfig import projectConfig
from source.data.bean.PullRequest import PullRequest
from source.scikit.CN.Gragh import Graph
from source.scikit.FPS.FPSAlgorithm import FPSAlgorithm
from source.scikit.service.BeanNumpyHelper import BeanNumpyHelper
from source.scikit.service.DataFrameColumnUtils import DataFrameColumnUtils
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.scikit.service.RecommendMetricUtils import RecommendMetricUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.Gephi import Gephi
from source.utils.Gexf import Gexf
from source.utils.StringKeyUtils import StringKeyUtils
from source.utils.pandas.pandasHelper import pandasHelper
from collections import deque
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori
from pyecharts import options as opts
from pyecharts.charts import Graph as EGraph


class CNTrain:
    """����CN������ͬһ��contributor������pr����һ���Ľ��"""
    PACCache = {}
    PNCCache = {}
    freq = None  # �Ƿ��Ѿ����ɹ�Ƶ����
    topKCommunityActiveUser = []  # ��community���Ծ�ĳ�Ա

    @staticmethod
    def clean():
        CNTrain.PACCache = {}
        CNTrain.PNCCache = {}
        CNTrain.freq = None  # �Ƿ��Ѿ����ɹ�Ƶ����
        CNTrain.topKCommunityActiveUser = []  # ��community���Ծ�ĳ�Ա

    @staticmethod
    def testCNAlgorithm(project, dates):
        """���� ѵ������"""
        recommendNum = 5  # �Ƽ�����
        excelName = f'outputCN_{project}.xls'
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
            CNTrain.clean()
            startTime = datetime.now()
            recommendList, answerList, prList, convertDict, trainSize = CNTrain.algorithmBody(date, project,
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
            filename = projectConfig.getCNDataPath() + os.sep + f'CN_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """��������ӳ���ֵ�"""
        train_data, train_data_y, test_data, test_data_y, convertDict = CNTrain.preProcess(df, date)

        prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])

        recommendList, answerList, authorList, typeList = CNTrain.RecommendByCN(project, date, train_data, train_data_y, test_data,
                                                          test_data_y, convertDict, recommendNum=recommendNum)

        # """�����Ƽ����������"""
        # DataProcessUtils.saveRecommendList(prList, recommendList, answerList, convertDict, authorList, typeList)

        """�������ز��� ѵ������С��������ͳ��"""
        from source.scikit.combine.CBTrain import CBTrain
        recommendList, answerList = CBTrain.recoverName(recommendList, answerList, convertDict)
        """��������ѵ���� ���Լ���С"""
        trainSize = (train_data.shape, test_data.shape)
        print(trainSize)

        return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def preProcess(df, dates):
        """����˵��
                    df����ȡ��dataframe����
                    dates:��Ԫ�飬����λ��Ϊ���Ե����� (,,year,month)
                   """

        """ע�⣺ �����ļ����Ѿ�����������"""

        """��comment��review����na��Ϣ������Ϊ����������õģ�����ֻ��ѵ����ȥ��na"""
        # """����NAN"""
        # df.dropna(how='any', inplace=True)
        # df.reset_index(drop=True, inplace=True)
        # df.fillna(value='', inplace=True)

        """��df���һ�б�ʶѵ�����Ͳ��Լ�"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == dates[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == dates[3]))
        """��reviewer�������ֻ����� �洢����ӳ���ֵ�������"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['pr_author', 'reviewer'])
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pull_number')))

        """���Ѿ��е����������ͱ�ǩ��ѵ�����Ĳ��"""
        train_data = df.loc[df['label'] == False].copy(deep=True)
        test_data = df.loc[df['label']].copy(deep=True)

        train_data.drop(columns=['label'], inplace=True)
        test_data.drop(columns=['label'], inplace=True)

        """8ii����NAN"""
        train_data.dropna(how='any', inplace=True)
        train_data.reset_index(drop=True, inplace=True)
        train_data.fillna(value='', inplace=True)

        """���˵�����ʱ�������ݼ�ʱ�䷶Χ��֮�������"""
        end_time = str(dates[2]) + "-" + str(dates[3]) + "-" + "01 00:00:00"
        train_data = train_data[train_data['commented_at'] < end_time]
        train_data.reset_index(drop=True, inplace=True)

        test_data_y = {}
        for pull_number in test_data.drop_duplicates(['pull_number'])['pull_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['reviewer'])['reviewer'])
            test_data_y[pull_number] = reviewers

        train_data_y = {}
        for pull_number in train_data.drop_duplicates(['pull_number'])['pull_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['reviewer'])['reviewer'])
            train_data_y[pull_number] = reviewers

        return train_data, train_data_y, test_data, test_data_y, convertDict

    @staticmethod
    def RecommendByCN(project, date, train_data, train_data_y, test_data, test_data_y, convertDict, recommendNum=5):
        """���������Ƽ��㷨"""
        recommendList = []
        answerList = []
        testDict = dict(list(test_data.groupby('pull_number')))
        authorList = []  # ����ͳ�������Ƽ����
        typeList = []

        """The start time and end time are highly related to the selection of training set"""
        # ��ʼʱ�䣺���ݼ���ʼʱ���ǰһ��
        start_time = time.strptime(str(date[0]) + "-" + str(date[1]) + "-" + "01 00:00:00", "%Y-%m-%d %H:%M:%S")
        start_time = int(time.mktime(start_time) - 86400)

        # ����ʱ�䣺���ݼ������һ��
        end_time = time.strptime(str(date[2]) + "-" + str(date[3]) + "-" + "01 00:00:00", "%Y-%m-%d %H:%M:%S")
        end_time = int(time.mktime(end_time) - 1)

        # ���һ��������Ϊ��ֹʱ��
        # comment_time_data = train_data['commented_at'].apply(lambda x: time.mktime(time.strptime(x, "%Y-%m-%d %H:%M:%S")))
        # end_time = max(comment_time_data.to_list())

        print("start building comments networks....")
        start = datetime.now()
        """������������"""
        graph = Graph()
        grouped_train_data = train_data.groupby([train_data['pr_author'], train_data['reviewer']])
        for relation, group in grouped_train_data:
            group.reset_index(drop=True, inplace=True)
            weight = CNTrain.caculateWeight(group, start_time, end_time)
            graph.add_edge(relation[0], relation[1], weight)
        print("finish building comments networks! ! ! cost time: {0}s".format(datetime.now() - start))

        # echarts��ͼ
        # CNTrain.drawCommentGraph(project, date, graph, convertDict)
        # gephi��������
        CNTrain.searchTopKByGephi(project, date, graph, convertDict, recommendNum)

        for test_pull_number, test_df in testDict.items():
            test_df.reset_index(drop=True, inplace=True)
            answerList.append(test_data_y[test_pull_number])
            pr_author = test_df.at[0, 'pr_author']
            node = graph.get_node(pr_author)
            authorList.append(pr_author)
            if node is not None and node.connectedTo:
                """PAC�Ƽ�"""
                recommendList.append(CNTrain.recommendByPAC(graph, pr_author, recommendNum))
                typeList.append('PAC')
            elif node is not None:
                """PNC�Ƽ�"""
                recommendList.append(CNTrain.recommendByPNC(train_data, graph, pr_author, recommendNum))
                typeList.append('PNC')
            else:
                """Gephi�Ƽ�"""
                recommendList.append(CNTrain.topKCommunityActiveUser)
                typeList.append('Gephi')
        return recommendList, answerList, authorList, typeList

    @staticmethod
    def caculateWeight(comment_records, start_time, end_time):
        weight_lambda = 0.8
        weight = 0

        grouped_comment_records = comment_records.groupby(comment_records['pull_number'])
        for pr, comments in grouped_comment_records:
            comments.reset_index(inplace=True, drop=True)
            """����ÿ�����ۣ�����Ȩ��"""
            for cm_idx, cm_row in comments.iterrows():
                cm_timestamp = time.strptime(cm_row['commented_at'], "%Y-%m-%d %H:%M:%S")
                cm_timestamp = int(time.mktime(cm_timestamp))
                """����tֵ: the element t(ij,r,n) is a time-sensitive factor """
                t = (cm_timestamp - start_time) / (end_time - start_time)
                cm_weight = math.pow(weight_lambda, cm_idx) * t
                weight += cm_weight
        return weight

    @staticmethod
    def recommendByPAC(graph, contributor, recommendNum):
        """For a PAC, it is natural to recommend the user who has previously interacted with the contributor directly"""
        if CNTrain.PACCache.__contains__(contributor):
            return CNTrain.PACCache[contributor]

        """��BFS�㷨�ҵ�topK"""
        start = graph.get_node(contributor)
        queue = deque([start])
        recommendList = []
        topk = recommendNum
        while queue:
            node = queue.popleft()
            node.rank_edges()
            node.marked = []
            while node.marked.__len__() < len(node.connectedTo):
                if topk == 0:
                    CNTrain.PACCache[contributor] = recommendList
                    return recommendList
                tmp = node.best_neighbor()
                node.mark_edge(tmp)
                """�����Ƽ����ѱ����������Ƽ���reviewe����<2 ���Ǳ��˵����"""
                if recommendList.__contains__(tmp.id) or tmp.in_cnt < 2 or tmp.id == contributor:
                    continue
                queue.append(tmp)
                recommendList.append(tmp.id)
                topk -= 1

        """��topk������"""
        if recommendList.__len__() < recommendNum:
            recommendList.extend(CNTrain.topKCommunityActiveUser)

        """������"""
        CNTrain.PACCache[contributor] = recommendList[0:recommendNum]
        return recommendList

    @staticmethod
    def recommendByPNC(train_data, graph, contributor, recommendNum):
        """For a PNC, since there is no prior knowledge of which developers used to review the submitter��s pull-request"""

        """����Apriori���ݼ�"""
        if CNTrain.freq is None:
            grouped_train_data = train_data.groupby(train_data['pull_number'])
            apriori_dataset = []
            for pull_number, group in grouped_train_data:
                reviewers = group['reviewer'].to_list()
                """����in_cnt<2��review"""
                # reviewers = [x for x in reviewers if graph.get_node(x).in_cnt < 2]
                apriori_dataset.append(list(set(reviewers)))
            te = TransactionEncoder()
            # ���� one-hot ����
            te_ary = te.fit(apriori_dataset).transform(apriori_dataset)
            df = pandas.DataFrame(te_ary, columns=te.columns_)

            # ���� Apriori�㷨 �ҳ�Ƶ���
            print("start gen apriori......")
            # TODO top-kƵ�������
            freq = apriori(df, min_support=0.01, use_colnames=True)
            CNTrain.freq = freq.sort_values(by="support", ascending=False)
            print("finish gen apriori!!!")

        """ֱ�Ӵӻ���ȡ���"""
        if CNTrain.PNCCache.__contains__(contributor):
            return CNTrain.PNCCache[contributor]

        """�ҵ����Լ�review��Ȥ������û���Ϊreviewer"""
        recommendList = []
        for idx, row in CNTrain.freq.iterrows():
            community = list(row['itemsets'])
            community = sorted(community,
                   key=lambda x:graph.get_node(x).in_cnt, reverse=True)
            if contributor in community and community.__len__() > 1:
                community.remove(contributor)
                recommendList.extend(community)

        # TODO ��ΪƵ�����Ŀ���٣��󲿷��û����Ҳ������Լ�review��Ȥ������û�������������topKActive���û�����
        if recommendList.__len__() < recommendNum:
            """��ʱ���ܻ�û����topKActiveContributor"""
            recommendList.extend(CNTrain.topKCommunityActiveUser)
        recommendList = recommendList[0:recommendNum]

        """������"""
        CNTrain.PNCCache[contributor] = recommendList
        return recommendList

    @staticmethod
    def searchTopKByGephi(project, date, graph, convertDict, recommendNum=5):
        """����Gephi�����������Ƽ���������Ծ����ߵ���"""

        """����gephi����"""
        file_name = CNTrain.genGephiData(project, date, graph, convertDict)
        """����gephi��������"""
        communities = Gephi().getCommunity(graph_file=file_name)
        """ɸѡ����Ա>2������"""
        communities = {k: v for k, v in communities.items() if v.__len__() >= 2}
        # ����community size����
        communities = sorted(communities.items(), key=lambda d: d[1].__len__(), reverse=True)

        # ѭ������communiity���Ӹ���community�ҳ����Ծ(���)��topK
        topKActiveContributor = []
        for i in range(0, recommendNum):
            for community in communities:
                """community�ڲ����������"""
                community_uids = sorted(community[1],
                       key=lambda x:graph.get_node(int(x)).in_cnt, reverse=True)
                for user in community_uids:
                    user = int(user)
                    if user in topKActiveContributor:
                        continue
                    topKActiveContributor.append(user)
                    break
                if topKActiveContributor.__len__() == recommendNum:
                    break
            if topKActiveContributor.__len__() == recommendNum:
                break

        CNTrain.topKCommunityActiveUser = topKActiveContributor[0:recommendNum]

    @staticmethod
    def drawCommentGraph(project, date, graph, convertDict):
        nodes = []
        links = []
        tempDict = {k: v for v, k in convertDict.items()}

        """����ͼ���ҳ�in_cnt��weight��������Сֵ�����ݹ�һ��"""
        in_min, in_max, w_min, w_max = [0, 0, 0, 0]
        for key, node in graph.node_list.items():
            in_max = max(in_max, node.in_cnt)
            for weight in node.connectedTo.values():
                w_max = max(w_max, weight)

        in_during = in_max - in_min
        w_during = w_max - w_min
        for key, node in graph.node_list.items():
            nodes.append({
                "name": tempDict[node.id],
                "symbolSize": 10 * (node.in_cnt - in_min) / in_during,
                "value": node.in_cnt
            })
            for to, weight in node.connectedTo.items():
                links.append({
                    "source": tempDict[node.id],
                    "target": tempDict[to.id],
                    "lineStyle": {
                        "width": 10 * (weight - w_min) / w_during
                    }
                })

        file_name = f'graph/{project}_{date[0]}_{date[1]}_{date[2]}_{date[3]}_cn-graph.html'
        EGraph().add("user",
                     nodes=nodes,
                     links=links,
                     repulsion=8000,
                     layout="circular",
                     is_rotate_label=True,
                     linestyle_opts=opts.LineStyleOpts(color="source", curve=0.3),
                     ) \
                .set_global_opts(
                title_opts=opts.TitleOpts(title="cn-graph"),
                legend_opts=opts.LegendOpts(orient="vertical", pos_left="2%", pos_top="20%"),
                ) \
                .render(file_name)


    @staticmethod
    def genGephiData(project, date, graph, convertDict):
        file_name = f'{os.curdir}/gephi/{project}_{date[0]}_{date[1]}_{date[2]}_{date[3]}_network'

        gexf = Gexf("reviewer_recommend", file_name)
        gexf_graph = gexf.addGraph("directed", "static", file_name)

        tempDict = {k: v for v, k in convertDict.items()}

        """����ͼ��weight�����ֵ�����ݹ�һ��"""
        w_min, w_max = (0, 0)
        for key, node in graph.node_list.items():
            for weight in node.connectedTo.values():
                w_max = max(w_max, weight)

        w_during = w_max - w_min
        # �߱��
        e_idx = 0
        for key, node in graph.node_list.items():
            gexf_graph.addNode(id=str(node.id), label=tempDict[node.id])
            for to, weight in node.connectedTo.items():
                gexf_graph.addNode(id=str(to.id), label=tempDict[to.id])
                gexf_graph.addEdge(id=e_idx, source=str(node.id), target=str(to.id), weight=10 * (weight - w_min) / w_during)
                e_idx += 1

        output_file = open(file_name + ".gexf", "wb")
        gexf.write(output_file)
        output_file.close()
        return file_name + ".gexf"


if __name__ == '__main__':
    dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
             (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
             (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    projects = ['react']
    for p in projects:
        projectName = p
        CNTrain.testCNAlgorithm(projectName, dates)