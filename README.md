下一步：启动运行

# 1. 安装 Docker Desktop，然后：
cd d:/VSproject/Information-platform
docker compose up -d

# 2. 安装前端依赖
cd frontend && npm install

# 3. 访问
# 后端 API 文档：http://localhost:8000/docs
# 前端：http://localhost:3000
首次登录用 .env 里配置的管理员账号（默认 admin@example.com / changeme123），进入设置页填入你的 LLM API Key 即可开始使用。