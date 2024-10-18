import xml.dom.minidom

from app.db import MainDb, DbPersist
from app.db.models import RSSTORRENTS
from app.utils import RssTitleUtils, StringUtils, RequestUtils, ExceptionUtils, DomUtils
from config import Config
import log

class RssHelper:
    _db = MainDb()

    @staticmethod
    def parse_rssxml(url, proxy=False):
        """
        解析RSS订阅URL，获取RSS中的种子信息
        :param url: RSS地址
        :param proxy: 是否使用代理
        :return: 种子信息列表，如为None代表Rss过期
        """
        _special_title_sites = {
            'pt.keepfrds.com': RssTitleUtils.keepfriends_title
        }

        _rss_expired_msg = [
            "RSS 链接已过期, 您需要获得一个新的!",
            "RSS Link has expired, You need to get a new one!"
        ]

        # 开始处理
        ret_array = []
        if not url:
            return []
        site_domain = StringUtils.get_url_domain(url)
        try:
            ret = RequestUtils(proxies=Config().get_proxies() if proxy else None).get_res(url)
            if not ret:
                return []
            ret.encoding = ret.apparent_encoding
        except Exception as e2:
            ExceptionUtils.exception_traceback(e2)
            return []
        if ret:
            ret_xml = ret.text
            try:
                # 解析XML
                dom_tree = xml.dom.minidom.parseString(ret_xml)
                rootNode = dom_tree.documentElement
                items = rootNode.getElementsByTagName("item")
                for item in items:
                    try:
                        # 标题
                        title = DomUtils.tag_value(item, "title", default="")
                        if not title:
                            continue
                        # 标题特殊处理
                        if site_domain and site_domain in _special_title_sites:
                            title = _special_title_sites.get(site_domain)(title)
                        # 描述
                        description = DomUtils.tag_value(item, "description", default="")
                        # 种子页面
                        link = DomUtils.tag_value(item, "link", default="")
                        # 种子链接
                        enclosure = DomUtils.tag_value(item, "enclosure", "url", default="")
                        if not enclosure and not link:
                            continue
                        # 部分RSS只有link没有enclosure
                        if not enclosure and link:
                            enclosure = link
                            link = None
                        # 大小
                        size = DomUtils.tag_value(item, "enclosure", "length", default=0)
                        if size and str(size).isdigit():
                            size = int(size)
                        else:
                            size = 0
                        # 发布日期
                        pubdate = DomUtils.tag_value(item, "pubDate", default="")
                        if pubdate:
                            # 转换为时间
                            pubdate = StringUtils.get_time_stamp(pubdate)
                        # 返回对象
                        tmp_dict = {'title': title,
                                    'enclosure': enclosure,
                                    'size': size,
                                    'description': description,
                                    'link': link,
                                    'pubdate': pubdate}
                        ret_array.append(tmp_dict)
                    except Exception as e1:
                        ExceptionUtils.exception_traceback(e1)
                        continue
            except Exception as e2:
                # RSS过期 观众RSS 链接已过期，您需要获得一个新的！  pthome RSS Link has expired, You need to get a new one!
                if ret_xml in _rss_expired_msg:
                    return None
                ExceptionUtils.exception_traceback(e2)
        return ret_array

    @DbPersist(_db)
    def insert_rss_torrents(self, media_info):
        """
        将RSS的记录插入数据库
        """
        self._db.insert(
            RSSTORRENTS(
                TORRENT_NAME=media_info.org_string,
                ENCLOSURE=media_info.enclosure,
                TYPE=media_info.type.value,
                TITLE=media_info.title,
                YEAR=media_info.year,
                SEASON=media_info.get_season_string(),
                EPISODE=media_info.get_episode_string()
            ))

    def is_rssd_by_enclosure(self, enclosure):
        """
        查询RSS是否处理过，根据下载链接
        """
        if not enclosure:
            return True
        if self._db.query(RSSTORRENTS).filter(RSSTORRENTS.ENCLOSURE == enclosure).count() > 0:
            return True
        else:
            return False

    def is_rssd_by_simple(self, torrent_name, enclosure):
        """
        查询RSS是否处理过，根据名称
        """
        if not torrent_name and not enclosure:
            return True
        if enclosure:
            ret = self._db.query(RSSTORRENTS).filter(RSSTORRENTS.ENCLOSURE == enclosure).count()
        else:
            ret = self._db.query(RSSTORRENTS).filter(RSSTORRENTS.TORRENT_NAME == torrent_name).count()
        return True if ret > 0 else False

    @DbPersist(_db)
    def simple_insert_rss_torrents(self, title, enclosure):
        """
        将RSS的记录插入数据库
        """
        self._db.insert(
            RSSTORRENTS(
                TORRENT_NAME=title,
                ENCLOSURE=enclosure
            ))

    @DbPersist(_db)
    def simple_delete_rss_torrents(self, title, enclosure=None):
        """
        删除RSS的记录
        """
        if enclosure:
            self._db.query(RSSTORRENTS).filter(RSSTORRENTS.TORRENT_NAME == title,
                                               RSSTORRENTS.ENCLOSURE == enclosure).delete()
        else:
            self._db.query(RSSTORRENTS).filter(RSSTORRENTS.TORRENT_NAME == title).delete()

    @DbPersist(_db)
    def truncate_rss_history(self):
        """
        清空RSS历史记录
        """
        self._db.query(RSSTORRENTS).delete()

    def crawl_homepage(url,api_key, proxy=False):
        """
        扫描馒头首页前100个资源，并返回RSS信息
        :param url: RSS地址
        :param proxy: 是否使用代理
        :return: 种子信息列表，如为None代表Rss过期
        """


        # 判断apikey是否存在
        if not api_key:
            log.error("【crawl_homepage】 没有配置API_KEY")
            return []

        params = {"mode": "movie", "categories": [], "visible": 1, "pageNumber": 1, "pageSize": 100}
        params_adult = {"mode":"adult","categories":[],"visible":1,"pageNumber":1,"pageSize":100}
        res = RequestUtils(
            headers={
                'x-api-key': api_key,
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json"
            },
            proxies=proxy,
            timeout=30
        ).post_res(url="https://api.m-team.cc/api/torrent/search", json=params_adult)
        ret_array = [] # 保存结果
        if res and res.status_code == 200:
            results = res.json().get('data', {}).get("data") or []
            for result in results:
                torrentid = int(result.get('id'))
                status = result.get('status')

                # 样例数据格式
                # {
                #     'title': '[AV(無碼)/HD Uncensored]RAS-0286 RAS-0280 ID5249 ID5233 ID5245[U3C3][皇家华人 爱豆传媒 杏吧][4.12 GB][N/A]',
                #     'enclosure': 'https: //kp.m-team.cc/detail/663345',
                #     'size': 0,
                #     'description': '<![CDATA[<p><br /><br /><img src="https://attach.greenhalt.info/attachs/202303/202303210944395fde50588d6fcd5ff237a8a04e7de4d5.jpg.thumb.jpg"/><br /><br /><br /><img src="https://attach.greenhalt.info/attachs/202303/202303210944526c7b789cf76d5898a15140f8d02a2f55.jpg.thumb.jpg"/><br /><br /><br /><img src="https://attach.greenhalt.info/attachs/202303/202303210944596e9d06a6ddc4f90e08cc5a94d510bd3e.jpg.thumb.jpg"/><br /><br /><img src="https://attach.greenhalt.info/attachs/202303/20230321094506dfca9ee5ea103523457fece2d53e069a.jpg.thumb.jpg"/><br /><br /><img src="https://attach.greenhalt.info/attachs/202303/20230321094520fa3cb4ee8915c0e53b9101d06a27e2e2.jpg.thumb.jpg"/><br /><br /><img src="https://attach.greenhalt.info/attachs/202303/202303210945344e23348059a0c0b35f029726440a526e.jpg.thumb.jpg"/><br /><br /><img src="https://attach.greenhalt.info/attachs/202303/202303210945450c040e040e3e82ac8a7eba9500b98c74.jpg.thumb.jpg"/><br />General<br />ID                             : 1 (0x1)<br />Complete name                  : C:\\20210924\\test\\RAS-0286 RAS-0280 ID5249 ID5233 ID5245[U3C3]\\RAS-0286_U3C3 .TS<br />Format                         : MPEG-TS<br />File size                      : 870 MiB<br />Duration                       : 41 min 15 s<br />Overall bit rate mode          : Variable<br />Overall bit rate               : 2 947 kb/s<br /><br />Video<br />ID                             : 256 (0x100)<br />Menu ID                        : 1 (0x1)<br />Format                         : AVC<br />Format/Info                    : Advanced Video Codec<br />Format profile                 : High@L3.1<br />Format settings                : CABAC / 4 Ref Frames<br />Format settings, CABAC         : Yes<br />Format settings, Reference fra : 4 frames<br />Codec ID                       : 27<br />Duration                       : 41 min 15 s<br />Width                          : 1 280 pixels<br />Height                         : 720 pixels<br />Display aspect ratio           : 16:9<br />Frame rate mode                : Variable<br />Color space                    : YUV<br />Chroma subsampling             : 4:2:0<br />Bit depth                      : 8 bits<br />Scan type                      : Progressive<br />Writing library                : x264 core 148 r2638 7599210<br />Encoding settings              : cabac=1 / ref=3 / deblock=1:0:0 / analyse=0x3:0x113 / me=hex / subme=7 / psy=1 / psy_rd=1.00:0.00 / mixed_ref=1 / me_range=16 / chroma_me=1 / trellis=1 / 8x8dct=1 / cqm=0 / deadzone=21,11 / fast_pskip=1 / chroma_qp_offset=-2 / threads=22 / lookahead_threads=3 / sliced_threads=0 / nr=0 / decimate=1 / interlaced=0 / bluray_compat=0 / constrained_intra=0 / bframes=3 / b_pyramid=2 / b_adapt=1 / b_bias=0 / direct=1 / weightb=1 / open_gop=0 / weightp=2 / keyint=30 / keyint_min=16 / scenecut=0 / intra_refresh=0 / rc_lookahead=30 / rc=crf / mbtree=1 / crf=24.0 / qcomp=0.60 / qpmin=0 / qpmax=69 / qpstep=4 / ip_ratio=1.40 / aq=1:1.00<br /><br />Audio<br />ID                             : 257 (0x101)<br />Menu ID                        : 1 (0x1)<br />Format                         : AAC LC<br />Format/Info                    : Advanced Audio Codec Low Complexity<br />Format version                 : Version 4<br />Muxing mode                    : ADTS<br />Codec ID                       : 15-2<br />Duration                       : 41 min 15 s<br />Bit rate mode                  : Variable<br />Channel(s)                     : 2 channels<br />Channel layout                 : L R<br />Sampling rate                  : 48.0 kHz<br />Frame rate                     : 46.875 FPS (1024 SPF)<br />Compression mode               : Lossy<br />Delay relative to video        : -67 ms<br /><br /></p>\n]]>',
                #     'link': None,
                #     'pubdate': datetime.datetime(2023, 3, 21, 1, 45, 51, tzinfo=tzutc())
                #     }
                # 种子名
                title = result.get('name')
                # 种子链接
                enclosure = "https://kp.m-team.cc/detail/{}".format(str(torrentid))  # 种子详情页
                # 种子大小
                size = int(result.get('size'))
                # 描述
                description = result.get('smallDescr')
                # 种子页面
                link = "https://kp.m-team.cc/detail/{}".format(str(torrentid))  # 种子详情页
                # 发布日期
                pubdate_str = StringUtils.timestamp_to_date(result.get('lastModifiedDate'))
                pubdate = StringUtils.get_time_stamp(pubdate_str)

                # 返回对象
                tmp_dict = {'title': title,
                            'enclosure': enclosure,
                            'size': size,
                            'description': description,
                            'link': link,
                            'pubdate': pubdate}
                ret_array.append(tmp_dict)


        elif res is not None:
            log.warn(f"【crawl_homepage】 首页爬取，错误码：{res.status_code}")
            return  []
        else:
            log.warn(f"【crawl_homepage】 首页爬取，无法连接 ")
            return  []
        return ret_array


# ====================问题点===============================
# 1、原始RSS订阅方式
# rss_helper = RssHelper()
# rss_url = "https://rss.m-team.cc/api/rss/fetch?audioCodecs=1%2C2%2C3%2C4%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C15&categories=410%2C424%2C437%2C431%2C429%2C430%2C426%2C432%2C436%2C440%2C425%2C433%2C411%2C412%2C413&labels=7&pageSize=50&sign=cdcdefcef3a62e43f45f945d96edf43d&standards=1%2C2%2C3%2C5%2C6%2C7&t=1719150153&tkeys=ttitle%2Ctcat%2Ctsmalldescr%2Ctsize%2Ctuploader&uid=317956&videoCodecs=1%2C2%2C3%2C4%2C16%2C19%2C21"
# ret_array = rss_helper.parse_rssxml(rss_url)
# print(ret_array)

# 2、测试首页爬取
api_key = "cd8470e0-d95c-4a60-9667-c32680e1a93b"
ret_array_new = RssHelper.crawl_homepage("https://api.m-team.cc/api/torrent/search",api_key=api_key)
print(ret_array_new)

