# Agent Social Platform · Frontend Prototype (Mock)

一个纯前端原型（无后端）：Onboarding → 搜索框 → 3 个 hard-coded 体验 → 匹配列表/理由/Badge → 聊天 + 日历邀请（全部 mock）。

## 本地运行

```bash
cd prototype-web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 构建

```bash
cd prototype-web
npm run build
```

## Render 部署（Static Site）

- Root Directory: `prototype-web`
- Build Command: `npm ci && npm run build`
- Publish Directory: `dist`
- Rewrites（SPA 路由必须）:
  - Source: `/*`
  - Destination: `/index.html`

（也可以直接用仓库根目录的 `render.yaml` 一键部署）

