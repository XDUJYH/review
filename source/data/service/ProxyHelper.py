# coding=gbk
import aiohttp
import requests


class ProxyHelper:
    """����ʹ�� ip����� proxy_pool��api�ӿ���"""

    STR_PROXY_GET_API = "http://127.0.0.1:5010/get/"
    STR_PROXY_GET_ALL_API = 'http://127.0.0.1:5010/get_all/'
    STR_PROXY_DELETE_API = 'http://127.0.0.1:5010/delete/?proxy={}'

    STR_KEY_PROXY = 'proxy'

    ip_pool = {}  # ip�����

    INT_INITIAL_POINT = 5
    INT_POSITIVE_POINT = 2  # ����������
    INT_NEGATIVE_POINT = -1  # ����������
    INT_DELETE_POINT = 0  # ɾ������
    INT_KILL_POINT = -100  # ֱ�Ӹɵ�

    @staticmethod
    async def getAsyncSingleProxy():
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(ProxyHelper.STR_PROXY_GET_API) as response:
                    json = await response.json(content_type=None)
            except Exception as e:
                print(e)
            if json is not None:
                proxy = json.get(ProxyHelper.STR_KEY_PROXY, None)
                if proxy is not None and ProxyHelper.ip_pool.get(proxy, None) is None:
                    ProxyHelper.ip_pool[proxy] = ProxyHelper.INT_INITIAL_POINT
                return proxy

    @staticmethod
    def getSingleProxy():
        json = requests.get(ProxyHelper.STR_PROXY_GET_API).json()
        if json is not None:
            proxy = json.get(ProxyHelper.STR_KEY_PROXY, None)
            if proxy is not None and ProxyHelper.ip_pool.get(proxy, None) is None:
                ProxyHelper.ip_pool[proxy] = ProxyHelper.INT_INITIAL_POINT
            return proxy

    @staticmethod
    def getAllProxy():
        return requests.get(ProxyHelper.STR_PROXY_GET_ALL_API).json()

    @staticmethod
    def delete_proxy(proxy):
        print('delete proxy:', proxy)
        requests.get(ProxyHelper.STR_PROXY_DELETE_API.format(proxy))

    @staticmethod
    async def judgeProxy(proxy, point):
        now = ProxyHelper.ip_pool[proxy]
        if now is not None:
            now += point
            if now < ProxyHelper.INT_DELETE_POINT:
                ProxyHelper.ip_pool.pop(proxy)
                ProxyHelper.delete_proxy(proxy)
            else:
                ProxyHelper.ip_pool[proxy] = now


if __name__ == '__main__':
    print(ProxyHelper.getSingleProxy())
