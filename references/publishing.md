# 公众号草稿发布

## 本地检查

```text
python <SKILL_DIR>/scripts/publish.py --dir delivery/rendered/article --cover delivery/assets/cover.png --dry-run
```

默认不带发布选项也只检查本地标题、封面和正文图片。`--dry-run` 不导入微信客户端、不获取 token、不上传图片、不写入草稿；不需要 AppID 或 AppSecret。

返回 `local_check_passed` 表示本地文件结构通过检查，不代表微信账户权限、IP 白名单或远程接口已验证。

## 本机凭据

实际写入草稿需要已有公众号的 AppID、AppSecret 和可用的接口权限，且当前出口 IP 已加入公众号后台白名单。由账户管理员在本机配置；不在聊天中粘贴密钥。

推荐环境变量：`WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`WECHAT_AUTHOR`。也支持被 Git 忽略的本机 `config.json`：

```json
{
  "wechat": {
    "app_id": "",
    "app_secret": "",
    "author": ""
  }
}
```

配置中留空不会触发网络请求，也不应把实际值填进公开仓库的样例。环境变量覆盖本机 JSON 配置。

## 明确写入草稿

确认用户已要求这次草稿写入，再执行：

```text
python <SKILL_DIR>/scripts/publish.py --dir delivery/rendered/article --cover delivery/assets/cover.png --publish
```

脚本先检查本地文件，再获取 token、上传正文图片与封面，最后调用微信草稿接口。发布失败可能已产生图片素材，因此不要把真实发布当成测试，不做无边界重试。

成功返回 `draft_created` 和草稿 `media_id`，并在文章目录写入不含 token、AppSecret 的 `publish-result.json`。这里没有群发接口；在公众号后台由管理员预览并选择后续发布操作。

`--input article.md --output <新目录> --cover <本地图片>` 支持先排版再检查或发布；如要写入草稿，仍需显式 `--publish`。

只上传正常 `article.html`，不上传图片内嵌版 HTML。内嵌版适合本地预览和手动复制；接口发布会把相对图片路径改成微信 CDN URL。WebP 等可解码的非标准图片在上传前转换为 PNG。

## 手动操作

打开 `preview-embedded.html`，检查后点击“复制到微信”，粘贴到公众号编辑器，手动上传封面。若内嵌图片过大或浏览器限制剪贴板，使用普通预览并在后台逐张插入本地图片。
