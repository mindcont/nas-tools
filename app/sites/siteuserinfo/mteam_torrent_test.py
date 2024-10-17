# -*- coding: utf-8 -*-
import re

import requests

import log

# from app.sites.siteuserinfo._base import _ISiteUserInfo, SITE_BASE_ORDER
from app.utils import StringUtils, RequestUtils
from app.utils.types import SiteSchema
from config import Config
from app.apis import MTeamApi

g_sys_role_list = []

# 系统角色
class MTeamSysRole(object):
    _id = ""
    _nameChs = ""
    _nameCht = ""
    _nameEng = ""
    _image = ""
    _color = ""
    _readAccess = 0
    _classUp = 0
    _registerWeek = 0
    _downloaded = 0
    _shareRate = 0
    _shareRateLimit = 0
    _sortPoint = 0






# 馒头站点解析
class MTeamTorrentUserInfo:

    def __init__(self, site_name, site_domain_url="", site_cookie="", session=None, ua="", apikey="", emulate=False,
                 proxy=""):
        self.schema = SiteSchema.MTeamTorrent
        self.order = 100
        self._base_url = site_domain_url
        self._cookie = site_cookie
        self._apikey = apikey
        self._proxy = proxy
        self._ua = ua
        self.session = session
        self.emulate = emulate
        self.userid = ""
        self.username = ""
        self.user_level = ""
        self.join_at = ""
        self.ratio = 0
        self.bonus = 0
        self.upload = 0
        self.download = 0
        self.seeding = 0
        self.leeching = 0
        self.seeding_size = 0
        self.seeding_info = []
        self.leeching_info = []

    @classmethod
    def match(cls, html_text):
        # 馒头手动绑定
        return False

    def _parse_logged_in(self, html_text):
        """
        解析用户是否已经登陆，馒头不需要判断登陆
        :param html_text:
        :return: True/False
        """
        # log.info(f"【MTeamUserInfo】 检查登陆成功")
        return True

    # 取系统角色
    def _mt_get_sys_roles(self):
        global g_sys_role_list
        if len(g_sys_role_list) > 0:
            return
        if not self._apikey:
            self.err_msg = "未设置站点Api-Key"
            log.warn(f"【MTeamUserInfo】 获取馒头系统角色失败, 未设置站点Api-Key")
            return
        site_url = "%s/api/member/sysRoleList" % MTeamApi.parse_api_domain(
            self._base_url
        )
        proxies = Config().get_proxies() if self._proxy else None
        res = RequestUtils(
            headers={
                "x-api-key": self._apikey,
                "Content-Type": "application/json",
                "User-Agent": self._ua,
                "Accept": "application/json",
            },
            proxies=proxies,
            timeout=30,
        ).post_res(url=site_url)
        if res and res.status_code == 200:
            msg = res.json().get("message")
            if msg != "SUCCESS":
                log.warn(f"【MTeamUserInfo】 获取馒头系统角色失败：{msg}")
                return
            results = res.json().get("data", [])
            for result in results:
                sysrole = MTeamSysRole()
                sysrole._id = result.get("id")
                sysrole._nameChs = result.get("nameChs")
                sysrole._nameCht = result.get("nameCht")
                sysrole._nameEng = result.get("nameEng")
                sysrole._image = result.get("image")
                sysrole._color = result.get("color")
                sysrole._readAccess = toint(result.get("readAccess"))
                sysrole._classUp = toint(result.get("classUp"))
                sysrole._registerWeek = toint(result.get("registerWeek"))
                sysrole._downloaded = toint(result.get("downloaded"))
                sysrole._shareRate = toint(result.get("shareRate"))
                sysrole._shareRateLimit = toint(result.get("shareRateLimit"))
                sysrole._sortPoint = toint(result.get("sortPoint"))
                g_sys_role_list.append(sysrole)
            log.info(
                f"【MTeamUserInfo】 获取馒头系统角色成功，共有{len(g_sys_role_list)}个角色"
            )
        elif res is not None:
            log.warn(
                f"【MTeamUserInfo】 获取馒头系统角色失败，错误码：{res.status_code}"
            )
        else:
            log.warn(f"【MTeamUserInfo】 获取馒头系统角色失败，无法连接 {site_url}")

    # 取用户属性
    def _mt_getprofile(self):
        if not self._apikey:
            self.err_msg = "未设置站点Api-Key"
            log.warn(f"【MTeamUserInfo】 获取馒头用户属性失败, 未设置站点Api-Key")
            return None
        site_url = "%s/api/member/profile" % MTeamApi.parse_api_domain(self._base_url)
        proxies = Config().get_proxies() if self._proxy else None
        res = RequestUtils(
            headers={
                "x-api-key": self._apikey,
                "Content-Type": "application/json",
                "User-Agent": self._ua,
                "Accept": "application/json",
            },
            proxies=proxies,
            timeout=30,
        ).post_res(url=site_url)
        if res and res.status_code == 200:
            msg = res.json().get("message")
            if msg != "SUCCESS":
                log.warn(f"【MTeamUserInfo】 获取馒头用户属性失败：{msg}")
                return None
            result = res.json().get("data", {})
            self.userid = result.get("id", "0")
            self.username = result.get("username")
            log.info(
                f"【MTeamUserInfo】 获取馒头用户属性成功: uid:{self.userid} username:{self.username}"
            )
            return result
        elif res is not None:
            log.warn(
                f"【MTeamUserInfo】 获取馒头用户属性失败，错误码：{res.status_code}"
            )
        else:
            log.warn(f"【MTeamUserInfo】 获取馒头用户属性失败，无法连接 {site_url}")
        return None

    def _mt_get_user_level(self, roleid):
        global g_sys_role_list
        if roleid is None:
            return ""
        for sysrole in g_sys_role_list:
            if sysrole._id == roleid:
                return sysrole._nameEng
        return ""

    # 在该函数里把用户所有信息返回
    def _parse_user_base_info(self, html_text):
        self._user_detail_page = ""
        self._torrent_seeding_page = ""
        self._user_detail_page = ""
        self._mt_get_sys_roles()
        user_data = self._mt_getprofile()
        if user_data is None:
            return
        memberCount = user_data.get("memberCount", {})
        # 用户等级
        self.user_level = self._mt_get_user_level(user_data.get("role"))
        # 加入日期
        self.join_at = user_data.get("createdDate", "")
        # 分享率
        self.ratio = memberCount.get("shareRate", 0)
        # 积分
        self.bonus = memberCount.get("bonus", 0)
        # 上传
        self.upload = toint(memberCount.get("uploaded", 0))
        # 下载
        self.download = toint(memberCount.get("downloaded", 0))
        # 拉取做种信息
        # self._mt_get_seeding_info()
        # 拉取下载信息
        # self._mt_get_leeching_info()

        log.info(f"【MTeamUserInfo】 用户信息：{self.username} {self.user_level} {self.join_at} {self.ratio} {self.bonus} {self.upload} {self.download} {self.seeding} {self.leeching} {self.seeding_size} {self.seeding_info} {self.leeching_info}")

    def _parse_site_page(self, html_text):
        # TODO
        pass

    def _parse_user_detail_info(self, html_text):
        """
        解析用户额外信息，加入时间，等级
        :param html_text:
        :return:
        """

    # 翻页获取做种信息
    def _mt_get_seeding_info(self, page_num=1, page_size=100):
        if not self._apikey:
            self.err_msg = "未设置站点Api-Key"
            log.warn(f"【MTeamUserInfo】 获取做种信息失败, 未设置站点Api-Key")
            return
        site_url = "%s/api/member/getUserTorrentList" % MTeamApi.parse_api_domain(
            self._base_url
        )
        params = {
            "userid": self.userid,
            "type": "SEEDING",
            "pageNumber": page_num,
            "pageSize": page_size,
        }
        proxies = Config().get_proxies() if self._proxy else None
        res = RequestUtils(
            headers={
                "x-api-key": self._apikey,
                "Content-Type": "application/json",
                "User-Agent": self._ua,
                "Accept": "application/json",
            },
            proxies=proxies,
            timeout=30,
        ).post_res(url=site_url, json=params)
        if res and res.status_code == 200:
            msg = res.json().get("message")
            if msg != "SUCCESS":
                log.warn(f"【MTeamUserInfo】 获取做种信息失败：{msg}")
                return
            res_data = res.json().get("data", {})
            total = toint(res_data.get("total"))
            total_pages = toint(res_data.get("totalPages"))
            # 做种数量
            self.seeding = total

            results = res_data.get("data", [])
            for result in results:
                peer_info = result.get("peer")
                torrent_info = result.get("torrent")
                torrent_status = torrent_info.get("status")
                # 做种大小
                self.seeding_size += toint(torrent_info.get("size"))
                # 做种人数, 种子大小
                self.seeding_info.append(
                    [
                        toint(torrent_status.get("seeders")),
                        toint(torrent_info.get("size")),
                    ]
                )
            if total_pages > page_num:
                return self._mt_get_seeding_info(page_num + 1, page_size)
        elif res is not None:
            log.warn(f"【MTeamUserInfo】 获取做种信息失败，错误码：{res.status_code}")
        else:
            log.warn(f"【MTeamUserInfo】 获取做种信息失败，无法连接 {site_url}")

    # 翻页获取下载信息
    def _mt_get_leeching_info(self, page_num=1, page_size=100):
        if not self._apikey:
            self.err_msg = "未设置站点Api-Key"
            log.warn(f"【MTeamUserInfo】 获取下载信息失败, 未设置站点Api-Key")
            return
        site_url = "%s/api/member/getUserTorrentList" % MTeamApi.parse_api_domain(
            self._base_url
        )
        params = {
            "userid": self.userid,
            "type": "LEECHING",
            "pageNumber": page_num,
            "pageSize": page_size,
        }
        proxies = Config().get_proxies() if self._proxy else None
        res = RequestUtils(
            headers={
                "x-api-key": self._apikey,
                "Content-Type": "application/json",
                "User-Agent": self._ua,
                "Accept": "application/json",
            },
            proxies=proxies,
            timeout=30,
        ).post_res(url=site_url, json=params)
        if res and res.status_code == 200:
            msg = res.json().get("message")
            if msg != "SUCCESS":
                log.warn(f"【MTeamUserInfo】 获取下载信息失败：{msg}")
                return
            res_data = res.json().get("data", {})
            total = toint(res_data.get("total"))
            # 下载数量
            self.leeching = total
        elif res is not None:
            log.warn(f"【MTeamUserInfo】 获取下载信息失败，错误码：{res.status_code}")
        else:
            log.warn(f"【MTeamUserInfo】 获取下载信息失败，无法连接 {site_url}")

    def _parse_user_torrent_seeding_info(self, html_text, multi_page=False):
        """
        做种相关信息
        :param html_text:
        :param multi_page: 是否多页数据
        :return: 下页地址
        """

    def _parse_user_traffic_info(self, html_text):
        pass

    def _parse_message_unread_links(self, html_text, msg_links):
        return None

    def _parse_message_content(self, html_text):
        return None, None, None


def toint(v):
    return int(float(v))

# 示例输入信息
site_name = "M-Team"
site_domain_url = "https://m-team.cc"
site_cookie = "your_cookie_here"
session = requests.Session()  # 假设你使用 requests 库
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
apikey = "cd8470e0-d95c-4a60-9667-c32680e1a93b"
emulate = True
proxy = "http://your_proxy_here"

# 检查站点域名并调用 MTeamTorrentUserInfo
mt= MTeamTorrentUserInfo(site_name, site_domain_url, site_cookie, session, ua, apikey, emulate, proxy)
print(mt._base_url)

print(mt._mt_get_sys_roles())
# mt._mt_getprofile()
# mt._mt_get_user_level(1)
# 解析用户信息
html_text = "your_html_text_here"
mt._parse_user_base_info(html_text)
# mt._mt_get_sys_roles()
