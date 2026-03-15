# 自动推送代码到 GitHub

本指南介绍如何设置定时自动推送代码到 GitHub。

---

## 快速开始

### 1. 运行安装脚本

```bash
bash scripts/setup_auto_push.sh
```

按提示选择推送频率（推荐每30分钟）。

### 2. 验证设置

```bash
# 查看定时任务
crontab -l

# 查看推送日志
tail -f /tmp/auto_git_push.log
```

---

## 工作原理

定时任务会自动执行以下操作：

1. **检查本地更改** - 如果有未提交的修改，自动提交
2. **检查远程更新** - 如果有远程更新，尝试合并（fast-forward only）
3. **推送到 GitHub** - 将本地提交推送到远程仓库
4. **记录日志** - 所有操作记录到 `/tmp/auto_git_push.log`

---

## 手动管理

### 查看定时任务
```bash
crontab -l
```

### 删除定时任务
```bash
crontab -e
# 删除包含 auto_git_push.sh 的行
```

### 手动执行推送
```bash
bash scripts/auto_git_push.sh
```

---

## 配置选项

### 修改推送频率

编辑 crontab：
```bash
crontab -e
```

修改时间设置：
```
# 每15分钟
*/15 * * * * /Users/xuhaoricky/ClawProject/Stock-trading-project/scripts/auto_git_push.sh

# 每小时
0 * * * * /Users/xuhaoricky/ClawProject/Stock-trading-project/scripts/auto_git_push.sh

# 每天凌晨2点
0 2 * * * /Users/xuhaoricky/ClawProject/Stock-trading-project/scripts/auto_git_push.sh
```

### 修改提交信息

编辑 `scripts/auto_git_push.sh`，修改这一行：
```bash
git commit -m "你的自定义提交信息: $DATE"
```

---

## 常见问题

### Q: 如果有冲突怎么办？
A: 脚本会跳过推送并记录错误日志。你需要手动解决：
```bash
cd /Users/xuhaoricky/ClawProject/Stock-trading-project
git status
# 解决冲突后
git add .
git commit -m "解决冲突"
git push
```

### Q: 敏感文件会被推送吗？
A: 不会。`.env` 和其他敏感文件已在 `.gitignore` 中排除。

### Q: 如何临时暂停自动推送？
A: 注释掉 crontab 中的任务：
```bash
crontab -e
# 在任务行前加 # 号
# */30 * * * * /Users/xuhaoricky/ClawProject/Stock-trading-project/scripts/auto_git_push.sh
```

### Q: 推送失败怎么通知我？
A: 脚本目前只记录日志。你可以修改脚本添加通知功能（如钉钉/Slack）。

---

## 安全建议

1. **定期检查日志** - 确保没有异常推送
2. **谨慎处理冲突** - 自动合并失败时需要人工介入
3. **保护好你的机器** - 定时任务需要你的 Git 凭据
4. **大型更改建议手动提交** - 保留有意义的提交信息

---

## 替代方案

### 方案A：使用 Git 钩子（即时推送）

每次提交后自动推送：
```bash
# 创建 post-commit 钩子
echo '#!/bin/bash
git push origin main' > .git/hooks/post-commit
chmod +x .git/hooks/post-commit
```

### 方案B：使用 GitHub Actions（CI/CD）

创建 `.github/workflows/auto-sync.yml`：
```yaml
name: Auto Sync
on:
  schedule:
    - cron: '*/30 * * * *'  # 每30分钟
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Pull changes
        run: git pull origin main
```

---

## 相关文件

- `scripts/auto_git_push.sh` - 自动推送脚本
- `scripts/setup_auto_push.sh` - 安装脚本
- `/tmp/auto_git_push.log` - 推送日志
