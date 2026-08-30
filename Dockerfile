FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 说明：构建期不建表（MySQL 服务可能尚未就绪），
# 建表统一在容器启动时执行（见 docker-compose 的 command）
EXPOSE 8000 8501
CMD ["sh", "-c", "python database/init_db.py && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
