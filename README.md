# TraceMoe 动漫场景识别插件

基于 trace.moe API 的 AstrBot 插件，可以通过图片识别动漫出处。

## 功能特性

- 🔍 **动漫场景识别** - 通过截图识别动漫、时间戳和集数
- 🖼️ **图片上传支持** - 直接发送图片进行识别  
- 📊 **详细结果** - 显示相似度、动漫信息、时间戳等
- 🌐 **AniList集成** - 获取详细的动漫信息
- 📱 **静态图片支持** - JPG、PNG、GIF、WebP等静态图片格式
- ⚙️ **高级选项** - 支持自动裁切黑边，提高识别准确度

## 使用方法

### 基本指令

```bash
/tracemoe              # 标准图片搜索
/tracemoe cut          # 自动裁切黑边后搜索
```

### 帮助指令

```bash
/tracemoe help         # 显示插件帮助
```

## 使用示例

1. **标准图片搜索**：
   发送 `/tracemoe` 指令并同时发送图片

2. **自动裁切黑边搜索**：
   发送 `/tracemoe cut` 指令并同时发送图片

3. **查看帮助**：

   ```bash
   /tracemoe help
   ```

## 搜索结果说明

插件会返回最相关的3个搜索结果，包含：

- 🎌 **动漫名称** - 日文原名或罗马音
- 📊 **相似度** - 百分比显示匹配程度
- ⏰ **时间戳** - 场景在动漫中的具体时间
- 📺 **集数信息** - 如果可识别的话
- 🔗 **MyAnimeList链接** - 查看详细信息

### 准确度说明

- **≥90%** - 结果通常准确可信
- **<90%** - 仅供参考

## API 限制

- **搜索配额**：游客每月1000次
- **图片大小**：最大25MB  
- **支持格式**：静态图片（jpg, png, gif, webp等）
- **推荐尺寸**：640x360px以获得最佳识别效果
- **并发限制**：根据服务器负载动态调整

## 技术特性

- 异步HTTP请求，不阻塞机器人
- 完整的错误处理和用户友好提示
- 资源管理和会话清理
- 智能图片组件识别和处理
- 支持自动裁切黑边功能
- 基于 multipart/form-data 的文件上传

## 数据来源

- [trace.moe](https://trace.moe/) - 动漫场景搜索引擎
- [AniList](https://anilist.co/) - 动漫数据库
- [MyAnimeList](https://myanimelist.net/) - 动漫信息网站

## 支持与反馈

如果遇到问题或有建议，请在项目的 GitHub Issues 中反馈。

---

## AstrBot Plugin Template

This plugin is based on AstrBot plugin template.

**Documentation**: [AstrBot 帮助文档](https://docs.astrbot.app)
**Template**: [Github 仓库](https://github.com/Soulter/helloworld)