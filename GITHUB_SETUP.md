# GitHub 仓库设置指南

## 快速设置

### 步骤1：在GitHub创建仓库
1. 访问 https://github.com/new
2. 仓库名：`quant-trading-system`
3. 选择 Public 或 Private
4. **不要**勾选 "Add a README file"
5. 点击 **Create repository**

### 步骤2：推送本地代码

```bash
# 替换 YOUR_USERNAME 为你的GitHub用户名
git remote add origin https://github.com/YOUR_USERNAME/quant-trading-system.git

# 推送代码
git branch -M main
git push -u origin main
```

### 步骤3：验证
打开 `https://github.com/YOUR_USERNAME/quant-trading-system` 查看代码

---

## 使用GitHub CLI（可选，更简便）

```bash
# 安装
brew install gh

# 登录
gh auth login

# 创建仓库并推送
gh repo create quant-trading-system --public --source=. --remote=origin --push
```

---

## 已有提交记录

当前仓库已有初始提交：
- **提交数**: 1
- **文件数**: 314
- **主要功能**: Phase 1 完成，包含数据同步、数据库设计、数据质量检查、复权计算、定时任务、血缘追踪
