import aiohttp
from typing import Optional, Dict, Any, List
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.message_components import Image

@register(
    "search_tracemoe",
    "PaloMiku",
    "基于 Trace.moe API 的动漫截图场景识别插件",
    "1.0.7"
)
class TraceMoePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.api_base = config.get("api_base", "https://api.trace.moe")
        self.max_results = config.get("max_results", 3)
        if self.max_results < 1:
            self.max_results = 1
        elif self.max_results > 10:
            self.max_results = 10
        
        self.api_key = config.get("api_key", "").strip()
        self.enable_preview = config.get("enable_preview", True)
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        log_msg = f"TraceMoe 插件已加载，API 地址: {self.api_base}，最大结果数量: {self.max_results}"
        if self.api_key:
            log_msg += "，使用 API 密钥"
        else:
            log_msg += "，访客模式"
        if self.enable_preview:
            log_msg += "，启用图片预览"
        logger.info(log_msg)

    async def initialize(self):
        """初始化 HTTP 会话"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "AstrBot-TraceMoe-Plugin/1.0.6"
            }
        )
        logger.info("TraceMoe 插件初始化完成")

    async def terminate(self):
        """清理资源"""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("TraceMoe 插件已停止")

    async def search_by_image_data(self, image_data: bytes, cut_borders: bool = False) -> Dict[str, Any]:
        """通过图片二进制数据搜索动漫"""
        await self._ensure_session()
        
        params = {"anilistInfo": ""}
        if cut_borders:
            params["cutBorders"] = ""
            
        search_url = f"{self.api_base}/search"
        headers = self._build_headers()
        
        form_data = aiohttp.FormData()
        form_data.add_field("image", image_data, content_type="image/jpeg")
        
        try:
            async with self.session.post(
                search_url, 
                params=params,
                data=form_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("error"):
                        raise ValueError(f"API 错误: {result['error']}")
                    return result
                else:
                    raise ValueError(self._handle_http_error(response.status, "搜索"))
        except aiohttp.ClientTimeout:
            raise ValueError("搜索请求超时，请稍后再试")
        except aiohttp.ClientError as e:
            raise ValueError(f"网络连接错误: {str(e)}")

    def _handle_http_error(self, status_code: int, operation: str = "请求") -> str:
        """统一处理HTTP错误状态码"""
        if status_code == 400:
            return "无效的请求数据或处理失败"
        elif status_code == 402:
            return "触及 API 并发限制或配额用尽"
        elif status_code == 403:
            return "无效的 API 密钥或无权限访问"
        elif status_code == 404:
            return "资源不存在或已失效"
        elif status_code == 413:
            return "文件过大（超过25MB）"
        elif status_code == 429:
            return "请求过于频繁，请稍后再试"
        elif status_code == 503:
            return "服务暂时不可用，请稍后再试"
        elif status_code >= 500:
            return "服务器内部错误，请稍后再试"
        else:
            return f"{operation}失败，HTTP状态码: {status_code}"

    async def _ensure_session(self):
        """确保HTTP会话已初始化"""
        if not self.session or self.session.closed:
            await self.initialize()

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {}
        if self.api_key:
            headers["x-trace-key"] = self.api_key
        return headers

    async def get_user_quota(self) -> Dict[str, Any]:
        """获取用户配额信息"""
        await self._ensure_session()
        me_url = f"{self.api_base}/me"
        headers = self._build_headers()
            
        try:
            async with self.session.get(me_url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise ValueError(self._handle_http_error(response.status, "查询配额"))
        except aiohttp.ClientTimeout:
            raise ValueError("查询请求超时，请稍后再试")
        except aiohttp.ClientError as e:
            raise ValueError(f"网络连接错误: {str(e)}")

    def format_time(self, seconds: float) -> str:
        """将秒数格式化为时分秒"""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        else:
            return f"{m:02d}:{s:02d}"

    async def format_search_result(self, result_data: Dict[str, Any]) -> List:
        """格式化搜索结果，返回消息链"""
        from astrbot.api.message_components import Plain
        
        if result_data.get("error"):
            return [Plain(f"搜索出错: {result_data['error']}")]
            
        results = result_data.get("result", [])
        if not results:
            return [Plain("未找到匹配的动漫场景")]
            
        message_chain = []
        
        if self.enable_preview and results:
            first_result = results[0]
            try:
                if first_result.get("image"):
                    image_url = first_result["image"] + "?size=m"  # 中等尺寸
                    message_chain.append(Image.fromURL(image_url))
            except Exception as e:
                logger.warning(f"加载预览图片失败: {e}")
        
        # 添加文本结果
        output_lines = ["🔍 动漫场景识别结果：\n"]
        
        for i, result in enumerate(results[:self.max_results], 1):
            similarity = result.get("similarity", 0) * 100
            
            anilist_info = result.get("anilist")
            if isinstance(anilist_info, dict):
                title_info = anilist_info.get("title", {})
                anime_title = (
                    title_info.get("native") or 
                    title_info.get("romaji") or 
                    title_info.get("english") or 
                    "未知动漫"
                )
                mal_id = anilist_info.get("idMal")
                mal_link = f"\n📺 MyAnimeList: https://myanimelist.net/anime/{mal_id}" if mal_id else ""
            else:
                anime_title = f"AniList ID: {anilist_info}"
                mal_link = ""

            result_text = f"#{i} 【{anime_title}】\n"
            result_text += f"📊 相似度: {similarity:.1f}%\n"
            result_text += f"⏰ 时间: {self.format_time(result.get('at', 0))}"
            
            from_time = result.get("from", 0)
            to_time = result.get("to", 0)
            if from_time != to_time:
                result_text += f" ({self.format_time(from_time)}-{self.format_time(to_time)})"
                
            result_text += f"\n📁 文件: {result.get('filename', '未知')}"
            
            episode = result.get("episode")
            if episode:
                result_text += f"\n📺 集数: 第{episode}集"
                
            result_text += mal_link + "\n"
            output_lines.append(result_text)
            
        footer = f"\n💡 搜索了 {result_data.get('frameCount', 0):,} 帧画面"
        footer += "\n⚠️ 相似度低于90%的结果可能不准确"
        output_lines.append(footer)
        
        message_chain.append(Plain("\n".join(output_lines)))
        
        return message_chain

    def extract_images_from_message(self, message_chain: List) -> List[Image]:
        """从消息链中提取图片组件"""
        return [comp for comp in message_chain if isinstance(comp, Image)]

    async def download_image_from_component(self, image_component: Image) -> bytes:
        """从图片组件下载图片数据"""
        await self._ensure_session()
        
        if not (hasattr(image_component, 'url') and image_component.url):
            raise ValueError("无法获取图片数据")
            
        try:
            async with self.session.get(image_component.url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    if len(image_data) > 25 * 1024 * 1024:  # 25MB
                        raise ValueError("图片文件过大（超过25MB）")
                    return image_data
                else:
                    raise ValueError(self._handle_http_error(response.status, "下载图片"))
        except aiohttp.ClientTimeout:
            raise ValueError("下载图片超时，请稍后再试")
        except aiohttp.ClientError as e:
            raise ValueError(f"网络连接错误: {str(e)}")

    @filter.command("tracemoe help")  
    async def show_info(self, event: AstrMessageEvent):
        """显示插件使用帮助"""
        info_text = """🎌 TraceMoe 动漫场景识别插件

📝 功能说明：
通过图片识别动漫截图出处，基于 trace.moe API

🎯 使用方法：
• /tracemoe + 图片 - 标准图片搜索
• /tracemoe cut + 图片 - 自动裁切黑边后搜索

📊 结果说明：
• 相似度 ≥90% - 结果较准确
• 相似度 <90% - 仅供参考
• 显示时间戳、集数、文件名等信息

💡 支持格式：
• 静态图片：jpg, png, gif, webp
• 推荐尺寸：640x360px
• 文件大小限制：25MB

⚙️ 高级选项：
• cut - 自动裁切黑边，提高识别准确度
• 适用于手机截图等包含黑边的图片
"""

        yield event.plain_result(info_text)
        event.stop_event()  # 停止事件传播，防止重复执行

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("tracemoe me")
    async def show_quota(self, event: AstrMessageEvent):
        """查询API使用配额"""
        try:
            # 确保会话已初始化
            if not self.session:
                await self.initialize()
            
            yield event.plain_result("🔍 正在查询API使用配额...")
            
            quota_data = await self.get_user_quota()
            
            user_id = quota_data.get("id", "未知")
            
            try:
                priority = int(quota_data.get("priority", 0))
                concurrency = int(quota_data.get("concurrency", 1))
                quota = int(quota_data.get("quota", 0))
                quota_used = int(quota_data.get("quotaUsed", 0))
            except (ValueError, TypeError) as e:
                logger.warning(f"配额数据类型转换失败: {e}")
                priority, concurrency, quota, quota_used = 0, 1, 0, 0
            
            quota_remaining = quota - quota_used
            usage_rate = (quota_used/quota*100) if quota > 0 else 0
            
            quota_info = f"""📊 TraceMoe API 配额信息

⚡ 优先级: {priority} (0为最低优先级)
🔄 并发限制: {concurrency} 个请求
📈 月度配额: {quota:,} 次
✅ 已使用: {quota_used:,} 次
💚 剩余配额: {quota_remaining:,} 次

📊 使用率: {usage_rate:.1f}%"""

            if self.api_key:
                quota_info += "\n🔑 使用 API 密钥认证"
            else:
                masked_ip = user_id[:8] + "****" if len(user_id) > 12 else "****"
                quota_info += f"\n🌐 访客模式 (IP: {masked_ip})"
                
            yield event.plain_result(quota_info)
            event.stop_event()
            
        except ValueError as e:
            logger.warning(f"TraceMoe配额查询失败: {e}")
            yield event.plain_result(f"❌ 查询配额失败: {str(e)}")
            event.stop_event()
        except Exception as e:
            logger.error(f"TraceMoe配额查询出现未知错误: {e}", exc_info=True)
            yield event.plain_result("❌ 查询配额时发生未知错误，请稍后再试")
            event.stop_event()

    @filter.command("tracemoe cut")
    async def search_anime_cut(self, event: AstrMessageEvent):
        """搜索动漫场景（自动裁切黑边）- 发送图片来识别动漫出处"""
        async for result in self._handle_search_request(event, cut_borders=True):
            yield result

    @filter.command("tracemoe")
    async def search_anime(self, event: AstrMessageEvent):
        """搜索动漫场景 - 发送图片来识别动漫出处"""
        # 检查是否为子命令，避免冲突
        message_str = event.message_str.strip()
        
        if message_str.startswith("/tracemoe cut") or message_str.startswith("/tracemoe help") or message_str.startswith("/tracemoe me"):
            return
            
        async for result in self._handle_search_request(event, cut_borders=False):
            yield result

    async def _handle_search_request(self, event: AstrMessageEvent, cut_borders: bool = False):
        """处理搜索请求，统一的错误处理和消息返回"""
        try:
            images = self.extract_images_from_message(event.get_messages())
            
            if not images:
                yield event.plain_result(
                    "🖼️ 请发送图片来搜索动漫！\n\n"
                    "使用方法：\n"
                    "• 发送 /tracemoe 并附带图片\n"
                    "• 发送 /tracemoe cut 并附带图片（自动裁切黑边）\n\n"
                    "💡 支持的图片格式：jpg, png, gif, webp 等\n"
                    "📏 推荐尺寸：640x360px\n"
                    "📦 文件大小限制：25MB\n"
                    "🔧 需要帮助请发送：/tracemoe help"
                )
                return
                
            yield event.plain_result("🔍 正在搜索动漫场景，请稍候...")
            
            image_data = await self.download_image_from_component(images[0])
            result = await self.search_by_image_data(image_data, cut_borders)
            formatted_result = await self.format_search_result(result)
            
            yield event.chain_result(formatted_result)
            
        except ValueError as e:
            yield event.plain_result(f"❌ 搜索失败: {str(e)}")
        except Exception as e:
            logger.error(f"TraceMoe搜索出现未知错误: {e}", exc_info=True)
            yield event.plain_result("❌ 搜索时发生未知错误，请稍后再试")
        finally:
            event.stop_event()  # 确保事件停止，防止重复执行
