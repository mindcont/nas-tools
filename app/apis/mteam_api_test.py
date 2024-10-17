# coding: utf-8
import json
import os
import shutil
from datetime import datetime

import re
import log
from app.helper import ChromeHelper, SiteHelper, DbHelper, RssHelper
# from app.message import Message
# from app.sites.site_limiter import SiteRateLimiter
from app.utils import RequestUtils, StringUtils, PathUtils, ExceptionUtils
# from app.utils.commons import singleton
from config import Config, RMT_SUBEXT
from urllib import parse

class MTeamApi:
    # 根据站点域名解析api域名
    @staticmethod
    def parse_api_domain(url):
        if not url:
            return ""
        scheme, netloc = StringUtils.get_url_netloc(url)
        parts = netloc.split('.')
        domain = ""
        if len(parts) > 2:
            parts[0] = "api"
            domain = '.'.join(parts)
        else:
            domain = "api."+'.'.join(parts)
        return f"{scheme}://{domain}"
    # 测试站点连通性
    @staticmethod
    def test_mt_connection(site_info):
        # 计时
        start_time = datetime.now()
        site_url = MTeamApi.parse_api_domain(site_info.get("signurl")) + "/api/system/hello"
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": site_info.get("ua"),
            "x-api-key": site_info.get("apikey"),
            "Accept": "application/json"
        }
        res = RequestUtils(headers=headers,
                           proxies=Config().get_proxies() if site_info.get("proxy") else None
                           ).post_res(url=site_url)
        seconds = int((datetime.now() - start_time).microseconds / 1000)
        if res and res.status_code == 200:
            msg = res.json().get("message") or "null"
            if msg == "SUCCESS":
                return True, "连接成功", seconds
            else:
                return False, msg, seconds
        elif res is not None:
            return False, f"连接失败，状态码：{res.status_code}", seconds
        else:
            return False, "无法打开网站", seconds

    # 根据种子详情页查询种子地址
    @staticmethod
    def get_torrent_url_by_detail_url(base_url, detailurl, site_info):
        m = re.match(".+/detail/([0-9]+)", detailurl)
        if not m:
            log.warn(f"【MTeanApi】 获取馒头种子连接失败 path：{detailurl}")
            return ""
        torrentid = int(m.group(1))
        apikey = site_info.get("apikey")
        if not apikey:
            log.warn(f"【MTeanApi】 {torrentid}未设置站点Api-Key，无法获取种子连接")
            return ""
        downloadurl = "%s/api/torrent/genDlToken" % MTeamApi.parse_api_domain(base_url)
        res = RequestUtils(
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": site_info.get("ua"),
                "x-api-key": site_info.get("apikey"),
            },
            proxies=Config().get_proxies() if site_info.get("proxy") else None,
            timeout=30
        ).post_res(url=downloadurl, data=("id=%d" % torrentid))
        if res and res.status_code == 200:
            res_json = res.json()
            msg = res_json.get('message')
            torrent_url = res_json.get('data')
            if msg != "SUCCESS":
                log.warn(f"【MTeanApi】 {torrentid}获取种子连接失败：{msg}")
                return ""
            log.info(f"【MTeanApi】 {torrentid} 获取馒头种子连接成功: {torrent_url}")
            return torrent_url
        elif res is not None:
            log.warn(f"【MTeanApi】 {torrentid}获取种子连接失败，错误码：{res.status_code}")
        else:
            log.warn(f"【MTeanApi】 {torrentid}获取种子连接失败，无法连接 {downloadurl}")
        return ""

    # 拉取馒头字幕列表
    @staticmethod
    def get_subtitle_list(base_url, torrentid, ua, apikey):
        subtitle_list = []
        site_url = "%s/api/subtitle/list" % base_url
        res = RequestUtils(
            headers={
                'x-api-key': apikey,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": ua,
                "Accept": "application/json"
            },
            timeout=30
        ).post_res(url=site_url, data=("id=%d" % torrentid))
        if res and res.status_code == 200:
            msg = res.json().get('message')
            if msg != "SUCCESS":
                log.warn(f"【MTeanApi】 获取馒头{torrentid}字幕列表失败：{msg}")
                return subtitle_list
            results = res.json().get('data', [])
            for result in results:
                subtitle = {
                    "id": result.get("id"),
                    "filename": result.get("filename"),
                }
                subtitle_list.append(subtitle)
            log.info(f"【MTeanApi】 获取馒头{torrentid}字幕列表成功，捕获：{len(subtitle_list)}条字幕信息")
        elif res is not None:
            log.warn(f"【MTeanApi】 获取馒头{torrentid}字幕列表失败，错误码：{res.status_code}")
        else:
            log.warn(f"【MTeanApi】 获取馒头{torrentid}字幕列表失败，无法连接 {site_url}")
        return subtitle_list

    # 下载单个馒头字幕
    @staticmethod
    def download_single_subtitle(base_url, torrentid, subtitle_info, ua, apikey, download_dir):
        subtitle_id = int(subtitle_info.get("id"))
        filename = subtitle_info.get("filename")
        # log.info(f"【Sites】开始下载馒头{torrentid}字幕 {filename}")
        site_url = "%s/api/subtitle/dl?id=%d" % (base_url, subtitle_id)
        res = RequestUtils(
            headers={
                'x-api-key': apikey,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": ua,
                "Accept": "*/*"
            },
            timeout=30
        ).get_res(site_url)
        if res and res.status_code == 200:
            # 创建目录
            if not os.path.exists(download_dir):
                os.makedirs(download_dir, exist_ok=True)
            # 保存ZIP
            file_name = filename
            if not file_name:
                log.warn(f"【MTeanApi】 馒头{torrentid} 字幕文件非法：{subtitle_id}")
                return
            save_tmp_path = Config().get_temp_path()
            if file_name.lower().endswith(".zip"):
                # ZIP包
                zip_file = os.path.join(save_tmp_path, file_name)
                # 解压路径
                zip_path = os.path.splitext(zip_file)[0]
                with open(zip_file, 'wb') as f:
                    f.write(res.content)
                # 解压文件
                shutil.unpack_archive(zip_file, zip_path, format='zip')
                # 遍历转移文件
                for sub_file in PathUtils.get_dir_files(in_path=zip_path, exts=RMT_SUBEXT):
                    target_sub_file = os.path.join(download_dir,
                                                   os.path.splitext(os.path.basename(sub_file))[0])
                    log.info(f"【MTeanApi】 馒头{torrentid} 转移字幕 {sub_file} 到 {target_sub_file}")
                    SiteHelper.transfer_subtitle(sub_file, target_sub_file)
                # 删除临时文件
                try:
                    shutil.rmtree(zip_path)
                    os.remove(zip_file)
                except Exception as err:
                    ExceptionUtils.exception_traceback(err)
            else:
                sub_file = os.path.join(save_tmp_path, file_name)
                # 保存
                with open(sub_file, 'wb') as f:
                    f.write(res.content)
                target_sub_file = os.path.join(download_dir,
                                               os.path.splitext(os.path.basename(sub_file))[0])
                log.info(f"【MTeanApi】 馒头{torrentid} 转移字幕 {sub_file} 到 {target_sub_file}")
                SiteHelper.transfer_subtitle(sub_file, target_sub_file)
        elif res is not None:
            log.warn(f"【MTeanApi】 下载馒头{torrentid}字幕 {filename} 失败，错误码：{res.status_code}")
        else:
            log.warn(f"【MTeanApi】 下载馒头{torrentid}字幕 {filename} 失败，无法连接 {site_url}")

    # 下载馒头字幕
    @staticmethod
    def download_subtitle(media_info, site_id, cookie, ua, apikey, download_dir):
        addr = parse.urlparse(media_info.page_url)
        log.info(f"【Sites】下载馒头字幕 {media_info.page_url}")
        # /detail/770**
        m = re.match("/detail/([0-9]+)", addr.path)
        if not m:
            log.warn(f"【MTeanApi】 获取馒头字幕失败 path：{addr.path}")
            return
        torrentid = int(m.group(1))
        if not apikey:
            log.warn(f"【MTeanApi】 获取馒头字幕失败, 未设置站点Api-Key")
            return
        base_url = MTeamApi.parse_api_domain(media_info.page_url)
        subtitle_list = MTeamApi.get_subtitle_list(base_url, torrentid, ua, apikey)
        # 下载所有字幕文件
        for subtitle_info in subtitle_list:
            MTeamApi.download_single_subtitle(base_url, torrentid, subtitle_info, ua, apikey, download_dir)

    # 检查m-team种子属性
    @staticmethod
    def check_torrent_attr(torrent_url, ua=None, apikey=None, proxy=False):
        ret_attr = {
            "free": False,
            "2xfree": False,
            "hr": False,
            "peer_count": 0,
            "downloadvolumefactor": 1.0,
            "uploadvolumefactor": 1.0,
        }
        addr = parse.urlparse(torrent_url)
        # /detail/770**
        m = re.match("/detail/([0-9]+)", addr.path)
        if not m:
            log.warn(f"【MTeanApi】 获取馒头种子属性失败 path：{addr.path}")
            return ret_attr
        torrentid = int(m.group(1))
        if not apikey:
            log.warn(f"【MTeanApi】 获取馒头种子属性失败, 未设置站点Api-Key")
            return ret_attr
        site_url = "%s/api/torrent/detail" % MTeamApi.parse_api_domain(torrent_url)
        res = RequestUtils(
            headers={
                'x-api-key': apikey,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": ua,
                "Accept": "application/json",
                # "origin": "https://kp.m-team.cc",
                # "authorization": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ4aG91c2UiLCJ1aWQiOjMxNzk1NiwianRpIjoiMmI2MTkwMDAtNTdhZS00ZDJmLWI5Y2UtY2FlODU1ZjBmNGE4IiwiaXNzIjoiaHR0cHM6Ly9hcGkubS10ZWFtLmNjIiwiaWF0IjoxNzI5MDY4MDIyLCJleHAiOjE3MzE2NjAwMjJ9.xVEEscsc4LP8rEen7F-ywj4z18qVDX9Wh-IM3NDlRhxnahI4VjicCt_yjlbIkd2iZmgSB7mlqsTEpP2qDcoYBA",
                # "Cookie": "cf_clearance=mFSX_y7Yw_9hfYO0Cs_hsm5Cb6NbKtRwEwypo0bIWgs-1729049848-1.2.1.1-jLzrrzOmlUBZgAEO5xVScu1CK3fr0_z3v3q3Gd3wSQi4h4ru5ZR2CNkKVVPrPjGcmO.V6bo8VYOIUs4u3QgyiZa22SxuaW7IRFhGFG.wYcKYITq3g_XzDP52__cPJzN3nFQW6_3r3CY50zF6gFPDYFt0zT4ErPE5vy28z6CTKkFKf_x68OZIhGhQtMvyhw9otoC0Hi0LtG8kvMYKJyYQlQTIktA9w54BBBIu6Z_mAOZl5nE8l.riJVavFrrvdpxNcJ37lg6VMx392vqqqVOVfJI0YQqnS3QaNnDMYlV8TKena46BKx04ZIOrlHZrnoQA_kZS859zStAgdj5CoGG5w2uBI9XLqjin8ha_njDYdt6KpjV8N_Q0Pxt0VSo4c61zHRbCF_aS8lw_tK6jBtc3sw7n.rAGCPvUi80Ikx6RTbcj6eWmxgwjiyq47AFoKRcY"
            },
            proxies=proxy,
            timeout=30
        ).post_res(url=site_url, data=("id=%d" % torrentid))
        if res and res.status_code == 200:
            msg = res.json().get('message')
            if msg != "SUCCESS":
                log.warn(f"【MTeanApi】 获取馒头种子{torrentid}属性失败：{msg}")
                return ret_attr
            result = res.json().get('data', {})
            status = result.get('status')
            ret_attr["peer_count"] = int(status.get('seeders'))
            """
            NORMAL:上传下载都1倍
            _2X_FREE:上傳乘以二倍，下載不計算流量。
            _2X_PERCENT_50:上傳乘以二倍，下載計算一半流量。
            _2X:上傳乘以二倍，下載計算正常流量。
            PERCENT_50:上傳計算正常流量，下載計算一半流量。
            PERCENT_30:上傳計算正常流量，下載計算該種子流量的30%。
            FREE:上傳計算正常流量，下載不計算流量。
            """
            discount = status.get('discount')
            if discount == "_2X_FREE":
                ret_attr["2xfree"] = True
                ret_attr["free"] = True
                ret_attr["downloadvolumefactor"] = 0
                ret_attr["uploadvolumefactor"] = 2.0
            elif discount == "_2X_PERCENT_50":
                ret_attr["2xfree"] = True
                ret_attr["free"] = True
                ret_attr["downloadvolumefactor"] = 0.5
                ret_attr["uploadvolumefactor"] = 2.0
            elif discount == "_2X":
                ret_attr["2xfree"] = True
                ret_attr["free"] = True
                ret_attr["downloadvolumefactor"] = 1.0
                ret_attr["uploadvolumefactor"] = 2.0
            elif discount == "PERCENT_50":
                ret_attr["downloadvolumefactor"] = 0.5
                ret_attr["uploadvolumefactor"] = 1.0
            elif discount == "PERCENT_30":
                ret_attr["downloadvolumefactor"] = 0.3
                ret_attr["uploadvolumefactor"] = 1.0
            elif discount == "FREE":
                ret_attr["free"] = True
                ret_attr["downloadvolumefactor"] = 0
                ret_attr["uploadvolumefactor"] = 1.0
            log.info(f"【MTeanApi】获取馒头种子{torrentid}属性成功: {ret_attr}")
        elif res is not None:
            log.warn(f"【MTeanApi】 获取馒头种子{torrentid}属性失败，错误码：{res.status_code}")
        else:
            log.warn(f"【MTeanApi】 获取馒头种子{torrentid}属性失败，无法连接 {site_url}")
        return ret_attr


site_info = {
    "signurl": "https://api.m-team.io/",
    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "apikey": "cd8470e0-d95c-4a60-9667-c32680e1a93b"
}

# 连接测试
# result = MTeamApi.test_mt_connection(site_info)
# print(result)

# 获取种子属性
# torrent_url = "https://kp.m-team.cc/detail/841831"
# ret= MTeamApi.check_torrent_attr(torrent_url, site_info["ua"], site_info["apikey"], )
# print(ret)

# #获取种子下载地址
torrent_url = "https://kp.m-team.cc/detail/841831"
ret = MTeamApi.get_torrent_url_by_detail_url(torrent_url, torrent_url, site_info)
print(ret)

#订阅地址RSS的解析获取
# rss_url = "https://rss.m-team.cc/api/rss/fetch?audioCodecs=1%2C2%2C3%2C4%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C15&categories=410%2C424%2C437%2C431%2C429%2C430%2C426%2C432%2C436%2C440%2C425%2C433%2C411%2C412%2C413&labels=7&pageSize=50&sign=cdcdefcef3a62e43f45f945d96edf43d&standards=1%2C2%2C3%2C5%2C6%2C7&t=1719150153&tkeys=ttitle%2Ctcat%2Ctsmalldescr%2Ctsize%2Ctuploader&uid=317956&videoCodecs=1%2C2%2C3%2C4%2C16%2C19%2C21"
# ret_array = RssHelper.parse_rssxml(rss_url)
# print(ret_array[0])
#
# #对 ret_array 进行处理, 从中提取出 title, enclosure,  并通过 check_torrent_attr 获取种子属性
# if not ret_array:
#     print("No ret_array")
#     exit()
# for item in ret_array:
#     title = item.get("title")
#     enclosure = item.get("enclosure")
#     print(title, enclosure)
#     ret = MTeamApi.check_torrent_attr(enclosure, site_info["ua"], site_info["apikey"])
#     print(ret)