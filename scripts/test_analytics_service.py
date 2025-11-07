"""
Test script for the analytics service to verify KPI calculations.
"""

import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.analytics_service import AnalyticsService


def test_extraction_accuracy(db: Session):
    """Test extraction accuracy metrics calculation."""
    print("Testing extraction accuracy metrics...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_extraction_accuracy_metrics(start_date, end_date)

    print(f"  Total extractions: {metrics.get('total_extractions', 0)}")
    print(f"  Average confidence: {metrics.get('average_confidence', 0):.4f}")
    print(f"  High confidence rate: {metrics.get('high_confidence_rate', 0):.2f}%")
    print(f"  Medium confidence rate: {metrics.get('medium_confidence_rate', 0):.2f}%")
    print(f"  Low confidence rate: {metrics.get('low_confidence_rate', 0):.2f}%")

    if 'error' in metrics:
        print(f"  Error: {metrics['error']}")
        return False

    return True


def test_validation_metrics(db: Session):
    """Test validation pass rates calculation."""
    print("Testing validation pass rates...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_validation_pass_rates(start_date, end_date)

    print(f"  Total validations: {metrics.get('total_validations', 0)}")
    print(f"  Pass rate: {metrics.get('pass_rate', 0):.2f}%")
    print(f"  Fail rate: {metrics.get('fail_rate', 0):.2f}%")
    print(f"  Trend data points: {len(metrics.get('validation_trend', []))}")

    if 'error' in metrics:
        print(f"  Error: {metrics['error']}")
        return False

    return True


def test_exception_analysis(db: Session):
    """Test exception analysis calculation."""
    print("Testing exception analysis...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_exception_analysis(start_date, end_date)

    print(f"  Total exceptions: {metrics.get('total_exceptions', 0)}")
    print(f"  Exception rate: {metrics.get('exception_rate', 0):.2f}%")
    print(f"  Resolved exceptions: {metrics.get('resolved_exceptions', 0)}")
    print(f"  Resolution rate: {metrics.get('resolution_rate', 0):.2f}%")
    print(f"  Reason code categories: {len(metrics.get('reason_code_breakdown', {}))}")

    if 'error' in metrics:
        print(f"  Error: {metrics['error']}")
        return False

    return True


def test_cycle_time_metrics(db: Session):
    """Test cycle time metrics calculation."""
    print("Testing cycle time metrics...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_cycle_time_metrics(start_date, end_date)

    print(f"  Total invoices: {metrics.get('total_invoices', 0)}")
    print(f"  Average processing time: {metrics.get('average_processing_time_hours', 0):.2f} hours")

    distribution = metrics.get('processing_time_distribution', {})
    print(f"  Processing time distribution:")
    print(f"    Under 1 hour: {distribution.get('under_1_hour', 0)}")
    print(f"    1-4 hours: {distribution.get('1_to_4_hours', 0)}")
    print(f"    4-24 hours: {distribution.get('4_to_24_hours', 0)}")
    print(f"    Over 24 hours: {distribution.get('over_24_hours', 0)}")

    if 'error' in metrics:
        print(f"  Error: {metrics['error']}")
        return False

    return True


def test_productivity_metrics(db: Session):
    """Test productivity metrics calculation."""
    print("Testing productivity metrics...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_productivity_metrics(start_date, end_date)

    print(f"  Total invoices received: {metrics.get('total_invoices_received', 0)}")
    print(f"  Total invoices processed: {metrics.get('total_invoices_processed', 0)}")
    print(f"  Processing efficiency: {metrics.get('processing_efficiency', 0):.2f}%")
    print(f"  Total exceptions resolved: {metrics.get('total_exceptions_resolved', 0)}")
    print(f"  Total exports attempted: {metrics.get('total_exports_attempted', 0)}")
    print(f"  Total exports successful: {metrics.get('total_exports_successful', 0)}")
    print(f"  Export success rate: {metrics.get('export_success_rate', 0):.2f}%")

    if 'error' in metrics:
        print(f"  Error: {metrics['error']}")
        return False

    return True


def test_reviewer_performance(db: Session):
    """Test reviewer performance calculation."""
    print("Testing reviewer performance...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_reviewer_performance(start_date, end_date)

    print(f"  Total reviewers: {metrics.get('total_reviewers', 0)}")
    print(f"  Total resolved exceptions: {metrics.get('total_resolved_exceptions', 0)}")

    reviewer_performance = metrics.get('reviewer_performance', {})
    print(f"  Individual reviewer data points: {len(reviewer_performance)}")

    # Show top performer
    if reviewer_performance:
        top_reviewer = max(reviewer_performance.items(), key=lambda x: x[1].get('resolved_count', 0))
        name, data = top_reviewer
        print(f"  Top performer: {name}")
        print(f"    Resolved: {data.get('resolved_count', 0)}")
        print(f"    Avg resolution time: {data.get('average_resolution_time_hours', 0):.2f} hours")

    if 'error' in metrics:
        print(f"  Error: {metrics['error']}")
        return False

    return True


def test_executive_summary(db: Session):
    """Test executive summary calculation."""
    print("Testing executive summary...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    summary = analytics_service.get_executive_summary(start_date, end_date)

    print(f"  Overall health score: {summary.get('overall_health_score', 0):.2f}")

    key_metrics = summary.get('key_metrics', {})
    print(f"  Key metrics:")
    print(f"    Total invoices: {key_metrics.get('total_invoices', 0)}")
    print(f"    Processing efficiency: {key_metrics.get('processing_efficiency', 0):.2f}%")
    print(f"    Extraction accuracy: {key_metrics.get('extraction_accuracy', 0):.2f}%")
    print(f"    Validation pass rate: {key_metrics.get('validation_pass_rate', 0):.2f}%")
    print(f"    Exception rate: {key_metrics.get('exception_rate', 0):.2f}%")
    print(f"    Avg processing time: {key_metrics.get('avg_processing_time_hours', 0):.2f} hours")

    recommendations = summary.get('recommendations', [])
    print(f"  Recommendations: {len(recommendations)}")
    for i, rec in enumerate(recommendations[:3], 1):  # Show first 3
        print(f"    {i}. {rec}")

    if 'error' in summary:
        print(f"  Error: {summary['error']}")
        return False

    return True


def test_trend_analysis(db: Session):
    """Test trend analysis calculation."""
    print("Testing trend analysis...")

    analytics_service = AnalyticsService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)  # Shorter period for trend testing

    trends = analytics_service.get_trend_analysis(start_date, end_date, "all")

    trend_data = trends.get('trends', {})
    print(f"  Volume trend points: {len(trend_data.get('volume', []))}")
    print(f"  Accuracy trend points: {len(trend_data.get('accuracy', []))}")
    print(f"  Exception trend points: {len(trend_data.get('exceptions', []))}")

    # Show sample trend data
    if trend_data.get('volume'):
        latest_volume = trend_data['volume'][-1]
        print(f"  Latest volume data: {latest_volume}")

    if 'error' in trends:
        print(f"  Error: {trends['error']}")
        return False

    return True


def main():
    """Main test function."""
    print("Starting analytics service tests...\n")

    db = SessionLocal()
    try:
        # Run all tests
        tests = [
            test_extraction_accuracy,
            test_validation_metrics,
            test_exception_analysis,
            test_cycle_time_metrics,
            test_productivity_metrics,
            test_reviewer_performance,
            test_executive_summary,
            test_trend_analysis
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                if test(db):
                    passed += 1
                    print("  ✓ PASSED\n")
                else:
                    failed += 1
                    print("  ✗ FAILED\n")
            except Exception as e:
                failed += 1
                print(f"  ✗ FAILED with exception: {e}\n")

        print(f"Test Results: {passed} passed, {failed} failed")

        if failed == 0:
            print("All tests passed! Analytics service is working correctly.")
            return 0
        else:
            print("Some tests failed. Please check the errors above.")
            return 1

    except Exception as e:
        print(f"Test execution failed: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())