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
            cost_data={'evidence': context.prompt_metadata} if context.prompt_metadata else {},
            confidence=None,
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
        
        import math
        totals = {}
        for service, rows in costs.items():
            values = [row.get('blended_cost') for row in rows if isinstance(row, dict)]
            valid = bool(rows) and len(values) == len(rows) and all(
                type(value) in (int, float) and math.isfinite(value) for value in values)
            valid = valid and all(row.get('currency') == 'USD' for row in rows)
            total = sum(values) if valid else None
            totals[service] = total if total is not None and math.isfinite(total) else None
        known = [value for value in totals.values() if value is not None]
        subtotal = sum(known) if known else None
        if subtotal is not None and not math.isfinite(subtotal): subtotal = None
        all_available = len(known) == len(totals) and subtotal is not None
        ordered = sorted(totals.items(), key=lambda pair: (pair[1] is not None, pair[1] if pair[1] is not None else 0), reverse=True)
        table = ['## Observed Cost Context', '',
            'USD BlendedCost across returned rows; date and invoice completeness remain unverified.', '',
            '| Service | Observed amount | Share of returned subtotal |',
            '|---------|----------------|----------------------------|']
        for service, value in ordered[:10]:
            label = str(service).replace('|', '/').replace('\n', ' ').replace('\r', ' ')
            amount = f'${value:.2f}' if value is not None else 'Unavailable'
            share = f'{value/subtotal*100:.1f}%' if value is not None and all_available and subtotal > 0 else 'Unavailable'
            table.append(f'| {label} | {amount} | {share} |')
        if len(ordered) > 10:
            table.extend(['', f'{len(ordered)-10} additional returned services are omitted from this table.'])
        if all_available:
            table.extend(['', f'Observed subtotal across all {len(totals)} returned services: ${subtotal:.2f}. This is not a verified account invoice total.'])
        else:
            partial = f'${subtotal:.2f}' if subtotal is not None else 'Unavailable'
            table.extend(['', f'Known observed subtotal: {partial}. {len(totals)-len(known)} service amounts unavailable; full returned subtotal and shares remain unavailable.'])
        return '\n'.join(table)

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
