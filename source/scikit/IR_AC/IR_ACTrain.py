# coding=gbk
import math
import os
import time
from datetime import datetime
from math import sqrt

import numpy
import pandas
from gensim import corpora, models
from pandas import DataFrame

from source.config.projectConfig import projectConfig
from source.nlp.FleshReadableUtils import FleshReadableUtils
from source.nlp.SplitWordHelper import SplitWordHelper
from source.nltk import nltkFunction
from source.scikit.ML.MLTrain import MLTrain
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.StringKeyUtils import StringKeyUtils
from source.utils.pandas.pandasHelper import pandasHelper


class IR_ACTrain:
    """��Ϊ������Ϣ������reviewer�Ƽ�  ������AC�㷨�ᵽ�ķ�ʽ"""

    @staticmethod
    def testAlgorithm(project, dates, filter_train=False, filter_test=False, error_analysis=False,
                      test_type=StringKeyUtils.STR_TEST_TYPE_SLIDE):  # ���case, Ԫ������ܹ���ʱ����,���һ�������ڲ���
        """
           algorithm : ������Ϣ����
        """

        recommendNum = 5  # �Ƽ�����
        excelName = f'outputIR_AC_{project}_{filter_train}_{filter_test}_{error_analysis}.xlsx'
        sheetName = 'result'

        """�����ۻ�����"""
        topks = []
        mrrs = []
        precisionks = []
        recallks = []
        fmeasureks = []
        recommend_positive_success_pr_ratios = []  # pr �����Ƽ��ɹ���ѡ�ı���
        recommend_positive_success_time_ratios = []  # �Ƽ�pr * �˴� �����Ƽ��ɹ���ѡ��Ƶ�α���
        recommend_negative_success_pr_ratios = []  # pr �����Ƽ���ѡHit �����˵���pr�ı���
        recommend_negative_success_time_ratios = []  # �Ƽ�pr * �˴������Ƽ���ѡHit ���Ǳ��˵���pr�ı���
        recommend_positive_fail_pr_ratios = []  # pr �����Ƽ���ѡ�Ƽ������pr����
        recommend_positive_fail_time_ratios = []  # pr ����pr * �˴����Ƽ������Ƶ�α���
        recommend_negative_fail_pr_ratios = []  # pr �����Ƽ���ѡ��֪���Ƿ���ȷ�ı���
        recommend_negative_fail_time_ratios = []  # pr����pr * �˴��в�֪���Ƿ���ȷ�ı���
        error_analysis_datas = None

        """��ʼ��excel�ļ�"""
        ExcelHelper().initExcelFile(fileName=excelName, sheetName=sheetName, excel_key_list=['ѵ����', '���Լ�'])
        for date in dates:
            startTime = datetime.now()
            """�����Ƽ��б�������"""

            recommendList, answerList, prList, convertDict, trainSize = IR_ACTrain.algorithmBody(date, project,
                                                                                                 recommendNum,
                                                                                                 filter_train=filter_train,
                                                                                                 filter_test=filter_test,
                                                                                                 test_type=test_type)

            topk, mrr, precisionk, recallk, fmeasurek = \
                DataProcessUtils.judgeRecommend(recommendList, answerList, recommendNum)

            topks.append(topk)
            mrrs.append(mrr)
            precisionks.append(precisionk)
            recallks.append(recallk)
            fmeasureks.append(fmeasurek)

            error_analysis_data = None
            filter_answer_list = None
            if error_analysis:
                if test_type == StringKeyUtils.STR_TEST_TYPE_SLIDE:
                    y = date[2]
                    m = date[3]
                    filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                    filter_answer_list = DataProcessUtils.getAnswerListFromChangeTriggerData(project, date, prList,
                                                                                             convertDict, filename,
                                                                                             'review_user_login',
                                                                                             'pr_number')
                elif test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
                    fileList = []
                    for i in range(date[0] * 12 + date[1], date[2] * 12 + date[3] + 1):  # ��ֵ�������ƴ��
                        y = int((i - i % 12) / 12)
                        m = i % 12
                        if m == 0:
                            m = 12
                            y = y - 1
                        fileList.append(
                            projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv')

                    filter_answer_list = DataProcessUtils.getAnswerListFromChangeTriggerDataByIncrement(project, prList,
                                                                                                        convertDict,
                                                                                                        fileList,
                                                                                                        'review_user_login',
                                                                                                        'pr_number')

                # recommend_positive_success_pr_ratio, recommend_positive_success_time_ratio, recommend_negative_success_pr_ratio, \
                # recommend_negative_success_time_ratio, recommend_positive_fail_pr_ratio, recommend_positive_fail_time_ratio, \
                # recommend_negative_fail_pr_ratio, recommend_negative_fail_time_ratio = DataProcessUtils.errorAnalysis(
                #     recommendList, answerList, filter_answer_list, recommendNum)
                # error_analysis_data = [recommend_positive_success_pr_ratio, recommend_positive_success_time_ratio,
                #                        recommend_negative_success_pr_ratio, recommend_negative_success_time_ratio,
                #                        recommend_positive_fail_pr_ratio, recommend_positive_fail_time_ratio,
                #                        recommend_negative_fail_pr_ratio, recommend_negative_fail_time_ratio]

                recommend_positive_success_pr_ratio, recommend_negative_success_pr_ratio, recommend_positive_fail_pr_ratio, \
                recommend_negative_fail_pr_ratio = DataProcessUtils.errorAnalysis(
                    recommendList, answerList, filter_answer_list, recommendNum)
                error_analysis_data = [recommend_positive_success_pr_ratio,
                                       recommend_negative_success_pr_ratio,
                                       recommend_positive_fail_pr_ratio,
                                       recommend_negative_fail_pr_ratio]

                # recommend_positive_success_pr_ratios.append(recommend_positive_success_pr_ratio)
                # recommend_positive_success_time_ratios.append(recommend_positive_success_time_ratio)
                # recommend_negative_success_pr_ratios.append(recommend_negative_success_pr_ratio)
                # recommend_negative_success_time_ratios.append(recommend_negative_success_time_ratio)
                # recommend_positive_fail_pr_ratios.append(recommend_positive_fail_pr_ratio)
                # recommend_positive_fail_time_ratios.append(recommend_positive_fail_time_ratio)
                # recommend_negative_fail_pr_ratios.append(recommend_negative_fail_pr_ratio)
                # recommend_negative_fail_time_ratios.append(recommend_negative_fail_time_ratio)

                recommend_positive_success_pr_ratios.append(recommend_positive_success_pr_ratio)
                recommend_negative_success_pr_ratios.append(recommend_negative_success_pr_ratio)
                recommend_positive_fail_pr_ratios.append(recommend_positive_fail_pr_ratio)
                recommend_negative_fail_pr_ratios.append(recommend_negative_fail_pr_ratio)

            if error_analysis_data:
                # error_analysis_datas = [recommend_positive_success_pr_ratios, recommend_positive_success_time_ratios,
                #                         recommend_negative_success_pr_ratios, recommend_negative_success_time_ratios,
                #                         recommend_positive_fail_pr_ratios, recommend_positive_fail_time_ratios,
                #                         recommend_negative_fail_pr_ratios, recommend_negative_fail_time_ratios]
                error_analysis_datas = [recommend_positive_success_pr_ratios,
                                        recommend_negative_success_pr_ratios,
                                        recommend_positive_fail_pr_ratios,
                                        recommend_negative_fail_pr_ratios]

            """���д��excel"""
            DataProcessUtils.saveResult(excelName, sheetName, topk, mrr, precisionk, recallk, fmeasurek, date)

            """�ļ��ָ�"""
            content = ['']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            content = ['ѵ����', '���Լ�']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            print("cost time:", datetime.now() - startTime)

        """�Ƽ�������ӻ�"""
        DataProcessUtils.recommendErrorAnalyzer2(error_analysis_datas, project,
                                                 f'IR_AC_{test_type}_{filter_train}_{filter_test}')

        """������ʷ�ۻ�����"""
        DataProcessUtils.saveFinallyResult(excelName, sheetName, topks, mrrs, precisionks, recallks,
                                           fmeasureks, error_analysis_datas)

    @staticmethod
    def algorithmBody(date, project, recommendNum=5, filter_train=False, filter_test=False,
                      test_type=StringKeyUtils.STR_TEST_TYPE_SLIDE):

        """�ṩ�������ں���Ŀ����
           �����Ƽ��б�ʹ�
           ����ӿڿ��Ա�����㷨����
        """
        df = None
        for i in range(date[0] * 12 + date[1], date[2] * 12 + date[3] + 1):  # ��ֵ�������ƴ��
            y = int((i - i % 12) / 12)
            m = i % 12
            if m == 0:
                m = 12
                y = y - 1

            print(y, m)
            filename = None
            if test_type == StringKeyUtils.STR_TEST_TYPE_SLIDE:
                if i < date[2] * 12 + date[3]:
                    if filter_train:
                        filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                    else:
                        filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    if filter_test:
                        filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                    else:
                        filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            elif test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
                if filter_test:
                    filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        if test_type == StringKeyUtils.STR_TEST_TYPE_SLIDE:
            df.reset_index(inplace=True, drop=True)
            """df��Ԥ����"""
            """Ԥ�����������ز���pr�б� 2020.4.11"""
            train_data, train_data_y, test_data, test_data_y, convertDict = IR_ACTrain.preProcessBySlide(df, date)

            prList = list(test_data['pr_number'])

            """�����㷨����Ƽ��б�"""
            recommendList, answerList = IR_ACTrain.RecommendByIR_AC_SLIDE(train_data, train_data_y, test_data,
                                                                          test_data_y, recommendNum=recommendNum)
            trainSize = (train_data.shape[0], test_data.shape[0])
            return recommendList, answerList, prList, convertDict, trainSize
        elif test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
            """df��Ԥ����"""
            """��������ӳ���ֵ�"""
            test_data, test_data_y, convertDict = IR_ACTrain.preProcessByIncrement(df, date)

            prList = list(test_data.drop_duplicates(['pr_number'])['pr_number'])
            """����Ԥ���һ��pr��Ԥ��"""
            prList.sort()
            prList.pop(0)
            recommendList, answerList = IR_ACTrain.RecommendByIR_AC_INCREMENT(test_data, test_data_y,
                                                                              recommendNum=recommendNum)

            """�������ز��� ѵ������С��������ͳ��"""

            """��������ѵ���� ���Լ���С"""
            trainSize = (test_data.shape)
            print(trainSize)

            # """����Ƽ��������ļ�"""
            # DataProcessUtils.saveRecommendList(prList, recommendList, answerList, convertDict)

            return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def preProcessByIncrement(df, dates):
        """����˵��
         df����ȡ��dataframe����
         dates:��Ϊ���Ե�������Ԫ��
        """
        """ע�⣺ �����ļ����Ѿ�����������"""

        """����NAN"""
        df.dropna(how='any', inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.fillna(value='', inplace=True)

        """����ʱ��ת��Ϊʱ���"""
        df['pr_created_at'] = df['pr_created_at'].apply(lambda x: time.mktime(time.strptime(x, "%Y-%m-%d %H:%M:%S")))
        df['pr_created_at'] = df['pr_created_at'] / (2400 * 36)

        """�ȶ��������������� ֻ���¸���Ȥ������"""
        df = df[['pr_number', 'pr_title', 'review_user_login', 'pr_created_at']].copy(deep=True)

        print("before filter:", df.shape)
        df.drop_duplicates(inplace=True)
        print("after filter:", df.shape)
        """�������������ִ���"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pr_number')))
        """�ȳ���������Ϣ����һ��"""
        df = df[['pr_number', 'pr_title', 'pr_created_at']].copy(deep=True)
        df.drop_duplicates(inplace=True)
        df.reset_index(drop=True, inplace=True)

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

        """���Լ�"""
        test_data = wordVectors
        """���Ϊ����"""
        test_data = DataProcessUtils.convertFeatureDictToDataFrame(test_data, featureNum=feature_cnt)
        test_data['pr_number'] = list(df['pr_number'])
        test_data['pr_created_at'] = list(df['pr_created_at'])
        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[r1, r2, ...]}, ... ,{}]
        """

        test_data_y = {}
        for pull_number in list(df['pr_number']):
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            test_data_y[pull_number] = reviewers

        """train_data ,test_data ���һ����pr number test_data_y ����ʽ��dict"""
        return test_data, test_data_y, convertDict

    @staticmethod
    def preProcessBySlide(df, dates):
        """����˵��
         df����ȡ��dataframe����
         dates:��Ϊ���Ե�������Ԫ��
        """
        """ע�⣺ �����ļ����Ѿ�����������"""

        """����NAN"""
        df.dropna(how='any', inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.fillna(value='', inplace=True)

        """��df���һ�б�ʶѵ�����Ͳ��Լ�"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == dates[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == dates[3]))

        """����ʱ��ת��Ϊʱ���"""
        df['pr_created_at'] = df['pr_created_at'].apply(lambda x: time.mktime(time.strptime(x, "%Y-%m-%d %H:%M:%S")))
        df['pr_created_at'] = df['pr_created_at'] / (24 * 3600)

        """�ȶ��������������� ֻ���¸���Ȥ������"""
        df = df[['pr_number', 'pr_title', 'review_user_login', 'label', 'pr_created_at']].copy(deep=True)

        print("before filter:", df.shape)
        df.drop_duplicates(inplace=True)
        print("after filter:", df.shape)
        """�������������ִ���"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pr_number')))
        """�ȳ���������Ϣ����һ��"""
        df = df[['pr_number', 'pr_title', 'label', 'pr_created_at']].copy(deep=True)
        df.drop_duplicates(inplace=True)
        df.reset_index(drop=True, inplace=True)

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
        train_data = DataProcessUtils.convertFeatureDictToDataFrame(train_data, featureNum=feature_cnt)
        test_data = DataProcessUtils.convertFeatureDictToDataFrame(test_data, featureNum=feature_cnt)
        train_data['pr_number'] = list(df.loc[df['label'] == False]['pr_number'])
        test_data['pr_number'] = list(df.loc[df['label'] == True]['pr_number'])
        train_data['pr_created_at'] = list(df.loc[df['label'] == False]['pr_created_at'])
        test_data['pr_created_at'] = list(df.loc[df['label'] == True]['pr_created_at'])

        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[r1, r2, ...]}, ... ,{}]
        """

        train_data_y = {}
        for pull_number in df.loc[df['label'] == False]['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            train_data_y[pull_number] = reviewers

        test_data_y = {}
        for pull_number in df.loc[df['label'] == True]['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            test_data_y[pull_number] = reviewers

        """train_data ,test_data ���һ����pr number test_data_y ����ʽ��dict"""
        return train_data, train_data_y, test_data, test_data_y, convertDict

    @staticmethod
    def RecommendByIR_AC_SLIDE(train_data, train_data_y, test_data, test_data_y, recommendNum=5, l=-1):
        """ʹ����Ϣ����  
           �����Ƕ��ǩ����
        """""

        recommendList = []  # �����case�Ƽ��б�
        answerList = []

        """��IR ����˷��Ż�"""
        """����train_data�ľ���"""
        df_train = train_data.copy(deep=True)
        df_train.drop(columns=['pr_created_at', 'pr_number'], inplace=True)
        """����test_data����"""
        df_test = test_data.copy(deep=True)
        df_test.drop(columns=['pr_created_at', 'pr_number'], inplace=True)

        """�������"""
        DIS = DataFrame(numpy.dot(df_test, df_train.T))  # train_num x test_num

        test_pr_list = tuple(test_data['pr_number'])
        train_pr_list = tuple(train_data['pr_number'])
        test_time_list = tuple(test_data['pr_created_at'])
        train_time_list = tuple(train_data['pr_created_at'])

        for index_test, pr_test in enumerate(test_pr_list):
            print(index_test)
            time1 = test_time_list[index_test]
            recommendScore = {}
            for index_train, pr_train in enumerate(train_pr_list):
                reviewers = train_data_y[pr_train]
                time2 = train_time_list[index_train]
                """����ʱ���"""
                gap = (time1 - time2)
                """�������ƶȲ��������һ��pr number"""
                score = DIS.iloc[index_test][index_train]
                score *= math.pow(gap, -l)
                #
                for reviewer in reviewers:
                    if recommendScore.get(reviewer, None) is None:
                        recommendScore[reviewer] = 0
                    recommendScore[reviewer] += score

            targetRecommendList = [x[0] for x in
                                   sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]
            # print(targetRecommendList)
            recommendList.append(targetRecommendList)
            answerList.append(test_data_y[pr_test])

        return [recommendList, answerList]

    @staticmethod
    def RecommendByIR_AC_INCREMENT(test_data, test_data_y, recommendNum=5, l=1):
        """ʹ����Ϣ����  
           �����Ƕ��ǩ����
        """""

        recommendList = []  # �����case�Ƽ��б�
        answerList = []

        """��IR ����˷��Ż�"""
        """����test_data����"""
        df_test = test_data.copy(deep=True)
        df_test.drop(columns=['pr_number', 'pr_created_at'], inplace=True)

        """�������"""
        DIS = DataFrame(numpy.dot(df_test, df_test.T))  # train_num x test_num

        test_data.sort_values(by=['pr_number'], inplace=True, ascending=True)
        prList = tuple(test_data['pr_number'])
        test_time_list = tuple(test_data['pr_created_at'])

        for test_index, test_pull_number in enumerate(prList):
            if test_index == 0:
                """��һ��prû����ʷ  �޷��Ƽ�"""
                continue
            print("index:", test_index, " now:", prList.__len__())
            recommendScore = {}
            """�����ȷ��"""
            time1 = test_time_list[test_index]

            train_pr_list = prList[:test_index]
            for train_index, train_pull_number in enumerate(train_pr_list):
                time2 = test_time_list[train_index]
                score = DIS.iloc[test_index][train_index]
                """����ʱ���"""
                gap = (time1 - time2)
                """�������ƶȲ��������һ��pr number"""
                score *= math.pow(gap, -l)
                for reviewer in test_data_y[train_pull_number]:
                    if recommendScore.get(reviewer, None) is None:
                        recommendScore[reviewer] = 0
                    recommendScore[reviewer] += score

            """��������������"""
            if recommendScore.items().__len__() < recommendNum:
                for i in range(0, recommendNum):
                    recommendScore[f'{StringKeyUtils.STR_USER_NONE}_{i}'] = 0

            targetRecommendList = [x[0] for x in
                                   sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]
            recommendList.append(targetRecommendList)
            answerList.append(test_data_y[test_pull_number])

        return [recommendList, answerList]

    @staticmethod
    def cos(dict1, dict2):
        """������������ϡ������ֵ�ļ�������"""
        if isinstance(dict1, dict) and isinstance(dict2, dict):
            """�ȼ���ģ��"""
            l1 = 0
            for v in dict1.values():
                l1 += v * v
            l2 = 0
            for v in dict2.values():
                l2 += v * v

            mul = 0
            """�����������"""
            for key in dict1.keys():
                if dict2.get(key, None) is not None:
                    mul += dict1[key] * dict2[key]

            if mul == 0:
                return 0
            return mul / (sqrt(l1) * sqrt(l2))

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
        return mul / (sqrt(l1) * sqrt(l2))


if __name__ == '__main__':
    # dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
    #          (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
    #          (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    # dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
    #          (2017, 1, 2018, 6)]
    dates = [(2018, 1, 2018, 2)]
    # projects = ['opencv', 'cakephp', 'akka', 'xbmc', 'babel', 'symfony', 'brew', 'django', 'netty', 'scikit-learn']
    projects = ['opencv']
    for p in projects:
        for test_type in [StringKeyUtils.STR_TEST_TYPE_SLIDE]:
            for t in [False]:
                if test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
                    dates = [(2018, 1, 2018, 2)]
                IR_ACTrain.testAlgorithm(p, dates, filter_train=t, filter_test=t, error_analysis=True, test_type=test_type)
