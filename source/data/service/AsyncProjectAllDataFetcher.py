# coding=gbk
import asyncio
import time

from source.config.configPraser import configPraser
from source.data.service.ApiHelper import ApiHelper
from source.data.service.AsyncApiHelper import AsyncApiHelper


class AsyncProjectAllDataFetcher:
    # ��ȡ��Ŀ��������Ϣ ������Ϣ�����첽��ȡ

    @staticmethod
    def getDataForRepository(owner, repo, limit=-1, start=-1):

        if start == -1:
            # ��ȡ��Ŀpull request������ ����ʹ��ͬ��������ȡ
            requestNumber = ApiHelper(owner, repo).getMaxSolvedPullRequestNumberForProject()
            print("total pull request number:", requestNumber)

            startNumber = requestNumber
        else:
            startNumber = start

        if limit == -1:
            limit = startNumber

        semaphore = asyncio.Semaphore(configPraser.getSemaphore())  # ���ٶ���������

        AsyncApiHelper.setRepo(owner, repo)

        t1 = time.time()
        loop = asyncio.get_event_loop()
        tasks = [asyncio.ensure_future(AsyncApiHelper.downloadInformation(pull_number, semaphore))
                 for pull_number in range(start, max(start - limit, 0), -1)]
        tasks = asyncio.gather(*tasks)
        loop.run_until_complete(tasks)

        t2 = time.time()
        print('cost time:', t2 - t1)


if __name__ == '__main__':
    AsyncProjectAllDataFetcher.getDataForRepository(owner=configPraser.getOwner(), repo=configPraser.getRepo()
                                                    , start=configPraser.getStart(), limit=configPraser.getLimit())
