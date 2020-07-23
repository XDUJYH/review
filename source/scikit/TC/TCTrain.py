# coding=gbk
import os
import time
from datetime import datetime

import pandas
from gensim import corpora, models

from source.config.projectConfig import projectConfig
from source.data.bean.PullRequest import PullRequest
from source.nlp.FleshReadableUtils import FleshReadableUtils
from source.nlp.SplitWordHelper import SplitWordHelper
from source.nltk import nltkFunction
from source.scikit.FPS.FPSAlgorithm import FPSAlgorithm
from source.scikit.service import MultisetHelper
from source.scikit.service.BeanNumpyHelper import BeanNumpyHelper
from source.scikit.service.DataFrameColumnUtils import DataFrameColumnUtils
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.scikit.service.MultisetHelper import WordMultiset
from source.scikit.service.RecommendMetricUtils import RecommendMetricUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.StringKeyUtils import StringKeyUtils
from source.utils.pandas.pandasHelper import pandasHelper


class TCTrain:

    """LDA����ģ�����������ߵĻ��� TCȡ֮Topic"""

    @staticmethod
    def TestAlgorithm(project, dates):
        """���� ѵ������"""
        recommendNum = 5  # �Ƽ�����
        excelName = f'outputTC_{project}.xlsx'
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
            recommendList, answerList, prList, convertDict, trainSize = TCTrain.algorithmBody(date, project,
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

        t1 = datetime.now()

        """����NAN"""
        df.dropna(how='any', inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.fillna(value='', inplace=True)

        """��df���һ�б�ʶѵ�����Ͳ��Լ�"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == dates[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == dates[3]))
        """��reviewer�������ֻ����� �洢����ӳ���ֵ�������"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pr_number')))

        commentDf = df[['pr_number', 'review_user_login', 'comment_body', 'label']].copy(deep=True)

        """�����ռ������ı������ִ�"""
        stopwords = SplitWordHelper().getEnglishStopList()  # ��ȡͨ��Ӣ��ͣ�ô�

        """�ȳ���������Ϣ����һ��"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'label']].copy(deep=True)
        df.drop_duplicates(inplace=True)
        df.reset_index(drop=True, inplace=True)

        """ѵ���Ͳ������ָ�"""
        df_train = df.loc[df['label'] == 0].copy(deep=True)
        df_test = df.loc[df['label'] == 1].copy(deep=True)
        df_test.reset_index(drop=True, inplace=True)

        """�ռ�ѵ�����е�pr���ı���Ϊ �ĵ���LDA��ȡ����"""
        trainTextList = []
        testTextList = []
        for row in df.itertuples(index=False, name='Pandas'):
            tempList = []
            """��ȡpull request��number"""
            pr_num = getattr(row, 'pr_number')
            label = getattr(row, 'label')

            """��ȡpull request�ı���"""
            pr_title = getattr(row, 'pr_title')
            pr_title_word_list = [x for x in FleshReadableUtils.word_list(pr_title) if x not in stopwords]
            """�Ե�������ȡ�ʸ�"""
            pr_title_word_list = nltkFunction.stemList(pr_title_word_list)
            tempList.extend(pr_title_word_list)

            """pull request��body"""
            pr_body = getattr(row, 'pr_body')
            pr_body_word_list = [x for x in FleshReadableUtils.word_list(pr_body) if x not in stopwords]
            """�Ե�������ȡ�ʸ�"""
            pr_body_word_list = nltkFunction.stemList(pr_body_word_list)
            tempList.extend(pr_body_word_list)

            if label == 0:
                trainTextList.append(tempList)
            elif label == 1:
                testTextList.append(tempList)

        """�ռ� ѵ�����е�comment"""
        trainCommentList = []
        review_comment_map = {}  # pr -> [(reviewer, [w1, w2, w3]), .....]
        for row in commentDf.itertuples(index=False, name='Pandas'):
            tempList = []
            """��ȡpull request��number"""
            pr_num = getattr(row, 'pr_number')
            label = getattr(row, 'label')
            reviewer = getattr(row, 'review_user_login')

            """��ȡpull request�ı���"""
            comment_body = getattr(row, 'comment_body')
            comment_body_word_list = [x for x in FleshReadableUtils.word_list(comment_body) if x not in stopwords]
            """�Ե�������ȡ�ʸ�"""
            comment_body_word_list = nltkFunction.stemList(comment_body_word_list)
            tempList.extend(comment_body_word_list)

            if review_comment_map.get(pr_num, None) is None:
                review_comment_map[pr_num] = []

            if label == 0:
                review_comment_map[pr_num].append((reviewer, tempList.copy()))
                trainCommentList.append(tempList)

        """����LDAģ����ȡ����"""
        # ����������ģ�͹����Ĳ����ˣ����ȹ�����Ƶ����
        allTextList = []
        allTextList.extend(trainTextList)
        allTextList.extend(trainCommentList)
        dictionary = corpora.Dictionary(trainTextList)
        corpus = [dictionary.doc2bow(text) for text in trainTextList]
        lda = models.LdaModel(corpus=corpus, id2word=dictionary, num_topics=20)
        topic_list = lda.print_topics(20)
        print("20������ĵ��ʷֲ�Ϊ��\n")
        for topic in topic_list:
            print(topic)

        """����ѵ�����Ͳ��Լ����������ֲ�
           pr_num -> {[(t1, p1), (t2, p2), .....]}
        """
        train_data = {}
        test_data = {}
        for index, d in enumerate(lda.get_document_topics([dictionary.doc2bow(text) for text in trainTextList])):
            train_data[df_train['pr_number'][index]] = d
        for index, d in enumerate(lda.get_document_topics([dictionary.doc2bow(text) for text in testTextList])):
            test_data[df_test['pr_number'][index]] = d

        train_data_y = {}  # pr -> [(reviewer, [(comment1), (comment2) ...])]
        for pull_number in df.loc[df['label'] == False]['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            reviewerList = []
            for reviewer in reviewers:
                commentTopicList = []
                for r, words in review_comment_map[pull_number]:
                    if r == reviewer:
                        commentTopicList.append(words)
                commentTopicList = lda.get_document_topics([dictionary.doc2bow(text) for text in commentTopicList])
                reviewerList.append((reviewer, [x for x in commentTopicList]))
            train_data_y[pull_number] = reviewerList

        test_data_y = {}
        for pull_number in df.loc[df['label'] == True]['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            reviewerList = []
            for reviewer in reviewers:
                commentTopicList = []
                for r, words in review_comment_map[pull_number]:
                    if r == reviewer:
                        commentTopicList.append(words)
                commentTopicList = lda.get_document_topics([dictionary.doc2bow(text) for text in commentTopicList])
                reviewerList.append((reviewer, commentTopicList))
            test_data_y[pull_number] = reviewerList

        print("preprocess cost time:", datetime.now() - t1)
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
            filename = projectConfig.getTCDataPath() + os.sep + f'TC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """��������ӳ���ֵ�"""
        train_data, train_data_y, test_data, test_data_y, convertDict = TCTrain.preProcess(df, date)

        prList = list(test_data.keys())
        prList.sort()

        recommendList, answerList = TCTrain.RecommendByTC(train_data, train_data_y, test_data,
                                                          test_data_y, recommendNum=recommendNum)

        """�������ز��� ѵ������С��������ͳ��"""

        """��������ѵ���� ���Լ���С"""
        trainSize = (train_data.items().__len__(), test_data.items().__len__())
        print(trainSize)

        return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def RecommendByTC(train_data, train_data_y, test_data, test_data_y, recommendNum=5):
        """ʹ��LDA ���⽨���û�����
           �����Ƕ��ǩ����
        """""

        recommendList = []  # �����case�Ƽ��б�
        answerList = []

        t1 = datetime.now()
        """ͨ��LDA�����û�����  ���ö��ؼ�"""
        candicates = {}
        allSet = WordMultiset()
        for pr_num in train_data.keys():
            prSet = train_data[pr_num]
            allSet.addByTuple(prSet)
            reviewers = train_data_y[pr_num]
            for reviewer, commentSetList in reviewers:
                if candicates.get(reviewer, None) is None:
                    candicates[reviewer] = WordMultiset()
                    candicates[reviewer].addByTuple(prSet)
                    for comment in commentSetList:
                        candicates[reviewer].addByTuple(comment)
                else:
                    candicates[reviewer].addByTuple(prSet)
                    for comment in commentSetList:
                        candicates[reviewer].addByTuple(comment)

        for v in candicates.values():
            allSet.add(v)
        for candicate, profile in candicates.items():
            profile.divide(allSet)
            # profile.equalization()
        print("user profile cost time:", datetime.now() - t1)

        prList = list(test_data.keys())
        prList.sort()

        for pr_num in prList:
            recommendScore = {}
            prSet = WordMultiset()
            prSet.addByTuple(test_data[pr_num])
            """���μ����ѡ�ߵ����ϵ��"""
            for candicate, profile in candicates.items():
                score = prSet.multiply(profile)
                recommendScore[candicate] = score
            targetRecommendList = [x[0] for x in
                                   sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]

            recommendList.append(targetRecommendList)
            answerList.append([x[0] for x in test_data_y[pr_num]])

        return [recommendList, answerList]


if __name__ == '__main__':
    # dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
    #          (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
    #          (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
             (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
             (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    # dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
    #          (2017, 1, 2018, 6)]
    # dates = [(2017, 1, 2017, 2), (2017, 1, 2017, 3), (2017, 1, 2017, 4), (2017, 1, 2017, 5), (2017, 1, 2017, 6),
    #          (2017, 1, 2017, 7)]
    projects = ['opencv', 'cakephp', 'yarn', 'akka', 'django', 'react']
    for p in projects:
        TCTrain.TestAlgorithm(p, dates)
