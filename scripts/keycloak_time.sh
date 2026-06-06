# 1. Останавливаем и удаляем контейнеры с томами (чистый старт)
docker compose -f docker-compose-keycloak.yml stop

# 2. Запускаем контейнер в фоне
docker compose -f docker-compose-keycloak.yml up -d

# 3. Замеряем время до готовности (опрос /health/ready на порту 9000)
time (while ! curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/health/ready | grep -q "200"; do sleep 1; done)
