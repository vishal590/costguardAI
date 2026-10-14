"""
Context Manager for retrieving cost data context.

This module retrieves relevant cost data for queries:
1. Historical cost data from Cost Explorer
2. Forecast data from Phase 2
3. Prevention actions from Phase 3
4. Budget status
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from ..utils.types import QueryIntent, CostContext, BudgetStatus

logger = logging.getLogger(__name__)


class ContextManager:
    """Retrieve relevant cost data for queries."""
    
    def __init__(
        self,
        cost_explorer_client=None,
        dynamodb_client=None,
        budgets_client=None,
        sts_client=None
    ):
        """
        Initialize context manager.
        
        Args:
            cost_explorer_client: AWS Cost Explorer client
            dynamodb_client: DynamoDB client for Phase 2/3 data
            budgets_client: AWS Budgets client
            sts_client: AWS STS client (optional, defaults to boto3.client('sts'))
        """
        self.cost_explorer_client = cost_explorer_client
        self.dynamodb_client = dynamodb_client
        self.budgets_client = budgets_client
        self.sts_client = sts_client
        
        logger.info("ContextManager initialized")
    
    def get_cost_context(self, intent: QueryIntent) -> CostContext:
        """
        Retrieve relevant cost data based on query intent.
        
        Args:
            intent: Parsed query intent
            
        Returns:
            CostContext with relevant data
        """
        logger.info(f"Retrieving context for intent: {intent.intent_type}")
        
        # Retrieve historical costs
        historical_costs = self.get_historical_costs(
            services=intent.services,
            start_date=intent.time_range[0],
            end_date=intent.time_range[1]
        )
        
        # Retrieve forecast data if relevant
        forecast_data = None
        if intent.intent_type in ['forecast', 'trend_analysis']:
            forecast_data = self.get_forecast_data(
                services=intent.services,
                days=30
            )
        
        # Retrieve prevention actions if relevant
        prevention_actions = []
        prevention_quality = {'status': 'not_requested'}
        if intent.intent_type in ['prevention', 'optimization']:
            prevention_actions = self.get_prevention_actions(
                start_date=intent.time_range[0],
                end_date=intent.time_range[1], report=prevention_quality
            )
        
        # Retrieve budget status
        current_budget = self._get_budget_status()
        
        # Detect anomalies in cost data
        anomaly_quality = {}
        anomalies = self._detect_anomalies(historical_costs, report=anomaly_quality)
        
        return CostContext(
            historical_costs=historical_costs,
            forecast_data=forecast_data,
            prevention_actions=prevention_actions,
            current_budget=current_budget,
            anomalies=anomalies,
            data_quality={
                'historical_status': 'observed' if historical_costs else 'unavailable_or_no_observations',
                'historical_cost_metric': 'BlendedCost',
                'estimated_dates': sorted({point['date'] for points in historical_costs.values() for point in points if point.get('is_estimated') is True}),
                'unknown_estimate_dates': sorted({point['date'] for points in historical_costs.values() for point in points if point.get('is_estimated') is None}),
                'observed_dates': sorted({point['date'] for points in historical_costs.values() for point in points}),
                'requested_period': {'start': intent.time_range[0].isoformat(), 'end_exclusive': intent.time_range[1].isoformat()},
                'budget_status': 'available' if current_budget else 'unavailable_or_ambiguous',
                'forecast_status': 'available' if forecast_data else 'unavailable_or_not_requested',
                'prevention_status': prevention_quality['status'], 'prevention_observations': prevention_quality,
                'anomaly_observations': anomaly_quality,
                'anomaly_metric': 'BlendedCost', 'anomaly_method': 'descriptive_two_sample_standard_deviations',
                'anomaly_scope': 'supplied_valid_USD_rows_only_not_calibrated_or_complete_dates',
                'anomaly_empty_rule': 'No returned flag does not establish normal spending or complete analysis',
                'missing_data_rule': 'Missing or empty context never establishes zero spending, no actions, or no risk.'
            }
        )
    
    def get_historical_costs(
        self,
        services: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch historical cost data from Cost Explorer.
        
        Args:
            services: List of AWS service identifiers
            start_date: Start date for cost data
            end_date: End date for cost data
            
        Returns:
            Dictionary mapping service to list of cost data points
        """
        if not self.cost_explorer_client:
            return {}
        try:
            from .cost_explorer import CostExplorerParams, fetch_cost_data
            from ..utils.helpers import cost_explorer_service_to_short
            selected = {cost_explorer_service_to_short(name) for name in services}
            records = fetch_cost_data(CostExplorerParams(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), 'DAILY'), client=self.cost_explorer_client)
            costs_by_service = {}
            for record in records:
                if selected and cost_explorer_service_to_short(record.service) not in selected: continue
                costs_by_service.setdefault(record.service, []).append({
                    'date': record.date, 'blended_cost': record.blended_cost,
                    'unblended_cost': record.unblended_cost, 'currency': record.currency, 'is_estimated': record.is_estimated
                })
            return costs_by_service
        except Exception as error:
            logger.warning('Advisor historical cost context unavailable: %s', type(error).__name__)
            return {}

    def get_forecast_data(
        self,
        services: List[str],
        days: int = 30
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """
        Fetch forecast data from Phase 2 DynamoDB table.
        
        Args:
            services: List of AWS service identifiers
            days: Number of days to forecast
            
        Returns:
            Dictionary mapping service to list of forecast points
        """
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot fetch forecasts")
            return None
        
        try:
            import os
            import math
            from .forecast_cache import ForecastCacheManager
            cache = ForecastCacheManager(self.dynamodb_client, os.environ.get('FORECAST_CACHE_TABLE', 'costguard-forecast-cache'))
            forecasts_by_service = {}
            from ..utils.helpers import cost_explorer_service_to_short
            for requested in services or [None]:
                service = cost_explorer_service_to_short(requested) if requested else None
                cached = cache.get_cached_forecast(service, days, 'daily')
                if not cached: continue
                metadata = cached.get('metadata', {})
                points = cached.get('forecast_data')
                if not isinstance(points, list) or len(points) != days: continue
                clean = []
                for point in points:
                    values = [point.get(name) for name in ('predicted_cost', 'confidence_lower', 'confidence_upper')]
                    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
                        clean = []; break
                    if not values[1] <= values[0] <= values[2]: clean = []; break
                    clean.append({**point, 'range_method': metadata.get('range_method', 'unspecified')})
                if clean: forecasts_by_service[service or 'total'] = clean

            logger.debug(f"Retrieved forecasts for {len(forecasts_by_service)} services")
            return forecasts_by_service if forecasts_by_service else None
            
        except Exception as e:
            logger.error(f"Error retrieving forecast data: {e}")
            return None
    
    def get_prevention_actions(self, start_date: datetime, end_date: datetime,
                               report: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Bounded legacy audit selection; rows and estimates do not verify execution/savings."""
        import os
        import math
        from datetime import UTC
        from boto3.dynamodb.types import TypeDeserializer
        from .time_values import parse_utc_timestamp
        report = report if report is not None else {}
        report.update({'status': 'reading', 'page_limit': 10, 'page_size': 100, 'returned_row_limit': 100,
            'pages_read': 0, 'examined_rows': 0, 'invalid_rows': 0, 'omitted_matching_rows': 0,
            'has_more_stored_rows': None, 'returned_rows': None,
            'selection_scope': 'bounded_scan_selection_not_latest_or_complete_action_history',
            'execution_verified': False, 'monetary_savings_verified': False})
        if not self.dynamodb_client:
            report['status'] = 'not_configured'; return []
        actions = []
        try:
            first = start_date.replace(tzinfo=UTC) if start_date.tzinfo is None else start_date.astimezone(UTC)
            last = end_date.replace(tzinfo=UTC) if end_date.tzinfo is None else end_date.astimezone(UTC)
            if first >= last: raise ValueError('Use a nonempty exclusive-end action window')
            deserialize = TypeDeserializer()
            request = {'TableName': os.environ.get('PREVENTION_AUDIT_TABLE', 'costguard-prevention-audit'), 'Limit': 100}
            seen = set()
            for _ in range(10):
                response = self.dynamodb_client.scan(**request)
                report['pages_read'] += 1
                for raw in response.get('Items', []):
                    report['examined_rows'] += 1
                    try:
                        item = {key: deserialize.deserialize(value) for key, value in raw.items()}
                        moment = parse_utc_timestamp(item.get('timestamp'))
                        if not first <= moment < last: continue
                        event_type = str(item.get('event_type', ''))
                        if event_type == 'pre_action_state' or event_type.startswith('rollback'): continue
                        if not isinstance(item.get('resource_id'), str) or not isinstance(item.get('action'), str):
                            raise ValueError('Unidentified action record')
                        estimate = item.get('estimated_savings')
                        try:
                            estimate = float(estimate) if estimate is not None and not isinstance(estimate, bool) else None
                            if estimate is not None and (not math.isfinite(estimate) or estimate < 0): estimate = None
                        except (ValueError, TypeError, OverflowError): estimate = None
                        if len(actions) >= 100:
                            report['omitted_matching_rows'] += 1; continue
                        actions.append({'resource_id': item['resource_id'][:256], 'action': item['action'][:128],
                            'timestamp': moment.isoformat(), 'estimated_savings': estimate,
                            'success': item.get('success') if isinstance(item.get('success'), bool) else None,
                            'execution_verified': False, 'monetary_savings_verified': False})
                    except (ValueError, TypeError, KeyError):
                        report['invalid_rows'] += 1
                cursor = response.get('LastEvaluatedKey')
                report['has_more_stored_rows'] = bool(cursor)
                if not cursor: break
                fingerprint = str(sorted(cursor.items()))
                if fingerprint in seen: raise ValueError('Repeated audit scan cursor')
                seen.add(fingerprint)
                request['ExclusiveStartKey'] = cursor
            report['returned_rows'] = len(actions)
            partial = report['has_more_stored_rows'] or report['omitted_matching_rows'] or report['invalid_rows']
            report['status'] = 'bounded_or_partial' if partial else 'observed_scan_selection'
            return sorted(actions, key=lambda item: item['timestamp'])
        except Exception as error:
            report.update({'status': 'unavailable', 'returned_rows': None, 'has_more_stored_rows': None})
            logger.warning('Advisor prevention context unavailable: %s', type(error).__name__)
            return []

    def _detect_anomalies(self, historical_costs: Dict[str, List[Dict[str, Any]]],
                          report: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Describe supplied USD BlendedCost rows; no calibrated anomaly probability."""
        import math
        import statistics
        report = report if report is not None else {}
        report.update({'considered_services': len(historical_costs), 'analyzed_services': 0,
            'skipped_services': 0, 'skipped_reasons': {}, 'returned_flags': 0,
            'metric': 'BlendedCost', 'currency': 'USD', 'calibrated': False,
            'date_coverage_verified': False, 'empty_flags_establish_normal_spending': False})
        def skip(reason):
            report['skipped_services'] += 1
            report['skipped_reasons'][reason] = report['skipped_reasons'].get(reason, 0)+1
        anomalies = []
        for service, rows in historical_costs.items():
            if not rows or len(rows) < 3:
                skip('insufficient_rows'); continue
            values, dates = [], set()
            valid = True
            for row in rows:
                if not isinstance(row, dict): valid = False; break
                value, day = row.get('blended_cost'), row.get('date')
                if (type(value) not in (int, float) or not math.isfinite(value)
                        or row.get('currency') != 'USD' or not isinstance(day, str) or day in dates):
                    valid = False; break
                try:
                    if datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m-%d') != day:
                        valid = False; break
                except ValueError:
                    valid = False; break
                values.append(float(value)); dates.add(day)
            if not valid:
                skip('invalid_or_duplicate_date_amount_currency'); continue
            try:
                mean, deviation = statistics.mean(values), statistics.stdev(values)
                if not math.isfinite(mean) or not math.isfinite(deviation):
                    skip('nonfinite_reference'); continue
                if deviation == 0:
                    report['analyzed_services'] += 1; continue
                lower, upper = mean-2*deviation, mean+2*deviation
                if not math.isfinite(lower) or not math.isfinite(upper):
                    skip('nonfinite_reference'); continue
            except (ValueError, OverflowError, ArithmeticError):
                skip('unavailable_reference'); continue
            report['analyzed_services'] += 1
            for row, value in zip(rows, values):
                if lower <= value <= upper: continue
                direction = 'spike' if value > upper else 'drop'
                anomalies.append({'service': service, 'date': row['date'], 'cost': value,
                    'metric': 'BlendedCost', 'currency': 'USD', 'type': direction,
                    'severity': 'review', 'method': 'sample_mean_plus_minus_two_sample_standard_deviations',
                    'baseline_mean': mean, 'sample_standard_deviation': deviation,
                    'lower_reference': lower, 'upper_reference': upper, 'baseline_row_count': len(values),
                    'confidence': None, 'date_coverage_verified': False,
                    'description': f'Observed {direction} versus a descriptive reference across supplied rows; not a calibrated anomaly or verified billing error.'})
        report['returned_flags'] = len(anomalies)
        report['status'] = 'descriptive_partial' if report['skipped_services'] else 'descriptive_supplied_rows' if historical_costs else 'no_observations'
        return anomalies

    def _get_account_id(self) -> Optional[str]:
        """
        Get AWS account ID from STS.
        
        Returns:
            Account ID string or None if unavailable
        """
        try:
            if not self.sts_client:
                import boto3
                sts = boto3.client('sts')
            else:
                sts = self.sts_client
            
            identity = sts.get_caller_identity()
            return identity.get('Account')
        except Exception as e:
            logger.error(f"Error retrieving account ID: {e}")
            return None
    
    def _get_budget_status(self) -> Optional[BudgetStatus]:
        """Select a configured budget or the only available budget, never an arbitrary first one."""
        if not self.budgets_client:
            return None
        try:
            import os
            from .budget_monitor import BudgetMonitor
            account_id = self._get_account_id()
            if not account_id:
                return None
            name = os.environ.get('ADVISOR_BUDGET_NAME')
            if name:
                budget = self.budgets_client.describe_budget(AccountId=account_id, BudgetName=name).get('Budget')
            else:
                request = {'AccountId': account_id}
                candidates, seen = [], set()
                while True:
                    response = self.budgets_client.describe_budgets(**request)
                    candidates.extend(response.get('Budgets', []))
                    if len(candidates) > 1:
                        logger.info('Advisor budget context unavailable: select ADVISOR_BUDGET_NAME')
                        return None
                    token = response.get('NextToken')
                    if not token: break
                    if token in seen: raise ValueError('Repeated budget page token')
                    seen.add(token)
                    request['NextToken'] = token
                budget = candidates[0] if candidates else None
            if not budget or budget.get('BudgetType') != 'COST':
                return None
            return BudgetMonitor(self.budgets_client, None)._create_budget_status(budget)
        except Exception as error:
            logger.warning('Advisor budget context unavailable: %s', type(error).__name__)
            return None
