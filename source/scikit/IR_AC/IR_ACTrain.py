# coding=gbk
import math
import os
import time
from datetime import datetime
from math import sqrt

import pandas
from gensim import corpora, models

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
    def testIR_ACAlgorithm(project, dates, filter_train=False, filter_test=False, error_analysis=False,
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

            recommendList, answerList, prList, convertDict, trainSize = IR_ACTrain.algorithmBody(date, project, recommendNum,
                                                                                              filter_train=filter_train,
                                                                                              filter_test=filter_test, test_type=test_type)

            topk, mrr, precisionk, recallk, fmeasurek = \
                DataProcessUtils.judgeRecommend(recommendList, answerList, recommendNum)

            topks.append(topk)
            mrrs.append(mrr)
            precisionks.append(precisionk)
            recallks.append(recallk)
            fmeasureks.append(fmeasurek)

            error_analysis_data = None
            if error_analysis:
                y = date[2]
                m = date[3]
                filename = projectConfig.getIR_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                filter_answer_list = DataProcessUtils.getAnswerListFromChangeTriggerData(project, date, prList,
                                                                                         convertDict, filename,
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
        DataProcessUtils.recommendErrorAnalyzer2(error_analysis_datas, project, 'IR_AC')

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
                            filename = projectConfig.getFPS_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                        else:
                            filename = projectConfig.getFPS_ACDataPath() + os.sep + f'IR_AC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
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

            prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])
            """����Ԥ���һ��pr��Ԥ��"""

            """2020.8.1 ����FPS��pr˳���ǵ������ڸ�Ϊ���򣬱��ں������㷨�Ƽ������Ƚ�"""
            prList.sort()
            prList.pop(0)
            recommendList, answerList = IR_ACTrain.RecommendByIR_AC_INCREMENT(test_data,  test_data_y, recommendNum=recommendNum)

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

        """�ȶ��������������� ֻ���¸���Ȥ������"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'review_user_login', 'label', 'pr_created_at']].copy(deep=True)

        print("before filter:", df.shape)
        df.drop_duplicates(inplace=True)
        print("after filter:", df.shape)
        """�������������ִ���"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pr_number')))
        """�ȳ���������Ϣ����һ��"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'label', 'pr_created_at']].copy(deep=True)
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

        """���Լ�"""
        test_data = wordVectors
        """���Ϊ����"""
        test_data = DataProcessUtils.convertFeatureDictToDataFrame(test_data, featureNum=feature_cnt)
        test_data['pr_number'] = list(df.loc[df['label'] == True]['pr_number'])
        test_data['pr_created_at'] = list(df.loc[df['label'] == True]['pr_number'])

        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[r1, r2, ...]}, ... ,{}]
        """

        test_data_y = {}
        for pull_number in df.loc[df['label'] == True]['pr_number']:
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

        """�ȶ��������������� ֻ���¸���Ȥ������"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'review_user_login', 'label', 'pr_created_at']].copy(deep=True)

        print("before filter:", df.shape)
        df.drop_duplicates(inplace=True)
        print("after filter:", df.shape)
        """�������������ִ���"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pr_number')))
        """�ȳ���������Ϣ����һ��"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'label', 'pr_created_at']].copy(deep=True)
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
        train_data = DataProcessUtils.convertFeatureDictToDataFrame(train_data, featureNum=feature_cnt)
        test_data = DataProcessUtils.convertFeatureDictToDataFrame(test_data, featureNum=feature_cnt)
        train_data['pr_number'] = list(df.loc[df['label'] == False]['pr_number'])
        test_data['pr_number'] = list(df.loc[df['label'] == True]['pr_number'])
        train_data['pr_created_at'] = list(df.loc[df['label'] == False]['pr_number'])
        test_data['pr_created_at'] = list(df.loc[df['label'] == True]['pr_number'])

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

        for targetData in test_data.itertuples(index=False):  # ��ÿһ��case���Ƽ�
            """itertuples ���д����е�ʱ�򷵻س���Ԫ�� >255"""
            targetNum = targetData[-2]
            recommendScore = {}
            for trainData in train_data.itertuples(index=False, name='Pandas'):
                trainNum = trainData[-2]
                reviewers = train_data_y[trainNum]

                """����ʱ���"""
                gap = (targetData[-1] - trainData[-1]).total_seconds() / (3600 * 24)

                """�������ƶȲ��������һ��pr number"""
                score = IR_ACTrain.cos2(targetData[0:targetData.__len__()-3], trainData[0:trainData.__len__()-3])
                score *= math.pow(score, -l)

                for reviewer in reviewers:
                    if recommendScore.get(reviewer, None) is None:
                        recommendScore[reviewer] = 0
                    recommendScore[reviewer] += score

            targetRecommendList = [x[0] for x in
                                   sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]
            # print(targetRecommendList)
            recommendList.append(targetRecommendList)
            answerList.append(test_data_y[targetNum])

        return [recommendList, answerList]

    @staticmethod
    def RecommendByIR_AC_INCREMENT(test_data, test_data_y, recommendNum=5, l=1):
        """ʹ����Ϣ����  
           �����Ƕ��ǩ����
        """""

        recommendList = []  # �����case�Ƽ��б�
        answerList = []

        for index, targetData in test_data.itertuples(index=True):  # ��ÿһ��case���Ƽ�
            """itertuples ���д����е�ʱ�򷵻س���Ԫ�� >255"""
            if index == 0:
                """��һ���޷�����"""
                continue
            targetNum = targetData[-2]  # pr ��dataframe�ĵ����ڶ���
            recommendScore = {}

            tempDf = test_data.loc[test_data[-2] <= targetNum]
            for trainData in tempDf.itertuples(index=False, name='Pandas'):
                trainNum = trainData[-2]
                reviewers = test_data_y[trainNum]

                """����ʱ���"""
                gap = (targetData[-1] - trainData[-1]).total_seconds() / (3600 * 24)

                """�������ƶȲ��������һ��pr number"""
                score = IR_ACTrain.cos2(targetData[0:targetData.__len__() - 3], trainData[0:trainData.__len__() - 3])
                score *= math.pow(gap, -l)
                for reviewer in reviewers:
                    if recommendScore.get(reviewer, None) is None:
                        recommendScore[reviewer] = 0
                    recommendScore[reviewer] += score

            """��������������"""
            if recommendScore.items().__len__() < recommendNum:
                for i in range(0, recommendNum):
                    recommendScore[f'{StringKeyUtils.STR_USER_NONE}_{i}'] = 0

            targetRecommendList = [x[0] for x in
                                   sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]
            # print(targetRecommendList)
            recommendList.append(targetRecommendList)
            answerList.append(test_data_y[targetNum])

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
    # dates = [(2018, 4, 2018, 5), (2018, 4, 2018, 7), (2018, 4, 2018, 10), (2018, 4, 2019, 1),
    #          (2018, 4, 2019, 4)]
    # dates = [(2018, 1, 2019, 5), (2018, 1, 2019, 6), (2018, 1, 2019, 7), (2018, 1, 2019, 8)]
    # dates = [(2017, 1, 2017, 2)]
    dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
             (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
             (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    projects = ['babel', 'symfony']
    for p in projects:
        IR_ACTrain.testIR_ACAlgorithm(p, dates, filter_train=False, filter_test=False, error_analysis=True,
                                   test_type=StringKeyUtils.STR_TEST_TYPE_INCREMENT)
