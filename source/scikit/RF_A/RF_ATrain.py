# coding=gbk
import os
from datetime import datetime
import heapq
import time
from math import ceil

import numpy
from gensim import models, corpora
from pandas import DataFrame
from sklearn.model_selection import PredefinedSplit
from sklearn.preprocessing import StandardScaler, MinMaxScaler

from source.config.projectConfig import projectConfig
from source.data.service.DataSourceHelper import  appendFilePathFeatureVector
from source.nlp.FleshReadableUtils import FleshReadableUtils
from source.nlp.SplitWordHelper import SplitWordHelper
from source.nltk import nltkFunction
from source.scikit.ML.MultipleLabelAlgorithm import MultipleLabelAlgorithm
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.pandas.pandasHelper import pandasHelper


class RF_ATrain:

    @staticmethod
    def preProcess(df, date, project, isSTD=False, isNOR=False):
        """����˵��
        df����ȡ��dataframe����
        testDate:��Ϊ���Ե����� (year,month)
        isSTD:�������Ƿ��׼��
        isNOR:�������Ƿ��һ��
        """
        print("start df shape:", df.shape)
        """����NA������"""
        df.dropna(axis=0, how='any', inplace=True)
        print("after fliter na:", df.shape)

        """��df���һ�б�ʶѵ�����Ͳ��Լ�"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == date[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == date[3]))
        df.reset_index(drop=True, inplace=True)

        """�������������ִ���"""
        """Ƶ�ʲ������������ڱ��֮ǰ���Ѿ������ˣ����ÿ��Ƿ��಻���������"""
        """����reviewer_user_login ���� ��һ�������Ӱ��candicateNum��������ں��������"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login', 'author_user_login'])
        recoverDict = {v: k for k, v in convertDict.items()}

        print(df.shape)
        candicateNum = max(df.loc[df['label'] == 0]['review_user_login'])
        print("candicate Num:", candicateNum)

        """�ȶ��������������� ֻ���¸���Ȥ������"""
        df = df[['pr_number', 'review_user_login', 'author_user_login', 'author_association', 'commits',
                 'deletions', 'additions', 'changed_files', 'label', 'merged']].copy(deep=True)

        print("before filter:", df.shape)
        df.drop_duplicates(inplace=True)
        print("after filter:", df.shape)

        """�������ߵĹ�ϵ"""
        df['author_association'] = df['author_association'].apply(lambda x: x == 'MEMBER')

        """�����ۻ�����ʷ����"""
        request_number_prs = []  # ����֮ǰ����������
        request_number_merged_prs = []  # ���߷����ı����ܵ�����
        request_number_rejected_prs = []  # ���߷������ܾ�������
        request_accept_rate = []  # ����pr�����ܵĸ���
        request_reject_rate = []  # ����pr���ܾ��ĸ���

        for row in df.itertuples():
            pr_num = getattr(row, 'pr_number')
            author = getattr(row, 'author_user_login')
            """������ʷ��pr"""
            temp_df = df.loc[(df['pr_number'] < pr_num)&(df['author_user_login'] == author)]
            request_number_prs.append(temp_df.shape[0])
            accept_times = temp_df.loc[temp_df['merged'] == 1].shape[0]
            request_number_merged_prs.append(accept_times)
            request_number_rejected_prs.append(temp_df.shape[0] - accept_times)
            if temp_df.shape[0] > 0:
                request_accept_rate.append(accept_times/temp_df.shape[0])
                request_reject_rate.append(1 - accept_times / temp_df.shape[0])
            else:
                request_accept_rate.append(0)
                request_reject_rate.append(0)

        df['request_number_prs'] = request_number_prs
        df['request_number_merged_prs'] = request_number_merged_prs
        df['request_number_rejected_prs'] = request_number_rejected_prs
        df['request_accept_rate'] = request_accept_rate
        df['request_reject_rate'] = request_reject_rate

        """��������Ƿ��ע��Ŀ"""
        user_watch_repo_relation_path = projectConfig.getUserWatchRepoRelation()
        userWatchRepoRelation = pandasHelper.readTSVFile(
            os.path.join(user_watch_repo_relation_path, f'userWatchRepoRelation.tsv'),
            pandasHelper.INT_READ_FILE_WITH_HEAD, low_memory=False
        )
        watchRepoMap = {}
        for k in convertDict.keys():
            """��ȡ reviewer �� follow �б�"""
            following_list = list(set(userWatchRepoRelation.loc[userWatchRepoRelation['login'] == k]['repo_full_name']))
            isFollow = False
            for repo in following_list:
                owner, name = repo.split('/')
                if name == project:
                    isFollow = True
            watchRepoMap[convertDict[k]] = isFollow

        request_watches = []
        for row in df.itertuples():
            author = getattr(row, 'author_user_login')
            request_watches.append(watchRepoMap[author])
        df['request_watches'] = request_watches

        """�������follower������ followings����, �Ƿ�follow�Ŷӳ�Ա"""

        user_follow_relation_path = projectConfig.getUserFollowRelation()
        userFollowRelation = pandasHelper.readTSVFile(
            os.path.join(user_follow_relation_path, f'userFollowRelation.tsv'),
            pandasHelper.INT_READ_FILE_WITH_HEAD, low_memory=False
        )

        followMap = {}
        followerCountMap = {}
        followingCountMap = {}
        followCoreMemberMap = {}

        """�ռ����ĳ�Ա�б�"""
        coreMemberList = list(set(df.loc[df['author_association'] == 1]['author_user_login']))

        for k in convertDict.keys():
            """��ȡ reviewer �� follow �б�"""
            following_list = list(set(userFollowRelation.loc[userFollowRelation['login'] == k]['following_login']))
            followingCountMap[convertDict[k]] = following_list.__len__()
            isFollowCoreMember = False
            for f in following_list:
                if f in convertDict.keys():
                    followMap[(convertDict[k], convertDict[f])] = 1
                if f in coreMemberList:
                    isFollowCoreMember = True
            followCoreMemberMap[convertDict[k]] = isFollowCoreMember

            follower_list = list(set(userFollowRelation.loc[userFollowRelation['following_login'] == k]['login']))
            followerCountMap[convertDict[k]] = follower_list.__len__()
            # for f in follower_list:
            #     if f in convertDict.keys():
            #         followMap[(convertDict[f], convertDict[k])] = 1

        request_number_follows = []
        request_number_following = []
        request_follow_ct = []
        for row in df.itertuples():
            pr_num = getattr(row, 'pr_number')
            author = getattr(row, 'author_user_login')
            """������ʷ��pr"""
            request_number_following.append(followingCountMap[author])
            request_number_follows.append(followerCountMap[author])
            request_follow_ct.append(followCoreMemberMap[author])

        df['request_number_following'] = request_number_following
        df['request_number_follows'] = request_number_follows
        df['request_follow_ct'] = request_follow_ct

        """����ǰͳ����ȷ��"""
        tagDict = dict(list(df.groupby('pr_number')))

        train_data = df.loc[df['label'] == 0].copy(deep=True)
        test_data = df.loc[df['label'] == 1].copy(deep=True)

        """����ת��Ϊ���ǩ����
            train_data_y   [{pull_number:[r1, r2, ...]}, ... ,{}]
        """
        train_data_y = {}
        pull_number_list = train_data.drop_duplicates(['pr_number']).copy(deep=True)['pr_number']
        for pull_number in pull_number_list:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            train_data_y[pull_number] = reviewers

        train_data.drop(columns=['review_user_login', 'author_user_login', 'label', 'merged'], inplace=True)
        train_data.drop_duplicates(inplace=True)
        train_data.drop_duplicates(subset=['pr_number'], inplace=True)
        train_data.drop(columns=['pr_number'], inplace=True)
        """ѵ���� ����������ǩ����ͨ�õ�ģʽ"""
        train_data_y = DataProcessUtils.convertLabelListToDataFrame(train_data_y, pull_number_list, candicateNum)

        test_data_y = {}
        pull_number_list = test_data.drop_duplicates(['pr_number']).copy(deep=True)['pr_number']
        for pull_number in test_data.drop_duplicates(['pr_number'])['pr_number']:
            reviewers = list(tagDict[pull_number].drop_duplicates(['review_user_login'])['review_user_login'])
            test_data_y[pull_number] = reviewers

        test_data.drop(columns=['review_user_login', 'author_user_login', 'label', 'merged'], inplace=True)
        test_data.drop_duplicates(subset=['pr_number'], inplace=True)

        """���pr list"""
        prList = list(test_data['pr_number'])
        test_data.drop(columns=['pr_number'], inplace=True)

        test_data_y = DataProcessUtils.convertLabelListToListArray(test_data_y, pull_number_list)

        """�����淶��"""
        if isSTD:
            stdsc = StandardScaler()
            train_data_std = stdsc.fit_transform(train_data)
            test_data_std = stdsc.transform(test_data)
            return train_data_std, train_data_y, test_data_std, test_data_y, convertDict, prList
        elif isNOR:
            maxminsc = MinMaxScaler()
            train_data_std = maxminsc.fit_transform(train_data)
            test_data_std = maxminsc.transform(test_data)
            return train_data_std, train_data_y, test_data_std, test_data_y, convertDict, prList
        else:
            return train_data, train_data_y, test_data, test_data_y, convertDict, prList

    @staticmethod
    def changeStringToNumber(data, columns, startNum=0):  # ��dataframe��һЩ�������ı�ת����  input: dataFrame����Ҫ�����ĳЩ��
        if isinstance(data, DataFrame):
            count = startNum
            convertDict = {}  # ����ת�����ֵ�  ��ʼΪ1
            for column in columns:
                pos = 0
                for item in data[column]:
                    if convertDict.get(item, None) is None:
                        count += 1
                        convertDict[item] = count
                    data.at[pos, column] = convertDict[item]
                    pos += 1

    @staticmethod
    def getSeriesBarPlot(series):
        #  ��� �������ݵ���״�ֲ�ͼ
        import matplotlib.pyplot as plt

        fig = plt.figure()
        # fig.add_subplot(2, 1, 1)
        counts = series.value_counts()
        print(counts)
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        counts.plot(kind='bar')
        plt.title('��Ŀrails����������ʷͳ��')
        plt.xlabel('��Ա')
        plt.ylabel('�������')
        plt.show()

    @staticmethod
    def testRF_AAlgorithms(projects, dates, filter_train=False, filter_test=False, error_analysis=True):
        """
           RF �㷨���������������޷���ML���ݣ�������һ���ļ�
        """
        startTime = datetime.now()

        for project in projects:
            excelName = f'outputRF_A_{project}_{filter_train}_{filter_test}_{error_analysis}.xlsx'
            recommendNum = 5  # �Ƽ�����
            sheetName = 'result'
            """��ʼ��excel�ļ�"""
            ExcelHelper().initExcelFile(fileName=excelName, sheetName=sheetName, excel_key_list=['ѵ����', '���Լ�'])
            """��ʼ����Ŀ̧ͷ"""
            content = ["��Ŀ���ƣ�", project]
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())

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

            for date in dates:
                recommendList, answerList, prList, convertDict, trainSize = RF_ATrain.algorithmBody(date, project,
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

                error_analysis_data = None
                if error_analysis:
                    y = date[2]
                    m = date[3]
                    filename = projectConfig.getRF_ADataPath() + os.sep + f'RF_A_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                    filter_answer_list = DataProcessUtils.getAnswerListFromChangeTriggerData(project, date,
                                                                                             prList,
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

                """�ļ��ָ�"""
                content = ['']
                ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
                content = ['ѵ����', '���Լ�']
                ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())

                print("cost time:", datetime.now() - startTime)
                """�Ƽ�������ӻ�"""
                DataProcessUtils.recommendErrorAnalyzer2(error_analysis_datas, project, f'RF_{filter_train}_{filter_test}')

                """������ʷ�ۻ�����"""
                DataProcessUtils.saveFinallyResult(excelName, sheetName, topks, mrrs, precisionks, recallks, fmeasureks,
                                                   error_analysis_datas)

    @staticmethod
    def algorithmBody(date, project, recommendNum=5, filter_train=False, filter_test=False):
        df = None
        """�������ļ����ϲ� """
        for i in range(date[0] * 12 + date[1], date[2] * 12 + date[3] + 1):  # ��ֵ�������ƴ��
            y = int((i - i % 12) / 12)
            m = i % 12
            if m == 0:
                m = 12
                y = y - 1

            print(y, m)
            if i < date[2] * 12 + date[3]:
                if filter_train:
                    filename = projectConfig.getRF_ADataPath() + os.sep + f'RF_A_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getRF_ADataPath() + os.sep + f'RF_A_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            else:
                if filter_test:
                    filename = projectConfig.getRF_ADataPath() + os.sep + f'RF_A_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getRF_ADataPath() + os.sep + f'RF_A_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            """�����Դ�head"""
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """��ȡ���Ե� pull number�б�"""
        train_data, train_data_y, test_data, test_data_y, convertDict, prList = RF_ATrain.preProcess(df, date, project, isNOR=True)
        print("train data:", train_data.shape)
        print("test data:", test_data.shape)

        recommendList, answerList = MultipleLabelAlgorithm.RecommendByRF(train_data, train_data_y, test_data,
                                                                          test_data_y, recommendNum)
        trainSize = (train_data.shape[0], test_data.shape[0])

        """�����Ƽ����������"""
        DataProcessUtils.saveRecommendList(prList, recommendList, answerList, convertDict, key=project + str(date))

        return recommendList, answerList, prList, convertDict, trainSize


if __name__ == '__main__':
    dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
             (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
             (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    # dates = [(2017, 1, 2017, 2)]
    projects = ['opencv', 'cakephp']
    # projects = ['opencv', 'cakephp', 'akka', 'xbmc', 'babel', 'symfony', 'brew', 'django', 'netty', 'scikit-learn']
    for t in [False]:
         RF_ATrain.testRF_AAlgorithms(projects, dates, filter_train=t, filter_test=t, error_analysis=True)

