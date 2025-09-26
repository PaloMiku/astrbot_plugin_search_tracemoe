import aiohttp
from typing import Optional, Dict, Any, List
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image

@register(
    "search_tracemoe",
    "PaloMiku",
    "基于 Trace.moe API 的动漫截图场景识别插件",
    "1.0.0"
)
class TraceMoePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.api_base = "https://api.trace.moe"
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """初始化 HTTP 会话"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "AstrBot-TraceMoe-Plugin/1.0.0"
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
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
            
        params = {"anilistInfo": ""}
        if cut_borders:
            params["cutBorders"] = ""
            
        search_url = f"{self.api_base}/search"
        
        form_data = aiohttp.FormData()
        form_data.add_field("image", image_data, content_type="image/jpeg")
        
        try:
            async with self.session.post(
                search_url, 
                params=params,
                data=form_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    # 检查 API 返回的错误信息
                    if result.get("error"):
                        raise ValueError(f"API 错误: {result['error']}")
                    return result
                elif response.status == 400:
                    raise ValueError("无效的图片数据或处理失败")
                elif response.status == 402:
                    raise ValueError("触及 API 并发限制或配额用尽")
                elif response.status == 413:
                    raise ValueError("图片文件过大（超过25MB）")
                elif response.status == 429:
                    raise ValueError("请求过于频繁，请稍后再试")
                elif response.status == 503:
                    raise ValueError("服务暂时不可用，请稍后再试")
                elif response.status >= 500:
                    raise ValueError("服务器内部错误，请稍后再试")
                else:
                    raise ValueError(f"搜索失败，HTTP状态码: {response.status}")
        except aiohttp.ClientTimeout:
            raise ValueError("搜索请求超时，请稍后再试")
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

    def format_search_result(self, result_data: Dict[str, Any]) -> str:
        """格式化搜索结果"""
        if result_data.get("error"):
            return f"搜索出错: {result_data['error']}"
            
        results = result_data.get("result", [])
        if not results:
            return "未找到匹配的动漫场景"
            
        output_lines = ["🔍 动漫场景识别结果：\n"]
        
        for i, result in enumerate(results[:3], 1):
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
        
        return "\n".join(output_lines)

    def extract_images_from_message(self, message_chain: List) -> List[Image]:
        """从消息链中提取图片组件"""
        return [comp for comp in message_chain if isinstance(comp, Image)]

    async def download_image_from_component(self, image_component: Image) -> bytes:
        """从图片组件下载图片数据"""
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
            
        if hasattr(image_component, 'url') and image_component.url:
            try:
                async with self.session.get(image_component.url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        # 检查图片大小，符合 API 限制
                        if len(image_data) > 25 * 1024 * 1024:  # 25MB
                            raise ValueError("图片文件过大（超过25MB）")
                        return image_data
                    elif response.status == 404:
                        raise ValueError("图片链接不存在或已失效")
                    elif response.status == 403:
                        raise ValueError("无权限访问图片链接")
                    else:
                        raise ValueError(f"无法下载图片，HTTP状态码: {response.status}")
            except aiohttp.ClientTimeout:
                raise ValueError("下载图片超时，请稍后再试")
            except aiohttp.ClientError as e:
                raise ValueError(f"网络连接错误: {str(e)}")
        else:
            raise ValueError("无法获取图片数据")

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

    @filter.command("tracemoe")
    async def search_anime(self, event: AstrMessageEvent):
        """搜索动漫场景 - 发送图片来识别动漫出处"""
        try:
            message_str = event.message_str.strip()
            message_chain = event.get_messages()
            images = self.extract_images_from_message(message_chain)
            
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
            
            cut_borders = message_str.lower().startswith("/tracemoe cut")
            
            result = await self.search_by_image_data(image_data, cut_borders=cut_borders)
            
            formatted_result = self.format_search_result(result)
            yield event.plain_result(formatted_result)
            
        except ValueError as e:
            yield event.plain_result(f"❌ 搜索失败: {str(e)}")
        except Exception as e:
            logger.error(f"TraceMoe搜索出现未知错误: {e}")
            yield event.plain_result("❌ 搜索时发生未知错误，请稍后再试")
