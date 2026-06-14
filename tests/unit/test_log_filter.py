import json
from utils.log_filter import filter_log_sources, get_filter_stats


def test_filter_log_sources_cloudtrail():
    raw_cloudtrail = {
        "Records": [
            {
                "eventName": "GetCallerIdentity",
                "eventType": "AwsApiCall",
                "readOnly": True,
                "http_status": 200
            },
            {
                "eventName": "DeleteBucket",
                "eventType": "AwsApiCall",
                "readOnly": False,
                "http_status": 200
            },
            {
                "eventName": "ListBuckets",
                "eventType": "AwsApiCall",
                "readOnly": True,
                "http_status": 200,
                "user_agent": "ELB-HealthChecker/2.0"
            },
            {
                "eventName": "DescribeInstances",
                "eventType": "AwsApiCall",
                "readOnly": True,
                "http_status": 200,
                "sourceIPAddress": "127.0.0.1"
            },
            {
                "eventName": "GetBucketLocation",
                "eventType": "AwsApiCall",
                "readOnly": True,
                "http_status": 200,
                "errorMessage": "AccessDenied"
            }
        ]
    }
    
    log_sources = [
        {
            "source_name": "cloudtrail",
            "source_type": "cloudtrail",
            "content": json.dumps(raw_cloudtrail)
        },
        {
            "source_name": "plain_text",
            "source_type": "custom",
            "content": "This is raw non-json healthcheck text line 1\nThis is raw non-json line 2"
        }
    ]

    filtered = filter_log_sources(log_sources)

    # Verify cloudtrail filtered content
    cloudtrail_filt = json.loads(filtered[0]["content"])
    records = cloudtrail_filt["Records"]
    
    # "GetCallerIdentity" (readOnly 200 with no write) -> noise, no security signals -> removed
    # "DeleteBucket" (readOnly False/has write) -> has "delete" -> security signal -> kept
    # "ListBuckets" (contains ELB-HealthChecker) -> noise, no security signals -> removed
    # "DescribeInstances" (contains 127.0.0.1) -> noise, no security signals -> removed
    # "GetBucketLocation" (contains errorMessage: "AccessDenied") -> has "error" & "deny" -> security signals -> kept
    assert len(records) == 2
    assert records[0]["eventName"] == "DeleteBucket"
    assert records[1]["eventName"] == "GetBucketLocation"

    # Verify plain text is unchanged
    assert filtered[1]["content"] == log_sources[1]["content"]


def test_get_filter_stats():
    original = [
        {
            "source_name": "cloudtrail",
            "content": json.dumps({"Records": [{}, {}, {}, {}]})
        },
        {
            "source_name": "plain_text",
            "content": "line1\nline2\nline3"
        }
    ]
    filtered = [
        {
            "source_name": "cloudtrail",
            "content": json.dumps({"Records": [{}]})
        },
        {
            "source_name": "plain_text",
            "content": "line1\nline2\nline3"
        }
    ]
    stats = get_filter_stats(original, filtered)
    
    assert stats["total_original_events"] == 7  # 4 records + 3 lines
    assert stats["total_filtered_events"] == 4  # 1 record + 3 lines
    # (7 - 4)/7 * 100 = 42.86
    assert stats["reduction_percentage"] == 42.86
    assert stats["per_source"][0] == {
        "source_name": "cloudtrail",
        "original": 4,
        "filtered": 1
    }
    assert stats["per_source"][1] == {
        "source_name": "plain_text",
        "original": 3,
        "filtered": 3
    }
