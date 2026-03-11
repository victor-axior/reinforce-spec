.PHONY: install lint typecheck test test-cov format clean build

install:
	npm install

lint:
	npx eslint src/ tests/

typecheck:
	npx tsc --noEmit

test:
	npx jest

test-cov:
	npx jest --coverage

format:
	npx prettier --write "src/**/*.ts" "tests/**/*.ts"

clean:
	npx rimraf dist coverage

build: clean
	npm run build
