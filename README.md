# zed-i18n

Zed 编辑器简体中文汉化版，每周自动构建。

原理：从上游 [zed-industries/zed](https://github.com/zed-industries/zed) 的 main 拉源码 →
按 `zh.json` 把英文字符串替换成中文 → 在 GitHub Actions 的 Windows 运行器上编译 → 发布 Release。

## 下载

到 [Releases](../../releases) 下最新的 `zed-windows-*.zip`，解压即用。
可用 `sha256sums.txt` 校验完整性。

## 仓库结构

| 文件 | 作用 |
|---|---|
| `zh.json` | 词典：源码文件 → {英文字面量: 中文}，唯一数据源 |
| `tools/i18n.py` | 词典工具：add / replace / check 三个子命令 |
| `.github/workflows/i18n-build.yml` | 构建流水线（定时 + 手动 + 触发文件） |
| `.github/workflows/cleanup.yml` | 一次性清理历史 Release / artifact |
| `.github/trigger-build` | 改这个文件并推送，立刻触发一次构建 |

## 加一条翻译

需要本地有一份上游源码：

```
git clone --depth 1 https://github.com/zed-industries/zed D:/zed-upstream
python tools/i18n.py add "Trust and Continue" "信任并继续" --src D:/zed-upstream
```

`add` 会自动扫源码，找到这句英文出现在哪些文件，写进 `zh.json`。
重复添加是安全的（报 unchanged 不重复写）；改译文会直接更新（报 updated）。

加完跑一遍校验，全部命中才算通过：

```
python tools/i18n.py check --src D:/zed-upstream
```

提交推送后，下次构建自动生效。

注意：单词级词条（如 `Default`）容易误伤配置键、枚举值，`add` 会警告；
确认它确实是界面文案再加。

## 构建

- 定时：每周日北京时间 03:00 自动构建。
  GitHub 规定仓库 60 天无活动会暂停定时任务，届时手动跑一次即可恢复。
- 手动：Actions → Zed 汉化每日构建 → Run workflow，可指定上游分支/标签、是否发 Release。
- 构建失败时，错误日志末尾 400 行会推到 `ci-log` 分支的 `last-error.txt`。

## 流水线步骤

拉上游源码 → `i18n.py replace` 替换中文 → 确认替换生效（含中文文件数兜底）→
`cargo build --release` → 打包 zip + sha256 → 发布 Release。
