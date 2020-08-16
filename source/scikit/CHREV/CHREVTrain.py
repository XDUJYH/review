# coding=gbk
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
from source.scikit.XF.XFTrain import XFTrain
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.pandas.pandasHelper import pandasHelper


class CHREVTrain:
    """�㷨 CHREV �Ƽ�"""

    @staticmethod
    def testCHREVAlgorithm(project, dates, filter_train=False, filter_test=False, error_analysis=False):
        # ���case, Ԫ������ܹ���ʱ����,���һ�������ڲ���
        recommendNum = 5  # �Ƽ�����
        excelName = f'outputCHREV_{project}_{filter_train}_{filter_test}_{error_analysis}.xlsx'
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

            recommendList, answerList, prList, convertDict, trainSize = CHREVTrain.algorithmBody(date, project, recommendNum,
                                                                                                 filter_test=filter_test,
                                                                                                 filter_train=filter_train)

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
                y = date[2]
                m = date[3]
                filename = projectConfig.getCHREVDataPath() + os.sep + f'CHREV_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
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
            DataProcessUtils.saveResult(excelName, sheetName, topk, mrr, precisionk, recallk, fmeasurek, date, error_analysis_data)

            """�����Ƽ����������"""
            DataProcessUtils.saveRecommendList(prList, recommendList,
                                               answerList, convertDict, filter_answer_list=filter_answer_list,
                                               key=project + str(date) + str(filter_train) + str(filter_test))

            """�ļ��ָ�"""
            content = ['']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            content = ['ѵ����', '���Լ�']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            print("cost time:", datetime.now() - startTime)

        """�Ƽ�������ӻ�"""
        DataProcessUtils.recommendErrorAnalyzer2(error_analysis_datas, project, f'CHREV_{filter_train}_{filter_test}')

        """������ʷ�ۻ�����"""
        DataProcessUtils.saveFinallyResult(excelName, sheetName, topks, mrrs, precisionks, recallks,
                                           fmeasureks, error_analysis_datas)


    @staticmethod
    def algorithmBody(date, project, recommendNum=5, filter_train=False, filter_test=False):

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

            if i < date[2] * 12 + date[3]:
                if filter_train:
                    filename = projectConfig.getCHREVDataPath() + os.sep + f'CHREV_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getCHREVDataPath() + os.sep + f'CHREV_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            else:
                if filter_test:
                    filename = projectConfig.getCHREVDataPath() + os.sep + f'CHREV_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getCHREVDataPath() + os.sep + f'CHREV_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'

            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """Ԥ�����������ز���pr�б� 2020.4.11"""
        train_data, train_data_y, test_data, test_data_y, convertDict = CHREVTrain.preProcess(df, date)

        prList = list(set(test_data['pr_number']))
        prList.sort()

        """�����㷨����Ƽ��б�"""
        recommendList, answerList = CHREVTrain.RecommendByCHREV(train_data, train_data_y, test_data,
                                                          test_data_y, recommendNum=recommendNum)
        trainSize = (train_data.shape[0], test_data.shape[0])
        return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def preProcess(df, dates):
        """����˵��
         df����ȡ��dataframe����
         dates:��Ϊ���Ե�������Ԫ��
        """
        """ע�⣺ �����ļ����Ѿ�����������"""

        """issue comment ��  review comment��ע��"""

        """����NAN"""
        # df.dropna(how='any', inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.fillna(value='', inplace=True)

        """��df���һ�б�ʶѵ�����Ͳ��Լ�"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == dates[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == dates[3]))

        """�������������ִ���"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        df['comment_at'] = df['comment_at'].apply(lambda x: time.strptime(x, "%Y-%m-%d %H:%M:%S"))
        """�� comment_at �������Ӿ��������ı�ʶ"""
        df['day'] = df['comment_at'].apply(lambda x: 10000 * x.tm_year + 100 * x.tm_mon + x.tm_mday)  # 20200821

        """�ȶ�tag�����"""
        temp_df = df.copy(deep=True)
        temp_df.drop(columns=['filename'], inplace=True)
        temp_df.drop_duplicates(inplace=True)
        tagDict = dict(list(temp_df.groupby('pr_number')))

        """�ȳ���������Ϣ����һ��"""
        df = df[['pr_number', 'filename', 'label']].copy(deep=True)
        df.drop_duplicates(inplace=True)
        df.reset_index(drop=True, inplace=True)

        """���Ѿ��е����������ͱ�ǩ��ѵ�����Ĳ��"""
        train_data = df.loc[df['label'] == False].copy(deep=True)
        test_data = df.loc[df['label']].copy(deep=True)

        train_data.drop(columns=['label'], inplace=True)
        test_data.drop(columns=['label'], inplace=True)

        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[(r1, d1), (r2, d2), ...]}, ... ,{}]
        """

        train_data_y = {}
        for pull_number in df.loc[df['label'] == False]['pr_number']:
            tempDf = tagDict[pull_number]
            reviewers = []
            for row in tempDf.itertuples(index=False, name='Pandas'):
                r = getattr(row, 'review_user_login')
                comment_node_id = getattr(row, 'comment_node_id')
                day = getattr(row, 'day')
                reviewers.append((r, comment_node_id, day))
            train_data_y[pull_number] = reviewers

        test_data_y = {}
        for pull_number in df.loc[df['label'] == True]['pr_number']:
            tempDf = tagDict[pull_number]
            reviewers = []
            for row in tempDf.itertuples(index=False, name='Pandas'):
                r = getattr(row, 'review_user_login')
                comment_node_id = getattr(row, 'comment_node_id')
                day = getattr(row, 'day')
                reviewers.append((r, comment_node_id, day))
            test_data_y[pull_number] = reviewers

        """train_data ,test_data ���һ����pr number test_data_y ����ʽ��dict"""
        return train_data, train_data_y, test_data, test_data_y, convertDict

    @staticmethod
    def getPackageLevelPath(filename, level):
        """����һ��·�������ػ��˶�Ӧ�ȼ���·��"""
        paths = filename.split('/')
        length = paths.__len__()
        if level >= length:
            return ""
        else:
            f = ""
            for i in range(0, length - level):
                if i != 0:
                    f += '/'
                f += paths[i]
            return f

    @staticmethod
    def filterPrByPath(df, f):
        """ͨ��·��f ����df���漰��pr�б�"""
        temp_df = df.copy(deep=True)
        temp_df['label'] = temp_df['filename'].apply(lambda x: x.find(f) == 0)
        temp_df = temp_df.loc[temp_df['label'] == 1]
        prs = list(set(temp_df['pr_number']))
        return prs


    @staticmethod
    def RecommendByCHREV(train_data, train_data_y, test_data, test_data_y, recommendNum=5):
        """ʹ��CHREV 
           �����Ƕ��ǩ����
        """""

        recommendList = []  # �����case�Ƽ��б�
        answerList = []

        prList = list(set(test_data['pr_number']))
        prList.sort()
        testDict = dict(list(test_data.groupby('pr_number')))

        pathLocalMap = {}  # f -> [pr]
        xFactorMap = {}  # (f, r) -> score

        for test_pull_number in prList:
            test_df = testDict[test_pull_number]
            """�����ȷ��"""
            answerList.append(list(set([x[0] for x in test_data_y[test_pull_number]])))
            # answerList.append(test_data_y[test_pull_number])

            """��ȡ�漰���ļ�·��"""
            files = list(set(test_df['filename']))
            recommendCase = []

            """package level ����·������ȣ�0���������·��"""
            packageLevel = 0
            while recommendCase.__len__() < recommendNum:
                """���ܻ�������ļ��������������Ҫ����Ƽ�"""
                scores = {}
                for file in files:
                    f = CHREVTrain.getPackageLevelPath(file, packageLevel)
                    """��ȡ·��f ����ʷ�ϳ��ֵ�pr"""
                    prs = pathLocalMap.get(f, None)
                    if prs is None:
                        prs = CHREVTrain.filterPrByPath(train_data, f)
                        pathLocalMap[f] = prs

                    """�����ļ�f ��RFԪ��"""
                    RF_C = 0  # ��ʷ�������f�������������
                    RF_W = 0  # ��ʷ����f�����workday
                    RF_T = 0  # ��ʷ����f�����������������

                    workLoad = set()

                    RE = {}  # reviewer-exprtise Map

                    for p2 in prs:
                        comments = train_data_y[p2]
                        RF_C += comments.__len__()
                        for comment in comments:
                            reviewer = comment[0]
                            day = comment[2]
                            if RE.get(reviewer, None) is None:
                                RE[reviewer] = [0, set(), 0]  # ��f�������۵������� workDay�б�, ����workday
                            workLoad.add(day)
                            RF_T = max(RF_T, day)

                            """���� RE �б�"""
                            RE[reviewer][1].add(day)
                            RE[reviewer][0] += 1
                            RE[reviewer][2] = max(RE[reviewer][2], day)

                    RF_W = workLoad.__len__()

                    """����ÿ�������ߵķ���"""
                    for r, [RE_C, RE_W, RE_T] in RE.items():
                        score = 0
                        score += RE_C / RF_C
                        score += RE_W.__len__() / RF_W
                        if RE_T == RF_T:
                            score += 1
                        else:
                            time1 = datetime(year=int(RF_T / 10000), month=int((RF_T % 10000) / 100), day=int(RF_T % 100))
                            time2 = datetime(year=int(RE_T / 10000), month=int((RE_T % 10000) / 100), day=int(RE_T % 100))
                            gap = (time1 - time2).total_seconds() / (3600 * 24)
                            score += 1 / gap
                        if scores.get(r, None) is None:
                            scores[r] = 0
                        scores[r] += score

                recommends = [x[0] for x in sorted(scores.items(), key=lambda d: d[1], reverse=True)]
                for r in recommends:
                    if r not in recommendCase and recommendCase.__len__() < recommendNum:
                        recommendCase.append(r)
                packageLevel += 1

            recommendList.append(recommendCase)
        return [recommendList, answerList]

if __name__ == '__main__':
    dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
             (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
             (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    projects = ['opencv', 'cakephp', 'akka', 'xbmc', 'babel', 'symfony', 'brew',
                'django', 'netty', 'scikit-learn', 'next.js', 'angular', 'moby',
                'metasploit-framework', 'Baystation12', 'react', 'pandas', 'joomla-cms',
                'grafana', 'salt']
    for p in projects:
        for t in [True]:
            CHREVTrain.testCHREVAlgorithm(p, dates, filter_train=t, filter_test=t, error_analysis=True)
            XFTrain.testXFAlgorithm(p, dates, filter_train=t, filter_test=t, error_analysis=True)
