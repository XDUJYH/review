# coding=gbk
from source.config.configPraser import configPraser
from source.database.DataBaseOpenHelper import DataBaseOpenHelper
from source.database.SqlUtils import SqlUtils


class SqlExecuteHelper:
    """����ִ��sql���"""

    @staticmethod
    def insertValuesIntoTable(tableName, items, valueDict, primaryKeys=None):
        """�������"""

        res = SqlExecuteHelper.queryValuesFromTable(tableName, primaryKeys, valueDict)
        if res is not None and res.__len__() > 0:
            if configPraser.getPrintMode():
                print('�����ظ�����ʧ��')
            return

        conn = DataBaseOpenHelper.connect()
        cursor = conn.cursor()
        format_table = SqlUtils.getInsertTableFormatString(tableName, items)
        format_values = SqlUtils.getInsertTableValuesString(items.__len__())

        if configPraser.getPrintMode():
            print(format_table)
            print(format_values)

        sql = SqlUtils.STR_SQL_INSERT_TABLE_UTILS.format(format_table, format_values)
        if configPraser.getPrintMode():
            print(sql)

        values = ()
        for item in items:
            values = values + (valueDict.get(item, None),)  # Ԫ�����
        try:
            cursor.execute(sql, values)
            conn.commit()
        except Exception as e:
            print(e)
            conn.rollback()
        conn.close()

    @staticmethod
    def queryValuesFromTable(tableName, items, valueDict):
        """��ѯ���ݿ�"""

        ret = []
        conn = DataBaseOpenHelper.connect()

        cursor = conn.cursor()
        format_values = SqlUtils.getQueryTableConditionString(items)
        sql = SqlUtils.STR_SQL_QUERY_TABLE_UTILS.format(tableName, format_values)
        if configPraser.getPrintMode():
            print(sql)

        values = ()
        if items is not None:
            for item in items:
                values = values + (valueDict.get(item, None),)  # Ԫ�����
        try:
            cursor.execute(sql, values)
            ret = cursor.fetchall()
            if configPraser.getPrintMode():
                print(ret)
        except Exception as e:
            print(e)
        conn.close()
        return ret

    @staticmethod
    def deleteValuesFromTable(tableName, items, valueDict):
        """ɾ��ĳ�ű�"""

        conn = DataBaseOpenHelper.connect()

        cursor = conn.cursor()
        format_values = SqlUtils.getQueryTableConditionString(items)
        sql = SqlUtils.STR_SQL_DELETE_TABLE_UTILS.format(tableName, format_values)
        if configPraser.getPrintMode():
            print(sql)

        values = ()
        if items is not None:
            for item in items:
                values = values + (valueDict.get(item, None),)  # Ԫ�����
        try:
            cursor.execute(sql, values)
            conn.commit()
        except Exception as e:
            print(e)
            conn.rollback()
        conn.close()

    @staticmethod
    def updateValuesFromTable(tableName, targets, targetsDict, conditions, conditionsDict):
        """�޸�ĳ�ű�"""

        conn = DataBaseOpenHelper.connect()

        cursor = conn.cursor()
        format_target = SqlUtils.getUpdateTableSetString(targets)
        format_condition = SqlUtils.getQueryTableConditionString(conditions)
        sql = SqlUtils.STR_SQL_UPDATE_TABLE_UTILS.format(tableName, format_target, format_condition)
        if configPraser.getPrintMode():
            print(sql)

        values = ()
        if targets is not None:
            for item in targets:
                values = values + (targetsDict.get(item, None),)

        if conditions is not None:
            for item in conditions:
                values = values + (conditionsDict.get(item, None),)  # Ԫ�����

        try:
            cursor.execute(sql, values)
            conn.commit()
        except Exception as e:
            print(e)
            conn.rollback()
        conn.close()


if __name__ == '__main__':
    #     SqlExecuteHelper().queryValuesFromTable('repository',['id','node_id'], {'id':8514,'node_id':'MDEwOlJlcG9zaXRvcnk4NTE0'})
    #     SqlExecuteHelper().queryValuesFromTable('userList',['login'],{'login':'rails'})
    #     SqlExecuteHelper().deleteValuesFromTable('userList',['login'],{'login':'rails'})
    SqlExecuteHelper().deleteValuesFromTable('repository', None, None)
    SqlExecuteHelper().deleteValuesFromTable('userList', None, None)

#    SqlExecuteHelper().updateValuesFromTable('userList', ['name','email'], {'name':'name1','email':None}, ['id'], {'id':4223})
