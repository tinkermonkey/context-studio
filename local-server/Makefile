.PHONY: benchmark-experiment benchmark-canon help

# Default pipeline config if not specified
PIPELINE ?= configs/extraction-default.json
CACHE_DIR := .benchmark-cache
REPORTS_DIR := reports
DATE := $(shell date +%Y%m%d)
CANON_DIR ?= datafiles/canon/software_architecture

help:
	@echo "Context Studio Benchmarking Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  benchmark-experiment PIPELINE=<path>  Run benchmark against TekGen, WebNLG, and the canon"
	@echo "  benchmark-canon                       Run only the canon benchmark"
	@echo ""
	@echo "Example:"
	@echo "  make benchmark-experiment PIPELINE=configs/extraction-experimental.json"
	@echo "  make benchmark-canon"

benchmark-experiment: check-pipeline validate-cache create-reports
	@echo "=== Extracting config slug from $(PIPELINE) ==="
	$(eval CONFIG_SLUG := $(basename $(notdir $(PIPELINE))))
	@echo "Config slug: $(CONFIG_SLUG)"

	@echo ""
	@echo "=== Running benchmark on TekGen dataset ==="
	python scripts/run_benchmark.py \
		--dataset text2kg-bench/wikidata-tekgen \
		--pipeline $(PIPELINE) \
		--out $(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-tekgen.json

	@echo ""
	@echo "=== Running benchmark on WebNLG dataset ==="
	python scripts/run_benchmark.py \
		--dataset text2kg-bench/dbpedia-webnlg \
		--pipeline $(PIPELINE) \
		--out $(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-webnlg.json

	@echo ""
	@echo "=== Running canon-software-architecture benchmark ==="
	python scripts/run_canon_benchmark.py \
		--canon-dir $(CANON_DIR) \
		--out $(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-canon.json

	@echo ""
	@echo "=== Generating cross-dataset comparison ==="
	python scripts/compare_benchmarks.py \
		--results $(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-tekgen.json \
		$(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-webnlg.json \
		$(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-canon.json \
		--out $(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-comparison

	@echo ""
	@echo "=== Auto-diffing against baseline ==="
	@python scripts/diff_benchmarks.py \
		--current $(REPORTS_DIR)/$(DATE)-$(CONFIG_SLUG)-comparison.json \
		--baseline reports/baseline-comparison.json

benchmark-canon: create-reports
	@echo "=== Running canon-software-architecture benchmark (standalone) ==="
	python scripts/run_canon_benchmark.py \
		--canon-dir $(CANON_DIR) \
		--out $(REPORTS_DIR)/$(DATE)-canon.json

check-pipeline:
	@if [ ! -f "$(PIPELINE)" ]; then \
		echo "Error: Pipeline config not found: $(PIPELINE)"; \
		exit 1; \
	fi
	@echo "✓ Pipeline config found: $(PIPELINE)"

validate-cache:
	@mkdir -p $(CACHE_DIR)
	@echo "✓ Cache directory ready: $(CACHE_DIR)"

create-reports:
	@mkdir -p $(REPORTS_DIR)
	@echo "✓ Reports directory ready: $(REPORTS_DIR)"
