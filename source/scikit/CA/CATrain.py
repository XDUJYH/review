# coding=gbk
import os
import time
from datetime import datetime
from functools import reduce
from math import sqrt

import numpy
import pandas
from gensim import corpora, models
from matplotlib.ticker import MultipleLocator
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from source.config.projectConfig import projectConfig
from source.data.service.DataSourceHelper import splitFileName
from source.nlp.FleshReadableUtils import FleshReadableUtils
from source.nlp.SplitWordHelper import SplitWordHelper
from source.nltk import nltkFunction
from source.scikit.ML.MLTrain import MLTrain
from source.scikit.service.DataProcessUtils import DataProcessUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.pandas.pandasHelper import pandasHelper
import sklearn.metrics
import matplotlib.pyplot as plt
import pandas
from pandas import DataFrame

projectName = ''

class CATrain:
    """��Ϊ�����û������reviewer�Ƽ�"""

    @staticmethod
    def testCAAlgorithm(project, dates):  # ���case, Ԫ������ܹ���ʱ����,���һ�������ڲ���
        """
           algorithm : �����û�����
        """

        recommendNum = 5  # �Ƽ�����
        excelName = f'outputCA.xlsx'
        sheetName = 'result'

        """��ʼ��excel�ļ�"""
        ExcelHelper().initExcelFile(fileName=excelName, sheetName=sheetName, excel_key_list=['ѵ����', '���Լ�'])
        for date in dates:
            startTime = datetime.now()
            """�����Ƽ��б�������"""

            CATrain.algorithmBody(date, project, recommendNum)
            # recommendList, answerList, prList, convertDict, trainSize = IRTrain.algorithmBody(date, project, recommendNum)

            # topk, mrr, precisionk, recallk, fmeasurek = \
            #     DataProcessUtils.judgeRecommend(recommendList, answerList, recommendNum)
            #
            # """���д��excel"""
            # DataProcessUtils.saveResult(excelName, sheetName, topk, mrr, precisionk, recallk, fmeasurek, date)
            #
            # """�ļ��ָ�"""
            # content = ['']
            # ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            # content = ['ѵ����', '���Լ�']
            # ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            # print("cost time:", datetime.now() - startTime)

    @staticmethod
    def algorithmBody(date, project, recommendNum=5):

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

            filename = projectConfig.getCADataPath() + os.sep \
                       + f'CA_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # �ϲ�

        df.reset_index(inplace=True, drop=True)
        """df��Ԥ����"""
        """Ԥ�����������ز���pr�б� 2020.4.11"""
        # train_data, train_data_y, test_data, test_data_y, convertDict = CATrain.preProcess(df, date)
        #
        # prList = list(test_data['pr_number'])
        #
        # """�����㷨����Ƽ��б�"""
        # recommendList, answerList = IRTrain.RecommendByIR(train_data, train_data_y, test_data,
        #                                                   test_data_y, recommendNum=recommendNum)
        # trainSize = (train_data.shape[0], test_data.shape[0])
        # return recommendList, answerList, prList, convertDict, trainSize

        CATrain.preProcess(df, date)

    @staticmethod
    def preProcess(df, dates):
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

        """Ƶ��ͳ��ÿһ��reviewer�Ĵ������ų��������ٵ�reviewer"""
        freq = {}
        for data in df.itertuples(index=False):
            name = data[list(df.columns).index('review_user_login')]
            if freq.get(name, None) is None:
                freq[name] = 0
            """ѵ�����û�������һ  ���Լ�ֱ�ӱ��� """
            if not data[list(df.columns).index('label')]:
                freq[name] += 1
            else:
                freq[name] += 1

        num = 5
        df['freq'] = df['review_user_login'].apply(lambda x: freq[x])
        df = df.loc[df['freq'] > num].copy(deep=True)
        df.drop(columns=['freq'], inplace=True)
        df.reset_index(drop=True, inplace=True)
        print("after lifter unexperienced user:", df.shape)

        """�ȶ��������������� ֻ���¸���Ȥ������"""
        df = df[['pull_number', 'review_user_login', 'commit_sha', 'file_filename', 'label']].copy(deep=True)

        print("before filter:", df.shape)
        df.drop_duplicates(inplace=True)
        print("after filter:", df.shape)
        """�������������ִ���"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        reviewer_num = convertDict.items().__len__()
        print("reviewer num:", convertDict.items().__len__())
        """���Լ� ѵ���������"""
        train_raw_df = df.loc[df['label'] == 0].copy(deep=True)
        # userDict = dict(list(train_raw_df.groupby('review_user_login')))
        # print(userDict)

        """�����û���ʷreview��¼��TF-IDFģ��"""

        """��ȡfilepath -> sub_filepathӳ���"""
        file_path_list = set(df['file_filename'].copy(deep=True))
        file_path_dict = {}
        for file_path in file_path_list:
            # sub_file_path = splitFileName(file_path)
            sub_file_path = file_path.split('/')
            if file_path not in file_path_dict:
                file_path_dict[file_path] = set()
            file_path_dict[file_path] = file_path_dict[file_path].union(sub_file_path)

        """��ȡpr_number -> sub_filepath����"""
        reviewer_to_file_path = df[['review_user_login', 'file_filename']]
        # ����reviewer���飬���ԭʼ���ϣ�δ�����ִʵ�filepath��"""
        groups = dict(list(reviewer_to_file_path.groupby('review_user_login')))
        # ��ȡĿ�����ϣ��������Զ���ִʺ�����ϣ�
        reviewer_file_path_corpora = []
        for reviewer in groups:
            paths = list(groups[reviewer]['file_filename'])
            sub_paths = list(map(lambda x: list(file_path_dict[x]), paths))
            sub_paths = reduce(lambda x, y: x + y, sub_paths)
            reviewer_file_path_corpora.append(sub_paths)

        """����tf-idf"""
        print("start tf_idf algorithm......")
        # �����ʵ�
        dictionary = corpora.Dictionary(reviewer_file_path_corpora)
        # ���ڴʵ佨���µ����Ͽ�
        corpus = [dictionary.doc2bow(text) for text in reviewer_file_path_corpora]
        # �����Ͽ�ѵ��TF-IDFģ��
        tf_idf_model = models.TfidfModel(corpus)
        # �õ���Ȩ����
        path_tf_tdf = list(tf_idf_model[corpus])
        print(path_tf_tdf)

        """����path_tf_tdf������pr_path��Ȩ����"""
        print("start merge tf_idf to origin_df......")
        reviewer_list = list(groups.keys())
        columns = ['review_user_login']
        path_ids = list(dictionary.token2id.values())
        path_ids = list(map(lambda x: str(x), path_ids))
        columns.extend(path_ids)
        reviewer_path_weight_df = pandas.DataFrame(columns=columns).fillna(value=0)
        for index, row in enumerate(path_tf_tdf):
            """���ֵ�ķ�ʽ���dataframe"""
            new_row = {'review_user_login': reviewer_list[index]}
            row = list(map(lambda x: (str(x[0]), x[1]), row))
            path_weight = dict(row)
            new_row = dict(new_row, **path_weight)
            reviewer_path_weight_df = reviewer_path_weight_df.append(new_row, ignore_index=True)
        reviewer_path_weight_df = reviewer_path_weight_df.fillna(value=0)
        print(reviewer_path_weight_df.shape)

        """ȥ���û���"""
        reviewer_path_weight_df.drop(columns=['review_user_login'], axis=1, inplace=True)
        print("before pca size:", reviewer_path_weight_df.shape)

        """PCA"""
        pca = PCA(n_components=0.95)
        reviewer_path_weight_df = pca.fit_transform(reviewer_path_weight_df)
        print("after pca size:", reviewer_path_weight_df.shape)

        """������׼��һ��"""
        stdsc = StandardScaler()
        reviewer_path_weight_df_std = stdsc.fit_transform(reviewer_path_weight_df)


        M = []
        N = []
        max_cluster = min(20, reviewer_num)
        for n in range(2, 20):
            y_pred = KMeans(n_clusters=n, random_state=9).fit_predict(reviewer_path_weight_df_std)
            from sklearn import metrics
            # m = metrics.calinski_harabasz_score(reviewer_path_weight_df, y_pred)
            m = sklearn.metrics.silhouette_score(reviewer_path_weight_df_std, y_pred,
                                                   sample_size=len(reviewer_path_weight_df_std), metric='euclidean')
            M.append(m)
            N.append(n)
            print(n ,m)
            print(y_pred)

            """�������������ͼ����"""
            nums = []
            x = []
            for i in range(0, n):
                nums.append(list(y_pred).count(i))
                x.append(i)
            print(x)
            print(nums)
            plt.subplot(5, 4, n-1)
            plt.bar(x=range(0, n), height=nums)
            # plt.title('cluster%d'%n)
        plt.savefig(f'��Ŀ{projectName}����ֲ�.png')
        # plt.show()

        M = DataFrame(M)
        N = DataFrame(N)
        # x_major_locator = MultipleLocator(1)  # x����Ϊ1
        fig = plt.figure()
        # ax1 = fig.add_subplot(111)
        # ax1.scatter(N, M, s=40, marker='o')
        # ax1.xaxis.set_major_locator(x_major_locator)
        plt.plot(N, M, marker='o', markersize=5)
        plt.xlabel('cluster number')
        plt.ylabel('slihouette score')
        plt.xlim(-0.5, 22)
        # for a, b in zip(list(N), list(M)):
        #     plt.text(a, b, b, ha='center', va='bottom', fontsize=20)
        # plt.legend()
        plt.savefig(f'��Ŀ{projectName}����ϵ��.png')
        # plt.show()

    # @staticmethod
    # def RecommendByIR(train_data, train_data_y, test_data, test_data_y, recommendNum=5):
    #     """ʹ����Ϣ����
    #        �����Ƕ��ǩ����
    #     """""
    #
    #     recommendList = []  # �����case�Ƽ��б�
    #     answerList = []
    #
    #     for targetData in test_data.itertuples(index=False):  # ��ÿһ��case���Ƽ�
    #         """itertuples ���д����е�ʱ�򷵻س���Ԫ�� >255"""
    #         targetNum = targetData[-1]
    #         recommendScore = {}
    #         for trainData in train_data.itertuples(index=False, name='Pandas'):
    #             trainNum = trainData[-1]
    #             reviewers = train_data_y[trainNum]
    #
    #             """�������ƶȲ��������һ��pr number"""
    #             score = IRTrain.cos2(targetData[0:targetData.__len__()-2], trainData[0:trainData.__len__()-2])
    #             for reviewer in reviewers:
    #                 if recommendScore.get(reviewer, None) is None:
    #                     recommendScore[reviewer] = 0
    #                 recommendScore[reviewer] += score
    #
    #         targetRecommendList = [x[0] for x in
    #                                sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]
    #         # print(targetRecommendList)
    #         recommendList.append(targetRecommendList)
    #         answerList.append(test_data_y[targetNum])
    #
    #     return [recommendList, answerList]

if __name__ == '__main__':
    # dates = [(2018, 4, 2018, 5), (2018, 4, 2018, 7), (2018, 4, 2018, 10), (2018, 4, 2019, 1),
    #          (2018, 4, 2019, 4)]
    # dates = [(2018, 1, 2019, 5), (2018, 1, 2019, 6), (2018, 1, 2019, 7), (2018, 1, 2019, 8)]
    dates = [(2018, 1, 2019, 12)]
    # projects = ['rails', 'bitcoin', 'cakephp', 'opencv', 'akka']
    # for p in projects:
    #     projectName = p
    #     CATrain.testCAAlgorithm(projectName, dates)

