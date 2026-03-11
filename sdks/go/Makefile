.PHONY: test test-race test-cov test-html lint vet fmt tidy clean build-examples

test:
	go test -v ./...

test-race:
	go test -v -race ./...

test-cov:
	go test -v -race -coverprofile=coverage.out ./...
	go tool cover -func=coverage.out

test-html: test-cov
	go tool cover -html=coverage.out -o coverage.html

lint:
	golangci-lint run ./...

vet:
	go vet ./...

fmt:
	gofmt -s -w .

tidy:
	go mod tidy

build-examples:
	go build ./examples/basic
	go build ./examples/feedback
	go build ./examples/hooks

clean:
	rm -f coverage.out coverage.html basic feedback hooks
