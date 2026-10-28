.PHONY: demo demo-down
demo:
	./scripts/demo.sh
demo-down:
	docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml down
