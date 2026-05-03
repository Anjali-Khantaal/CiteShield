PYTHON ?= python
COMPOSE_FILE ?= deploy/docker/compose.yaml
K8S_OVERLAY ?= deploy/k8s/overlays/local
K8S_MONITORING_OVERLAY ?= deploy/k8s/overlays/local-with-monitoring
K8S_IMAGE ?= citeshield-api:local
KIND_CLUSTER ?= kind

.PHONY: setup test up down eval benchmark multimodal-download multimodal-process multimodal-ingest multimodal-demo multimodal-demo-llm build kind-load k8s-deploy k8s-deploy-monitoring k8s-smoke k8s-clean k8s-clean-monitoring

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

benchmark:
	EMBEDDING_BACKEND=hash GENERATOR_BACKEND=extractive $(PYTHON) scripts/run_benchmark.py

multimodal-download:
	$(PYTHON) scripts/download_multimodal_samples.py

multimodal-process:
	$(PYTHON) scripts/process_multimodal.py

multimodal-ingest:
	EMBEDDING_BACKEND=hash GENERATOR_BACKEND=extractive $(PYTHON) scripts/process_multimodal.py --ingest

multimodal-demo:
	$(PYTHON) scripts/download_multimodal_samples.py
	EMBEDDING_BACKEND=hash GENERATOR_BACKEND=extractive $(PYTHON) scripts/process_multimodal.py --ingest --demo-query

multimodal-demo-llm:
	$(PYTHON) scripts/download_multimodal_samples.py
	$(PYTHON) scripts/process_multimodal.py --ingest --demo-query --demo-generator configured

build:
	docker build -f deploy/docker/Dockerfile -t $(K8S_IMAGE) .

kind-load:
	kind load docker-image $(K8S_IMAGE) --name $(KIND_CLUSTER)

k8s-deploy:
	kubectl apply -k $(K8S_OVERLAY)

k8s-deploy-monitoring:
	kubectl apply -k $(K8S_MONITORING_OVERLAY)

k8s-smoke:
	bash scripts/smoke_k8s.sh

k8s-clean:
	kubectl delete -k $(K8S_OVERLAY) --ignore-not-found

k8s-clean-monitoring:
	kubectl delete -k $(K8S_MONITORING_OVERLAY) --ignore-not-found
