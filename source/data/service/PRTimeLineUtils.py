# coding=gbk
from source.data.bean.PRTimeLineRelation import PRTimeLineRelation
from source.utils.StringKeyUtils import StringKeyUtils


class PRTimeLineUtils:
    """���pull request��timeline��һЩ����Ĺ�����"""

    @staticmethod
    def splitTimeLine(prTimeLineItems):
        """��һ��������ʱ���߷ָ�  ����Ϊһϵ�е�review����ص�commit��event"""
        """ע������ʱ�����ǵ���� 2020.8.5"""
        """ע��������reopen�Ķ��⴦���߼�
            һ��closed��reopend �м��item������һ��pair�У�change����reopen�¼���
            ����pair�е�comment��Ϊ��ͳͳ��Ч��  ���ɶε�closed-reopen��ʱ���߿���
            �ֳ����ɶ�  reopend��prռ��ԼΪ1.5% ������΢����һ�°ɣ����ⲻ��  2020.10.31
        """

        """�ȱ���prTimeLineItems���Ƿ���ҪӦΪreopen�¼����ָ �ָ�ʣ�µ��൱�ڵ�������Сpr"""
        tempPrTimeLineItems = prTimeLineItems.copy()
        prTimeLineItemsLists = []  # ���ܻ�ָ�����ɴε�����pr����
        reviewPair = []  # review -> [{(changeNode, changeNode)): reviewNodes}, {}, ...]

        pair_review_node_list = []
        pair_change_node_list = []

        prTimeLineItems = []
        isInClosedGap = False  # �����ж��Ƿ���Closed��Reopend�ļ�϶������ǣ���ΪTrue
        for item in tempPrTimeLineItems:
            if isInClosedGap:
                if item.typename == PRTimeLineUtils.getClosedType():  # ����gap״̬
                    isInClosedGap = False
                    if pair_change_node_list.__len__() > 0 or pair_review_node_list.__len__() > 0:
                        reviewPair.append((pair_change_node_list, pair_review_node_list))
                    pair_change_node_list = []
                    pair_review_node_list = []
                    """����itemList�У�������"""
                    prTimeLineItems.append(item)
                else:
                    """gap ״̬Ӧ��ֻ��̸������û��change, ���Է���review����"""
                    """fix bug ������Ҫ����change��type
                       �������� https://github.com/opencv/opencv/pull/12623
                    """
                    if item.typename in PRTimeLineUtils.getReviewType():
                        pair_review_node_list.append(item)
                        """����"""
            else:
                if item.typename == PRTimeLineUtils.getReopenedType():  # ����gap״̬
                    isInClosedGap = True
                    """�Ȱ�֮ǰ�ķ�gap�Ļ��Ϊһ��������pr"""
                    if prTimeLineItems.__len__() > 0:
                        prTimeLineItemsLists.append(prTimeLineItems)
                    prTimeLineItems = []
                    pair_change_node_list.append(item)
                else:
                    """����״̬"""
                    prTimeLineItems.append(item)

        """��β����"""
        if prTimeLineItems.__len__() > 0:
            prTimeLineItemsLists.append(prTimeLineItems)

        """����Reopend�ķָ������Ҫ�ֳɼ�������"""
        for prTimeLineItems in prTimeLineItemsLists:
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
                if item.typename in PRTimeLineUtils.getChangeType() or\
                        item.typename in PRTimeLineUtils.getReviewType():
                    last_item = item

            # ע������change_node_listΪ�յ�pairҲ�����������©����Ч����
            if pair_change_node_list.__len__() > 0 or pair_review_node_list.__len__() > 0:
                reviewPair.append((pair_change_node_list, pair_review_node_list))

        return reviewPair

    @staticmethod
    def getChangeType():
        """ע�� reopened���ӽ�ȥ����Ϊ�����Ǵ�����"""
        return [StringKeyUtils.STR_KEY_PULL_REQUEST_COMMIT, StringKeyUtils.STR_KEY_HEAD_REF_PUSHED_EVENT,
                StringKeyUtils.STR_KEY_MERGED_EVENT, StringKeyUtils.STR_KEY_CLOSED_EVENT]

    @staticmethod
    def getReviewType():
        return [StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW, StringKeyUtils.STR_KEY_PULL_REQUEST_REVIEW_THREAD]

    @staticmethod
    def getClosedType():
        return StringKeyUtils.STR_KEY_CLOSED_EVENT
    @staticmethod

    def getReopenedType():
        return StringKeyUtils.STR_KEY_REOPENED_EVENT
