# coding=gbk
import math
import os
import time
from datetime import datetime

import pandas

from source.config.projectConfig import projectConfig
from source.data.bean.PullRequest import PullRequest
from source.scikit.FPS.FPSAlgorithm import FPSAlgorithm
from source.scikit.service.BeanNumpyHelper import BeanNumpyHelper
from source.scikit.service.DataFrameColumnUtils import DataFrameColumnUtils
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.scikit.service.RecommendMetricUtils import RecommendMetricUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.StringKeyUtils import StringKeyUtils
from source.utils.pandas.pandasHelper import pandasHelper


class FPS_ACTrain:

    @staticmethod
    def TestAlgorithm(project, dates, filter_train=False, filter_test=False, error_analysis=False,
                      test_type=StringKeyUtils.STR_TEST_TYPE_SLIDE):
        """  2020.8.6
        ������������  filter_train ��  filter_test
         �ֱ����������Ƿ�ʹ��change trigger���˵����ݼ�

        2020.8.13 ���Ӳ���test_type������ѵ��������
        test_type_slide ����֮ǰ�Ļ�������
        test_type_increment ��AC�㷨��������ѵ����ϸ����pr
        ��ʱ��  filter_test�������ã�����filter_trainʧЧ
        """
        """���� ѵ������"""

        recommendNum = 5  # �Ƽ�����
        excelName = f'outputFPS_AC_{project}_{filter_train}_{filter_test}_{error_analysis}_{test_type}.xlsx'
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
            recommendList, answerList, prList, convertDict, trainSize = FPS_ACTrain.algorithmBody(date, project,
                                                                                                  recommendNum,
                                                                                                  filter_train=filter_train,
                                                                                                  filter_test=filter_test,
                                                                                                  test_type=test_type)
            """�����Ƽ��б�������"""
            topk, mrr, precisionk, recallk, fmeasurek = \
                DataProcessUtils.judgeRecommend(recommendList, answerList, recommendNum)

            topks.append(topk)
            mrrs.append(mrr)
            precisionks.append(precisionk)
            recallks.append(recallk)
            fmeasureks.append(fmeasurek)

            error_analysis_data = None
            if error_analysis:
                filter_answer_list = None
                if test_type == StringKeyUtils.STR_TEST_TYPE_SLIDE:
                    y = date[2]
                    m = date[3]
                    filename = projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                    filter_answer_list = DataProcessUtils.getAnswerListFromChangeTriggerData(project, date, prList,
                                                                                             convertDict, filename,
                                                                                             'review_user_login',
                                                                                             'pull_number')
                elif test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
                    fileList = []
                    for i in range(date[0] * 12 + date[1], date[2] * 12 + date[3] + 1):  # ��ֵ�������ƴ��
                        y = int((i - i % 12) / 12)
                        m = i % 12
                        if m == 0:
                            m = 12
                            y = y - 1
                        fileList.append(projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv')

                    filter_answer_list = DataProcessUtils.getAnswerListFromChangeTriggerDataByIncrement(project, prList,
                                                                                             convertDict, fileList,
                                                                                             'review_user_login',
                                                                                             'pull_number')

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
            DataProcessUtils.saveResult(excelName, sheetName, topk, mrr, precisionk, recallk, fmeasurek, date,
                                        error_analysis_data)

            """�ļ��ָ�"""
            content = ['']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            content = ['ѵ����', '���Լ�']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())

            print("cost time:", datetime.now() - startTime)

        """�Ƽ�������ӻ�"""
        DataProcessUtils.recommendErrorAnalyzer2(error_analysis_datas, project, f'FPS_AC_{filter_train}_{filter_train}_{test_type}')

        """������ʷ�ۻ�����"""
        DataProcessUtils.saveFinallyResult(excelName, sheetName, topks, mrrs, precisionks, recallks,
                                           fmeasureks, error_analysis_datas)

    @staticmethod
    def preProcessBySlide(df, dates):
        """����˵��
            df����ȡ��dataframe����
            dates:��Ԫ�飬����λ��Ϊ���Ե����� (,,year,month)
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
        """��reviewer�������ֻ����� �洢����ӳ���ֵ�������"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])

        """ʱ��תΪʱ���"""
        df['test'] = df['pr_created_at']
        df['pr_created_at'] = df['pr_created_at'].apply(
            lambda x: time.mktime(time.strptime(x, "%Y-%m-%d %H:%M:%S")))
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pull_number')))

        print("before drop:", df.shape)
        df = df.copy(deep=True)
        df.drop(columns=['review_user_login', 'repo_full_name'], inplace=True)
        df.drop_duplicates(['pull_number', 'commit_sha', 'file_filename'], inplace=True)
        print("after drop:", df.shape)

        """���Ѿ��е����������ͱ�ǩ��ѵ�����Ĳ��"""
        train_data = df.loc[df['label'] == False].copy(deep=True)
        test_data = df.loc[df['label']].copy(deep=True)

        train_data.drop(columns=['label'], inplace=True)
        test_data.drop(columns=['label'], inplace=True)

        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[r1, r2, ...]}, ... ,{}]
        """

        train_data_y = {}
        for pull_number in train_data.drop_duplicates(['pull_number'])['pull_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            train_data_y[pull_number] = reviewers

        test_data_y = {}
        for pull_number in test_data.drop_duplicates(['pull_number'])['pull_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            test_data_y[pull_number] = reviewers

        return train_data, train_data_y, test_data, test_data_y, convertDict

    @staticmethod
    def preProcessByIncrement(df, dates):
        """����˵��
            df����ȡ��dataframe����
            dates:��Ԫ�飬ʱ�����൱�ڶ��ǲ��Լ�, û������
        """

        """ע�⣺ �����ļ����Ѿ�����������"""

        """����NAN"""
        df.dropna(how='any', inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.fillna(value='', inplace=True)

        """��reviewer�������ֻ����� �洢����ӳ���ֵ�������"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        """�ȶ�tag�����"""
        tagDict = dict(list(df.groupby('pull_number')))

        """ʱ��תΪʱ���"""
        df['pr_created_at'] = df['pr_created_at'].apply(
            lambda x: time.mktime(time.strptime(x, "%Y-%m-%d %H:%M:%S")))

        print("before drop:", df.shape)
        df = df.copy(deep=True)
        df.drop(columns=['review_user_login', 'repo_full_name'], inplace=True)
        df.drop_duplicates(['pull_number', 'commit_sha', 'file_filename'], inplace=True)
        print("after drop:", df.shape)

        test_data = df
        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[r1, r2, ...]}, ... ,{}]
        """

        test_data_y = {}
        for pull_number in df.drop_duplicates(['pull_number'])['pull_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            test_data_y[pull_number] = reviewers

        return test_data, test_data_y, convertDict

    @staticmethod
    def algorithmBody(date, project, recommendNum=5, filter_train=True, filter_test=True,
                      test_type=StringKeyUtils.STR_TEST_TYPE_SLIDE):

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

            print(y, m)
            filename = None
            if test_type == StringKeyUtils.STR_TEST_TYPE_SLIDE:
                if i < date[2] * 12 + date[3]:
                    if filter_train:
                        filename = projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                    else:
                        filename = projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    if filter_test:
                        filename = projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                    else:
                        filename = projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            elif test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
                if filter_test:
                    filename = projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getFPS_ACDataPath() + os.sep + f'FPS_AC_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'

            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)

        if test_type == StringKeyUtils.STR_TEST_TYPE_SLIDE:
            """df��Ԥ����"""
            """��������ӳ���ֵ�"""
            train_data, train_data_y, test_data, test_data_y, convertDict = FPS_ACTrain.preProcessBySlide(df, date)

            prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])
            """2020.8.1 ����FPS��pr˳���ǵ������ڸ�Ϊ���򣬱��ں������㷨�Ƽ������Ƚ�"""
            prList.sort()

            recommendList, answerList = FPS_ACTrain.RecommendByFPS_AC_SLIDE(train_data, train_data_y, test_data,
                                                                            test_data_y, recommendNum=recommendNum)

            """�������ز��� ѵ������С��������ͳ��"""

            """��������ѵ���� ���Լ���С"""
            trainSize = (train_data.shape, test_data.shape)
            print(trainSize)

            # """����Ƽ��������ļ�"""
            # DataProcessUtils.saveRecommendList(prList, recommendList, answerList, convertDict)

            return recommendList, answerList, prList, convertDict, trainSize
        elif test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
            """df��Ԥ����"""
            """��������ӳ���ֵ�"""
            test_data, test_data_y, convertDict = FPS_ACTrain.preProcessByIncrement(df, date)

            prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])
            """����Ԥ���һ��pr��Ԥ��"""

            """2020.8.1 ����FPS��pr˳���ǵ������ڸ�Ϊ���򣬱��ں������㷨�Ƽ������Ƚ�"""
            prList.sort()
            prList.pop(0)

            recommendList, answerList = FPS_ACTrain.RecommendByFPS_AC_INCREMENT(test_data, test_data_y, recommendNum=recommendNum)

            """�������ز��� ѵ������С��������ͳ��"""

            """��������ѵ���� ���Լ���С"""
            trainSize = (test_data.shape)
            print(trainSize)

            # """����Ƽ��������ļ�"""
            # DataProcessUtils.saveRecommendList(prList, recommendList, answerList, convertDict)

            return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def RecommendByFPS_AC_SLIDE(train_data, train_data_y, test_data, test_data_y, recommendNum=5, l=1):
        """���ǩ�����FPS"""

        recommendList = []
        answerList = []
        testDict = dict(list(test_data.groupby('pull_number')))
        trainDict = dict(list(train_data.groupby('pull_number')))
        testTuple = sorted(testDict.items(), key=lambda x: x[0], reverse=False)
        for test_pull_number, test_df in testTuple:
            scores = {}  # ��ʼ�������ֵ�
            """�����ȷ��"""
            answerList.append(test_data_y[test_pull_number])
            for train_pull_number, train_df in trainDict.items():
                paths1 = list(train_df['file_filename'])
                paths2 = list(test_df['file_filename'])
                score = 0

                """����ʱ���"""
                gap = (list(test_df['pr_created_at'])[0] -list(train_df['pr_created_at'])[0]) / (3600 * 24)

                for filename1 in paths1:
                    for filename2 in paths2:
                        score += FPSAlgorithm.LCP_2(filename1, filename2) * math.pow(gap, -1)
                score /= paths1.__len__() * paths2.__len__()
                for reviewer in train_data_y[train_pull_number]:
                    if scores.get(reviewer, None) is None:
                        scores[reviewer] = 0
                    scores[reviewer] += score
            recommendList.append([x[0] for x in sorted(scores.items(),
                                                       key=lambda d: d[1], reverse=True)[0:recommendNum]])

        return [recommendList, answerList]

    @staticmethod
    def RecommendByFPS_AC_INCREMENT(test_data, test_data_y, recommendNum=5, l=1):
        """���ǩ�����FPS"""

        """��ȡprList"""
        prList = list(test_data.drop_duplicates(['pull_number'])['pull_number'])
        prList.sort()

        recommendList = []
        answerList = []
        testDict = dict(list(test_data.groupby('pull_number')))
        for pr_index, test_pull_number in enumerate(prList):
            if pr_index == 0:
                """��һ��prû����ʷ  �޷��Ƽ�"""
                continue
            test_df = testDict[test_pull_number]
            scores = {}  # ��ʼ�������ֵ�
            """�����ȷ��"""
            answerList.append(test_data_y[test_pull_number])

            train_pr_list = prList[:pr_index]
            for train_pull_number in train_pr_list:
                train_df = testDict[train_pull_number]
                paths1 = list(train_df['file_filename'])
                paths2 = list(test_df['file_filename'])
                score = 0

                """����ʱ���"""
                gap = (list(test_df['pr_created_at'])[0] - list(train_df['pr_created_at'])[0]) / (3600 * 24)

                for filename1 in paths1:
                    for filename2 in paths2:
                        score += FPSAlgorithm.LCP_2(filename1, filename2) * math.pow(gap, -l)  # ֻ�����ǰ׺
                score /= paths1.__len__() * paths2.__len__()
                for reviewer in test_data_y[train_pull_number]:
                    if scores.get(reviewer, None) is None:
                        scores[reviewer] = 0
                    scores[reviewer] += score

            """��������������"""
            if scores.items().__len__() < recommendNum:
                for i in range(0, recommendNum):
                    scores[f'{StringKeyUtils.STR_USER_NONE}_{i}'] = -1
            recommendList.append([x[0] for x in sorted(scores.items(),
                                                       key=lambda d: d[1], reverse=True)[0:recommendNum]])

        return [recommendList, answerList]


if __name__ == '__main__':
    dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
             (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
             (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    # dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
    #          (2017, 1, 2018, 6)]
    projects = ['opencv', 'cakephp', 'akka', 'xbmc', 'babel', 'symfony', 'brew', 'django', 'netty', 'scikit-learn']
    # projects = ['opencv']
    for p in projects:
        for test_type in [StringKeyUtils.STR_TEST_TYPE_INCREMENT]:
            for t in [False]:
                if test_type == StringKeyUtils.STR_TEST_TYPE_INCREMENT:
                    dates = [(2018, 1, 2018, 12)]
                FPS_ACTrain.TestAlgorithm(p, dates, filter_train=t, filter_test=t, error_analysis=True,
                                          test_type=test_type)
