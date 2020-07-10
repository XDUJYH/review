# coding=gbk
import os
import time
from datetime import datetime

import pandas

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
from source.scikit.service.RecommendMetricUtils import RecommendMetricUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.StringKeyUtils import StringKeyUtils
from source.utils.pandas.pandasHelper import pandasHelper


class PBTrain:

    @staticmethod
    def TestAlgorithm(project, dates):
        """���� ѵ������"""
        recommendNum = 5  # �Ƽ�����
        excelName = f'outputPB_{project}.xlsx'
        sheetName = 'result'

        """��ʼ��excel�ļ�"""
        ExcelHelper().initExcelFile(fileName=excelName, sheetName=sheetName, excel_key_list=['ѵ����', '���Լ�'])
        for date in dates:
            startTime = datetime.now()
            recommendList, answerList, prList, convertDict, trainSize = PBTrain.algorithmBody(date, project,
                                                                                              recommendNum)
            """�����Ƽ��б�������"""
            topk, mrr, precisionk, recallk, fmeasurek = \
                DataProcessUtils.judgeRecommend(recommendList, answerList, recommendNum)

            """���д��excel"""
            DataProcessUtils.saveResult(excelName, sheetName, topk, mrr, precisionk, recallk, fmeasurek, date)

            """�ļ��ָ�"""
            content = ['']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            content = ['ѵ����', '���Լ�']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())

            print("cost time:", datetime.now() - startTime)

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

        """�ȳ���������Ϣ����һ��"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'label']].copy(deep=True)
        df.drop_duplicates(inplace=True)
        df.reset_index(drop=True, inplace=True)

        """�����ռ������ı������ִ�"""
        stopwords = SplitWordHelper().getEnglishStopList()  # ��ȡͨ��Ӣ��ͣ�ô�

        textList = []
        """����������  PB�㷨��ѵ��������dataFrame
           { p1:set1, p2:set2, ... }
        """
        train_data = {}
        test_data = {}
        for row in df.itertuples(index=False, name='Pandas'):
            tempList = []
            """��ȡpull request��number"""
            pr_num = getattr(row, 'pr_number')
            label = getattr(row, 'label')

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

            wordSet = MultisetHelper.WordMultiset()
            wordSet.add(tempList)

            if label == 0:
                train_data[pr_num] = wordSet
            else:
                test_data[pr_num] = wordSet

        print("train size:", train_data.items().__len__())
        print("test size:", test_data.items().__len__())

        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[(r1, s1), (r2, s2), ...]}, ... ,{}]
            
            r ����reviewer
            s ������
        """

        train_data_y = {}
        for pull_number in df.loc[df['label'] == False]['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            tempDf = tagDict[pull_number][['review_user_login', 'comment_body']].copy(deep=True)
            commentDict = dict(list(tempDf.groupby('review_user_login')))
            reviewerList = []
            for reviewer in reviewers:
                commentDf = commentDict[reviewer]
                wordSet = MultisetHelper.WordMultiset()
                for row in commentDf.itertuples(index=False, name='Pandas'):
                    comment = getattr(row, 'comment_body')
                    comment_body_word_list = [x for x in FleshReadableUtils.word_list(comment) if x not in stopwords]
                    """�Ե�������ȡ�ʸ�"""
                    comment_body_word_list = nltkFunction.stemList(comment_body_word_list)
                    wordSet.add(comment_body_word_list)
                reviewerList.append((reviewer, wordSet))
            train_data_y[pull_number] = reviewerList

        test_data_y = {}
        for pull_number in df.loc[df['label'] == True]['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            tempDf = tagDict[pull_number][['review_user_login', 'comment_body']].copy(deep=True)
            commentDict = dict(list(tempDf.groupby('review_user_login')))
            reviewerList = []
            for reviewer in reviewers:
                commentDf = commentDict[reviewer]
                wordSet = MultisetHelper.WordMultiset()
                for row in commentDf.itertuples(index=False, name='Pandas'):
                    comment = getattr(row, 'comment_body')
                    comment_body_word_list = [x for x in FleshReadableUtils.word_list(comment) if x not in stopwords]
                    """�Ե�������ȡ�ʸ�"""
                    comment_body_word_list = nltkFunction.stemList(comment_body_word_list)
                    wordSet.add(comment_body_word_list)
                reviewerList.append((reviewer, wordSet))
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
            filename = projectConfig.getPBDataPath() + os.sep + f'PB_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """��������ӳ���ֵ�"""
        train_data, train_data_y, test_data, test_data_y, convertDict = PBTrain.preProcess(df, date)

        prList = None

        recommendList, answerList = PBTrain.RecommendByPB(train_data, train_data_y, test_data,
                                                          test_data_y, recommendNum=recommendNum)

        """�������ز��� ѵ������С��������ͳ��"""

        """��������ѵ���� ���Լ���С"""
        trainSize = (train_data.items().__len__(), test_data.items().__len__())
        print(trainSize)

        return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def RecommendByPB(train_data, train_data_y, test_data, test_data_y, recommendNum=5):
        """ʹ���û�����
           �����Ƕ��ǩ����
        """""

        recommendList = []  # �����case�Ƽ��б�
        answerList = []

        t1 = datetime.now()
        """�����û�����"""
        candicates = {}
        for pr_num in train_data.keys():
            prSet = train_data[pr_num]
            reviewers = train_data_y[pr_num]
            for reviewer, commentSet in reviewers:
                if candicates.get(reviewer, None) is None:
                    candicates[reviewer] = commentSet.copy()
                    candicates[reviewer].add(prSet)
                else:
                    candicates[reviewer].add(commentSet)
                    candicates[reviewer].add(prSet)
        print("user profile cost time:", datetime.now() - t1)

        for pr_num in test_data.keys():
            recommendScore = {}
            prSet = test_data[pr_num]
            """���μ����ѡ�ߵ����ϵ��"""
            for candicate, profile in candicates.items():
                score = prSet.TverskyIndex(profile, 0, 1)
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
             (2017, 1, 2018, 6)]
    # dates = [(2017, 1, 2017, 2), (2017, 1, 2017, 3), (2017, 1, 2017, 4), (2017, 1, 2017, 5), (2017, 1, 2017, 6),
    #          (2017, 1, 2017, 7)]
    projects = ['cakephp']
    for p in projects:
        PBTrain.TestAlgorithm(p, dates)
