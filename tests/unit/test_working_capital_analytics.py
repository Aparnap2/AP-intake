"""
Comprehensive Test-Driven Development tests for Working Capital Analytics Service.

This module implements thorough unit tests for all working capital analytics calculations,
ensuring financial accuracy, performance optimization, and edge case handling.
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any
import uuid

from app.services.working_capital_analytics import WorkingCapitalAnalytics
from app.models.working_capital import (
    CashFlowProjection,
    PaymentOptimization,
    EarlyPaymentDiscount,
    CollectionMetrics,
    WorkingCapitalScore
)
from app.models.ar_invoice import ARInvoice, Customer, PaymentStatus, CollectionPriority


class TestCashFlowForecasting:
    """Test cases for cash flow forecasting algorithms."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def sample_invoices(self) -> List[Dict]:
        """Create sample invoice data for testing."""
        base_date = datetime.now()
        return [
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('10000.00'),
                'outstanding_amount': Decimal('10000.00'),
                'due_date': base_date + timedelta(days=15),
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('5000.00'),
                'outstanding_amount': Decimal('2500.00'),
                'due_date': base_date + timedelta(days=30),
                'status': PaymentStatus.PARTIALLY_PAID,
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('15000.00'),
                'outstanding_amount': Decimal('15000.00'),
                'due_date': base_date + timedelta(days=60),
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('8000.00'),
                'outstanding_amount': Decimal('8000.00'),
                'due_date': base_date + timedelta(days=90),
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            }
        ]

    @pytest.mark.asyncio
    async def test_30_day_cash_flow_projection(self, mock_db_session, sample_invoices):
        """Test 30-day cash flow projection calculation."""
        # Setup mock to return only invoices due within 30 days
        mock_invoices = [inv for inv in sample_invoices if inv['due_date'] <= datetime.now() + timedelta(days=30)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        projection = await analytics.calculate_cash_flow_projection(days=30)

        # Verify structure
        assert 'total_projected' in projection
        assert 'daily_breakdown' in projection
        assert 'weekly_breakdown' in projection
        assert 'confidence_score' in projection

        # Verify calculations
        expected_total = sum(inv['outstanding_amount'] for inv in mock_invoices)
        assert projection['total_projected'] == expected_total
        assert len(projection['daily_breakdown']) <= 30
        assert len(projection['weekly_breakdown']) <= 5  # 30 days / 7 days

    @pytest.mark.asyncio
    async def test_60_day_cash_flow_projection(self, mock_db_session, sample_invoices):
        """Test 60-day cash flow projection calculation."""
        mock_invoices = [inv for inv in sample_invoices if inv['due_date'] <= datetime.now() + timedelta(days=60)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        projection = await analytics.calculate_cash_flow_projection(days=60)

        expected_total = sum(inv['outstanding_amount'] for inv in mock_invoices)
        assert projection['total_projected'] == expected_total
        assert len(projection['weekly_breakdown']) <= 9  # 60 days / 7 days
        assert len(projection['monthly_breakdown']) <= 2  # 60 days / 30 days

    @pytest.mark.asyncio
    async def test_90_day_cash_flow_projection(self, mock_db_session, sample_invoices):
        """Test 90-day cash flow projection calculation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        projection = await analytics.calculate_cash_flow_projection(days=90)

        expected_total = sum(inv['outstanding_amount'] for inv in sample_invoices)
        assert projection['total_projected'] == expected_total
        assert len(projection['weekly_breakdown']) <= 13  # 90 days / 7 days
        assert len(projection['monthly_breakdown']) <= 3  # 90 days / 30 days

    @pytest.mark.asyncio
    async def test_seasonal_pattern_detection(self, mock_db_session):
        """Test seasonal pattern detection in cash flow."""
        # Create invoices with seasonal patterns
        base_date = datetime.now()
        seasonal_invoices = []

        # Add invoices for different months to simulate seasonality
        for month_offset in range(12):
            for week_in_month in range(4):
                invoice_date = base_date + timedelta(days=month_offset * 30 + week_in_month * 7)
                seasonal_invoices.append({
                    'id': uuid.uuid4(),
                    'total_amount': Decimal('5000.00'),
                    'outstanding_amount': Decimal('5000.00'),
                    'due_date': invoice_date,
                    'status': PaymentStatus.PENDING,
                    'customer_id': uuid.uuid4()
                })

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = seasonal_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        patterns = await analytics.detect_seasonal_patterns()

        assert 'seasonal_index' in patterns
        assert 'peak_months' in patterns
        assert 'low_months' in patterns
        assert 'confidence_level' in patterns
        assert len(patterns['seasonal_index']) == 12  # 12 months

    @pytest.mark.asyncio
    async def test_scenario_analysis_optimistic(self, mock_db_session, sample_invoices):
        """Test optimistic scenario analysis for cash flow."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        scenarios = await analytics.analyze_cash_flow_scenarios()

        assert 'optimistic' in scenarios
        assert 'pessimistic' in scenarios
        assert 'realistic' in scenarios

        optimistic = scenarios['optimistic']
        assert 'projected_cash_flow' in optimistic
        assert 'assumptions' in optimistic
        assert optimistic['assumptions']['payment_rate'] > 0.8  # Higher payment rate
        assert optimistic['assumptions']['collection_efficiency'] > 0.9

    @pytest.mark.asyncio
    async def test_scenario_analysis_pessimistic(self, mock_db_session, sample_invoices):
        """Test pessimistic scenario analysis for cash flow."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        scenarios = await analytics.analyze_cash_flow_scenarios()

        pessimistic = scenarios['pessimistic']
        assert pessimistic['assumptions']['payment_rate'] < 0.6  # Lower payment rate
        assert pessimistic['assumptions']['collection_efficiency'] < 0.7
        assert pessimistic['assumptions']['default_rate'] > 0.05  # Some defaults

    @pytest.mark.asyncio
    async def test_cash_flow_accuracy_validation(self, mock_db_session):
        """Test accuracy validation of cash flow projections."""
        # Create historical data
        historical_dates = [
            datetime.now() - timedelta(days=180 + i * 30) for i in range(6)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock historical accuracy data
        with patch.object(analytics, 'get_historical_accuracy') as mock_accuracy:
            mock_accuracy.return_value = {
                'mape': 15.2,  # Mean Absolute Percentage Error
                'bias': -2.1,   # Slight underprediction
                'accuracy_score': 84.8
            }

            accuracy = await analytics.validate_projection_accuracy()

            assert 'mape' in accuracy
            assert 'bias' in accuracy
            assert 'accuracy_score' in accuracy
            assert 'recommendations' in accuracy
            assert accuracy['accuracy_score'] == 84.8

    @pytest.mark.asyncio
    async def test_empty_cash_flow_projection(self, mock_db_session):
        """Test cash flow projection with no invoices."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        projection = await analytics.calculate_cash_flow_projection(days=30)

        assert projection['total_projected'] == Decimal('0.00')
        assert len(projection['daily_breakdown']) == 0
        assert len(projection['weekly_breakdown']) == 0


class TestPaymentOptimization:
    """Test cases for payment optimization algorithms."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def sample_discount_invoices(self) -> List[Dict]:
        """Create sample invoices with early payment discounts."""
        base_date = datetime.now()
        return [
            {
                'id': uuid.uuid4(),
                'invoice_number': 'INV-001',
                'total_amount': Decimal('10000.00'),
                'outstanding_amount': Decimal('10000.00'),
                'due_date': base_date + timedelta(days=30),
                'invoice_date': base_date - timedelta(days=10),
                'early_payment_discount_percent': Decimal('2.00'),
                'early_payment_discount_days': '10',
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'invoice_number': 'INV-002',
                'total_amount': Decimal('5000.00'),
                'outstanding_amount': Decimal('5000.00'),
                'due_date': base_date + timedelta(days=45),
                'invoice_date': base_date - timedelta(days=5),
                'early_payment_discount_percent': Decimal('1.50'),
                'early_payment_discount_days': '15',
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'invoice_number': 'INV-003',
                'total_amount': Decimal('8000.00'),
                'outstanding_amount': Decimal('8000.00'),
                'due_date': base_date + timedelta(days=60),
                'invoice_date': base_date - timedelta(days=20),
                'early_payment_discount_percent': Decimal('3.00'),
                'early_payment_discount_days': '5',  # Expired
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            }
        ]

    @pytest.mark.asyncio
    async def test_optimal_payment_timing_calculation(self, mock_db_session, sample_discount_invoices):
        """Test optimal payment timing calculations."""
        # Filter out expired discount
        valid_invoices = [inv for inv in sample_discount_invoices if inv['early_payment_discount_days'] != '5']
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = valid_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        recommendations = await analytics.calculate_optimal_payment_timing()

        assert len(recommendations) == 2  # Only valid discounts

        for rec in recommendations:
            assert 'invoice_id' in rec
            assert 'optimal_payment_date' in rec
            assert 'discount_savings' in rec
            assert 'working_capital_impact' in rec
            assert 'recommendation' in rec

            # Verify discount calculations
            if rec.get('discount_available'):
                expected_discount = rec['outstanding_amount'] * (rec['discount_percent'] / Decimal('100'))
                assert rec['discount_savings'] == expected_discount

    @pytest.mark.asyncio
    async def test_early_payment_discount_analysis(self, mock_db_session, sample_discount_invoices):
        """Test early payment discount opportunity analysis."""
        # Mock invoices that still have valid discounts
        valid_discount_invoices = [
            inv for inv in sample_discount_invoices
            if inv['early_payment_discount_days'] != '5'
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = valid_discount_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        analysis = await analytics.analyze_early_payment_discounts()

        assert 'total_opportunities' in analysis
        assert 'potential_savings' in analysis
        assert 'opportunities' in analysis
        assert 'roi_analysis' in analysis

        assert analysis['total_opportunities'] == 2
        expected_savings = (
            Decimal('10000.00') * Decimal('0.02') +  # 2% of $10,000
            Decimal('5000.00') * Decimal('0.015')    # 1.5% of $5,000
        )
        assert analysis['potential_savings'] == expected_savings

    @pytest.mark.asyncio
    async def test_working_capital_impact_scoring(self, mock_db_session):
        """Test working capital impact scoring for payment decisions."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Test different scenarios
        scenarios = [
            {
                'amount': Decimal('10000.00'),
                'discount_percent': Decimal('2.00'),
                'payment_terms': 30,
                'cost_of_capital': Decimal('0.08')  # 8% annual
            },
            {
                'amount': Decimal('5000.00'),
                'discount_percent': Decimal('1.00'),
                'payment_terms': 60,
                'cost_of_capital': Decimal('0.10')  # 10% annual
            }
        ]

        for scenario in scenarios:
            impact_score = await analytics.calculate_working_capital_impact(**scenario)

            assert 'net_benefit' in impact_score
            assert 'annualized_return' in impact_score
            assert 'recommendation' in impact_score
            assert 'impact_score' in impact_score

            # Verify annualized return calculation
            discount_amount = scenario['amount'] * (scenario['discount_percent'] / Decimal('100'))
            days_saved = scenario['payment_terms']
            expected_annualized_return = (discount_amount / scenario['amount']) * (365 / days_saved)
            assert abs(impact_score['annualized_return'] - float(expected_annualized_return)) < 0.01

    @pytest.mark.asyncio
    async def test_roi_calculations_for_payment_decisions(self, mock_db_session):
        """Test ROI calculations for payment timing decisions."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        payment_analysis = await analytics.calculate_payment_roi(
            invoice_amount=Decimal('10000.00'),
            discount_percent=Decimal('2.00'),
            discount_days=10,
            regular_terms=30,
            cost_of_capital=Decimal('0.08')
        )

        assert 'discount_amount' in payment_analysis
        assert 'cost_of_early_payment' in payment_analysis
        assert 'net_roi' in payment_analysis
        assert 'annualized_roi' in payment_analysis
        assert 'recommendation' in payment_analysis

        # Verify calculations
        expected_discount = Decimal('200.00')  # 2% of $10,000
        assert payment_analysis['discount_amount'] == expected_discount

        # Early payment cost for 20 days (30-10) at 8% annual
        expected_cost = Decimal('10000.00') * Decimal('0.08') * (Decimal('20') / Decimal('365'))
        assert abs(payment_analysis['cost_of_early_payment'] - expected_cost) < Decimal('0.01')

    @pytest.mark.asyncio
    async def test_payment_optimization_with_multiple_invoices(self, mock_db_session):
        """Test payment optimization across multiple invoices."""
        # Create invoices with varying terms and discounts
        invoices = []
        for i in range(10):
            invoices.append({
                'id': uuid.uuid4(),
                'total_amount': Decimal(str(1000 + i * 500)),
                'outstanding_amount': Decimal(str(1000 + i * 500)),
                'due_date': datetime.now() + timedelta(days=30 + i * 5),
                'early_payment_discount_percent': Decimal(str(1.0 + i * 0.2)),
                'early_payment_discount_days': str(15 - i),
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            })

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        optimization = await analytics.optimize_payment_schedule()

        assert 'payment_schedule' in optimization
        assert 'total_savings' in optimization
        assert 'working_capital_preserved' in optimization
        assert 'priority_list' in optimization

        # Verify schedule is sorted by priority (highest ROI first)
        schedule = optimization['payment_schedule']
        if len(schedule) > 1:
            for i in range(len(schedule) - 1):
                assert schedule[i]['priority_score'] >= schedule[i + 1]['priority_score']


class TestCollectionEfficiency:
    """Test cases for collection efficiency metrics."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def sample_collection_data(self) -> List[Dict]:
        """Create sample data for collection efficiency testing."""
        base_date = datetime.now()
        return [
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('10000.00'),
                'outstanding_amount': Decimal('0.00'),
                'status': PaymentStatus.PAID,
                'paid_at': base_date - timedelta(days=5),
                'invoice_date': base_date - timedelta(days=35),  # Paid in 30 days
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('5000.00'),
                'outstanding_amount': Decimal('5000.00'),
                'status': PaymentStatus.OVERDUE,
                'due_date': base_date - timedelta(days=15),
                'invoice_date': base_date - timedelta(days=45),
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('8000.00'),
                'outstanding_amount': Decimal('2000.00'),
                'status': PaymentStatus.PARTIALLY_PAID,
                'paid_at': base_date - timedelta(days=10),
                'invoice_date': base_date - timedelta(days=25),  # Partial payment in 15 days
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'total_amount': Decimal('3000.00'),
                'outstanding_amount': Decimal('3000.00'),
                'status': PaymentStatus.PENDING,
                'due_date': base_date + timedelta(days=15),
                'invoice_date': base_date - timedelta(days=15),
                'customer_id': uuid.uuid4()
            }
        ]

    @pytest.mark.asyncio
    async def test_dso_calculation(self, mock_db_session, sample_collection_data):
        """Test Days Sales Outstanding (DSO) calculation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_collection_data
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        dso_metrics = await analytics.calculate_dso()

        assert 'current_dso' in dso_metrics
        assert 'dso_trend' in dso_metrics
        assert 'industry_comparison' in dso_metrics
        assert 'recommendations' in dso_metrics

        # Calculate expected DSO manually
        total_outstanding = sum(inv['outstanding_amount'] for inv in sample_collection_data if inv['outstanding_amount'] > 0)
        total_revenue = sum(inv['total_amount'] for inv in sample_collection_data)

        if total_revenue > 0:
            expected_dso = (total_outstanding / total_revenue) * 365
            assert abs(dso_metrics['current_dso'] - float(expected_dso)) < 1.0

    @pytest.mark.asyncio
    async def test_collection_effectiveness_index(self, mock_db_session, sample_collection_data):
        """Test Collection Effectiveness Index calculation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_collection_data
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        cei_metrics = await analytics.calculate_collection_effectiveness_index()

        assert 'cei_score' in cei_metrics
        assert 'collection_rate' in cei_metrics
        assert 'recovery_rate' in cei_metrics
        assert 'benchmark_comparison' in cei_metrics

        # Verify CEI calculation: CEI = (Beginning Collections + Current Collections) / (Beginning Receivables + Credit Sales)
        beginning_collections = Decimal('0.00')
        current_collections = sum(inv['total_amount'] for inv in sample_collection_data if inv['status'] == PaymentStatus.PAID)
        beginning_receivables = sum(inv['total_amount'] for inv in sample_collection_data)
        credit_sales = beginning_receivables  # Assuming all are credit sales for this test

        expected_cei = ((beginning_collections + current_collections) / (beginning_receivables + credit_sales)) * 100
        assert abs(cei_metrics['cei_score'] - float(expected_cei)) < 1.0

    @pytest.mark.asyncio
    async def test_aging_bucket_analysis(self, mock_db_session):
        """Test aging bucket analysis for receivables."""
        base_date = datetime.now()
        aging_invoices = [
            {
                'id': uuid.uuid4(),
                'outstanding_amount': Decimal('5000.00'),
                'due_date': base_date - timedelta(days=5),   # Current
                'status': PaymentStatus.PENDING
            },
            {
                'id': uuid.uuid4(),
                'outstanding_amount': Decimal('3000.00'),
                'due_date': base_date - timedelta(days=15),  # 1-30 days
                'status': PaymentStatus.OVERDUE
            },
            {
                'id': uuid.uuid4(),
                'outstanding_amount': Decimal('2000.00'),
                'due_date': base_date - timedelta(days=45),  # 31-60 days
                'status': PaymentStatus.OVERDUE
            },
            {
                'id': uuid.uuid4(),
                'outstanding_amount': Decimal('1000.00'),
                'due_date': base_date - timedelta(days=75),  # 61-90 days
                'status': PaymentStatus.OVERDUE
            },
            {
                'id': uuid.uuid4(),
                'outstanding_amount': Decimal('500.00'),
                'due_date': base_date - timedelta(days=95),  # 90+ days
                'status': PaymentStatus.OVERDUE
            }
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = aging_invoices
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        aging_analysis = await analytics.analyze_aging_buckets()

        assert 'current' in aging_analysis
        assert 'days_1_30' in aging_analysis
        assert 'days_31_60' in aging_analysis
        assert 'days_61_90' in aging_analysis
        assert 'days_over_90' in aging_analysis
        assert 'total_outstanding' in aging_analysis
        assert 'risk_assessment' in aging_analysis

        # Verify bucket calculations
        assert aging_analysis['current']['amount'] == Decimal('5000.00')
        assert aging_analysis['days_1_30']['amount'] == Decimal('3000.00')
        assert aging_analysis['days_31_60']['amount'] == Decimal('2000.00')
        assert aging_analysis['days_61_90']['amount'] == Decimal('1000.00')
        assert aging_analysis['days_over_90']['amount'] == Decimal('500.00')

        total_outstanding = sum(bucket['amount'] for bucket in aging_analysis.values() if isinstance(bucket, dict) and 'amount' in bucket)
        assert aging_analysis['total_outstanding'] == total_outstanding

    @pytest.mark.asyncio
    async def test_payment_pattern_analysis(self, mock_db_session):
        """Test payment pattern analysis for customers."""
        # Create payment history data
        payment_history = []
        base_date = datetime.now()

        for i in range(50):  # 50 payments over time
            payment_days = 20 + (i % 40)  # Varying from 20 to 60 days
            payment_history.append({
                'invoice_date': base_date - timedelta(days=100 + i * 5),
                'paid_at': base_date - timedelta(days=100 + i * 5 - payment_days),
                'total_amount': Decimal(str(1000 + i * 100)),
                'customer_id': uuid.uuid4()
            })

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = payment_history
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        patterns = await analytics.analyze_payment_patterns()

        assert 'average_payment_days' in patterns
        assert 'payment_distribution' in patterns
        assert 'seasonal_trends' in patterns
        assert 'predictability_score' in patterns

        # Verify average calculation
        all_payment_days = []
        for payment in payment_history:
            days = (payment['paid_at'] - payment['invoice_date']).days
            all_payment_days.append(days)

        expected_avg = sum(all_payment_days) / len(all_payment_days)
        assert abs(patterns['average_payment_days'] - expected_avg) < 1.0

    @pytest.mark.asyncio
    async def test_collection_efficiency_trends(self, mock_db_session):
        """Test collection efficiency trend analysis over time."""
        # Create time-series data
        trends_data = []
        base_date = datetime.now()

        for month_offset in range(12):
            month_data = {
                'period': base_date - timedelta(days=month_offset * 30),
                'total_invoices': 50 + month_offset * 2,
                'paid_invoices': 45 + month_offset * 2,
                'average_days_to_pay': 35 - month_offset * 0.5,
                'collection_rate': 0.9 + month_offset * 0.002
            }
            trends_data.append(month_data)

        analytics = WorkingCapitalAnalytics(mock_db_session)

        with patch.object(analytics, 'get_historical_collection_data') as mock_history:
            mock_history.return_value = trends_data

            trends = await analytics.analyze_collection_efficiency_trends()

            assert 'collection_rate_trend' in trends
            assert 'dso_trend' in trends
            assert 'improvement_areas' in trends
            assert 'forecast' in trends

            # Verify trend calculation
            assert len(trends['collection_rate_trend']) == 12
            assert 'direction' in trends['collection_rate_trend'][0]  # improving, declining, stable


class TestEarlyPaymentDiscounts:
    """Test cases for early payment discount detection and analysis."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def discount_opportunities(self) -> List[Dict]:
        """Create sample early payment discount opportunities."""
        base_date = datetime.now()
        return [
            {
                'id': uuid.uuid4(),
                'invoice_number': 'DISC-001',
                'total_amount': Decimal('20000.00'),
                'outstanding_amount': Decimal('20000.00'),
                'invoice_date': base_date - timedelta(days=5),
                'due_date': base_date + timedelta(days=25),
                'early_payment_discount_percent': Decimal('2.50'),
                'early_payment_discount_days': '10',
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'invoice_number': 'DISC-002',
                'total_amount': Decimal('15000.00'),
                'outstanding_amount': Decimal('15000.00'),
                'invoice_date': base_date - timedelta(days=3),
                'due_date': base_date + timedelta(days=27),
                'early_payment_discount_percent': Decimal('1.00'),
                'early_payment_discount_days': '15',
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            },
            {
                'id': uuid.uuid4(),
                'invoice_number': 'DISC-003',
                'total_amount': Decimal('25000.00'),
                'outstanding_amount': Decimal('25000.00'),
                'invoice_date': base_date - timedelta(days=12),
                'due_date': base_date + timedelta(days=18),
                'early_payment_discount_percent': Decimal('3.00'),
                'early_payment_discount_days': '5',  # Expired yesterday
                'status': PaymentStatus.PENDING,
                'customer_id': uuid.uuid4()
            }
        ]

    @pytest.mark.asyncio
    async def test_discount_opportunity_detection(self, mock_db_session, discount_opportunities):
        """Test detection of early payment discount opportunities."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = discount_opportunities
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        opportunities = await analytics.detect_discount_opportunities()

        assert 'total_opportunities' in opportunities
        assert 'available_opportunities' in opportunities
        assert 'expired_opportunities' in opportunities
        assert 'total_potential_savings' in opportunities
        assert 'opportunities_list' in opportunities

        # Should find 2 available opportunities (one expired)
        assert opportunities['available_opportunities'] == 2
        assert opportunities['expired_opportunities'] == 1

        # Calculate expected savings
        expected_savings = (
            Decimal('20000.00') * Decimal('0.025') +  # 2.5% of $20,000
            Decimal('15000.00') * Decimal('0.01')     # 1% of $15,000
        )
        assert opportunities['total_potential_savings'] == expected_savings

    @pytest.mark.asyncio
    async def test_break_even_analysis_for_discounts(self, mock_db_session):
        """Test break-even analysis for early payment discounts."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Test various discount scenarios
        scenarios = [
            {
                'invoice_amount': Decimal('10000.00'),
                'discount_percent': Decimal('2.00'),
                'discount_period_days': 10,
                'normal_terms_days': 30,
                'cost_of_capital': Decimal('0.08')
            },
            {
                'invoice_amount': Decimal('50000.00'),
                'discount_percent': Decimal('1.50'),
                'discount_period_days': 15,
                'normal_terms_days': 45,
                'cost_of_capital': Decimal('0.10')
            }
        ]

        for scenario in scenarios:
            analysis = await analytics.analyze_discount_break_even(**scenario)

            assert 'discount_amount' in analysis
            assert 'savings_from_early_payment' in analysis
            assert 'break_even_point' in analysis
            assert 'net_benefit' in analysis
            assert 'recommendation' in analysis

            # Verify break-even calculation
            discount_amount = scenario['invoice_amount'] * (scenario['discount_percent'] / Decimal('100'))
            daily_cost_of_capital = scenario['cost_of_capital'] / Decimal('365')
            days_saved = scenario['normal_terms_days'] - scenario['discount_period_days']
            expected_savings = scenario['invoice_amount'] * daily_cost_of_capital * days_saved

            assert analysis['discount_amount'] == discount_amount
            assert abs(analysis['savings_from_early_payment'] - expected_savings) < Decimal('0.01')

    @pytest.mark.asyncio
    async def test_cost_benefit_calculations(self, mock_db_session):
        """Test comprehensive cost-benefit analysis for discounts."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        cost_benefit = await analytics.analyze_discount_cost_benefit(
            total_discountable_amount=Decimal('100000.00'),
            average_discount_percent=Decimal('2.00'),
            average_payment_terms=45,
            cost_of_capital=Decimal('0.08'),
            administrative_cost_per_payment=Decimal('25.00')
        )

        assert 'total_discount_cost' in cost_benefit
        assert 'total_working_capital_savings' in cost_benefit
        assert 'net_financial_impact' in cost_benefit
        assert 'roi_percentage' in cost_benefit
        assert 'recommendation' in cost_benefit

        # Verify calculations
        expected_discount_cost = Decimal('100000.00') * Decimal('0.02')  # 2% discount
        assert cost_benefit['total_discount_cost'] == expected_discount_cost

        # Working capital savings from early payment
        days_saved = 45  # Assuming payment at discount period
        expected_savings = Decimal('100000.00') * Decimal('0.08') * (Decimal('45') / Decimal('365'))
        assert abs(cost_benefit['total_working_capital_savings'] - expected_savings) < Decimal('1.00')

    @pytest.mark.asyncio
    async def test_historical_discount_accuracy(self, mock_db_session):
        """Test analysis of historical discount utilization accuracy."""
        # Mock historical discount data
        historical_data = [
            {
                'period': '2024-01',
                'total_opportunities': Decimal('50000.00'),
                'utilized_discounts': Decimal('40000.00'),
                'actual_savings': Decimal('800.00'),
                'projected_savings': Decimal('1000.00')
            },
            {
                'period': '2024-02',
                'total_opportunities': Decimal('60000.00'),
                'utilized_discounts': Decimal('55000.00'),
                'actual_savings': Decimal('1100.00'),
                'projected_savings': Decimal('1200.00')
            }
        ]

        analytics = WorkingCapitalAnalytics(mock_db_session)

        with patch.object(analytics, 'get_historical_discount_data') as mock_history:
            mock_history.return_value = historical_data

            accuracy = await analytics.analyze_historical_discount_accuracy()

            assert 'utilization_rate' in accuracy
            assert 'prediction_accuracy' in accuracy
            assert 'trend_analysis' in accuracy
            assert 'improvement_recommendations' in accuracy

            # Verify utilization rate calculation
            total_opportunities = sum(data['total_opportunities'] for data in historical_data)
            total_utilized = sum(data['utilized_discounts'] for data in historical_data)
            expected_utilization = (total_utilized / total_opportunities) * 100
            assert accuracy['utilization_rate'] == expected_utilization

    @pytest.mark.asyncio
    async def test_discount_optimization_recommendations(self, mock_db_session, discount_opportunities):
        """Test generation of discount optimization recommendations."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = discount_opportunities
        mock_db_session.execute.return_value = mock_result

        analytics = WorkingCapitalAnalytics(mock_db_session)
        recommendations = await analytics.generate_discount_optimization_recommendations()

        assert 'priority_opportunities' in recommendations
        assert 'process_improvements' in recommendations
        assert 'financial_impact' in recommendations
        assert 'implementation_timeline' in recommendations

        # Should prioritize higher percentage discounts with longer remaining periods
        priority_list = recommendations['priority_opportunities']
        if len(priority_list) > 1:
            for i in range(len(priority_list) - 1):
                # Higher priority should have either higher discount or more days remaining
                current = priority_list[i]
                next_item = priority_list[i + 1]
                assert (
                    current['discount_percent'] >= next_item['discount_percent'] or
                    current['days_remaining'] >= next_item['days_remaining']
                )

    @pytest.mark.asyncio
    async def test_discount_risk_assessment(self, mock_db_session):
        """Test risk assessment for early payment discount programs."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        risk_assessment = await analytics.assess_discount_program_risks(
            annual_revenue=Decimal('10000000.00'),
            average_discount_percent=Decimal('2.00'),
            expected_utilization_rate=Decimal('0.7'),
            customer_concentration_risk=Decimal('0.3'),  # 30% of revenue from top customers
            cash_flow_volatility=Decimal('0.15')  # 15% monthly variance
        )

        assert 'overall_risk_level' in risk_assessment
        assert 'financial_risk' in risk_assessment
        assert 'operational_risk' in risk_assessment
        assert 'mitigation_strategies' in risk_assessment
        assert 'risk_tolerance_check' in risk_assessment

        # Verify risk calculations
        expected_annual_discount_cost = Decimal('10000000.00') * Decimal('0.02') * Decimal('0.7')
        assert risk_assessment['financial_risk']['annual_cost'] == expected_annual_discount_cost


class TestWorkingCapitalScoring:
    """Test cases for working capital optimization scoring system."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_overall_working_capital_score(self, mock_db_session):
        """Test calculation of overall working capital optimization score."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock component scores
        with patch.object(analytics, 'calculate_collection_efficiency_score') as mock_collection, \
             patch.object(analytics, 'calculate_payment_optimization_score') as mock_payment, \
             patch.object(analytics, 'calculate_discount_utilization_score') as mock_discount:

            mock_collection.return_value = {'score': 85.0, 'weight': 0.4}
            mock_payment.return_value = {'score': 75.0, 'weight': 0.35}
            mock_discount.return_value = {'score': 90.0, 'weight': 0.25}

            overall_score = await analytics.calculate_overall_working_capital_score()

            assert 'total_score' in overall_score
            assert 'component_scores' in overall_score
            assert 'benchmark_comparison' in overall_score
            assert 'improvement_areas' in overall_score

            # Verify weighted average calculation
            expected_score = (85.0 * 0.4) + (75.0 * 0.35) + (90.0 * 0.25)
            assert overall_score['total_score'] == expected_score

    @pytest.mark.asyncio
    async def test_collection_efficiency_scoring(self, mock_db_session):
        """Test collection efficiency component scoring."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock collection metrics
        collection_metrics = {
            'dso': 35.0,  # Days Sales Outstanding
            'collection_rate': 0.92,  # 92% collection rate
            'overdue_percentage': 0.08,  # 8% overdue
            'cei': 85.0  # Collection Effectiveness Index
        }

        score = await analytics.calculate_collection_efficiency_score(collection_metrics)

        assert 'score' in score
        assert 'sub_scores' in score
        assert 'trend_analysis' in score
        assert 'industry_benchmark' in score

        # Verify score is within expected range
        assert 0 <= score['score'] <= 100

        # Good metrics should result in higher scores
        assert score['score'] > 70  # Should be good with these metrics

    @pytest.mark.asyncio
    async def test_payment_optimization_scoring(self, mock_db_session):
        """Test payment optimization component scoring."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock payment optimization metrics
        payment_metrics = {
            'early_payment_utilization': 0.75,  # 75% utilization
            'payment_timing_efficiency': 0.80,  # 80% efficiency
            'working_capital_turnover': 6.5,  # 6.5x annual turnover
            'cash_conversion_cycle': 25.0  # 25 days
        }

        score = await analytics.calculate_payment_optimization_score(payment_metrics)

        assert 'score' in score
        assert 'sub_scores' in score
        assert 'optimization_opportunities' in score
        assert 'potential_improvement' in score

        # Verify score calculation
        assert 0 <= score['score'] <= 100
        assert len(score['sub_scores']) == 4  # One for each metric

    @pytest.mark.asyncio
    async def test_discount_utilization_scoring(self, mock_db_session):
        """Test early payment discount utilization scoring."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock discount utilization metrics
        discount_metrics = {
            'utilization_rate': 0.85,  # 85% of available discounts used
            'roi_achieved': 1.25,  # 125% ROI on discount program
            'savings_captured': 0.90,  # 90% of potential savings captured
            'accuracy_rate': 0.95  # 95% accuracy in discount predictions
        }

        score = await analytics.calculate_discount_utilization_score(discount_metrics)

        assert 'score' in score
        assert 'sub_scores' in score
        assert 'savings_analysis' in score
        assert 'efficiency_metrics' in score

        # High utilization should result in high score
        assert score['score'] > 80

    @pytest.mark.asyncio
    async def test_benchmark_comparison(self, mock_db_session):
        """Test industry benchmark comparison for working capital metrics."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock company metrics and industry benchmarks
        company_metrics = {
            'dso': 35.0,
            'cash_conversion_cycle': 25.0,
            'working_capital_turnover': 6.5
        }

        industry_benchmarks = {
            'dso': {'median': 45.0, 'top_quartile': 30.0, 'bottom_quartile': 60.0},
            'cash_conversion_cycle': {'median': 35.0, 'top_quartile': 20.0, 'bottom_quartile': 50.0},
            'working_capital_turnover': {'median': 5.0, 'top_quartile': 8.0, 'bottom_quartile': 3.0}
        }

        comparison = await analytics.compare_with_industry_benchmarks(company_metrics, industry_benchmarks)

        assert 'overall_percentile' in comparison
        assert 'metric_comparisons' in comparison
        assert 'competitive_positioning' in comparison
        assert 'improvement_targets' in comparison

        # Should perform well compared to industry
        assert comparison['overall_percentile'] > 60

    @pytest.mark.asyncio
    async def test_score_trend_analysis(self, mock_db_session):
        """Test trend analysis of working capital scores over time."""
        # Mock historical score data
        historical_scores = [
            {'date': '2024-01', 'total_score': 72.0, 'collection_score': 70.0, 'payment_score': 75.0, 'discount_score': 71.0},
            {'date': '2024-02', 'total_score': 75.0, 'collection_score': 73.0, 'payment_score': 77.0, 'discount_score': 75.0},
            {'date': '2024-03', 'total_score': 78.0, 'collection_score': 76.0, 'payment_score': 80.0, 'discount_score': 78.0},
            {'date': '2024-04', 'total_score': 82.0, 'collection_score': 80.0, 'payment_score': 83.0, 'discount_score': 83.0}
        ]

        analytics = WorkingCapitalAnalytics(mock_db_session)

        with patch.object(analytics, 'get_historical_scores') as mock_history:
            mock_history.return_value = historical_scores

            trends = await analytics.analyze_score_trends()

            assert 'overall_trend' in trends
            assert 'component_trends' in trends
            assert 'improvement_rate' in trends
            assert 'forecast' in trends

            # Should show improving trend
            assert trends['overall_trend']['direction'] == 'improving'
            assert trends['improvement_rate'] > 0

    @pytest.mark.asyncio
    async def test_actionable_recommendations_generation(self, mock_db_session):
        """Test generation of actionable recommendations based on scores."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock current scores and metrics
        current_state = {
            'total_score': 75.0,
            'component_scores': {
                'collection_efficiency': {'score': 70.0, 'issues': ['high_dso', 'overdue_rate']},
                'payment_optimization': {'score': 80.0, 'issues': ['missed_discounts']},
                'discount_utilization': {'score': 75.0, 'issues': ['low_utilization']}
            },
            'key_metrics': {
                'dso': 45.0,
                'overdue_rate': 0.15,
                'discount_utilization': 0.65,
                'working_capital_turnover': 5.5
            }
        }

        recommendations = await analytics.generate_actionable_recommendations(current_state)

        assert 'priority_actions' in recommendations
        assert 'quick_wins' in recommendations
        assert 'long_term_improvements' in recommendations
        assert 'expected_impact' in recommendations
        assert 'implementation_plan' in recommendations

        # Should have recommendations for each identified issue
        assert len(recommendations['priority_actions']) >= 2  # At least one priority action

        # Quick wins should be easy to implement
        for quick_win in recommendations['quick_wins']:
            assert 'effort' in quick_win
            assert 'impact' in quick_win
            assert quick_win['effort'] == 'low'  # Quick wins should be low effort

    @pytest.mark.asyncio
    async def test_working_capital_kpi_dashboard(self, mock_db_session):
        """Test comprehensive KPI dashboard for working capital."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Mock all required data
        with patch.object(analytics, 'calculate_overall_working_capital_score') as mock_overall, \
             patch.object(analytics, 'calculate_cash_flow_projection') as mock_cash_flow, \
             patch.object(analytics, 'detect_discount_opportunities') as mock_discounts, \
             patch.object(analytics, 'analyze_aging_buckets') as mock_aging:

            mock_overall.return_value = {'total_score': 82.0, 'component_scores': {}}
            mock_cash_flow.return_value = {'total_projected': Decimal('100000.00'), 'confidence_score': 85.0}
            mock_discounts.return_value = {'total_opportunities': 5, 'total_potential_savings': Decimal('2500.00')}
            mock_aging.return_value = {'total_outstanding': Decimal('50000.00'), 'risk_assessment': 'medium'}

            dashboard = await analytics.generate_working_capital_dashboard()

            assert 'overall_score' in dashboard
            assert 'cash_flow_metrics' in dashboard
            assert 'collection_metrics' in dashboard
            assert 'discount_opportunities' in dashboard
            assert 'risk_indicators' in dashboard
            assert 'trend_data' in dashboard
            assert 'alerts' in dashboard

            # Dashboard should provide comprehensive view
            assert len(dashboard) >= 6  # At least 6 major sections

    @pytest.mark.asyncio
    async def test_performance_validation(self, mock_db_session):
        """Test performance validation of analytics calculations."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Test calculation performance
        import time

        start_time = time.time()

        # Simulate multiple calculations
        with patch.object(analytics, 'get_invoice_data') as mock_data:
            mock_data.return_value = [{'id': uuid.uuid4(), 'amount': Decimal('1000.00')} for _ in range(1000)]

            # Run multiple calculations
            await analytics.calculate_cash_flow_projection(days=90)
            await analytics.detect_discount_opportunities()
            await analytics.analyze_aging_buckets()
            await analytics.calculate_overall_working_capital_score()

        end_time = time.time()
        calculation_time = end_time - start_time

        # Performance requirement: all calculations should complete within 2 seconds
        assert calculation_time < 2.0, f"Calculations took {calculation_time:.2f} seconds, expected < 2.0 seconds"

    @pytest.mark.asyncio
    async def test_edge_cases_and_error_handling(self, mock_db_session):
        """Test edge cases and error handling in analytics calculations."""
        analytics = WorkingCapitalAnalytics(mock_db_session)

        # Test with no data
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Should handle empty data gracefully
        cash_flow = await analytics.calculate_cash_flow_projection(days=30)
        assert cash_flow['total_projected'] == Decimal('0.00')

        discounts = await analytics.detect_discount_opportunities()
        assert discounts['total_opportunities'] == 0

        aging = await analytics.analyze_aging_buckets()
        assert aging['total_outstanding'] == Decimal('0.00')

        # Test with invalid data
        invalid_invoices = [
            {'id': uuid.uuid4(), 'total_amount': Decimal('-1000.00')},  # Negative amount
            {'id': uuid.uuid4(), 'outstanding_amount': None},  # None amount
        ]

        mock_result.scalars.return_value.all.return_value = invalid_invoices

        # Should handle invalid data gracefully
        with pytest.raises((ValueError, TypeError)):
            await analytics.calculate_cash_flow_projection(days=30)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])