# coding=gbk
import os
import time

from pandas import DataFrame

from source.config.projectConfig import projectConfig
from source.scikit.service.RecommendMetricUtils import RecommendMetricUtils
from source.utils.ExcelHelper import ExcelHelper
from source.utils.pandas.pandasHelper import pandasHelper


class DataProcessUtils:
    """用于处理项目数据一些通用的方法工具类"""

    """由于有些列名会有重合，采用重命名"""
    COLUMN_NAME_ALL = ['pr_repo_full_name', 'pr_number', 'pr_id', 'pr_node_id',
                       'pr_state', 'pr_title', 'pr_user_login', 'pr_body',
                       'pr_created_at',
                       'pr_updated_at', 'pr_closed_at', 'pr_merged_at', 'pr_merge_commit_sha',
                       'pr_author_association', 'pr_merged', 'pr_comments', 'pr_review_comments',
                       'pr_commits', 'pr_additions', 'pr_deletions', 'pr_changed_files',
                       'pr_head_label', 'pr_base_label',
                       'review_repo_full_name', 'review_pull_number',
                       'review_id', 'review_user_login', 'review_body', 'review_state', 'review_author_association',
                       'review_submitted_at', 'review_commit_id', 'review_node_id',

                       'commit_sha',
                       'commit_node_id', 'commit_author_login', 'commit_committer_login', 'commit_commit_author_date',
                       'commit_commit_committer_date', 'commit_commit_message', 'commit_commit_comment_count',
                       'commit_status_total', 'commit_status_additions', 'commit_status_deletions',

                       'file_commit_sha',
                       'file_sha', 'file_filename', 'file_status', 'file_additions', 'file_deletions', 'file_changes',
                       'file_patch',

                       'review_comment_id', 'review_comment_user_login', 'review_comment_body',
                       'review_comment_pull_request_review_id', 'review_comment_diff_hunk', 'review_comment_path',
                       'review_comment_commit_id', 'review_comment_position', 'review_comment_original_position',
                       'review_comment_original_commit_id', 'review_comment_created_at', 'review_comment_updated_at',
                       'review_comment_author_association', 'review_comment_start_line',
                       'review_comment_original_start_line',
                       'review_comment_start_side', 'review_comment_line', 'review_comment_original_line',
                       'review_comment_side', 'review_comment_in_reply_to_id', 'review_comment_node_id',
                       'review_comment_change_trigger']

    """ 上面col来源SQL语句：
            select *
        from pullRequest, review, gitCommit, gitFile, reviewComment
        where pullRequest.repo_full_name = 'scala/scala' and
          review.repo_full_name = pullRequest.repo_full_name
        and pullRequest.number = review.pull_number and
          gitCommit.sha = review.commit_id and gitFile.commit_sha = gitCommit.sha
        and reviewComment.pull_request_review_id = review.id
    """

    @staticmethod
    def splitDataByMonth(filename, targetPath):
        """把提供的filename 中的数据按照日期分类并切分生成不同文件
            targetPath: 切分文件目标路径
        """

        df = pandasHelper.readTSVFile(filename, pandasHelper.INT_READ_FILE_WITHOUT_HEAD, low_memory=False)
        print(DataProcessUtils.COLUMN_NAME_ALL.__len__())
        df.columns = DataProcessUtils.COLUMN_NAME_ALL
        print(df['pr_created_at'])

        df['label'] = df['pr_created_at'].apply(lambda x: (time.strptime(x, "%Y-%m-%d %H:%M:%S")))
        df['label_y'] = df['label'].apply(lambda x: x.tm_year)
        df['label_m'] = df['label'].apply(lambda x: x.tm_mon)
        print(max(df['label']), min(df['label']))

        maxYear = max(df['label']).tm_year
        maxMonth = max(df['label']).tm_mon
        minYear = min(df['label']).tm_year
        minMonth = min(df['label']).tm_mon
        print(maxYear, maxMonth, minYear, minMonth)

        start = minYear * 12 + minMonth
        end = maxYear * 12 + maxMonth
        for i in range(start, end + 1):
            y = int((i - i % 12) / 12)
            m = i % 12
            if m == 0:
                m = 12
                y = y - 1
            print(y, m)
            subDf = df.loc[(df['label_y'] == y) & (df['label_m'] == m)].copy(deep=True)
            subDf.drop(columns=['label', 'label_y', 'label_m'], inplace=True)
            # print(subDf)
            print(subDf.shape)
            sub_filename = f'{filename.split(os.sep)[-1].split(".")[0]}_{y}_{m}_to_{y}_{m}.tsv'
            pandasHelper.writeTSVFile(os.path.join(targetPath, sub_filename), subDf)

    @staticmethod
    def changeStringToNumber(data, columns):  # 对dataframe的一些特征做文本转数字  input: dataFrame，需要处理的某些列
        if isinstance(data, DataFrame):  # 注意： dataframe之前需要resetindex
            count = 0
            convertDict = {}  # 用于转换的字典  开始为1
            for column in columns:
                pos = 0
                for item in data[column]:
                    if convertDict.get(item, None) is None:
                        count += 1
                        convertDict[item] = count
                    data.at[pos, column] = convertDict[item]
                    pos += 1

    @staticmethod
    def judgeRecommend(recommendList, answer, recommendNum):

        """评价推荐表现"""
        topk = RecommendMetricUtils.topKAccuracy(recommendList, answer, recommendNum)
        print(topk)
        mrr = RecommendMetricUtils.MRR(recommendList, answer, recommendNum)
        print(mrr)

        return topk, mrr

    @staticmethod
    def saveResult(filename, sheetName, topk, mrr, date):
        """时间和准确率"""
        content = None
        if date[3] == 1:
            content = [f"{date[2]}.{date[3]}", f"{date[0]}.{date[1]} - {date[2] - 1}.{12}", "TopKAccuracy"]
        else:
            content = [f"{date[2]}.{date[3]}", f"{date[0]}.{date[1]} - {date[2]}.{date[3] - 1}", "TopKAccuracy"]

        ExcelHelper().appendExcelRow(filename, sheetName, content, style=ExcelHelper.getNormalStyle())
        content = ['', '', 1, 2, 3, 4, 5]
        ExcelHelper().appendExcelRow(filename, sheetName, content, style=ExcelHelper.getNormalStyle())
        content = ['', ''] + topk
        ExcelHelper().appendExcelRow(filename, sheetName, content, style=ExcelHelper.getNormalStyle())
        content = ['', '', 'MRR']
        ExcelHelper().appendExcelRow(filename, sheetName, content, style=ExcelHelper.getNormalStyle())
        content = ['', '', 1, 2, 3, 4, 5]
        ExcelHelper().appendExcelRow(filename, sheetName, content, style=ExcelHelper.getNormalStyle())
        content = ['', ''] + mrr
        ExcelHelper().appendExcelRow(filename, sheetName, content, style=ExcelHelper.getNormalStyle())


if __name__ == '__main__':
    DataProcessUtils.splitDataByMonth(projectConfig.getRootPath() + r'\data\train\ALL_scala_data.tsv',
                                      projectConfig.getRootPath() + r'\data\train\all' + os.sep)

    print(pandasHelper.readTSVFile(
        projectConfig.getRootPath() + r'\data\train\all\ALL_scala_data_2012_6_to_2012_6.tsv', ))
