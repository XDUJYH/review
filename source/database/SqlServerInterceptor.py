#coding=gbk
from source.utils.DataInterceptor import DataInterceptor
from source.data.bean.Beanbase import BeanBase

class SqlServerInterceptor(DataInterceptor):
    '''dataInterceptor��ʵ����'''
    
    @staticmethod
    def convertFromBeanbaseToOutput(bean):
        
        if(not isinstance(bean, BeanBase)):
            return None #��������ת��ʧ��
        
        #sqlserver��bit�洢��bool������Ҫת��
        
        for item in bean.getItemKeyListWithType():
            if(item[1] == BeanBase.DATA_TYPE_BOOLEAN):
                if(getattr(bean,item[0], None) == True):
                    setattr(bean,item[0], 1)
                elif(getattr(bean, item[0], None) == False):
                    setattr(bean,item[0],0)
        
        return bean
        