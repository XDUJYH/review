# coding=gbk
from source.data.bean.PRTimeLineRelation import PRTimeLineRelation
from source.utils.StringKeyUtils import StringKeyUtils


class PRTimeLineUtils:
    """���pull request��timeline��һЩ����Ĺ�����"""

    @staticmethod
    def splitTimeLine(prTimeLineItems):
        """��һ��������ʱ���߷ָ�  ����Ϊһϵ�е�review����ص�commit��event"""
        """ע������ʱ�����ǵ���� 2020.8.5"""

        reviewPair = []  # review -> [{(changeNode, changeNode)): reviewNodes}, {}, ...]

        pair_review_node_list = []
        pair_change_node_list = []
        last_item = None
        for item in prTimeLineItems:
            if item.typename in PRTimeLineUtils.getChangeType() and (last_item is not None and last_item.typename in PRTimeLineUtils.getReviewType()):
                """���������change���ͣ�����һ����comment�������µ�pair"""
                # push pair
                # ע������change_node_listΪ�յ�pairҲ�����������©����Ч����
                if pair_change_node_list.__len__() > 0 or pair_review_node_list.__len__() > 0:
                    reviewPair.append((pair_change_node_list, pair_review_node_list))
                # ������pair
                pair_review_node_list = []
                pair_change_node_list = [item]
            elif item.typename in PRTimeLineUtils.getChangeType() and (last_item is None or (last_item is not None and last_item.typename in PRTimeLineUtils.getChangeType())):
                """���������change���ͣ�����һ����change������change_node_list"""
                pair_change_node_list.append(item)
            elif item.typename in PRTimeLineUtils.getReviewType() and pair_change_node_list.__len__() > 0:
                """���������comment���ͣ���change_list��Ϊ�գ�����review_node_list"""
                pair_review_node_list.append(item)
            elif item.typename in PRTimeLineUtils.getReviewType() and pair_change_node_list.__len__() == 0:
                """���������comment���ͣ���change_listΪ�գ���Ȼ����review_node_list"""
                pair_review_node_list.append(item)
            last_item = item

        # ע������change_node_listΪ�յ�pairҲ�����������©����Ч����
        if pair_change_node_list.__len__() > 0 or pair_review_node_list.__len__() > 0:
            reviewPair.append((pair_change_node_list, pair_review_node_list))

        return reviewPair

    @staticmethod
    def getChangeType():
        return [StringKeyUtils.STR_KEY_PULL_REQUEST_COMMIT, StringKeyUtils.STR_KEY_HEAD_REF_PUSHED_EVENT,
                StringKeyUtils.STR_KEY_MERGED_EVENT]

    @staticmethod
    def getReviewType():
        return [StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW, StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW_THREAD,
                StringKeyUtils.STR_KEY_ISSUE_COMMENT]
