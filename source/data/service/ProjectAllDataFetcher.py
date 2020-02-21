#coding=gbk
from source.data.service.ApiHelper import ApiHelper
from source.database.SqlExecuteHelper import SqlExecuteHelper
from source.database.SqlUtils import SqlUtils
from source.database.SqlServerInterceptor import SqlServerInterceptor


class ProjectAllDataFetcher:
    '''���ڻ�ȡ��Ŀ������Ϣ����'''
    
    
    def getAllDataForProject(self, owner, repo):
        
        helper = ApiHelper(owner=owner,repo=repo)
        helper.setAuthorization(True)
        
        self.getDataForRepository(helper)
        '''��ȡ��Ŀ����Ϣ'''
        
    
    def getDataForRepository(self, helper):
        
        project = helper.getInformationForProject()
        print(project)
        if(project != None):
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_REPOS
                                                   , project.getItemKeyList()
                                                   , project.getValueDict()
                                                   , project.getIdentifyKeys())
        #�洢��Ŀ��owner��Ϣ 
        if(project.owner != None and project.owner.login != None):
            user = helper.getInformationForUser(project.owner.login)
#             user = SqlServerInterceptor.convertFromBeanbaseToOutput(user) 
            
            print(user.getValueDict())
            
            SqlExecuteHelper.insertValuesIntoTable(SqlUtils.STR_TABLE_NAME_USER
                                                   , user.getItemKeyList()
                                                   , user.getValueDict()
                                                   , user.getIdentifyKeys())

    def getPullRequestForRepository(self, helper):
        pass
        

    

if __name__ == '__main__':
    ProjectAllDataFetcher().getAllDataForProject('rails','rails')
    ProjectAllDataFetcher().getAllDataForProject('ctripcorp','apollo')
    
    