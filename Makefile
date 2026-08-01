.PHONY: install test api web
install:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e "./apps/api[dev]"
	cd apps/web && npm install
test:
	.venv/bin/python -m pytest apps/api/tests -q
	cd apps/web && npm run typecheck
api:
	.venv/bin/uvicorn brixta_twin.app:app --reload --port 8100
web:
	cd apps/web && npm run dev

