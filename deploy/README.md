# About_Me_Agent 部署手册（Nginx 反向代理）

> 阶段 A：Nginx 站到最前面，公网只暴露 80，后端 uvicorn 退回 127.0.0.1。
> 阶段 B：Nginx 直接托管 Vue 打包产物（等阶段 A 验证通过再做）。

---

## 第 0 步：先探测服务器现状（**别急着装，先看清楚**）

在服务器上跑这几条，把输出贴回来：

```bash
# 1) 什么系统、什么版本（决定用 apt 还是 yum 装 nginx）
cat /etc/os-release | head -3

# 2) nginx 装了吗
nginx -v 2>&1 || echo ">>> nginx NOT installed"

# 3) 后端现在怎么跑的（找 uvicorn 进程）
ps -ef | grep -i uvicorn | grep -v grep

# 4) 80 / 8000 端口谁在听
ss -lntp 2>/dev/null | grep -E ':(80|8000)' || netstat -lntp 2>/dev/null | grep -E ':(80|8000)'

# 5) 项目目录在哪
ls -d /root/* /opt/* /home/* 2>/dev/null | head -20
```

**为什么先探测**：装法（apt/yum）、配置目录（`conf.d` vs `sites-available`）、
后端进程管理方式（systemd / nohup / screen）都不一样，瞎装容易和现有环境打架。

---

## 第 1 步：安装 nginx

```bash
# Debian / Ubuntu
apt update && apt install -y nginx

# CentOS / Alibaba Cloud Linux / RHEL
yum install -y nginx
```

装完确认：

```bash
nginx -v
systemctl status nginx --no-pager
```

---

## 第 2 步：**干掉默认站点**（最常见的坑）

系统自带的 nginx 通常已经开了一个「欢迎页」server，占着 80 端口。
不处理的话，访问 IP 会看到 `Welcome to nginx!` 而不是你的站点。

```bash
# Debian / Ubuntu：默认站点是软链，删掉软链即可
ls -l /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# CentOS / Alibaba Cloud Linux：默认 server 写死在主配置里，
# 用编辑器把那个 server { listen 80; ... } 整段注释掉
vi /etc/nginx/nginx.conf
```

> 我们的 `aboutme.conf` 里写了 `server_name 8.148.192.49;`，
> 所以即使没删干净，用 IP 访问也会优先命中我们的站点。
> 但删掉更干净，避免以后接域名时莫名走错 server。

---

## 第 3 步：放配置 + 测试 + 生效

```bash
# 把 aboutme.conf 传到 /etc/nginx/conf.d/
# 位置：About_Me_Agent/deploy/nginx/aboutme.conf

# 语法自检：这一步不过，绝不 reload！
nginx -t

# 过了才生效（reload 是平滑重启，不断现有连接）
systemctl reload nginx
```

`nginx -t` 输出应该类似：

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

---

## 第 4 步：验收清单

| # | 验收项 | 命令 / 操作 | 期望 |
|---|---|---|---|
| 1 | 80 端口通了 | 浏览器开 `http://8.148.192.49/` | 看到聊天页面 |
| 2 | 8000 还在直连 | 浏览器开 `http://8.148.192.49:8000/` | 仍能打开（阶段 A 先不动它，留作退路） |
| 3 | SSE 流式没被缓冲 | 提问，看回答 | **逐字蹦**，不是卡几秒后整段出现 |
| 4 | 真实 IP 透传了 | 看后端日志 / 连续提问 11 次 | 被限流的是「你自己的 IP」，不是 127.0.0.1 |
| 5 | gzip 生效 | `curl -H "Accept-Encoding: gzip" -I http://127.0.0.1/static/index.html` | 响应头有 `Content-Encoding: gzip` |
| 6 | Nginx 限流生效 | `for i in $(seq 1 100); do curl -s -o /dev/null -w "%{http_code} " http://127.0.0.1/api/links; done` | 出现连续的 `503` |

> 验收 4 是重点：**套了代理之后，`request.client.host` 还能不能拿到真实 IP**。
> 现代 uvicorn 默认 `--proxy-headers` 开、`--forwarded-allow-ips=127.0.0.1`，
> 配合 Nginx 的 `X-Forwarded-For` 应该自动就对了——但要**实测**，别信默认。

---

## 第 5 步（可选）：把 uvicorn 收回内网

阶段 A 验证通过后，让 8000 只监听本机：

```bash
# 之前（对全网暴露）
uvicorn app:app --host 0.0.0.0 --port 8000

# 之后（只有 Nginx 能访问）
uvicorn app:app --host 127.0.0.1 --port 8000
```

同时云服务器**安全组**里关掉 8000 端口的外部放行。

---

## 阶段 B：Nginx 托管 Vue 前端

```bash
# 本地
cd About_Me_Agent/frontend
npm run build          # 产出 frontend/dist/

# 上传
scp -r dist/* root@8.148.192.49:/var/www/aboutme/
```

⚠️ **前置改动**：`frontend/src/api.ts` 里 `baseURL` 现在是写死的
`http://localhost:8000`，部署后必须改成同源（相对路径），否则线上请求会打到
用户自己的电脑上。这是「本地能跑、线上必挂」的典型坑，阶段 B 再处理。
