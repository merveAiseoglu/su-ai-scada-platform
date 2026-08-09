.PHONY: up down logs rebuild db-shell backend-shell

# Bring all services up in detached mode
up:
	docker-compose up -d

# Take all services down and remove orphans
down:
	docker-compose down --remove-orphans

# View logs for all services (follow)
logs:
	docker-compose logs -f

# Force rebuild of images and start up
rebuild:
	docker-compose up -d --build

# Open a psql shell inside the database container
db-shell:
	docker-compose exec postgres psql -U postgres -d su_ai

# Open a bash shell inside the backend container
backend-shell:
	docker-compose exec backend /bin/bash
