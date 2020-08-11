# coding=gbk
import math
import operator
import os
import time
from datetime import datetime
from functools import cmp_to_key

import pandas
import pyecharts
from gensim import corpora, models
from pyecharts.options import series_options

from source.config.projectConfig import projectConfig
from source.data.bean.PullRequest import PullRequest
from source.nlp.FleshReadableUtils import FleshReadableUtils
from source.nlp.SplitWordHelper import SplitWordHelper
from source.nltk import nltkFunction
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


class CN_IRTrain:
    """����CN������ͬһ��contributor������pr����һ���Ľ��"""
    PACCache = {}
    PNCCache = {}
    freq = None  # �Ƿ��Ѿ����ɹ�Ƶ����
    topKCommunityActiveUser = []  # ��community���Ծ�ĳ�Ա

    @staticmethod
    def clean():
        CN_IRTrain.PACCache = {}
        CN_IRTrain.PNCCache = {}
        CN_IRTrain.freq = None  # �Ƿ��Ѿ����ɹ�Ƶ����
        CN_IRTrain.topKCommunityActiveUser = []  # ��community���Ծ�ĳ�Ա

    @staticmethod
    def testCN_IRAlgorithm(project, dates, filter_train=False, filter_test=False):
        """���� ѵ������"""
        recommendNum = 5  # �Ƽ�����
        excelName = f'outputCN_IR_{project}_{filter_train}_{filter_test}.xls'
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
            CN_IRTrain.clean()
            startTime = datetime.now()
            recommendList, answerList, prList, convertDict, trainSize = CN_IRTrain.algorithmBody(date, project,
                                                                                                 recommendNum,
                                                                                                 filter_train=filter_train,
                                                                                                 filter_test=filter_test)
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
    def algorithmBody(date, project, recommendNum=5, filter_train=False, filter_test=False):

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
            if i < date[2] * 12 + date[3]:
                if filter_train:
                    filename = projectConfig.getCN_IRDataPath() + os.sep + f'CN_IR_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getCN_IRDataPath() + os.sep + f'CN_IR_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            else:
                if filter_test:
                    filename = projectConfig.getCN_IRDataPath() + os.sep + f'CN_IR_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getCN_IRDataPath() + os.sep + f'CN_IR_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """��������ӳ���ֵ�"""
        train_data, train_data_y, test_data, test_data_y, convertDict = CN_IRTrain.preProcess(df, date)

        prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])
        prList.sort()

        recommendList, answerList, authorList, typeList = CN_IRTrain.RecommendByCN_IR(project, date, train_data, train_data_y, test_data,
                                                                                   test_data_y, convertDict, recommendNum=recommendNum)

        """�����Ƽ����������"""
        DataProcessUtils.saveRecommendList(prList, recommendList, answerList, convertDict, authorList, key=project + str(date))

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
        df['pr_title'].fillna(value='', inplace=True)
        df['pr_body'].fillna(value='', inplace=True)

        """��df���һ�б�ʶѵ�����Ͳ��Լ�"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == dates[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == dates[3]))
        """��reviewer�������ֻ����� �洢����ӳ���ֵ�������"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['pr_author', 'reviewer'])

        """�����ռ������ı������ִ�"""
        stopwords = SplitWordHelper().getEnglishStopList()  # ��ȡͨ��Ӣ��ͣ�ô�

        textList = []
        for row in df.itertuples(index=False, name='Pandas'):
            tempList = []
            """��ȡpull request�ı���"""
            pr_title = getattr(row, 'pr_title')
            pr_title_word_list = [x for x in FleshReadableUtils.word_list(pr_title) if x not in stopwords]

            """����������ȡ�ʸ�Ч�������½��� ��������"""

            """�Ե�������ȡ�ʸ�"""
            pr_title_word_list = nltkFunction.stemList(pr_title_word_list)
            tempList.extend(pr_title_word_list)

            """pull request��body"""
            pr_body = getattr(row, 'pr_body')
            pr_body_word_list = [x for x in FleshReadableUtils.word_list(pr_body) if x not in stopwords]
            """�Ե�������ȡ�ʸ�"""
            pr_body_word_list = nltkFunction.stemList(pr_body_word_list)
            tempList.extend(pr_body_word_list)
            textList.append(tempList)

        print(textList.__len__())
        """�Էִ��б����ֵ� ����ȡ������"""
        dictionary = corpora.Dictionary(textList)
        print('�ʵ䣺', dictionary)

        feature_cnt = len(dictionary.token2id)
        print("�ʵ���������", feature_cnt)

        """���ݴʵ佨�����Ͽ�"""
        corpus = [dictionary.doc2bow(text) for text in textList]
        # print('���Ͽ�:', corpus)
        """���Ͽ�ѵ��TF-IDFģ��"""
        tfidf = models.TfidfModel(corpus)

        """�ٴα������ݣ��γ�������������ϡ��������ʽ"""
        wordVectors = []
        for i in range(0, df.shape[0]):
            wordVectors.append(dict(tfidf[dictionary.doc2bow(textList[i])]))

        """���Ѿ��еı������������ͱ�ǩ��ѵ�����Ͳ��Լ��Ĳ��"""
        trainData_index = df.loc[df['label'] == False].index
        testData_index = df.loc[df['label'] == True].index

        """ѵ����"""
        train_data = [wordVectors[x] for x in trainData_index]
        """���Լ�"""
        test_data = [wordVectors[x] for x in testData_index]
        """���Ϊ����"""
        train_v_data = DataProcessUtils.convertFeatureDictToDataFrame(train_data, featureNum=feature_cnt)
        test_v_data = DataProcessUtils.convertFeatureDictToDataFrame(test_data, featureNum=feature_cnt)

        train_data = df.loc[df['label'] == False]
        train_data.reset_index(drop=True, inplace=True)
        test_data = df.loc[df['label'] == True]
        test_data.reset_index(drop=True, inplace=True)

        train_data = train_data.join(train_v_data)
        train_data.drop(columns=['label'], inplace=True)

        test_data = test_data.join(test_v_data)
        test_data.drop(columns=['label'], inplace=True)

        """8ii����NAN"""
        train_data.dropna(how='any', inplace=True)
        train_data.reset_index(drop=True, inplace=True)
        train_data.fillna(value='', inplace=True)

        """�ȶ�tag�����"""
        trainDict = dict(list(train_data.groupby('pull_number')))
        testDict = dict(list(test_data.groupby('pull_number')))

        """���˵�����ʱ�������ݼ�ʱ�䷶Χ��֮�������"""
        end_time = str(dates[2]) + "-" + str(dates[3]) + "-" + "01 00:00:00"
        train_data = train_data[train_data['commented_at'] < end_time]
        train_data.reset_index(drop=True, inplace=True)

        test_data_y = {}
        for pull_number in test_data.drop_duplicates(['pull_number'])['pull_number']:
            reviewers = list(testDict[pull_number].drop_duplicates(['reviewer'])['reviewer'])
            test_data_y[pull_number] = reviewers

        train_data_y = {}
        for pull_number in train_data.drop_duplicates(['pull_number'])['pull_number']:
            reviewers = list(trainDict[pull_number].drop_duplicates(['reviewer'])['reviewer'])
            train_data_y[pull_number] = reviewers

        return train_data, train_data_y, test_data, test_data_y, convertDict

    @staticmethod
    def RecommendByCN_IR(project, date, train_data, train_data_y, test_data, test_data_y, convertDict, recommendNum=5):
        """���������Ƽ��㷨"""
        recommendList = []
        answerList = []
        testDict = dict(list(test_data.groupby('pull_number')))
        authorList = []  # ����ͳ�������Ƽ����
        typeList = []
        testTuple = sorted(testDict.items(), key=lambda x: x[0])

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
            cn_weight = CN_IRTrain.caculateWeight(group, start_time, end_time)
            graph.add_edge(relation[0], relation[1], cn_weight)
        print("finish building comments networks! ! ! cost time: {0}s".format(datetime.now() - start))

        """��Ȩ��һ��"""
        for key, node in graph.node_list.items():
            for to, weight in node.connectedTo.items():
                node.connectedTo[to] = weight/graph.max_weight

        # echarts��ͼ
        # CNTrain.drawCommentGraph(project, date, graph, convertDict)
        # gephi��������
        CN_IRTrain.searchTopKByGephi(project, date, graph, convertDict, recommendNum)

        train_data.drop(columns=['comment_node', 'reviewer', 'commented_at', 'reviewer_association', 'comment_type'], inplace=True)
        train_data.drop_duplicates(inplace=True)

        test_data.drop(columns=['comment_node', 'reviewer', 'commented_at', 'reviewer_association', 'comment_type'], inplace=True)
        test_data.drop_duplicates(inplace=True)
        now = 1
        total = test_data.shape[0]
        for targetData in test_data.itertuples(index=False):
            targetNum = targetData[1]
            targetAuthor = targetData[4]
            authorList.append(targetAuthor)
            recommendScore = {}
            max_ir_score = 0
            for trainData in train_data.itertuples(index=False, name='Pandas'):
                trainNum = trainData[1]
                reviewers = train_data_y[trainNum]

                """�������ƶȲ��������һ��pr number"""
                score = CN_IRTrain.cos2(targetData[12:targetData.__len__()], trainData[12:trainData.__len__()])
                for reviewer in reviewers:
                    if recommendScore.get(reviewer, None) is None:
                        recommendScore[reviewer] = 0
                    recommendScore[reviewer] += score
                    max_ir_score = max(recommendScore[reviewer], max_ir_score)

            for rev, weight in recommendScore.items():
                author_node = graph.get_node(targetAuthor)
                if author_node is None:
                     continue
                rev_node = graph.get_node(rev)
                # IR������һ
                weight /= max_ir_score
                if author_node.connectedTo.__contains__(rev_node):
                    recommendScore[rev] = weight + author_node.connectedTo[rev_node]
                else:
                    recommendScore[rev] = weight

            targetRecommendList = [x[0] for x in
                                   sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]

            recommendList.append(targetRecommendList)
            answerList.append(test_data_y[targetNum])
            print("now: {0}, total: {1}".format(now, total))
            now += 1

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
    def cos2(tuple1, tuple2):
        if tuple1.__len__() != tuple2.__len__():
            raise Exception("tuple length not equal!")
        """��������Ԫ�������"""
        """�ȼ���ģ��"""
        l1 = 0
        for v in tuple1:
            l1 += v * v
        l2 = 0
        for v in tuple2:
            l2 += v * v
        mul = 0
        """�����������"""
        len = tuple1.__len__()
        for i in range(0, len):
            mul += tuple1[i] * tuple2[i]
        if mul == 0:
            return 0
        return mul / (math.sqrt(l1) * math.sqrt(l2))

    @staticmethod
    def searchTopKByGephi(project, date, graph, convertDict, recommendNum=5):
        """����Gephi�����������Ƽ���������Ծ����ߵ���"""

        """����gephi����"""
        file_name = CN_IRTrain.genGephiData(project, date, graph, convertDict)
        """����gephi��������"""
        communities, modularity = Gephi().getCommunity(graph_file=file_name)
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

        CN_IRTrain.topKCommunityActiveUser = topKActiveContributor[0:recommendNum]

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
    projects = ['opencv']
    for p in projects:
        projectName = p
        CN_IRTrain.testCN_IRAlgorithm(projectName, dates, filter_train=False, filter_test=True)