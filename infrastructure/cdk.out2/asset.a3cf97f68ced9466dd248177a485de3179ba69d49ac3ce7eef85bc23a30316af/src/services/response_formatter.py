"""
Response Formatter for AI advisor responses.

This module formats AI responses for display:
1. Markdown formatting
2. Cost comparison tables
3. Number highlighting
4. Response truncation
"""

from typing import Dict, Any, List
import logging

from ..utils.types import CostContext, AdvisorResponse

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Format AI responses for display."""
    
    def __init__(self):
        """Initialize response formatter."""
        logger.info("ResponseFormatter initialized")
    
    def format_response(
        self,
        raw_response: str,
        context: CostContext
    ) -> AdvisorResponse:
        """
        Format response with markdown, tables, and highlights.
        
        Args:
            raw_response: Raw AI response text
            context: Cost context used for response
            
        Returns:
            Formatted AdvisorResponse
        """
        logger.debug("Formatting response")
        
        # Highlight numbers
        formatted_text = self.highlight_numbers(raw_response)
        
        # Truncate if too long
        formatted_text = self.truncate_response(formatted_text, max_words=500)
        
        # Add cost table if context has multiple services
        if context.historical_costs and len(context.historical_costs) > 1:
            cost_table = self.create_cost_table(context.historical_costs)
            formatted_text += f"\n\n{cost_table}"
        
        # Create AdvisorResponse (recommendations extracted by Bedrock client)
        return AdvisorResponse(
            response_text=formatted_text,
            recommendations=[],  # Populated by Bedrock client
            cost_data={},  # Populated by Bedrock client
            confidence=0.8,
            cached=False
        )
    
    def create_cost_table(self, costs: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Create markdown table for cost comparisons.
        
        Args:
            costs: Dictionary mapping service to cost data points
            
        Returns:
            Markdown table string
        """
        if not costs:
            return ""
        
        # Calculate totals for each service
        service_totals = {}
        for service, cost_list in costs.items():
            total = sum(c.get('blended_cost', 0) for c in cost_list)
            service_totals[service] = total
        
        # Sort by cost (highest first)
        sorted_services = sorted(
            service_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Build table
        table_lines = [
            "## Cost Breakdown",
            "",
            "| Service | Total Cost | Percentage |",
            "|---------|------------|------------|"
        ]
        
        total_cost = sum(service_totals.values())
        
        for service, cost in sorted_services[:10]:  # Top 10 services
            percentage = (cost / total_cost * 100) if total_cost > 0 else 0
            table_lines.append(
                f"| {service} | ${cost:.2f} | {percentage:.1f}% |"
            )
        
        # Add total row
        table_lines.append(f"| **Total** | **${total_cost:.2f}** | **100%** |")
        
        return "\n".join(table_lines)
    
    def highlight_numbers(self, text: str) -> str:
        """
        Highlight costs and percentages in text.
        
        Args:
            text: Response text
            
        Returns:
            Text with highlighted numbers
        """
        import re
        
        # Highlight dollar amounts with bold
        text = re.sub(
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'**$\1**',
            text
        )
        
        # Highlight percentages with bold
        text = re.sub(
            r'(\d+(?:\.\d+)?)\s*%',
            r'**\1%**',
            text
        )
        
        return text
    
    def truncate_response(self, text: str, max_words: int = 500) -> str:
        """
        Truncate long responses while preserving meaning.
        
        Args:
            text: Response text
            max_words: Maximum word count
            
        Returns:
            Truncated text
        """
        words = text.split()
        
        if len(words) <= max_words:
            return text
        
        # Truncate at sentence boundary near max_words
        truncated_words = words[:max_words]
        truncated_text = ' '.join(truncated_words)
        
        # Find last sentence boundary
        last_period = truncated_text.rfind('.')
        if last_period > len(truncated_text) * 0.8:  # If period is in last 20%
            truncated_text = truncated_text[:last_period + 1]
        
        truncated_text += "\n\n*[Response truncated for brevity]*"
        
        logger.debug(f"Truncated response from {len(words)} to ~{max_words} words")
        return truncated_text
