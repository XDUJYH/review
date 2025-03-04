# coding=gbk
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
from source.utils.pandas.pandasHelper import pandasHelper


class IRTrain:
    """作为基于信息检索的reviewer推荐"""

    @staticmethod
    def testIRAlgorithm(project, dates, filter_train=False, filter_test=False, error_analysis=False):  # 多个case, 元组代表总共的时间跨度,最后一个月用于测试
        """
           algorithm : 基于信息检索
        """

        recommendNum = 5  # 推荐数量
        excelName = f'outputIR_{project}_{filter_train}_{filter_test}_{error_analysis}.xlsx'
        sheetName = 'result'


        """计算累积数据"""
        topks = []
        mrrs = []
        precisionks = []
        recallks = []
        fmeasureks = []
        recommend_positive_success_pr_ratios = []  # pr 中有推荐成功人选的比例
        recommend_positive_success_time_ratios = []  # 推荐pr * 人次 中有推荐成功人选的频次比例
        recommend_negative_success_pr_ratios = []  # pr 中有推荐人选Hit 但被滤掉的pr的比例
        recommend_negative_success_time_ratios = []  # 推荐pr * 人次中有推荐人选Hit 但是被滤掉的pr的比例
        recommend_positive_fail_pr_ratios = []  # pr 中有推荐人选推荐错误的pr比例
        recommend_positive_fail_time_ratios = []  # pr 中有pr * 人次有推荐错误的频次比例
        recommend_negative_fail_pr_ratios = []  # pr 中有推荐人选不知道是否正确的比例
        recommend_negative_fail_time_ratios = []  # pr中有pr * 人次有不知道是否正确的比例
        error_analysis_datas = None

        """初始化excel文件"""
        ExcelHelper().initExcelFile(fileName=excelName, sheetName=sheetName, excel_key_list=['训练集', '测试集'])
        for date in dates:
            startTime = datetime.now()
            """根据推荐列表做评价"""

            recommendList, answerList, prList, convertDict, trainSize = IRTrain.algorithmBody(date, project, recommendNum,
                                                                                              filter_train=filter_train,
                                                                                              filter_test=filter_test)


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
                filename = projectConfig.getIRDataPath() + os.sep + f'IR_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
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

            """结果写入excel"""
            DataProcessUtils.saveResult(excelName, sheetName, topk, mrr, precisionk, recallk, fmeasurek, date)

            """文件分割"""
            content = ['']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            content = ['训练集', '测试集']
            ExcelHelper().appendExcelRow(excelName, sheetName, content, style=ExcelHelper.getNormalStyle())
            print("cost time:", datetime.now() - startTime)

        """推荐错误可视化"""
        DataProcessUtils.recommendErrorAnalyzer2(error_analysis_datas, project, f'IR_{filter_train}_{filter_test}')

        """计算历史累积数据"""
        DataProcessUtils.saveFinallyResult(excelName, sheetName, topks, mrrs, precisionks, recallks,
                                           fmeasureks, error_analysis_datas)


    @staticmethod
    def algorithmBody(date, project, recommendNum=5, filter_train=False, filter_test=False):

        """提供单个日期和项目名称
           返回推荐列表和答案
           这个接口可以被混合算法调用
        """
        df = None
        for i in range(date[0] * 12 + date[1], date[2] * 12 + date[3] + 1):  # 拆分的数据做拼接
            y = int((i - i % 12) / 12)
            m = i % 12
            if m == 0:
                m = 12
                y = y - 1

            print(y, m)

            if i < date[2] * 12 + date[3]:
                if filter_train:
                    filename = projectConfig.getIRDataPath() + os.sep + f'IR_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getIRDataPath() + os.sep + f'IR_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'
            else:
                if filter_test:
                    filename = projectConfig.getIRDataPath() + os.sep + f'IR_ALL_{project}_data_change_trigger_{y}_{m}_to_{y}_{m}.tsv'
                else:
                    filename = projectConfig.getIRDataPath() + os.sep + f'IR_ALL_{project}_data_{y}_{m}_to_{y}_{m}.tsv'

            if df is None:
                df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
            else:
                temp = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITH_HEAD)
                df = df.append(temp)  # 合并

        df.reset_index(inplace=True, drop=True)
        """df做预处理"""
        """预处理新增返回测试pr列表 2020.4.11"""
        train_data, train_data_y, test_data, test_data_y, convertDict = IRTrain.preProcess(df, date)

        prList = list(test_data['pr_number'])

        """根据算法获得推荐列表"""
        recommendList, answerList = IRTrain.RecommendByIR(train_data, train_data_y, test_data,
                                                          test_data_y, recommendNum=recommendNum)
        trainSize = (train_data.shape[0], test_data.shape[0])
        return recommendList, answerList, prList, convertDict, trainSize

    @staticmethod
    def preProcess(df, dates):
        """参数说明
         df：读取的dataframe对象
         dates:作为测试的年月四元组
        """
        """注意： 输入文件中已经带有列名了"""

        """处理NAN"""
        df.dropna(how='any', inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.fillna(value='', inplace=True)

        """对df添加一列标识训练集和测试集"""
        df['label'] = df['pr_created_at'].apply(
            lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_year == dates[2] and
                       time.strptime(x, "%Y-%m-%d %H:%M:%S").tm_mon == dates[3]))

        """先对输入数据做精简 只留下感兴趣的数据"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'review_user_login', 'label']].copy(deep=True)

        print("before filter:", df.shape)
        df.drop_duplicates(inplace=True)
        print("after filter:", df.shape)
        """对人名字做数字处理"""
        convertDict = DataProcessUtils.changeStringToNumber(df, ['review_user_login'])
        """先对tag做拆分"""
        tagDict = dict(list(df.groupby('pr_number')))
        """先尝试所有信息团在一起"""
        df = df[['pr_number', 'pr_title', 'pr_body', 'label']].copy(deep=True)
        df.drop_duplicates(inplace=True)
        df.reset_index(drop=True, inplace=True)

        """用于收集所有文本向量分词"""
        stopwords = SplitWordHelper().getEnglishStopList()  # 获取通用英语停用词

        textList = []
        for row in df.itertuples(index=False, name='Pandas'):
            tempList = []
            """获取pull request的标题"""
            pr_title = getattr(row, 'pr_title')
            pr_title_word_list = [x for x in FleshReadableUtils.word_list(pr_title) if x not in stopwords]

            """初步尝试提取词干效果反而下降了 。。。。"""

            """对单词做提取词干"""
            pr_title_word_list = nltkFunction.stemList(pr_title_word_list)
            tempList.extend(pr_title_word_list)

            """pull request的body"""
            pr_body = getattr(row, 'pr_body')
            pr_body_word_list = [x for x in FleshReadableUtils.word_list(pr_body) if x not in stopwords]
            """对单词做提取词干"""
            pr_body_word_list = nltkFunction.stemList(pr_body_word_list)
            tempList.extend(pr_body_word_list)
            textList.append(tempList)

        print(textList.__len__())
        """对分词列表建立字典 并提取特征数"""
        dictionary = corpora.Dictionary(textList)
        print('词典：', dictionary)

        feature_cnt = len(dictionary.token2id)
        print("词典特征数：", feature_cnt)

        """根据词典建立语料库"""
        corpus = [dictionary.doc2bow(text) for text in textList]
        # print('语料库:', corpus)
        """语料库训练TF-IDF模型"""
        tfidf = models.TfidfModel(corpus)

        """再次遍历数据，形成向量，向量是稀疏矩阵的形式"""
        wordVectors = []
        for i in range(0, df.shape[0]):
            wordVectors.append(dict(tfidf[dictionary.doc2bow(textList[i])]))

        """对已经有的本文特征向量和标签做训练集和测试集的拆分"""

        trainData_index = df.loc[df['label'] == False].index
        testData_index = df.loc[df['label'] == True].index

        """训练集"""
        train_data = [wordVectors[x] for x in trainData_index]
        """测试集"""
        test_data = [wordVectors[x] for x in testData_index]
        """填充为向量"""
        train_data = DataProcessUtils.convertFeatureDictToDataFrame(train_data, featureNum=feature_cnt)
        test_data = DataProcessUtils.convertFeatureDictToDataFrame(test_data, featureNum=feature_cnt)
        train_data['pr_number'] = list(df.loc[df['label'] == False]['pr_number'])
        test_data['pr_number'] = list(df.loc[df['label'] == True]['pr_number'])

        """问题转化为多标签问题
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

        """train_data ,test_data 最后一列是pr number test_data_y 的形式是dict"""
        return train_data, train_data_y, test_data, test_data_y, convertDict

    @staticmethod
    def RecommendByIR(train_data, train_data_y, test_data, test_data_y, recommendNum=5):
        """使用信息检索  
           并且是多标签分类
        """""

        recommendList = []  # 最后多个case推荐列表
        answerList = []

        """对IR 矩阵乘法优化"""
        """计算train_data的矩阵"""
        df_train = train_data.copy(deep=True)
        df_train.drop(columns=['pr_number'], inplace=True)
        """计算test_data矩阵"""
        df_test = test_data.copy(deep=True)
        df_test.drop(columns=['pr_number'], inplace=True)

        """计算距离"""
        DIS = DataFrame(numpy.dot(df_test, df_train.T))  # train_num x t

        # for targetData in test_data.itertuples(index=False):  # 对每一个case做推荐
        #     """itertuples 具有大量列的时候返回常规元组 >255"""
        #     targetNum = targetData[-1]
        #     recommendScore = {}
        #     for trainData in train_data.itertuples(index=False, name='Pandas'):
        #         trainNum = trainData[-1]
        #         reviewers = train_data_y[trainNum]
        #
        #         """计算相似度不带上最后一个pr number"""
        #         score = IRTrain.cos2(targetData[0:targetData.__len__()-2], trainData[0:trainData.__len__()-2])
        #         for reviewer in reviewers:
        #             if recommendScore.get(reviewer, None) is None:
        #                 recommendScore[reviewer] = 0
        #             recommendScore[reviewer] += score
        #
        #     targetRecommendList = [x[0] for x in
        #                            sorted(recommendScore.items(), key=lambda d: d[1], reverse=True)[0:recommendNum]]
        #     # print(targetRecommendList)
        #     recommendList.append(targetRecommendList)
        #     answerList.append(test_data_y[targetNum])

        test_pr_list = tuple(test_data['pr_number'])
        train_pr_list = tuple(train_data['pr_number'])

        for index_test, pr_test in enumerate(test_pr_list):
            print(index_test, "  all:", test_pr_list.__len__())
            recommendScore = {}
            for index_train, pr_train in enumerate(train_pr_list):
                reviewers = train_data_y[pr_train]
                """计算时间差"""
                """计算相似度不带上最后一个pr number"""
                score = DIS.iloc[index_test][index_train]
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
    def cos(dict1, dict2):
        """计算两个代码稀疏矩阵字典的计算余弦"""
        if isinstance(dict1, dict) and isinstance(dict2, dict):
            """先计算模长"""
            l1 = 0
            for v in dict1.values():
                l1 += v * v
            l2 = 0
            for v in dict2.values():
                l2 += v * v

            mul = 0
            """计算向量相乘"""
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
        """计算两个元组的余弦"""
        """先计算模长"""
        l1 = 0
        for v in tuple1:
            l1 += v * v
        l2 = 0
        for v in tuple2:
            l2 += v * v
        mul = 0
        """计算向量相乘"""
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
    # dates = [(2017, 1, 2018, 1), (2017, 1, 2018, 2), (2017, 1, 2018, 3), (2017, 1, 2018, 4), (2017, 1, 2018, 5),
    #          (2017, 1, 2018, 6), (2017, 1, 2018, 7), (2017, 1, 2018, 8), (2017, 1, 2018, 9), (2017, 1, 2018, 10),
    #          (2017, 1, 2018, 11), (2017, 1, 2018, 12)]
    dates = [(2017, 1, 2018, 1)]
    # projects = ['react', 'pandas']
    projects = ['opencv']
    for p in projects:
        IRTrain.testIRAlgorithm(p, dates, filter_train=False, filter_test=False, error_analysis=True)
