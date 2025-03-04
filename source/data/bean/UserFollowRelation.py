from source.data.bean.Beanbase import BeanBase
from source.utils.StringKeyUtils import StringKeyUtils


class UserFollowRelation(BeanBase):
    """github中的分支数据类"""

    def __init__(self):
        self.login = None  # 主题
        self.following_login = None  # follow 的对象

    @staticmethod
    def getIdentifyKeys():
        return [StringKeyUtils.STR_KEY_LOGIN, StringKeyUtils.STR_KEY_FOLLOWING_LOGIN]

    @staticmethod
    def getItemKeyList():
        items = [StringKeyUtils.STR_KEY_LOGIN, StringKeyUtils.STR_KEY_FOLLOWING_LOGIN]

        return items

    @staticmethod
    def getItemKeyListWithType():
        items = [(StringKeyUtils.STR_KEY_LOGIN, BeanBase.DATA_TYPE_STRING),
                 (StringKeyUtils.STR_KEY_FOLLOWING_LOGIN, BeanBase.DATA_TYPE_STRING)]

        return items

    def getValueDict(self):
        items = {StringKeyUtils.STR_KEY_LOGIN: self.login,
                 StringKeyUtils.STR_KEY_FOLLOWING_LOGIN: self.following_login}

        return items

    class parserV4(BeanBase.parser):

        @staticmethod
        def parser(src):
            """返回  [followingList, followingCount, lastFollowingCurosr, followerList, followerCount,
            lastFollowedCursor] """
            followingList = []
            followerList = []
            followingCount = 0
            followerCount = 0
            lastFollowingCursor = None
            lastFollowerCursor = None

            if isinstance(src, dict):
                """ 从following list 来解析"""
                data = src.get(StringKeyUtils.STR_KEY_DATA, None)
                if isinstance(data, dict):
                    userData = data.get(StringKeyUtils.STR_KEY_USER, None)
                    if isinstance(userData, dict):
                        login = userData.get(StringKeyUtils.STR_KEY_LOGIN, None)

                        followingListData = userData.get(StringKeyUtils.STR_KEY_FOLLOWING, None)
                        if isinstance(followingListData, dict):
                            totalCount = followingListData.get(StringKeyUtils.STR_KEY_TOTAL_COUNT_V4)
                            followingCount = totalCount
                            """如果发现 totolCount 大于 50"""
                            print("login:", login, "  following:", totalCount)
                            edgeData = followingListData.get(StringKeyUtils.STR_KEY_EDGES, None)
                            if isinstance(edgeData, list):
                                for edge in edgeData:
                                    if isinstance(edge, dict):
                                        node = edge.get(StringKeyUtils.STR_KEY_NODE, None)
                                        lastFollowingCursor = edge.get(StringKeyUtils.STR_KEY_CURSOR, None)
                                        if isinstance(node, dict):
                                            following_login = node.get(StringKeyUtils.STR_KEY_LOGIN, None)
                                            relation = UserFollowRelation()
                                            relation.login = login
                                            relation.following_login = following_login
                                            followingList.append(relation)

                        followerListData = userData.get(StringKeyUtils.STR_KEY_FOLLOWERS, None)
                        if isinstance(followingListData, dict):
                            totalCount = followerListData.get(StringKeyUtils.STR_KEY_TOTAL_COUNT_V4)
                            followerCount = totalCount
                            """如果发现 totolCount 大于 50"""
                            print("login:", login, "  following:", totalCount)
                            edgeData = followerListData.get(StringKeyUtils.STR_KEY_EDGES, None)
                            if isinstance(edgeData, list):
                                for edge in edgeData:
                                    if isinstance(edge, dict):
                                        node = edge.get(StringKeyUtils.STR_KEY_NODE, None)
                                        lastFollowerCursor = edge.get(StringKeyUtils.STR_KEY_CURSOR, None)
                                        if isinstance(node, dict):
                                            following_login = node.get(StringKeyUtils.STR_KEY_LOGIN, None)
                                            """颠倒"""
                                            relation = UserFollowRelation()
                                            relation.login = following_login
                                            relation.following_login = login
                                            followerList.append(relation)

                return [followingList, followingCount, lastFollowingCursor,
                        followerList, followerCount, lastFollowerCursor]
