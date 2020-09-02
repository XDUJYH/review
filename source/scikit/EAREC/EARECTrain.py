# coding=gbk
import sys
import os

sys.path.append("/root/zjq_rev")
import time
from datetime import datetime

from pandas import DataFrame
import numpy

from source.config.projectConfig import projectConfig
from source.nlp.FleshReadableUtils import FleshReadableUtils
from source.nlp.SplitWordHelper import SplitWordHelper
from source.nltk import nltkFunction
from source.scikit.EAREC.Edge import Edge
from source.scikit.EAREC.Node import Node
from source.scikit.EAREC.Graph import Graph
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.pandas.pandasHelper import pandasHelper
from gensim import corpora, models


class EARECTrain:
    """EAREC�㷨"""

    @staticmethod
    def testEARECAlgorithm(project, dates, filter_train=False, filter_test=False, a=0.5):
        """���� ѵ������"""
        recommendNum = 5  # �Ƽ�����
        excelName = f'outputEAREC_{project}_{filter_train}_{filter_test}.xls'
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
            recommendList, answerList, prList, convertDict, trainSize = EARECTrain.algorithmBody(date, project,
                                                                                                 recommendNum,
                                                                                                 filter_train=filter_train,
                                                                                                 filter_test=filter_test,
                                                                                                 a=a)
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
    def algorithmBody(date, project, recommendNum=5, filter_train=False, filter_test=False, a=0.5):

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
                    filename = projectConfig.getEARECDataPath() + os.sep + f'EAREC_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getEARECDataPath() + os.sep + f'EAREC_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            else:
                if filter_test:
                    filename = projectConfig.getEARECDataPath() + os.sep + f'EAREC_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getEARECDataPath() + os.sep + f'EAREC_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """��������ӳ���ֵ�"""
        train_data, train_data_y, test_data, test_data_y, convertDict = EARECTrain.preProcess(df, date)

        prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])
        # prList.sort()

        recommendList, answerList, = EARECTrain.RecommendByEAREC(train_data, train_data_y, test_data,
                                                                 test_data_y, convertDict, recommendNum=recommendNum,
                                                                 a=a)

        """�����Ƽ����������"""
        DataProcessUtils.saveRecommendList(prList, recommendList, answerList, convertDict, key=project + str(date))

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

        """���ݴʵ佨�����Ͽ�"""
        corpus = [dictionary.doc2bow(text) for text in textList]
        # print('���Ͽ�:', corpus)
        """���Ͽ�ѵ��TF-IDFģ��"""
        tfidf = models.TfidfModel(corpus)
        corpus_tfidf = tfidf[corpus]

        topic_num = 10
        lsi = models.LsiModel(corpus_tfidf, id2word=dictionary, num_topics=topic_num)
        topic_list = lsi.print_topics(20)
        print("{0}������ĵ��ʷֲ�Ϊ��\n".format(topic_num))
        for topic in topic_list:
            print(topic)

        """�ٴα������ݣ��γ�������������ϡ��������ʽ"""
        wordVectors = []
        for i in range(0, df.shape[0]):
            wordVectors.append(dict(lsi[dictionary.doc2bow(textList[i])]))

        """���Ѿ��еı������������ͱ�ǩ��ѵ�����Ͳ��Լ��Ĳ��"""
        trainData_index = df.loc[df['label'] == False].index
        testData_index = df.loc[df['label'] == True].index

        """ѵ����"""
        train_data = [wordVectors[x] for x in trainData_index]
        """���Լ�"""
        test_data = [wordVectors[x] for x in testData_index]
        """���Ϊ����"""
        train_v_data = DataProcessUtils.convertFeatureDictToDataFrame(train_data, featureNum=topic_num)
        test_v_data = DataProcessUtils.convertFeatureDictToDataFrame(test_data, featureNum=topic_num)

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
    def RecommendByEAREC(train_data, train_data_y, test_data, test_data_y, convertDict, recommendNum=5, a=0.5):
        """EAREC�Ƽ��㷨"""

        recommendList = []
        answerList = []

        print("start building reviewer<->reviewer relations....")
        start = datetime.now()

        """����train_data�ľ���"""
        df_train = train_data.copy(deep=True)
        df_train = df_train.iloc[:, 12:22]
        """����test_data����"""
        df_test = test_data.copy(deep=True)
        df_test = df_test.iloc[:, 12:22]

        """�������"""
        DIS = DataFrame(numpy.dot(df_test, df_train.T))

        """����ģ��"""
        train_len_dict = {}
        test_len_dict = {}

        for index, row in train_data.iterrows():
            train_len_dict[row['pull_number']] = numpy.linalg.norm(row[12:22])
        for index, row in test_data.iterrows():
            test_len_dict[row['pull_number']] = numpy.linalg.norm(row[12:22])

        graph = Graph()

        """���Ӻ�ѡ�˵Ķ���"""
        candidates = list(set(train_data['reviewer']))
        for candidate in candidates:
            graph.add_node(nodeType=Node.STR_NODE_TYPE_REVIEWER, contentKey=candidate,
                           description=f"reviewer:{candidate}")

        # ���ڼ�������������֮�����س̶�
        scoreMap = {}
        """����reviewer, reviewer��ϵ"""
        grouped_train_data = train_data.groupby(train_data['pull_number'])
        for pr, group in grouped_train_data:
            reviewers = list(set(group['reviewer'].to_list()))
            reviewers = sorted(reviewers)
            for i in range(0, reviewers.__len__()):
                for j in range(i + 1, reviewers.__len__()):
                    if scoreMap.get((reviewers[i], reviewers[j]), None) is None:
                        scoreMap[(reviewers[i], reviewers[j])] = 0
                    scoreMap[(reviewers[i], reviewers[j])] += 1
                    # reviewer_i = graph.get_node_by_content(Node.STR_NODE_TYPE_REVIEWER, reviewers[i])
                    # reviewer_j = graph.get_node_by_content(Node.STR_NODE_TYPE_REVIEWER, reviewers[j])
                    # # ��Ȩ�ۼ�
                    # graph.add_edge(nodes=[reviewer_i.id, reviewer_j.id],
                    #                edgeType=Edge.STR_EDGE_TYPE_REVIEWER_REVIEWER,
                    #                weight=1,
                    #                description=f" pr review relation between reviewer {reviewers[i]} and reviewer {reviewers[j]}")
        for reviewers, weight in scoreMap.items():
            i, j = reviewers
            reviewer_i = graph.get_node_by_content(Node.STR_NODE_TYPE_REVIEWER, i)
            reviewer_j = graph.get_node_by_content(Node.STR_NODE_TYPE_REVIEWER, j)
            graph.add_edge(nodes=[reviewer_i.id, reviewer_j.id],
                           edgeType=Edge.STR_EDGE_TYPE_REVIEWER_REVIEWER,
                           weight=weight,
                           description=f" pr review relation between reviewer {i} and reviewer {j}")
        print("finish building reviewer<->reviewer relations!  cost time: {0}s".format(datetime.now() - start))

        print("start building reviewer<->ipr relations....")
        test_pr_list = tuple(test_data['pull_number'])  # ��setѹ���ᵼ�º���dis��ȡ��λ
        train_pr_list = tuple(train_data['pull_number'])

        prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])
        cur = 1
        for pr_num in prList:

            print(cur, "  all:", prList.__len__())
            cur += 1

            """���pr�ڵ�"""
            pr_node = graph.add_node(nodeType=Node.STR_NODE_TYPE_PR, contentKey=pr_num, description=f"pr:{pr_num}")

            """��ʼ��p����"""
            p = numpy.zeros((graph.num_nodes, 1))

            for candidate in candidates:
                candidateNode = graph.get_node_by_content(Node.STR_NODE_TYPE_REVIEWER, candidate)
                """�ҵ���ѡ���������pr"""
                commented_pr_df = train_data[train_data['reviewer'] == candidate]
                max_score = commented_pr_df.shape[0]
                commented_pr_df_grouped = commented_pr_df.groupby(commented_pr_df['pull_number'])
                score = 0
                for pr, comments in commented_pr_df_grouped:
                    index_train = train_pr_list.index(pr)
                    index_test = test_pr_list.index(pr_num)
                    score += comments.shape[0] * DIS.iloc[index_test][index_train] / (
                                train_len_dict[pr] * test_len_dict[pr_num])
                score /= max_score

                """����p����"""
                p[candidateNode.id] = score

                """����reviewer->ipr��"""
                graph.add_edge(nodes=[candidateNode.id, pr_node.id],
                               edgeType=Edge.STR_EDGE_TYPE_PR_REVIEW_RELATION,
                               weight=score,
                               description=f" pr review relation between reviewer {candidate} and ipr {pr_num}")
            """����w����"""
            graph.updateW()
            """����q����"""
            q = numpy.zeros((graph.num_nodes, 1))
            q[pr_node.id][0] = 1

            """��������"""
            for c in range(0, 6):  # ����6��
                tmp = numpy.dot(graph.W, p)
                p = (1 - a) * tmp + a * q

            """���ó���p����˭�ķ�����ǰ��"""
            score_dict = {}
            for i in range(0, p.__len__() - 1):
                node = graph.get_node_by_key(i)
                score_dict[node.contentKey] = p[i]

            recommendList.append(
                [x[0] for x in sorted(score_dict.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]])
            answerList.append(test_data_y[pr_num])

            """ɾ�� pr �ڵ�"""
            graph.remove_node_by_key(pr_node.id)

        return recommendList, answerList


if __name__ == '__main__':
    dates = [(2017, 1, 2018, 6)]
    projects = ['opencv']
    for p in projects:
        projectName = p
        """���������0.1-0.9���Եģ�ÿ����Ŀѡ����õ�topk��Ϊ�����û��ͳһ�ˣ���������ȡ��0.5"""
        EARECTrain.testEARECAlgorithm(projectName, dates, filter_train=True, filter_test=True, a=0.9)
