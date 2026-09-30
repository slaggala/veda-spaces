# Veda staging infrastructure (AUT-001). Run from the repository root with `make -C infra <target>`.
# Tools can be overridden, e.g. `make -C infra check TERRAFORM=/path/to/terraform`.
#
# Static checks never touch AWS. Only bootstrap-plan / bootstrap-apply / discover need AWS credentials, and
# they refuse any account other than EXPECTED_ACCOUNT_ID.

SHELL      := /bin/bash
TERRAFORM  ?= terraform
TFLINT     ?= tflint
CHECKOV    ?= checkov
SHELLCHECK ?= shellcheck
ACTIONLINT ?= actionlint

ROOTS      := terraform/bootstrap
SCRIPTS    := $(wildcard scripts/*.sh)
WORKFLOWS  := $(wildcard ../.github/workflows/0*.yml)

# Offline checks run with credentials disabled so they can never reach an AWS account by accident.
OFFLINE_ENV := AWS_PROFILE= AWS_ACCESS_KEY_ID= AWS_SECRET_ACCESS_KEY= AWS_SESSION_TOKEN= \
               AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true

.PHONY: help check fmt fmt-check validate test test-scripts lint tflint checkov shellcheck actionlint \
        discover bootstrap-plan bootstrap-apply github-environments github-verify github-variables clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-22s %s\n", $$1, $$2}'

check: fmt-check validate test test-scripts lint ## All offline checks (no AWS access)

fmt: ## Format Terraform
	$(TERRAFORM) fmt -recursive terraform

fmt-check: ## Fail on unformatted Terraform
	$(TERRAFORM) fmt -check -diff -recursive terraform

validate: ## terraform init (no backend) + validate for every root
	@for r in $(ROOTS); do \
	  echo "== validate $$r"; \
	  (cd $$r && $(OFFLINE_ENV) $(TERRAFORM) init -backend=false -input=false >/dev/null && $(OFFLINE_ENV) $(TERRAFORM) validate) || exit 1; \
	done

test: ## terraform test (offline, overridden provider values; creates nothing)
	@for r in $(ROOTS); do \
	  echo "== test $$r"; \
	  (cd $$r && $(OFFLINE_ENV) $(TERRAFORM) init -backend=false -input=false >/dev/null && $(OFFLINE_ENV) $(TERRAFORM) test) || exit 1; \
	done

test-scripts: ## Script, plan-guard, workflow and negative Terraform tests (offline; stubbed aws/gh)
	$(OFFLINE_ENV) TERRAFORM=$(TERRAFORM) tests/run.sh

lint: tflint checkov shellcheck actionlint ## All linters

tflint: ## tflint with the AWS ruleset
	$(TFLINT) --config=$(CURDIR)/.tflint.hcl --init
	@for r in $(ROOTS); do $(TFLINT) --config=$(CURDIR)/.tflint.hcl --chdir=$$r || exit 1; done

checkov: ## checkov (every skip is inline and justified)
	@for r in $(ROOTS); do $(CHECKOV) -d $$r --framework terraform --compact --quiet --skip-download || exit 1; done

shellcheck: ## shellcheck the scripts and their tests
	$(SHELLCHECK) $(SCRIPTS) tests/run.sh tests/stubs/aws tests/stubs/gh tests/stubs/terraform

actionlint: ## actionlint the infra workflows
	$(ACTIONLINT) $(WORKFLOWS)

discover: ## Read-only discovery (needs EXPECTED_ACCOUNT_ID and a session in that account)
	scripts/discover.sh --expected-account-id "$(EXPECTED_ACCOUNT_ID)"

bootstrap-plan: ## Bootstrap plan: read-only (needs EXPECTED_ACCOUNT_ID)
	scripts/bootstrap.sh --mode plan --expected-account-id "$(EXPECTED_ACCOUNT_ID)"

bootstrap-apply: ## Apply the plan it shows, or the approved PLAN_FILE whose SHA-256 is PLAN_SHA256 (type the account ID)
	scripts/bootstrap.sh --mode apply --expected-account-id "$(EXPECTED_ACCOUNT_ID)" \
	  $(if $(PLAN_FILE),--plan-file $(PLAN_FILE) --plan-meta $(or $(PLAN_META),generated/bootstrap-plan.meta.json) \
	  --plan-sha256 "$(PLAN_SHA256)")

github-environments: ## Dry run of the GitHub environments and main protection (APPLY=1 to apply; REVIEWERS=a,b)
	scripts/github-setup.sh $(if $(REVIEWERS),--reviewers $(REVIEWERS)) $(if $(APPLY),--apply)

github-verify: ## Read back environments and main protection; fail on drift (full: needs admin)
	scripts/github-setup.sh --verify

github-variables: ## Dry run of the GitHub variables from bootstrap outputs (APPLY=1 to set them)
	scripts/github-setup.sh --outputs generated/bootstrap-outputs.json --variables-only $(if $(APPLY),--apply)

clean: ## Remove local Terraform working files and generated output (never state in S3)
	rm -rf generated terraform/*/.terraform terraform/*/generated.auto.tfvars.json terraform/*/backend_s3.tf
