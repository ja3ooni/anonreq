.PHONY: demo demo-down
demo:
	./scripts/demo.sh
demo-down:
	@if [ -f web/docker-compose.demo.yml ]; then docker compose -p anonreq-web $$([ -f .env ] && echo --env-file .env) -f web/docker-compose.yml -f web/docker-compose.demo.yml down; fi
	docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml down
