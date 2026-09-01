# 法律文件智慧分析系統 — 一鍵部署（§4.10.2）
# 三階段：資料準備 → 索引建構 → 服務啟動。

.PHONY: help install index api web up down

help:
	@echo "可用目標："
	@echo "  make install   安裝後端 (pip) 與前端 (pnpm) 相依套件"
	@echo "  make index     建構 ChromaDB 雙索引（法規 laws、判決 judgements）"
	@echo "  make api       啟動 FastAPI 後端（http://localhost:8000）"
	@echo "  make web       啟動 Next.js 前端（http://localhost:3000）"
	@echo "  make up        以 docker compose 啟動完整系統"
	@echo "  make down      停止 docker compose 服務"

install:
	cd system && pip install -r requirements.txt
	cd web && pnpm install

index:
	cd system && python3 scripts/build_index.py

api:
	cd system && bash scripts/run_api.sh

web:
	cd web && pnpm dev

up:
	docker compose -f docs/docker-compose.yml up -d --build

down:
	docker compose -f docs/docker-compose.yml down
