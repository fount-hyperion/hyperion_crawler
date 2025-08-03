#!/bin/bash

# 테스트 실행 스크립트

echo "Running Hyperion Crawler Tests"
echo "=============================="

# Python 경로 확인
echo "Python version:"
python --version

# 필요한 패키지 확인
echo -e "\nChecking required packages..."
python -c "import pykrx; print('✓ pykrx installed')"
python -c "import kardia; print('✓ kardia installed')"
python -c "import pytest; print('✓ pytest installed')"

# 테스트 실행
echo -e "\nRunning unit tests..."
python -m pytest tests/unit/ -v --tb=short --cov=api/src --cov-report=term-missing

# 테스트 결과 요약
if [ $? -eq 0 ]; then
    echo -e "\n✅ All tests passed!"
else
    echo -e "\n❌ Some tests failed!"
    exit 1
fi

# 커버리지 리포트
echo -e "\nTest coverage report saved to: htmlcov/index.html"