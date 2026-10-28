# Sources and changes

This project combines the user's `wechat-article-pipeline` writing and image-packaging workflow with the formatting resources of:

- Upstream: https://github.com/xiaohuailabs/xiaohu-wechat-format
- Author/account: xiaohuailabs and upstream contributors
- Snapshot: `dbddf0fd9c1189a6f3e0bec1bebb1b0e47e8ddf0`
- License declaration: the upstream README states MIT. The pinned archive does not contain a separate LICENSE file; this declaration and the upstream attribution are retained here.

Derived files are `scripts/format.py`, `scripts/zh_punctuation_fix.py`, `scripts/theme_lint.py`, `templates/`, and `themes/`. The 85 theme files are retained from that snapshot. `scripts/embed_images.py` originates in the user's article workflow.

Integration changes include configuration without mandatory local secrets, configurable output/cache directories, portable Python subprocess and file URI handling, collision-safe local image names, UTF-8 console handling, explicit rejection of unsupported SVG input, a complete local packaging command, and a rewritten draft publisher whose default and `--dry-run` modes perform no network requests.

The combined skill instructions, documentation, packaging, tests, and revised publisher are maintained by haibo0505. No affiliation with or endorsement by WeChat, Tencent, OpenAI, Anthropic, or the upstream author is implied.
