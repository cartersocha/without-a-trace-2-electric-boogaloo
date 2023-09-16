.PHONY: all - Default target
all: build

.PHONY: build - Build the collector
build: components/k8snetlogreceiver/factory.go
	builder --config otelcol-builder.yaml

.PHONY: test - Run tests for tcpstatsreceiver
test:
	cd components/k8snetlogreceiver && go test -v ./...

.PHONY: docker - Build docker image
docker:
	docker build . -t lightstep/without-a-trace-collector:latest