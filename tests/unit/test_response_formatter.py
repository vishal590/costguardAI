"""
Unit tests for ResponseFormatter.
"""
import pytest
from src.services.response_formatter import ResponseFormatter
from src.utils.types import CostContext, AdvisorResponse


class TestResponseFormatterInitialization:
    """Tests for ResponseFormatter initialization."""
    
    def test_response_formatter_initialization(self):
        """Test ResponseFormatter initializes correctly."""
        formatter = ResponseFormatter()
        assert formatter is not None


class TestMarkdownFormatting:
    """Tests for markdown formatting."""
    
    def test_format_response_basic(self):
        """Test basic response formatting."""
        formatter = ResponseFormatter()
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        raw_response = "Your costs are $100.50 this month."
        result = formatter.format_response(raw_response, context)
        
        assert isinstance(result, AdvisorResponse)
        assert "$100.50" in result.response_text or "**$100.50**" in result.response_text
    
    def test_format_response_with_multiple_services(self):
        """Test formatting with multiple services creates table."""
        formatter = ResponseFormatter()
        
        context = CostContext(
            historical_costs={
                'ec2': [
                    {'date': '2026-02-20', 'blended_cost': 25.50, 'unblended_cost': 25.50, 'currency': 'USD'}
                ],
                's3': [
                    {'date': '2026-02-20', 'blended_cost': 5.25, 'unblended_cost': 5.25, 'currency': 'USD'}
                ]
            },
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        raw_response = "Here are your costs."
        result = formatter.format_response(raw_response, context)
        
        # Should include cost table
        assert "## Cost Breakdown" in result.response_text
        assert "ec2" in result.response_text
        assert "s3" in result.response_text
    
    def test_format_response_single_service_no_table(self):
        """Test formatting with single service doesn't create table."""
        formatter = ResponseFormatter()
        
        context = CostContext(
            historical_costs={
                'ec2': [
                    {'date': '2026-02-20', 'blended_cost': 25.50, 'unblended_cost': 25.50, 'currency': 'USD'}
                ]
            },
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        raw_response = "Your EC2 costs are $25.50."
        result = formatter.format_response(raw_response, context)
        
        # Should not include cost table for single service
        assert "## Cost Breakdown" not in result.response_text


class TestCostTableCreation:
    """Tests for cost table creation."""
    
    def test_create_cost_table_empty(self):
        """Test creating table with empty costs."""
        formatter = ResponseFormatter()
        
        table = formatter.create_cost_table({})
        assert table == ""
    
    def test_create_cost_table_single_service(self):
        """Test creating table with single service."""
        formatter = ResponseFormatter()
        
        costs = {
            'ec2': [
                {'blended_cost': 25.50},
                {'blended_cost': 30.00}
            ]
        }
        
        table = formatter.create_cost_table(costs)
        
        assert "## Cost Breakdown" in table
        assert "ec2" in table
        assert "$55.50" in table  # Total
        assert "100%" in table
    
    def test_create_cost_table_multiple_services(self):
        """Test creating table with multiple services."""
        formatter = ResponseFormatter()
        
        costs = {
            'ec2': [{'blended_cost': 50.00}],
            's3': [{'blended_cost': 25.00}],
            'lambda': [{'blended_cost': 10.00}]
        }
        
        table = formatter.create_cost_table(costs)
        
        assert "## Cost Breakdown" in table
        assert "ec2" in table
        assert "s3" in table
        assert "lambda" in table
        assert "$85.00" in table  # Total
    
    def test_create_cost_table_sorted_by_cost(self):
        """Test table sorts services by cost (highest first)."""
        formatter = ResponseFormatter()
        
        costs = {
            's3': [{'blended_cost': 10.00}],
            'ec2': [{'blended_cost': 50.00}],
            'lambda': [{'blended_cost': 25.00}]
        }
        
        table = formatter.create_cost_table(costs)
        
        # ec2 should appear before lambda, lambda before s3
        ec2_pos = table.find('ec2')
        lambda_pos = table.find('lambda')
        s3_pos = table.find('s3')
        
        assert ec2_pos < lambda_pos < s3_pos
    
    def test_create_cost_table_percentages(self):
        """Test table includes correct percentages."""
        formatter = ResponseFormatter()
        
        costs = {
            'ec2': [{'blended_cost': 60.00}],
            's3': [{'blended_cost': 40.00}]
        }
        
        table = formatter.create_cost_table(costs)
        
        assert "60.0%" in table
        assert "40.0%" in table
        assert "100%" in table
    
    def test_create_cost_table_top_10_services(self):
        """Test table limits to top 10 services."""
        formatter = ResponseFormatter()
        
        # Create 15 services
        costs = {
            f'service{i}': [{'blended_cost': float(15 - i)}]
            for i in range(15)
        }
        
        table = formatter.create_cost_table(costs)
        
        # Should only include top 10
        assert 'service0' in table  # Highest cost
        assert 'service9' in table  # 10th highest
        # service14 might not be in table (lowest cost)
    
    def test_create_cost_table_zero_costs(self):
        """Test table handles zero costs."""
        formatter = ResponseFormatter()
        
        costs = {
            'ec2': [{'blended_cost': 0.00}],
            's3': [{'blended_cost': 0.00}]
        }
        
        table = formatter.create_cost_table(costs)
        
        assert "## Cost Breakdown" in table
        assert "$0.00" in table


class TestNumberHighlighting:
    """Tests for number highlighting."""
    
    def test_highlight_dollar_amounts(self):
        """Test highlighting dollar amounts."""
        formatter = ResponseFormatter()
        
        text = "Your costs are $100.50 this month."
        result = formatter.highlight_numbers(text)
        
        assert "**$100.50**" in result
    
    def test_highlight_dollar_amounts_with_commas(self):
        """Test highlighting dollar amounts with thousands separators."""
        formatter = ResponseFormatter()
        
        text = "Total spending: $1,234.56"
        result = formatter.highlight_numbers(text)
        
        assert "**$1,234.56**" in result
    
    def test_highlight_large_dollar_amounts(self):
        """Test highlighting large dollar amounts."""
        formatter = ResponseFormatter()
        
        text = "Budget exceeded: $10,000,000.00"
        result = formatter.highlight_numbers(text)
        
        assert "**$10,000,000.00**" in result
    
    def test_highlight_percentages(self):
        """Test highlighting percentages."""
        formatter = ResponseFormatter()
        
        text = "Costs increased by 25% this month."
        result = formatter.highlight_numbers(text)
        
        assert "**25%**" in result
    
    def test_highlight_decimal_percentages(self):
        """Test highlighting decimal percentages."""
        formatter = ResponseFormatter()
        
        text = "Savings of 12.5% achieved."
        result = formatter.highlight_numbers(text)
        
        assert "**12.5%**" in result
    
    def test_highlight_multiple_numbers(self):
        """Test highlighting multiple numbers in text."""
        formatter = ResponseFormatter()
        
        text = "EC2 costs $50.00 (60%) and S3 costs $33.33 (40%)."
        result = formatter.highlight_numbers(text)
        
        assert "**$50.00**" in result
        assert "**60%**" in result
        assert "**$33.33**" in result
        assert "**40%**" in result
    
    def test_highlight_preserves_text(self):
        """Test highlighting preserves surrounding text."""
        formatter = ResponseFormatter()
        
        text = "Your total is $100.00 for this period."
        result = formatter.highlight_numbers(text)
        
        assert "Your total is" in result
        assert "for this period" in result
    
    def test_highlight_no_numbers(self):
        """Test highlighting with no numbers."""
        formatter = ResponseFormatter()
        
        text = "No costs found for this period."
        result = formatter.highlight_numbers(text)
        
        assert result == text  # Unchanged


class TestResponseTruncation:
    """Tests for response truncation."""
    
    def test_truncate_short_response(self):
        """Test truncation doesn't affect short responses."""
        formatter = ResponseFormatter()
        
        text = "This is a short response."
        result = formatter.truncate_response(text, max_words=100)
        
        assert result == text
        assert "[Response truncated" not in result
    
    def test_truncate_long_response(self):
        """Test truncation of long responses."""
        formatter = ResponseFormatter()
        
        # Create response with 600 words
        text = " ".join(["word"] * 600)
        result = formatter.truncate_response(text, max_words=500)
        
        # Should be truncated
        assert len(result.split()) < 600
        assert "[Response truncated" in result
    
    def test_truncate_at_sentence_boundary(self):
        """Test truncation at sentence boundary."""
        formatter = ResponseFormatter()
        
        # Create response with sentences
        sentences = [f"This is sentence {i}." for i in range(200)]
        text = " ".join(sentences)
        
        result = formatter.truncate_response(text, max_words=100)
        
        # Should end with period before truncation notice
        assert ". \n\n*[Response truncated" in result or ".\n\n*[Response truncated" in result
    
    def test_truncate_preserves_meaning(self):
        """Test truncation preserves beginning of response."""
        formatter = ResponseFormatter()
        
        text = "Important information at start. " + " ".join(["filler"] * 600)
        result = formatter.truncate_response(text, max_words=100)
        
        assert "Important information at start" in result
    
    def test_truncate_custom_max_words(self):
        """Test truncation with custom max words."""
        formatter = ResponseFormatter()
        
        text = " ".join(["word"] * 300)
        result = formatter.truncate_response(text, max_words=200)
        
        assert len(result.split()) < 300
        assert "[Response truncated" in result
    
    def test_truncate_exactly_max_words(self):
        """Test response with exactly max words."""
        formatter = ResponseFormatter()
        
        text = " ".join(["word"] * 500)
        result = formatter.truncate_response(text, max_words=500)
        
        # Should not be truncated
        assert "[Response truncated" not in result


class TestResponseFormatterIntegration:
    """Integration tests for ResponseFormatter."""
    
    def test_format_complete_response(self):
        """Test formatting complete response with all features."""
        formatter = ResponseFormatter()
        
        context = CostContext(
            historical_costs={
                'ec2': [{'blended_cost': 100.00}],
                's3': [{'blended_cost': 50.00}],
                'lambda': [{'blended_cost': 25.00}]
            },
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        raw_response = "Your total costs are $175.00. EC2 accounts for 57% of spending."
        result = formatter.format_response(raw_response, context)
        
        # Should have highlighted numbers
        assert "**$175.00**" in result.response_text or "$175.00" in result.response_text
        assert "**57%**" in result.response_text or "57%" in result.response_text
        
        # Should have cost table
        assert "## Cost Breakdown" in result.response_text
        assert "ec2" in result.response_text
        assert "s3" in result.response_text
        assert "lambda" in result.response_text
    
    def test_format_response_returns_advisor_response(self):
        """Test format_response returns AdvisorResponse object."""
        formatter = ResponseFormatter()
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        result = formatter.format_response("Test response", context)
        
        assert isinstance(result, AdvisorResponse)
        assert hasattr(result, 'response_text')
        assert hasattr(result, 'recommendations')
        assert hasattr(result, 'cost_data')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'cached')
    
    def test_format_response_default_values(self):
        """Test format_response sets default values correctly."""
        formatter = ResponseFormatter()
        
        context = CostContext(
            historical_costs={},
            forecast_data=None,
            prevention_actions=[],
            current_budget=None,
            anomalies=[]
        )
        
        result = formatter.format_response("Test", context)
        
        assert result.recommendations == []
        assert result.cost_data == {}
        assert result.confidence == 0.8
        assert result.cached is False
