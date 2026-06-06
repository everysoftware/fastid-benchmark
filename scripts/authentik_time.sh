# 1. Очистка (опционально, но рекомендуется для "холодного" старта)
docker compose stop

# 2. Запуск контейнеров в фоне
docker compose up -d

# 3. Замер времени до готовности через HTTP-опрос эндпоинта
time (while ! curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/-/health/ready/ | grep -q "200\|204"; do sleep 1; done)
