# CodingGirl Desktop

CodingGirl 的 Tauri 桌面应用，提供现代化的 AI 编程助手界面。

## 🚀 快速开始

### 安装依赖
```bash
npm install
```

### 开发模式
```bash
npm run dev
```

### 构建生产版本
```bash
npm run build
```

### 打包桌面应用
```bash
npm run tauri build
```

## 📖 文档

### 新用户必读
- **[快速开始.md](./快速开始.md)** - 快速上手指南
- **[完成总结.md](./完成总结.md)** - 最新功能总结
- **[UI_CHANGES_V3.md](./UI_CHANGES_V3.md)** - UI 变更详细说明

### 开发者文档
- **[V3_IMPLEMENTATION.md](./V3_IMPLEMENTATION.md)** - 技术实现文档
- **[DEVELOPMENT_CHECKLIST.md](./DEVELOPMENT_CHECKLIST.md)** - 开发规范和检查清单
- **[VISUAL_COMPARISON.md](./VISUAL_COMPARISON.md)** - V2 和 V3 视觉对比

### 历史文档
- **[STYLE_CHANGES.md](./STYLE_CHANGES.md)** - 样式系统变更
- **[LAYOUT_REDESIGN.md](./LAYOUT_REDESIGN.md)** - 布局重设计文档

## ✨ 主要特性

### WorkspacePageV3 (最新版本)

#### 1. 自定义标题栏
- 完全自定义的窗口控制
- 集成导航和工具按钮
- 支持拖拽移动窗口

#### 2. 简化的项目管理
- 清晰的项目-会话层级结构
- 展开/折叠项目查看会话
- 快速创建和删除会话

#### 3. 动态模式选择
- Plan（只读分析）
- Build（需要审批）
- Auto（自动应用）
- 对话过程中可随时切换

#### 4. 统一的页面布局
- 所有页面使用相同的标题栏
- 一致的视觉风格
- 响应式设计

## 🎨 技术栈

- **框架**: React 18 + TypeScript
- **路由**: React Router v6
- **状态管理**: Zustand
- **样式**: Tailwind CSS
- **桌面框架**: Tauri v2
- **构建工具**: Vite

## 📁 项目结构

```
src/
├── components/
│   ├── layout/          # 布局组件
│   │   ├── custom-titlebar.tsx
│   │   └── page-layout.tsx
│   ├── workspace/       # 工作台组件
│   │   ├── workspace-layout.tsx
│   │   ├── left-sidebar.tsx
│   │   ├── chat-area.tsx
│   │   └── right-sidebar.tsx
│   └── ui/             # 通用 UI 组件
├── pages/              # 页面组件
│   ├── workspace-page-v3.tsx
│   ├── repositories-page.tsx
│   ├── settings-page.tsx
│   └── plugins-page.tsx
├── store/              # 状态管理
├── types/              # 类型定义
└── api/                # API 接口
```

## 🔧 开发指南

### 代码规范
- 使用 TypeScript 严格模式
- 遵循 ESLint 规则
- 使用 Prettier 格式化代码

### 提交规范
```
<type>(<scope>): <subject>

<body>

<footer>
```

类型：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试
- `chore`: 构建/工具

### 测试
```bash
# TypeScript 检查
npm run build

# ESLint 检查
npm run lint
```

## 🎯 路由

- `/` - 工作台（V3）
- `/workspace` - 工作台（V3）
- `/workspace-v1` - 工作台（V1，用于对比）
- `/repositories` - 仓库管理
- `/settings` - 设置
- `/plugins` - 插件管理

## 🌟 最新更新 (V3)

### 2024-03-07
- ✅ 实现自定义标题栏
- ✅ 简化左侧导航栏
- ✅ 动态模式选择
- ✅ 统一页面布局
- ✅ 配置 Tauri 自定义窗口
- ✅ 完整的文档

详见 [完成总结.md](./完成总结.md)

## 📝 待实现功能

### 高优先级
- [ ] 终端面板组件
- [ ] 键盘快捷键系统
- [ ] 窗口状态持久化

### 中优先级
- [ ] 会话搜索和过滤
- [ ] 虚拟滚动优化
- [ ] UI 动画增强

### 低优先级
- [ ] 多窗口支持
- [ ] 自定义主题编辑器
- [ ] 协作功能

详见 [DEVELOPMENT_CHECKLIST.md](./DEVELOPMENT_CHECKLIST.md)

## 🐛 问题反馈

如遇到问题，请：
1. 查看相关文档
2. 检查控制台错误
3. 提交 Issue

## 📞 资源链接

### 官方文档
- [Tauri](https://tauri.app/)
- [React](https://react.dev/)
- [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS](https://tailwindcss.com/)

### 项目文档
- [快速开始](./快速开始.md)
- [技术实现](./V3_IMPLEMENTATION.md)
- [开发指南](./DEVELOPMENT_CHECKLIST.md)

## 📄 许可证

[项目许可证信息]

## 🙏 致谢

本项目参考了以下优秀项目：
- [OpenCode](https://github.com/opencodeiiit/opencode-ui)
- [Codex App](https://codex.app)

---

**当前版本**: V3.0.0  
**最后更新**: 2024-03-07
