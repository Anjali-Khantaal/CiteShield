PYTHON ?= python
COMPOSE_FILE ?= deploy/docker/compose.yaml
K8S_OVERLAY ?= deploy/k8s/overlays/local

.PHONY: setup test up down eval build k8s-deploy k8s-smoke k8s-clean

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt


test:
	$(PYTHON) -m pytest -q

up:
	docker compose -f $(COMPOSE_FILE) up --build -d

down:
	docker compose -f $(COMPOSE_FILE) down

eval:
	EMBEDDING_BACKEND=hash GENERATOR_BACKEND=extractive $(PYTHON) scripts/evaluate.py --local-path artifacts/qdrant_eval

build:
	docker build -f deploy/docker/Dockerfile -t citeshield-api:local .

k8s-deploy:
	kubectl apply -k $(K8S_OVERLAY)

k8s-smoke:
	bash scripts/smoke_k8s.sh

k8s-clean:
	kubectl delete -k $(K8S_OVERLAY) --ignore-not-found
