.PHONY: benchmark-experiment help

# Default pipeline config if not specified
PIPELINE ?= configs/extraction-experimental.json
CACHE_DIR := .benchmark-cache
REPORTS_DIR := reports

help:
	@echo "Context Studio Benchmarking Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  benchmark-experiment PIPELINE=<path>  Run benchmark against both datasets"
	@echo ""
	@echo "Example:"
	@echo "  make benchmark-experiment PIPELINE=configs/extraction-experimental.json"

benchmark-experiment: check-pipeline validate-cache create-reports
	@echo "=== Extracting config slug from $(PIPELINE) ==="
	$(eval CONFIG_SLUG := $(basename $(notdir $(PIPELINE))))
	@echo "Config slug: $(CONFIG_SLUG)"

	@echo ""
	@echo "=== Running benchmark on TekGen dataset ==="
	python scripts/run_benchmark.py \
		--dataset text2kg-bench/wikidata-tekgen \
		--pipeline $(PIPELINE) \
		--out $(REPORTS_DIR)/$(CONFIG_SLUG)-tekgen.json

	@echo ""
	@echo "=== Running benchmark on WebNLG dataset ==="
	python scripts/run_benchmark.py \
		--dataset text2kg-bench/dbpedia-webnlg \
		--pipeline $(PIPELINE) \
		--out $(REPORTS_DIR)/$(CONFIG_SLUG)-webnlg.json

	@echo ""
	@echo "=== Generating cross-dataset comparison ==="
	python scripts/compare_benchmarks.py \
		--results $(REPORTS_DIR)/$(CONFIG_SLUG)-tekgen.json $(REPORTS_DIR)/$(CONFIG_SLUG)-webnlg.json \
		--out $(REPORTS_DIR)/$(CONFIG_SLUG)-comparison

	@echo ""
	@echo "=== Auto-diffing against baseline ==="
	@python scripts/diff_benchmarks.py \
		--current $(REPORTS_DIR)/$(CONFIG_SLUG)-comparison.json \
		--baseline reports/baseline-comparison.json \
		--cache $(CACHE_DIR)

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
