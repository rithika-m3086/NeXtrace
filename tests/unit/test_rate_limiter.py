import time
import pytest
from utils.rate_limiter import RateLimiter, call_with_retry, default_rate_limiter


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    default_rate_limiter.requests.clear()


def test_rate_limiter_requests_wait(monkeypatch):
    limiter = RateLimiter()
    curr_time = [100.0]
    monkeypatch.setattr(time, "time", lambda: curr_time[0])
    
    slept = []
    def mock_sleep(x):
        slept.append(x)
        curr_time[0] += x
    monkeypatch.setattr(time, "sleep", mock_sleep)
    
    for _ in range(60):
        limiter.wait_if_needed(estimated_tokens=10)
        
    assert len(limiter.requests) == 60
    
    # Request 61 should trigger a wait
    limiter.wait_if_needed(estimated_tokens=10)
    assert len(slept) == 1
    assert slept[0] == 60.0


def test_rate_limiter_tokens_wait(monkeypatch):
    limiter = RateLimiter()
    curr_time = [100.0]
    monkeypatch.setattr(time, "time", lambda: curr_time[0])
    slept = []
    def mock_sleep(x):
        slept.append(x)
        curr_time[0] += x
    monkeypatch.setattr(time, "sleep", mock_sleep)
    
    limiter.wait_if_needed(estimated_tokens=40000)
    limiter.wait_if_needed(estimated_tokens=40000)
    assert len(slept) == 0
    
    limiter.wait_if_needed(estimated_tokens=30000)
    assert len(slept) == 1
    assert slept[0] == 60.0


def test_call_with_retry_success():
    def mock_fn(val):
        return val * 2
        
    result = call_with_retry(mock_fn, 5, estimated_tokens=10)
    assert result == 10


def test_call_with_retry_other_exception():
    def mock_fn():
        raise ValueError("ordinary error")
        
    with pytest.raises(ValueError, match="ordinary error"):
        call_with_retry(mock_fn, estimated_tokens=10)


def test_call_with_retry_rate_limit(monkeypatch):
    calls = [0]
    slept = []
    monkeypatch.setattr(time, "sleep", lambda x: slept.append(x))
    
    class MockRateLimitError(Exception):
        status_code = 429
        
    def mock_fn():
        calls[0] += 1
        if calls[0] < 3:
            raise MockRateLimitError("Rate limit exceeded")
        return "success"
        
    result = call_with_retry(mock_fn, estimated_tokens=10)
    assert result == "success"
    assert calls[0] == 3
    assert len(slept) == 2
    assert slept[0] == 1.0
    assert slept[1] == 2.0


def test_call_with_retry_exhausted(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda x: None)
    
    class MockRateLimitError(Exception):
        status_code = 429
        
    def mock_fn():
        raise MockRateLimitError("Always 429")
        
    with pytest.raises(RuntimeError, match="Rate limit retry attempts exhausted"):
        call_with_retry(mock_fn, estimated_tokens=10)
